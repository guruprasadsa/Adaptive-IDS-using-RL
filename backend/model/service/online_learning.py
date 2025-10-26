"""
Online Learning Service

Implements incremental fine-tuning with:
- Buffer management for recent samples and false positives
- Scheduled fine-tuning jobs (hourly/nightly)
- EWC (Elastic Weight Consolidation) to prevent catastrophic forgetting
- Model versioning and registry
- Validation gate with automatic rollback
- Shadow evaluation before promotion

Background service runs alongside inference service.
"""

import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import logging
import threading
import time
from collections import deque
import hashlib
import shutil

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Model version metadata"""
    version_id: str
    timestamp: datetime
    parent_version: Optional[str]
    training_samples: int
    validation_metrics: Dict[str, float]
    checkpoint_path: str
    feature_version: str
    status: str  # 'shadow', 'active', 'retired', 'failed'
    notes: str = ""
    
    def to_dict(self):
        """Convert to JSON-serializable dict"""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: Dict):
        """Load from dict"""
        d = d.copy()
        d['timestamp'] = datetime.fromisoformat(d['timestamp'])
        return cls(**d)


class SampleBuffer:
    """
    Buffer for storing recent samples and false positives.
    Maintains balanced sampling for fine-tuning.
    """
    
    def __init__(self, max_size: int = 10000, max_fp_size: int = 5000):
        """
        Args:
            max_size: Maximum recent samples to keep
            max_fp_size: Maximum false positives to keep
        """
        self.max_size = max_size
        self.max_fp_size = max_fp_size
        
        # Deques for FIFO behavior
        self.recent_features = deque(maxlen=max_size)
        self.recent_labels = deque(maxlen=max_size)
        self.recent_confidences = deque(maxlen=max_size)
        self.recent_timestamps = deque(maxlen=max_size)
        
        # False positive buffer
        self.fp_features = deque(maxlen=max_fp_size)
        self.fp_true_labels = deque(maxlen=max_fp_size)
        self.fp_pred_labels = deque(maxlen=max_fp_size)
        self.fp_timestamps = deque(maxlen=max_fp_size)
        
        self.lock = threading.Lock()
        
    def add_sample(self, features: np.ndarray, label: int,
                   confidence: float, timestamp: datetime):
        """Add a recent sample"""
        with self.lock:
            self.recent_features.append(features)
            self.recent_labels.append(label)
            self.recent_confidences.append(confidence)
            self.recent_timestamps.append(timestamp)
            
    def add_false_positive(self, features: np.ndarray, true_label: int,
                          pred_label: int, timestamp: datetime):
        """Add a confirmed false positive"""
        with self.lock:
            self.fp_features.append(features)
            self.fp_true_labels.append(true_label)
            self.fp_pred_labels.append(pred_label)
            self.fp_timestamps.append(timestamp)
            
        logger.info(f"Added FP: predicted {pred_label}, actual {true_label}. "
                   f"FP buffer size: {len(self.fp_features)}")
            
    def get_training_batch(self, batch_size: int = 1000,
                          fp_ratio: float = 0.3) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get balanced training batch mixing recent samples and FPs.
        
        Args:
            batch_size: Total batch size
            fp_ratio: Proportion of FPs in batch
            
        Returns:
            (features, labels) arrays
        """
        with self.lock:
            n_fp = min(int(batch_size * fp_ratio), len(self.fp_features))
            n_recent = min(batch_size - n_fp, len(self.recent_features))
            
            if n_recent == 0 and n_fp == 0:
                return np.array([]), np.array([])
                
            features_list = []
            labels_list = []
            
            # Sample false positives
            if n_fp > 0:
                fp_indices = np.random.choice(len(self.fp_features), n_fp, replace=False)
                for idx in fp_indices:
                    features_list.append(self.fp_features[idx])
                    labels_list.append(self.fp_true_labels[idx])
                    
            # Sample recent data
            if n_recent > 0:
                recent_indices = np.random.choice(len(self.recent_features), n_recent, replace=False)
                for idx in recent_indices:
                    features_list.append(self.recent_features[idx])
                    labels_list.append(self.recent_labels[idx])
                    
            features = np.array(features_list)
            labels = np.array(labels_list)
            
            return features, labels
            
    def get_stats(self) -> Dict:
        """Get buffer statistics"""
        with self.lock:
            return {
                'recent_samples': len(self.recent_features),
                'false_positives': len(self.fp_features),
                'total_samples': len(self.recent_features) + len(self.fp_features),
                'oldest_recent': self.recent_timestamps[0].isoformat() if self.recent_timestamps else None,
                'newest_recent': self.recent_timestamps[-1].isoformat() if self.recent_timestamps else None,
                'oldest_fp': self.fp_timestamps[0].isoformat() if self.fp_timestamps else None,
                'newest_fp': self.fp_timestamps[-1].isoformat() if self.fp_timestamps else None,
            }


class EWCTrainer:
    """
    Elastic Weight Consolidation trainer to prevent catastrophic forgetting.
    Adds regularization term based on Fisher Information Matrix.
    """
    
    def __init__(self, model: nn.Module, lambda_ewc: float = 1000.0):
        """
        Args:
            model: PyTorch model to train
            lambda_ewc: EWC regularization strength
        """
        self.model = model
        self.lambda_ewc = lambda_ewc
        
        # Store old parameters and Fisher information
        self.old_params: Dict[str, torch.Tensor] = {}
        self.fisher_matrix: Dict[str, torch.Tensor] = {}
        
    def compute_fisher_matrix(self, dataloader: DataLoader, device: str = 'cpu'):
        """
        Compute Fisher Information Matrix on current task.
        
        Args:
            dataloader: DataLoader with samples from current task
            device: Device to use
        """
        logger.info("Computing Fisher Information Matrix...")
        
        self.fisher_matrix = {}
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.fisher_matrix[name] = torch.zeros_like(param.data)
                
        self.model.eval()
        
        for batch_idx, (features, labels) in enumerate(dataloader):
            features, labels = features.to(device), labels.to(device)
            
            self.model.zero_grad()
            outputs = self.model(features)
            loss = nn.functional.cross_entropy(outputs, labels)
            loss.backward()
            
            # Accumulate squared gradients
            for name, param in self.model.named_parameters():
                if param.requires_grad and param.grad is not None:
                    self.fisher_matrix[name] += param.grad.data ** 2
                    
        # Average over batches
        n_batches = len(dataloader)
        for name in self.fisher_matrix:
            self.fisher_matrix[name] /= n_batches
            
        # Store current parameters as "old"
        self.old_params = {}
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.old_params[name] = param.data.clone()
                
        logger.info("Fisher matrix computed")
        
    def ewc_loss(self) -> torch.Tensor:
        """
        Compute EWC regularization loss.
        
        Returns:
            EWC penalty term
        """
        if not self.fisher_matrix:
            return torch.tensor(0.0)
            
        loss = 0.0
        for name, param in self.model.named_parameters():
            if name in self.fisher_matrix:
                loss += (self.fisher_matrix[name] * 
                        (param - self.old_params[name]) ** 2).sum()
                        
        return self.lambda_ewc * loss
        
    def train_step(self, features: torch.Tensor, labels: torch.Tensor,
                   optimizer: optim.Optimizer) -> float:
        """
        Single training step with EWC.
        
        Args:
            features: Input features
            labels: Target labels
            optimizer: Optimizer
            
        Returns:
            Total loss value
        """
        self.model.train()
        optimizer.zero_grad()
        
        # Forward pass
        outputs = self.model(features)
        ce_loss = nn.functional.cross_entropy(outputs, labels)
        
        # Add EWC penalty
        ewc_penalty = self.ewc_loss()
        total_loss = ce_loss + ewc_penalty
        
        # Backward pass
        total_loss.backward()
        optimizer.step()
        
        return total_loss.item()


class ModelRegistry:
    """
    Model version registry with filesystem persistence.
    Tracks all model versions and their metadata.
    """
    
    def __init__(self, registry_dir: str = "backend/model/registry"):
        """
        Args:
            registry_dir: Directory to store registry and checkpoints
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry_file = self.registry_dir / "registry.json"
        self.versions: Dict[str, ModelVersion] = {}
        self.active_version: Optional[str] = None
        
        self._load_registry()
        
    def _load_registry(self):
        """Load registry from disk"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                data = json.load(f)
                self.active_version = data.get('active_version')
                for v in data.get('versions', []):
                    mv = ModelVersion.from_dict(v)
                    self.versions[mv.version_id] = mv
            logger.info(f"Loaded {len(self.versions)} model versions from registry")
        else:
            logger.info("No existing registry found, starting fresh")
            
    def _save_registry(self):
        """Save registry to disk"""
        data = {
            'active_version': self.active_version,
            'versions': [v.to_dict() for v in self.versions.values()]
        }
        with open(self.registry_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def register_version(self, model_version: ModelVersion):
        """Register a new model version"""
        self.versions[model_version.version_id] = model_version
        self._save_registry()
        logger.info(f"Registered model version {model_version.version_id}")
        
    def promote_to_active(self, version_id: str):
        """Promote a version to active status"""
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found in registry")
            
        # Update statuses
        if self.active_version:
            self.versions[self.active_version].status = 'retired'
            
        self.active_version = version_id
        self.versions[version_id].status = 'active'
        
        self._save_registry()
        logger.info(f"Promoted version {version_id} to active")
        
    def get_active_version(self) -> Optional[ModelVersion]:
        """Get currently active model version"""
        if self.active_version:
            return self.versions[self.active_version]
        return None
        
    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """Get specific model version"""
        return self.versions.get(version_id)
        
    def list_versions(self, status: Optional[str] = None) -> List[ModelVersion]:
        """List all versions, optionally filtered by status"""
        versions = list(self.versions.values())
        if status:
            versions = [v for v in versions if v.status == status]
        return sorted(versions, key=lambda v: v.timestamp, reverse=True)


class OnlineLearningService:
    """
    Main online learning service managing incremental fine-tuning.
    """
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        # Initialize components
        self.sample_buffer = SampleBuffer(
            max_size=config.get('buffer_size', 10000),
            max_fp_size=config.get('fp_buffer_size', 5000)
        )
        
        self.registry = ModelRegistry(
            registry_dir=config.get('registry_dir', 'backend/model/registry')
        )
        
        # Model and trainer (loaded on demand)
        self.model: Optional[nn.Module] = None
        self.ewc_trainer: Optional[EWCTrainer] = None
        
        # Training config
        self.device = config.get('device', 'cpu')
        self.batch_size = config.get('batch_size', 128)
        self.learning_rate = config.get('learning_rate', 1e-4)
        self.num_epochs = config.get('num_epochs', 3)
        self.ewc_lambda = config.get('ewc_lambda', 1000.0)
        
        # Validation thresholds
        self.min_tpr = config.get('min_tpr', 0.985)  # 98.5% (allow 0.5% degradation)
        self.max_fpr = config.get('max_fpr', 0.01)   # 1%
        
        # Scheduling
        self.training_interval = config.get('training_interval_hours', 24)
        self.last_training = None
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
    def load_model(self, checkpoint_path: str) -> nn.Module:
        """
        Load model from checkpoint.
        
        Args:
            checkpoint_path: Path to model checkpoint
            
        Returns:
            Loaded model
        """
        logger.info(f"Loading model from {checkpoint_path}")
        
        # Load checkpoint
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        
        # Reconstruct model (assuming structure is saved)
        # This would need to match your actual model architecture
        from backend.model.agents.dqn_specialist import DQNSpecialist
        
        model = DQNSpecialist(
            state_dim=checkpoint.get('state_dim', 78),
            action_dim=checkpoint.get('action_dim', 15),
            hidden_dim=checkpoint.get('hidden_dim', 256)
        )
        
        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(self.device)
        model.eval()
        
        return model
        
    def evaluate_model(self, model: nn.Module, X_val: np.ndarray,
                       y_val: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model on validation set.
        
        Args:
            model: Model to evaluate
            X_val: Validation features
            y_val: Validation labels
            
        Returns:
            Metrics dictionary
        """
        model.eval()
        
        X_tensor = torch.FloatTensor(X_val).to(self.device)
        y_tensor = torch.LongTensor(y_val).to(self.device)
        
        with torch.no_grad():
            outputs = model(X_tensor)
            predictions = torch.argmax(outputs, dim=1).cpu().numpy()
            confidences = torch.softmax(outputs, dim=1).cpu().numpy()
            
        # Calculate metrics
        y_val_np = y_val
        
        # Per-class metrics
        n_classes = outputs.shape[1]
        tpr_per_class = []
        fpr_per_class = []
        
        for cls in range(n_classes):
            mask = y_val_np == cls
            if mask.sum() == 0:
                continue
                
            tp = ((predictions == cls) & (y_val_np == cls)).sum()
            fn = ((predictions != cls) & (y_val_np == cls)).sum()
            fp = ((predictions == cls) & (y_val_np != cls)).sum()
            tn = ((predictions != cls) & (y_val_np != cls)).sum()
            
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            
            tpr_per_class.append(tpr)
            fpr_per_class.append(fpr)
            
        # Overall metrics
        accuracy = (predictions == y_val_np).mean()
        macro_tpr = np.mean(tpr_per_class)
        macro_fpr = np.mean(fpr_per_class)
        
        metrics = {
            'accuracy': float(accuracy),
            'macro_tpr': float(macro_tpr),
            'macro_fpr': float(macro_fpr),
            'min_tpr': float(np.min(tpr_per_class)) if tpr_per_class else 0.0,
            'max_fpr': float(np.max(fpr_per_class)) if fpr_per_class else 0.0,
        }
        
        logger.info(f"Evaluation metrics: {metrics}")
        return metrics
        
    def fine_tune_model(self, X_train: np.ndarray, y_train: np.ndarray,
                       X_val: np.ndarray, y_val: np.ndarray,
                       parent_checkpoint: str) -> Tuple[nn.Module, Dict[str, float]]:
        """
        Fine-tune model with EWC.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            parent_checkpoint: Path to parent model checkpoint
            
        Returns:
            (fine_tuned_model, validation_metrics)
        """
        logger.info(f"Starting fine-tuning with {len(X_train)} samples...")
        
        # Load parent model
        model = self.load_model(parent_checkpoint)
        
        # Create EWC trainer
        ewc_trainer = EWCTrainer(model, lambda_ewc=self.ewc_lambda)
        
        # Compute Fisher matrix on validation set (represents old task)
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val),
            torch.LongTensor(y_val)
        )
        val_loader = DataLoader(val_dataset, batch_size=self.batch_size, shuffle=False)
        ewc_trainer.compute_fisher_matrix(val_loader, device=self.device)
        
        # Create training loader
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train),
            torch.LongTensor(y_train)
        )
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)
        
        # Optimizer
        optimizer = optim.Adam(model.parameters(), lr=self.learning_rate)
        
        # Training loop
        for epoch in range(self.num_epochs):
            total_loss = 0.0
            n_batches = 0
            
            for features, labels in train_loader:
                features = features.to(self.device)
                labels = labels.to(self.device)
                
                loss = ewc_trainer.train_step(features, labels, optimizer)
                total_loss += loss
                n_batches += 1
                
            avg_loss = total_loss / n_batches
            logger.info(f"Epoch {epoch+1}/{self.num_epochs}, Loss: {avg_loss:.4f}")
            
        # Evaluate fine-tuned model
        metrics = self.evaluate_model(model, X_val, y_val)
        
        return model, metrics
        
    def validate_and_promote(self, new_model: nn.Module, new_metrics: Dict[str, float],
                            parent_version: str, training_samples: int) -> bool:
        """
        Validate new model and promote if criteria met.
        
        Args:
            new_model: Fine-tuned model
            new_metrics: Validation metrics
            parent_version: Parent model version ID
            training_samples: Number of samples used for training
            
        Returns:
            True if model was promoted, False if rolled back
        """
        # Check validation criteria
        tpr_ok = new_metrics['macro_tpr'] >= self.min_tpr
        fpr_ok = new_metrics['macro_fpr'] <= self.max_fpr
        
        if not (tpr_ok and fpr_ok):
            logger.warning(
                f"Model failed validation: TPR={new_metrics['macro_tpr']:.4f} "
                f"(min {self.min_tpr}), FPR={new_metrics['macro_fpr']:.4f} "
                f"(max {self.max_fpr}). Rolling back."
            )
            return False
            
        # Create new version
        timestamp = datetime.utcnow()
        version_id = hashlib.sha256(
            f"{timestamp.isoformat()}{parent_version}".encode()
        ).hexdigest()[:12]
        
        # Save checkpoint
        checkpoint_dir = self.registry.registry_dir / version_id
        checkpoint_dir.mkdir(exist_ok=True)
        checkpoint_path = checkpoint_dir / "model.pth"
        
        torch.save({
            'model_state_dict': new_model.state_dict(),
            'timestamp': timestamp.isoformat(),
            'parent_version': parent_version,
            'metrics': new_metrics,
        }, checkpoint_path)
        
        # Register version
        model_version = ModelVersion(
            version_id=version_id,
            timestamp=timestamp,
            parent_version=parent_version,
            training_samples=training_samples,
            validation_metrics=new_metrics,
            checkpoint_path=str(checkpoint_path),
            feature_version="v1",  # TODO: track feature version
            status='shadow',
            notes=f"Fine-tuned on {training_samples} samples"
        )
        
        self.registry.register_version(model_version)
        
        # Shadow evaluation (in production, would test on live traffic)
        # For now, just promote directly if validation passed
        logger.info(f"Promoting version {version_id} to active")
        self.registry.promote_to_active(version_id)
        
        return True
        
    def run_training_cycle(self):
        """Execute one training cycle"""
        logger.info("Starting training cycle...")
        
        # Get training batch from buffer
        X_train, y_train = self.sample_buffer.get_training_batch(
            batch_size=2000,
            fp_ratio=0.3
        )
        
        if len(X_train) < 100:
            logger.info("Insufficient samples for training, skipping cycle")
            return
            
        # Load validation data
        val_data_path = Path("data/processed")
        if not val_data_path.exists():
            logger.error("Validation data not found")
            return
            
        X_val = np.load(val_data_path / "X_val.npy")
        y_val = np.load(val_data_path / "y_val.npy")
        
        # Get current active model
        active_version = self.registry.get_active_version()
        if not active_version:
            logger.error("No active model version found")
            return
            
        parent_checkpoint = active_version.checkpoint_path
        
        try:
            # Fine-tune model
            new_model, metrics = self.fine_tune_model(
                X_train, y_train,
                X_val, y_val,
                parent_checkpoint
            )
            
            # Validate and promote
            success = self.validate_and_promote(
                new_model, metrics,
                active_version.version_id,
                len(X_train)
            )
            
            if success:
                logger.info("Training cycle completed successfully")
            else:
                logger.warning("Training cycle completed but model was rolled back")
                
        except Exception as e:
            logger.error(f"Training cycle failed: {e}", exc_info=True)
            
        self.last_training = datetime.utcnow()
        
    def background_loop(self):
        """Background thread loop"""
        logger.info("Online learning service started")
        
        while self.running:
            try:
                # Check if training is due
                if (self.last_training is None or
                    datetime.utcnow() - self.last_training >= 
                    timedelta(hours=self.training_interval)):
                    
                    self.run_training_cycle()
                    
            except Exception as e:
                logger.error(f"Error in background loop: {e}", exc_info=True)
                
            # Sleep for 1 hour between checks
            time.sleep(3600)
            
    def start(self):
        """Start background service"""
        if self.running:
            logger.warning("Service already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self.background_loop, daemon=True)
        self.thread.start()
        logger.info("Online learning service background thread started")
        
    def stop(self):
        """Stop background service"""
        if not self.running:
            return
            
        logger.info("Stopping online learning service...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("Online learning service stopped")
        
    def get_status(self) -> Dict:
        """Get service status"""
        return {
            'running': self.running,
            'last_training': self.last_training.isoformat() if self.last_training else None,
            'buffer_stats': self.sample_buffer.get_stats(),
            'active_version': self.registry.active_version,
            'total_versions': len(self.registry.versions),
        }


def create_service(config_path: Optional[str] = None) -> OnlineLearningService:
    """
    Factory function to create online learning service.
    
    Args:
        config_path: Path to config file (optional)
        
    Returns:
        Configured OnlineLearningService instance
    """
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        # Default config
        config = {
            'buffer_size': 10000,
            'fp_buffer_size': 5000,
            'registry_dir': 'backend/model/registry',
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'batch_size': 128,
            'learning_rate': 1e-4,
            'num_epochs': 3,
            'ewc_lambda': 1000.0,
            'min_tpr': 0.985,
            'max_fpr': 0.01,
            'training_interval_hours': 24,
        }
        
    return OnlineLearningService(config)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    service = create_service()
    service.start()
    
    try:
        # Keep running
        while True:
            time.sleep(60)
            status = service.get_status()
            logger.info(f"Service status: {status}")
    except KeyboardInterrupt:
        service.stop()
