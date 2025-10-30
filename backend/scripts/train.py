"""
Hybrid Multi-Agent RL Training Script
Trains A3C Router + DQN Specialists on preprocessed IDS datasets
"""

import os
import sys
import json
import argparse
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from torch.utils.tensorboard import SummaryWriter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.agents.a3c_router import A3CRouter, A3CLoss, create_a3c_model
from model.agents.dqn_specialist import DQNSpecialist, create_specialists
from model.replay.prioritized_buffer import MultiBufferManager
from model.utils.calibration import TemperatureScaling, evaluate_calibration

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CurriculumScheduler:
    """
    Curriculum learning scheduler
    Gradually introduces harder attack classes during training
    """
    
    def __init__(self, num_classes: int, warmup_epochs: int = 5):
        self.num_classes = num_classes
        self.warmup_epochs = warmup_epochs
        
        # Define class difficulty (0=easiest, higher=harder)
        # Benign and simple attacks are easier
        self.class_difficulty = {
            0: 0,   # Benign
            1: 1,   # DoS variants
            2: 3,   # DDoS (harder due to distributed nature)
            3: 1,   # PortScan (easy pattern)
            4: 2,   # BruteForce
            5: 2,   # WebAttack
            6: 4,   # Infiltration (complex)
            7: 4,   # Botnet (complex)
            8: 3,   # HeartBleed
            # Add more as needed
        }
        
        # Default difficulty for unlisted classes
        for i in range(num_classes):
            if i not in self.class_difficulty:
                self.class_difficulty[i] = 2
    
    def get_active_classes(self, epoch: int) -> list:
        """Get list of classes to train on for given epoch"""
        # Start with at least 3 classes to make routing non-trivial
        if epoch < self.warmup_epochs:
            # Warmup: easiest classes (multiple to force routing)
            max_difficulty = 1  # Include difficulty 0 and 1
        elif epoch < self.warmup_epochs * 2:
            # Phase 2: add difficulty 2
            max_difficulty = 2
        elif epoch < self.warmup_epochs * 3:
            # Phase 3: add difficulty 3
            max_difficulty = 3
        elif epoch < self.warmup_epochs * 4:
            # Phase 4: add difficulty 4
            max_difficulty = 4
        else:
            # Final: all classes
            max_difficulty = 10
        
        active = [
            cls for cls in range(self.num_classes)
            if self.class_difficulty.get(cls, 2) <= max_difficulty
        ]
        
        # Ensure at least 3 classes for meaningful routing
        if len(active) < 3:
            # Add more classes up to difficulty 2
            active = [
                cls for cls in range(self.num_classes)
                if self.class_difficulty.get(cls, 2) <= max(max_difficulty, 2)
            ]
        
        logger.info(f"Epoch {epoch}: Active classes = {active} (max_difficulty={max_difficulty})")
        return active


class EarlyStopping:
    """Early stopping with patience"""
    
    def __init__(self, patience: int = 10, min_delta: float = 0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_score = None
        self.early_stop = False
    
    def __call__(self, val_metric: float) -> bool:
        """
        Check if should stop training
        
        Args:
            val_metric: Validation metric (higher is better)
        
        Returns:
            True if should stop
        """
        if self.best_score is None:
            self.best_score = val_metric
            return False
        
        if val_metric > self.best_score + self.min_delta:
            # Improvement
            self.best_score = val_metric
            self.counter = 0
        else:
            # No improvement
            self.counter += 1
            logger.info(f"EarlyStopping counter: {self.counter}/{self.patience}")
            
            if self.counter >= self.patience:
                self.early_stop = True
                return True
        
        return False


class CheckpointManager:
    """Manage model checkpoints"""
    
    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(exist_ok=True, parents=True)
        self.best_metric = -float('inf')
    
    def save_checkpoint(
        self,
        epoch: int,
        router: A3CRouter,
        specialists: Dict[int, DQNSpecialist],
        router_optimizer: optim.Optimizer,
        specialist_optimizers: Dict[int, optim.Optimizer],
        metrics: dict,
        is_best: bool = False
    ):
        """Save training checkpoint"""
        checkpoint = {
            'epoch': epoch,
            'router_state_dict': router.state_dict(),
            'router_optimizer_state_dict': router_optimizer.state_dict(),
            'specialist_state_dicts': {
                sp_id: sp.online_net.state_dict()
                for sp_id, sp in specialists.items()
            },
            'specialist_optimizer_state_dicts': {
                sp_id: opt.state_dict()
                for sp_id, opt in specialist_optimizers.items()
            },
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save regular checkpoint
        checkpoint_path = self.checkpoint_dir / f'checkpoint_epoch_{epoch}.pt'
        torch.save(checkpoint, checkpoint_path)
        logger.info(f"Saved checkpoint to {checkpoint_path}")
        
        # Save best checkpoint
        if is_best:
            best_path = self.checkpoint_dir / 'best_model.pt'
            torch.save(checkpoint, best_path)
            logger.info(f"Saved best model to {best_path}")
            self.best_metric = metrics.get('val_f1', 0)
        
        # Keep only last 5 checkpoints
        self._cleanup_old_checkpoints()
    
    def _cleanup_old_checkpoints(self, keep_last: int = 5):
        """Remove old checkpoints, keeping only the last N"""
        checkpoints = sorted(
            self.checkpoint_dir.glob('checkpoint_epoch_*.pt'),
            key=lambda p: p.stat().st_mtime
        )
        
        if len(checkpoints) > keep_last:
            for old_checkpoint in checkpoints[:-keep_last]:
                old_checkpoint.unlink()
                logger.debug(f"Removed old checkpoint: {old_checkpoint}")
    
    def load_checkpoint(self, checkpoint_path: Path) -> dict:
        """Load checkpoint"""
        checkpoint = torch.load(checkpoint_path)
        logger.info(f"Loaded checkpoint from {checkpoint_path}")
        return checkpoint


def load_preprocessed_data(data_dir: Path) -> Tuple:
    """Load preprocessed training data"""
    logger.info(f"Loading preprocessed data from {data_dir}")
    
    # Load splits
    X_train = np.load(data_dir / 'X_train.npy')
    y_train = np.load(data_dir / 'y_train.npy')
    X_val = np.load(data_dir / 'X_val.npy')
    y_val = np.load(data_dir / 'y_val.npy')
    
    # Load taxonomy
    with open(data_dir / 'taxonomy.json', 'r') as f:
        taxonomy = json.load(f)
    
    # Load metadata
    with open(data_dir / 'metadata.json', 'r') as f:
        metadata = json.load(f)
    
    logger.info(f"Train: {X_train.shape}, Val: {X_val.shape}")
    logger.info(f"Classes: {taxonomy['num_classes']}")
    
    return X_train, y_train, X_val, y_val, taxonomy, metadata


def create_data_loaders(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    batch_size: int = 256,
    num_workers: int = 2,
    use_balanced_sampling: bool = True
) -> Tuple[DataLoader, DataLoader]:
    """Create PyTorch data loaders with optional class-balanced sampling"""
    
    # Convert to tensors
    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.LongTensor(y_train)
    X_val_t = torch.FloatTensor(X_val)
    y_val_t = torch.LongTensor(y_val)
    
    # Create datasets
    train_dataset = TensorDataset(X_train_t, y_train_t)
    val_dataset = TensorDataset(X_val_t, y_val_t)
    
    # Create class-balanced sampler for training to handle imbalance
    sampler = None
    shuffle = True
    
    if use_balanced_sampling:
        # Compute class weights (inverse of class frequency)
        class_counts = np.bincount(y_train)
        
        # IMPROVED: Use smoothed inverse frequency to avoid over-sampling rare classes
        # Original: weight = 1 / count (too extreme for 2037:1 imbalance)
        # Improved: weight = 1 / sqrt(count) (more moderate)
        class_weights_sampling = 1.0 / np.sqrt(class_counts)
        
        # Clip to prevent extreme over-sampling (max 100x over-representation)
        max_weight = class_weights_sampling.min() * 100
        class_weights_sampling = np.clip(class_weights_sampling, None, max_weight)
        
        # Assign weight to each sample based on its class
        sample_weights = class_weights_sampling[y_train]
        
        # Create weighted sampler (oversamples minority classes)
        sampler = WeightedRandomSampler(
            weights=sample_weights,
            num_samples=len(y_train),
            replacement=True
        )
        shuffle = False  # Can't use shuffle with sampler
        
        logger.info(f"Using class-balanced sampling with smoothed weights")
        logger.info(f"Sampling weight range: [{class_weights_sampling.min():.6f}, {class_weights_sampling.max():.6f}]")
        logger.info(f"Sampling weight ratio: {class_weights_sampling.max() / class_weights_sampling.min():.2f}x")
    
    # Create loaders with parallel data loading
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        sampler=sampler,
        num_workers=num_workers,
        pin_memory=True,
        persistent_workers=True if num_workers > 0 else False
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        persistent_workers=True if num_workers > 0 else False
    )
    
    return train_loader, val_loader


def train_epoch(
    epoch: int,
    router: A3CRouter,
    specialists: Dict[int, DQNSpecialist],
    router_optimizer: optim.Optimizer,
    specialist_optimizers: Dict[int, optim.Optimizer],
    train_loader: DataLoader,
    buffer_manager: MultiBufferManager,
    a3c_loss_fn: A3CLoss,
    curriculum: CurriculumScheduler,
    device: str,
    writer: SummaryWriter,
    epsilon: float = 0.1,  # Epsilon-greedy exploration
    train_specialist_every: int = 1,  # Train specialists every N batches
    use_amp: bool = False,  # Use automatic mixed precision
    scaler: Optional[torch.cuda.amp.GradScaler] = None,  # AMP gradient scaler
    class_weights: Optional[torch.Tensor] = None  # Class weights for balanced rewards
) -> dict:
    """Train for one epoch"""
    
    router.train()
    for specialist in specialists.values():
        specialist.online_net.train()
    
    total_router_loss = 0
    total_specialist_loss = 0
    router_correct = 0  # Accumulated rewards
    router_routing_correct = 0  # Actually correct routing decisions
    specialist_correct = 0  # Correct specialist predictions
    specialist_total = 0  # Total specialist predictions made
    total_samples = 0
    
    active_classes = curriculum.get_active_classes(epoch)
    
    for batch_idx, (states, labels) in enumerate(train_loader):
        states = states.to(device)
        labels = labels.to(device)
        
        # Filter by curriculum (only train on active classes)
        mask = torch.zeros(len(labels), dtype=torch.bool, device=device)
        for cls in active_classes:
            mask |= (labels == cls)
        
        if mask.sum() == 0:
            continue
        
        states = states[mask]
        labels = labels[mask]
        batch_size = len(states)
        
        # === Router Training ===
        # Router selects specialists (use AMP if enabled)
        with torch.amp.autocast('cuda', enabled=use_amp):
            specialist_actions, log_probs, entropy, values = router(states)
        
        # Apply epsilon-greedy exploration PER SAMPLE
        exploration_mask = torch.rand(len(states), device=device) < epsilon
        random_actions = torch.tensor(
            [np.random.choice(active_classes) for _ in range(len(states))],
            device=device, dtype=torch.long
        )
        
        # Mix policy and random actions
        original_actions = specialist_actions.clone()
        specialist_actions = torch.where(exploration_mask, random_actions, specialist_actions)
        
        # Track routing accuracy (did router select the correct specialist?)
        # Correct routing = specialist ID matches true label
        correct_routing = (original_actions == labels)
        router_routing_correct += correct_routing.sum().item()
        
        # Compute rewards based on specialist predictions (VECTORIZED)
        # IMPROVED: Multi-objective reward to encourage proper routing AND accuracy
        rewards = torch.zeros_like(specialist_actions, dtype=torch.float32)
        
        with torch.no_grad(), torch.amp.autocast('cuda', enabled=use_amp):
            # Group by specialist ID for batch processing
            for sp_id in torch.unique(specialist_actions):
                sp_id_int = sp_id.item()
                if sp_id_int not in specialists:
                    continue
                
                # Get all samples assigned to this specialist
                sp_mask = (specialist_actions == sp_id)
                if sp_mask.sum() == 0:
                    continue
                
                sp_states_batch = states[sp_mask]
                sp_labels_batch = labels[sp_mask]
                
                # Batch prediction for this specialist
                sp_q_values = specialists[sp_id_int].compute_q_values(sp_states_batch)
                sp_preds = sp_q_values.argmax(dim=1)
                sp_confidence = sp_q_values.max(dim=1)[0]  # Get Q-value confidence
                
                # Correctness check
                is_positive_class = (sp_labels_batch == sp_id_int)
                is_correct = (sp_preds == 1) & is_positive_class | (sp_preds == 0) & ~is_positive_class
                
                # IMPROVED REWARD STRUCTURE:
                # 1. Base correctness reward (scaled by difficulty)
                # Correct predictions get positive reward, incorrect get penalty
                correctness_reward = torch.where(
                    is_correct,
                    torch.ones_like(is_correct, dtype=torch.float32) * 2.0,  # Correct: +2.0
                    torch.ones_like(is_correct, dtype=torch.float32) * -0.5  # Wrong: -0.5
                )
                
                # 2. Routing bonus: reward router for sending samples to the RIGHT specialist
                # This is the KEY signal for learning routing policy
                # Give bonus if sample's true label matches the specialist ID
                routing_bonus = torch.where(
                    is_positive_class,
                    torch.ones_like(is_positive_class, dtype=torch.float32) * 1.5,  # Right specialist: +1.5
                    torch.zeros_like(is_positive_class, dtype=torch.float32)         # Wrong specialist: 0
                )
                
                # 3. Confidence bonus: reward high-confidence correct predictions
                # Penalize low-confidence predictions (uncertainty is bad)
                confidence_factor = torch.where(
                    is_correct,
                    (sp_confidence - 0.5).clamp(min=0) * 0.5,  # Correct & confident: +0.25
                    torch.zeros_like(sp_confidence)             # Incorrect: no bonus
                )
                
                # Combine rewards (additive)
                # NOTE: Max possible = 2.0 + 1.5 + 0.25 = 3.75
                base_rewards = correctness_reward + routing_bonus + confidence_factor
                
                # Apply class weights MORE MODERATELY
                # Use log-scale to prevent explosion on rare classes
                if class_weights is not None:
                    batch_class_weights = class_weights[sp_labels_batch]
                    # Use geometric mean instead of multiplication to reduce extremes
                    # This keeps rewards in reasonable range while still emphasizing rare classes
                    weight_factor = torch.sqrt(batch_class_weights)  # sqrt reduces impact
                    rewards[sp_mask] = base_rewards * weight_factor
                else:
                    rewards[sp_mask] = base_rewards
        
        # Compute next values (for GAE)
        with torch.no_grad(), torch.amp.autocast('cuda', enabled=use_amp):
            _, _, _, next_values = router(states)
        
        dones = torch.ones_like(rewards)  # Episodic
        
        # Compute advantages
        advantages, returns = a3c_loss_fn.compute_advantages(
            rewards, values, next_values, dones
        )
        
        # Only update router on NON-random actions (exclude epsilon-greedy samples)
        # This prevents policy corruption from learning on random actions
        policy_mask = ~exploration_mask
        
        if policy_mask.sum() > 0:
            # Filter to only policy-driven actions
            policy_log_probs = log_probs[policy_mask]
            policy_advantages = advantages[policy_mask]
            policy_values = values[policy_mask]
            policy_returns = returns[policy_mask]
            policy_entropy = entropy[policy_mask]
            
            # Compute router loss only on policy actions
            with torch.amp.autocast('cuda', enabled=use_amp):
                router_loss, router_loss_dict = a3c_loss_fn.compute_loss(
                    policy_log_probs, policy_advantages, policy_values, 
                    policy_returns, policy_entropy
                )
            
            # Update router (with AMP scaling if enabled)
            router_optimizer.zero_grad()
            if use_amp and scaler is not None:
                scaler.scale(router_loss).backward()
                scaler.unscale_(router_optimizer)
                torch.nn.utils.clip_grad_norm_(router.parameters(), max_norm=10.0)
                scaler.step(router_optimizer)
                scaler.update()
            else:
                router_loss.backward()
                torch.nn.utils.clip_grad_norm_(router.parameters(), max_norm=10.0)
                router_optimizer.step()
            
            total_router_loss += router_loss.item()
        else:
            # All actions were random, skip router update
            router_loss = torch.tensor(0.0)
        
        router_correct += rewards.sum().item()
        
        # === Specialist Training (with frequency control for memory efficiency) ===
        # IMPROVED: Train specialists on ALL classes, not just their assigned class
        # This prevents specialists from becoming too narrow and improves generalization
        
        # Skip specialist training for some batches to reduce GPU memory usage
        if batch_idx % train_specialist_every != 0:
            total_samples += batch_size
            continue
        
        # For each specialist, train on its samples AND some from other classes (as negatives)
        for sp_id, specialist in specialists.items():
            # Get positive samples (this specialist's class)
            positive_mask = (labels == sp_id)
            
            # Get negative samples (other classes) - sample subset to balance
            negative_mask = (labels != sp_id)
            
            # Need at least some positive samples
            if positive_mask.sum() < 1:
                continue
            
            # IMPROVED: Adaptive negative sampling based on positive count
            # For rare classes: use more negatives to learn discrimination
            # For common classes: use fewer negatives to speed up training
            num_positives = positive_mask.sum().item()
            
            # Adaptive ratio: rare classes get more negatives (up to 5x)
            # Common classes get fewer negatives (down to 1x)
            if num_positives < 10:
                negative_ratio = 5  # Rare: 5 negatives per positive
            elif num_positives < 50:
                negative_ratio = 3  # Uncommon: 3 negatives per positive
            else:
                negative_ratio = 2  # Common: 2 negatives per positive
            
            num_negatives = min(negative_mask.sum().item(), num_positives * negative_ratio)
            
            if num_negatives > 0:
                # Sample negatives randomly (prioritize other attack classes over benign)
                negative_indices = torch.where(negative_mask)[0]
                
                # If we have non-benign negatives, prioritize them (harder examples)
                non_benign_negative_mask = negative_mask & (labels != 0)
                if non_benign_negative_mask.sum() > num_negatives // 2:
                    # Sample 50% from other attacks, 50% from benign
                    non_benign_indices = torch.where(non_benign_negative_mask)[0]
                    benign_negative_mask = negative_mask & (labels == 0)
                    benign_indices = torch.where(benign_negative_mask)[0]
                    
                    num_attack_negatives = min(len(non_benign_indices), num_negatives // 2)
                    num_benign_negatives = num_negatives - num_attack_negatives
                    
                    sampled_attack_indices = non_benign_indices[torch.randperm(len(non_benign_indices))[:num_attack_negatives]]
                    sampled_benign_indices = benign_indices[torch.randperm(len(benign_indices))[:num_benign_negatives]]
                    sampled_negative_indices = torch.cat([sampled_attack_indices, sampled_benign_indices])
                else:
                    # Just sample randomly from all negatives
                    sampled_negative_indices = negative_indices[torch.randperm(len(negative_indices))[:num_negatives]]
                
                # Combine positive and sampled negative indices
                positive_indices = torch.where(positive_mask)[0]
                combined_indices = torch.cat([positive_indices, sampled_negative_indices])
                
                sp_states = states[combined_indices]
                sp_labels_binary = (labels[combined_indices] == sp_id).long()
            else:
                # Only positive samples
                sp_states = states[positive_mask]
                sp_labels_binary = torch.ones(positive_mask.sum(), dtype=torch.long, device=device)
            
            # Add to replay buffer (VECTORIZED - single CPU transfer)
            sp_states_np = sp_states.cpu().numpy()
            sp_labels_np = sp_labels_binary.cpu().numpy()
            
            for i in range(len(sp_states)):
                buffer_manager.add(
                    specialist_id=sp_id,
                    state=sp_states_np[i],
                    action=sp_labels_np[i],
                    reward=5.0 if sp_labels_np[i] == 1 else -2.0,  # INCREASED: was 1.0/-1.0, now 5x stronger signal
                    next_state=sp_states_np[i],  # Same state (stateless)
                    done=True,
                    class_label=sp_labels_np[i]
                )
            
            # Train from replay buffer if enough samples
            buffer_size = len(buffer_manager.buffers[sp_id])
            if buffer_size >= 32:
                # Sample batch size proportional to buffer size (up to 64)
                sample_size = min(64, max(32, buffer_size // 10))
                
                # Sample from buffer
                (buf_states, buf_actions, buf_rewards, buf_next_states,
                 buf_dones, buf_labels, buf_indices, buf_weights) = buffer_manager.sample(sp_id, sample_size)
                
                buf_states = torch.FloatTensor(buf_states).to(device)
                buf_actions = torch.LongTensor(buf_actions).to(device)
                buf_rewards = torch.FloatTensor(buf_rewards).to(device)
                buf_next_states = torch.FloatTensor(buf_next_states).to(device)
                buf_dones = torch.FloatTensor(buf_dones).to(device)
                buf_weights = torch.FloatTensor(buf_weights).to(device)
                
                # Compute loss (with AMP)
                with torch.amp.autocast('cuda', enabled=use_amp):
                    sp_loss, td_errors, sp_info = specialist.compute_loss(
                        buf_states, buf_actions, buf_rewards,
                        buf_next_states, buf_dones, buf_weights
                    )
                
                # Update specialist (with AMP scaling if enabled)
                specialist_optimizers[sp_id].zero_grad()
                if use_amp and scaler is not None:
                    scaler.scale(sp_loss).backward()
                    scaler.unscale_(specialist_optimizers[sp_id])
                    torch.nn.utils.clip_grad_norm_(specialist.online_net.parameters(), max_norm=10.0)
                    scaler.step(specialist_optimizers[sp_id])
                    scaler.update()
                else:
                    sp_loss.backward()
                    torch.nn.utils.clip_grad_norm_(specialist.online_net.parameters(), max_norm=10.0)
                    specialist_optimizers[sp_id].step()
                
                # Update priorities
                buffer_manager.update_priorities(sp_id, buf_indices, td_errors.cpu().numpy())
                
                # Update target network
                specialist.maybe_update_target()
                
                total_specialist_loss += sp_loss.item()
                
                # Compute specialist accuracy on CURRENT batch (not buffer)
                with torch.no_grad(), torch.amp.autocast('cuda', enabled=use_amp):
                    sp_q_values = specialist.compute_q_values(sp_states)
                    sp_preds = sp_q_values.argmax(dim=1)
                    specialist_correct += (sp_preds == sp_labels_binary).sum().item()
                    specialist_total += len(sp_states)  # Track total predictions
        
        total_samples += batch_size
        
        # Log batch metrics (reduced frequency for speed)
        if batch_idx % 500 == 0:
            exploration_rate = exploration_mask.float().mean().item() if 'exploration_mask' in locals() else 0.0
            
            # Log routing distribution to detect collapse
            unique_actions, action_counts = torch.unique(specialist_actions, return_counts=True)
            routing_entropy = -torch.sum((action_counts.float() / len(specialist_actions)) * 
                                        torch.log(action_counts.float() / len(specialist_actions) + 1e-8))
            
            logger.info(
                f"Epoch {epoch} Batch {batch_idx}/{len(train_loader)}: "
                f"Router Loss={router_loss.item():.4f}, "
                f"Specialist Reward={rewards.mean().item():.3f}, "
                f"Policy Entropy={entropy.mean().item():.4f}, "
                f"Routing Entropy={routing_entropy.item():.3f}, "
                f"Exploration={exploration_rate:.3f}, "
                f"Unique Specialists={len(unique_actions)}"
            )
    
    # Epoch metrics
    metrics = {
        'train_router_loss': total_router_loss / len(train_loader),
        'train_specialist_loss': total_specialist_loss / max(1, len(specialists)),
        'train_avg_reward': router_correct / total_samples,  # Average reward per sample
        'train_routing_accuracy': router_routing_correct / total_samples,  # % routed to correct specialist
        'train_specialist_acc': specialist_correct / max(1, specialist_total)  # FIX: Divide by specialist total, not all samples
    }
    
    # Log routing statistics to detect collapse
    logger.info(f"Epoch {epoch} Training Summary:")
    logger.info(f"  Average Reward: {metrics['train_avg_reward']:.4f} (max ~3.75, higher is better)")
    logger.info(f"  Routing Accuracy: {metrics['train_routing_accuracy']:.4f} (% samples sent to correct specialist)")
    logger.info(f"  Specialist Accuracy: {metrics['train_specialist_acc']:.4f} (binary classification on {specialist_total} samples)")
    logger.info(f"  Router Loss: {metrics['train_router_loss']:.4f}")
    logger.info(f"  Specialist Loss: {metrics['train_specialist_loss']:.4f}")
    
    # Log to tensorboard
    for key, value in metrics.items():
        writer.add_scalar(f'train/{key}', value, epoch)
    
    return metrics


def validate_epoch(
    epoch: int,
    router: A3CRouter,
    specialists: Dict[int, DQNSpecialist],
    val_loader: DataLoader,
    device: str,
    writer: SummaryWriter
) -> dict:
    """Validate for one epoch"""
    
    router.eval()
    for specialist in specialists.values():
        specialist.online_net.eval()
    
    all_preds = []
    all_labels = []
    router_correct = 0
    total_samples = 0
    
    with torch.no_grad():
        for states, labels in val_loader:
            states = states.to(device)
            labels = labels.to(device)
            
            # Router selects specialists
            specialist_actions, _, _, _ = router(states)
            
            # Track routing distribution for diagnostics
            unique_actions, action_counts = torch.unique(specialist_actions, return_counts=True)
            
            # Get predictions from selected specialists
            preds = torch.zeros_like(labels)
            
            for i in range(len(states)):
                sp_id = specialist_actions[i].item()
                if sp_id in specialists:
                    sp_q_values = specialists[sp_id].compute_q_values(states[i:i+1])
                    sp_pred = sp_q_values.argmax(dim=1).item()
                    # If specialist says attack (1), use specialist ID, else benign (0)
                    preds[i] = sp_id if sp_pred == 1 else 0
                else:
                    preds[i] = 0  # Default to benign
            
            all_preds.append(preds.cpu())
            all_labels.append(labels.cpu())
            
            router_correct += (specialist_actions == labels).sum().item()
            total_samples += len(labels)
    
    all_preds = torch.cat(all_preds)
    all_labels = torch.cat(all_labels)
    
    # Log routing distribution
    logger.info(f"Validation routing distribution: {dict(zip(unique_actions.cpu().numpy(), action_counts.cpu().numpy()))}")
    
    # Compute metrics
    accuracy = (all_preds == all_labels).float().mean().item()
    router_acc = router_correct / total_samples
    
    # Compute per-class metrics
    num_classes = all_labels.max().item() + 1
    precision_per_class = []
    recall_per_class = []
    
    for cls in range(num_classes):
        tp = ((all_preds == cls) & (all_labels == cls)).sum().item()
        fp = ((all_preds == cls) & (all_labels != cls)).sum().item()
        fn = ((all_preds != cls) & (all_labels == cls)).sum().item()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        precision_per_class.append(precision)
        recall_per_class.append(recall)
    
    # Macro F1
    f1_per_class = [
        2 * p * r / (p + r) if (p + r) > 0 else 0
        for p, r in zip(precision_per_class, recall_per_class)
    ]
    macro_f1 = np.mean(f1_per_class)
    
    metrics = {
        'val_accuracy': accuracy,
        'val_router_acc': router_acc,
        'val_macro_precision': np.mean(precision_per_class),
        'val_macro_recall': np.mean(recall_per_class),
        'val_macro_f1': macro_f1
    }
    
    # Log to tensorboard
    for key, value in metrics.items():
        writer.add_scalar(f'val/{key}', value, epoch)
    
    logger.info(
        f"Validation Epoch {epoch}: "
        f"Acc={accuracy:.4f}, F1={macro_f1:.4f}, Router Acc={router_acc:.4f}"
    )
    
    return metrics


def main(args):
    """Main training function"""
    
    logger.info("="*70)
    logger.info("Hybrid Multi-Agent RL Training")
    logger.info("="*70)
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() and not args.no_cuda else 'cpu')
    logger.info(f"Using device: {device}")
    
    # Setup directories
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / 'data' / 'processed'
    output_dir = project_root / 'backend' / 'model' / 'output'
    checkpoint_dir = output_dir / 'checkpoints'
    log_dir = output_dir / 'logs'
    
    output_dir.mkdir(exist_ok=True, parents=True)
    checkpoint_dir.mkdir(exist_ok=True, parents=True)
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # Load data
    X_train, y_train, X_val, y_val, taxonomy, metadata = load_preprocessed_data(data_dir)
    num_classes = taxonomy['num_classes']
    input_dim = X_train.shape[1]
    
    # Create data loaders
    num_workers = 2 if not args.no_cuda else 0  # Parallel data loading on GPU systems
    train_loader, val_loader = create_data_loaders(
        X_train, y_train, X_val, y_val, 
        batch_size=args.batch_size,
        num_workers=num_workers,
        use_balanced_sampling=args.use_balanced_sampling
    )
    
    # Create models
    logger.info("Creating models...")
    router = create_a3c_model(
        input_dim=input_dim,
        num_specialists=num_classes,
        hidden_dims=[128, 64],
        entropy_coef=args.entropy_coef,
        device=device
    )
    
    specialist_names = taxonomy['classes']
    specialists = create_specialists(
        num_specialists=num_classes,
        specialist_names=specialist_names,
        input_dim=input_dim,
        hidden_dims=[128, 64],
        use_noisy=args.use_noisy,
        gamma=args.gamma,
        n_step=args.n_step,
        target_update_freq=args.target_update_freq,
        device=device
    )
    
    # Create optimizers
    router_optimizer = optim.Adam(router.parameters(), lr=args.lr_router)
    specialist_optimizers = {
        sp_id: optim.Adam(sp.online_net.parameters(), lr=args.lr_specialist)
        for sp_id, sp in specialists.items()
    }
    
    # Create replay buffer manager
    buffer_manager = MultiBufferManager(
        num_specialists=num_classes,
        capacity_per_specialist=args.buffer_capacity,
        num_classes_per_specialist=2,  # Binary per specialist
        alpha=0.6,
        beta=0.4,
        beta_increment=0.001
    )
    
    # Compute class weights for reward balancing (inverse of actual distribution)
    # IMPROVED: Use log-scaling to avoid extreme weights with 2037:1 imbalance
    class_counts = np.bincount(y_train)
    total_samples = len(y_train)
    
    # Strategy 1: Use effective number of samples (from Class-Balanced Loss paper)
    # This smooths extreme imbalances better than inverse frequency
    beta = 0.9999  # Smoothing parameter (higher = more smoothing)
    effective_num = 1.0 - np.power(beta, class_counts)
    class_weights_raw = (1.0 - beta) / effective_num
    
    # Strategy 2: Apply sqrt to further reduce extremes
    class_weights_sqrt = np.sqrt(class_weights_raw)
    
    # Strategy 3: Clip weights to reasonable range (prevent any class from dominating)
    # Keep weights between 0.1 and 10.0 (100x range instead of 2000x)
    class_weights_clipped = np.clip(class_weights_sqrt, 0.1, 10.0)
    
    # Convert to tensor and normalize to mean=1.0
    class_weights = torch.FloatTensor(class_weights_clipped).to(device)
    class_weights = class_weights / class_weights.mean()
    
    logger.info(f"Class counts: {class_counts}")
    logger.info(f"Class weights for rewards: {class_weights.cpu().numpy()}")
    logger.info(f"Weight ratio (max/min): {class_weights.max().item() / class_weights.min().item():.2f}x")
    
    # Create training components
    # Entropy coefficient tuning:
    # - With extreme imbalance + aggressive balanced sampling: need HIGH entropy (3x)
    # - With smoothed balanced sampling + better rewards: need MODERATE entropy (2x)
    effective_entropy_coef = args.entropy_coef * 2.0  # Double instead of triple
    logger.info(f"Using effective entropy coefficient: {effective_entropy_coef}")
    logger.info(f"This encourages diverse routing while allowing convergence")
    
    a3c_loss_fn = A3CLoss(actor_coef=1.0, critic_coef=0.5, entropy_coef=effective_entropy_coef)
    curriculum = CurriculumScheduler(num_classes, warmup_epochs=args.warmup_epochs)
    early_stopping = EarlyStopping(patience=args.patience, min_delta=0.001)
    checkpoint_manager = CheckpointManager(checkpoint_dir)
    
    # Tensorboard writer
    writer = SummaryWriter(log_dir=log_dir / f'run_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    
    # Load checkpoint if resuming
    start_epoch = 0
    best_f1 = 0
    
    if args.resume:
        if args.resume == 'auto':
            # Auto-detect latest checkpoint
            resume_path = checkpoint_dir / 'best_model.pt'
            if not resume_path.exists():
                # Try latest checkpoint
                checkpoints = sorted(checkpoint_dir.glob('checkpoint_epoch_*.pt'))
                if checkpoints:
                    resume_path = checkpoints[-1]
                else:
                    logger.warning("No checkpoint found to resume from. Starting fresh.")
                    args.resume = None
        else:
            resume_path = Path(args.resume)
        
        if args.resume and resume_path.exists():
            logger.info(f"Resuming from checkpoint: {resume_path}")
            checkpoint = checkpoint_manager.load_checkpoint(resume_path)
            
            # Load model states
            router.load_state_dict(checkpoint['router_state_dict'])
            router_optimizer.load_state_dict(checkpoint['router_optimizer_state_dict'])
            
            for sp_id, sp in specialists.items():
                if sp_id in checkpoint['specialist_state_dicts']:
                    sp.online_net.load_state_dict(checkpoint['specialist_state_dicts'][sp_id])
                    sp.target_net.load_state_dict(checkpoint['specialist_state_dicts'][sp_id])
            
            for sp_id, opt in specialist_optimizers.items():
                if sp_id in checkpoint['specialist_optimizer_state_dicts']:
                    opt.load_state_dict(checkpoint['specialist_optimizer_state_dicts'][sp_id])
            
            # Resume from next epoch
            start_epoch = checkpoint['epoch'] + 1
            best_f1 = checkpoint['metrics'].get('val_macro_f1', 0)
            
            logger.info(f"Resumed from epoch {checkpoint['epoch']}, best F1: {best_f1:.4f}")
            logger.info(f"Continuing training from epoch {start_epoch}")
        elif args.resume:
            logger.error(f"Checkpoint not found: {resume_path}")
            logger.info("Starting training from scratch")
    
    # Training loop
    logger.info("Starting training...")
    if args.use_amp:
        logger.info("Mixed precision training (AMP) enabled")
    start_time = time.time()
    
    # Create AMP gradient scaler if using mixed precision
    scaler = torch.amp.GradScaler('cuda') if args.use_amp else None
    
    # Epsilon decay for exploration
    # INCREASED initial epsilon to force more exploration early
    epsilon_start = 0.5  # Start with 50% random routing
    epsilon_end = 0.1    # End with 10% (still some randomness)
    epsilon_decay = (epsilon_start - epsilon_end) / args.num_epochs
    
    for epoch in range(start_epoch, args.num_epochs):
        epoch_start = time.time()
        
        # Calculate current epsilon
        epsilon = max(epsilon_end, epsilon_start - epoch * epsilon_decay)
        logger.info(f"Epoch {epoch}: Exploration epsilon = {epsilon:.3f}")
        
        # Train
        train_metrics = train_epoch(
            epoch, router, specialists, router_optimizer, specialist_optimizers,
            train_loader, buffer_manager, a3c_loss_fn, curriculum, device, writer, epsilon,
            train_specialist_every=args.train_specialist_every,
            use_amp=args.use_amp,
            scaler=scaler,
            class_weights=class_weights
        )
        
        # Validate
        val_metrics = validate_epoch(
            epoch, router, specialists, val_loader, device, writer
        )
        
        # Clear GPU cache to free memory (important for 4GB VRAM)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Combined metrics
        all_metrics = {**train_metrics, **val_metrics}
        
        epoch_time = time.time() - epoch_start
        logger.info(f"Epoch {epoch} completed in {epoch_time:.2f}s")
        
        # Check if best model
        is_best = val_metrics['val_macro_f1'] > best_f1
        if is_best:
            best_f1 = val_metrics['val_macro_f1']
            logger.info(f"New best F1: {best_f1:.4f}")
        
        # Save checkpoint
        if (epoch + 1) % args.save_freq == 0 or is_best:
            checkpoint_manager.save_checkpoint(
                epoch, router, specialists, router_optimizer,
                specialist_optimizers, all_metrics, is_best
            )
        
        # Early stopping
        if early_stopping(val_metrics['val_macro_f1']):
            logger.info(f"Early stopping triggered at epoch {epoch}")
            break
    
    total_time = time.time() - start_time
    logger.info(f"Training completed in {total_time/3600:.2f} hours")
    logger.info(f"Best validation F1: {best_f1:.4f}")
    
    # Close writer
    writer.close()
    
    # Save label_classes.json for API consumption
    with open(output_dir / 'label_classes.json', 'w') as f:
        json.dump(taxonomy['classes'], f, indent=2)
    
    # Also save to checkpoints directory for API discovery
    with open(checkpoint_dir / 'label_classes.json', 'w') as f:
        json.dump(taxonomy['classes'], f, indent=2)
    
    logger.info(f"Saved label classes to {output_dir / 'label_classes.json'} and {checkpoint_dir / 'label_classes.json'}")
    
    logger.info("="*70)
    logger.info("Training Complete!")
    logger.info("="*70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train Hybrid RL IDS')
    
    # Model hyperparameters
    parser.add_argument('--lr-router', type=float, default=0.001, help='Router learning rate')
    parser.add_argument('--lr-specialist', type=float, default=0.0005, help='Specialist learning rate')
    parser.add_argument('--gamma', type=float, default=0.99, help='Discount factor')
    parser.add_argument('--entropy-coef', type=float, default=0.25, help='Entropy coefficient (will be doubled internally to 0.5 for diversity)')
    parser.add_argument('--n-step', type=int, default=3, help='N-step returns')
    parser.add_argument('--target-update-freq', type=int, default=100, help='Target network update frequency')
    parser.add_argument('--use-noisy', action='store_true', help='Use NoisyNets')
    
    # Training hyperparameters
    parser.add_argument('--num-epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=512, help='Batch size (optimized for RTX 3050 4GB)')
    parser.add_argument('--buffer-capacity', type=int, default=5000, help='Replay buffer capacity (reduced for 4GB VRAM)')
    parser.add_argument('--use-amp', action='store_true', help='Use automatic mixed precision (faster on RTX 30-series)')
    parser.add_argument('--use-balanced-sampling', action='store_true', help='Use class-balanced sampling to handle imbalance (recommended)')
    parser.add_argument('--gradient-accumulation', type=int, default=1, help='Gradient accumulation steps (larger effective batch size)')
    parser.add_argument('--warmup-epochs', type=int, default=3, help='Curriculum warmup epochs (reduced for faster training)')
    parser.add_argument('--train-specialist-every', type=int, default=1, help='Train specialists every N batches (1=every batch for faster learning)')
    parser.add_argument('--patience', type=int, default=10, help='Early stopping patience')
    parser.add_argument('--save-freq', type=int, default=10, help='Checkpoint save frequency (reduced to save disk I/O)')
    parser.add_argument('--resume', type=str, default=None, help='Resume from checkpoint (path to .pt file or "auto" for latest)')
    
    # System
    parser.add_argument('--no-cuda', action='store_true', help='Disable CUDA')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    # Set random seeds
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    
    main(args)
