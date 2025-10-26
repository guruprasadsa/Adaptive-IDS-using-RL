"""
Prioritized Experience Replay Buffer
Implements sum tree for efficient priority-based sampling with per-class quotas
"""

import numpy as np
import torch
from typing import Tuple, Dict, List, Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SumTree:
    """
    Sum tree data structure for efficient prioritized sampling
    Binary tree where each node stores sum of priorities of its children
    """
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1, dtype=np.float32)
        self.data = np.empty(capacity, dtype=object)  # Use empty instead of zeros
        self.data.fill(None)  # Initialize with None
        self.data_pointer = 0
        self.n_entries = 0
    
    def _propagate(self, idx: int, change: float):
        """Propagate priority change up the tree"""
        parent = (idx - 1) // 2
        self.tree[parent] += change
        
        if parent != 0:
            self._propagate(parent, change)
    
    def _retrieve(self, idx: int, s: float) -> int:
        """Find sample index for given priority value"""
        left = 2 * idx + 1
        right = left + 1
        
        # If leaf node, return data index
        if left >= len(self.tree):
            return idx
        
        # Traverse left if priority sum is sufficient
        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])
    
    def total(self) -> float:
        """Return total priority sum"""
        return self.tree[0]
    
    def add(self, priority: float, data: object):
        """Add new experience with given priority"""
        # Data pointer wraps around when capacity reached
        idx = self.data_pointer + self.capacity - 1
        
        self.data[self.data_pointer] = data
        self.update(idx, priority)
        
        self.data_pointer = (self.data_pointer + 1) % self.capacity
        self.n_entries = min(self.n_entries + 1, self.capacity)
    
    def update(self, idx: int, priority: float):
        """Update priority of existing sample"""
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)
    
    def get(self, s: float) -> Tuple[int, float, object]:
        """
        Retrieve sample based on priority value
        
        Args:
            s: Priority value to sample
        
        Returns:
            idx: Tree index
            priority: Priority value
            data: Stored experience
        """
        idx = self._retrieve(0, s)
        data_idx = idx - self.capacity + 1
        
        return idx, self.tree[idx], self.data[data_idx]


class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay with per-class buffers
    Ensures minority classes have minimum representation in batches
    """
    
    def __init__(
        self,
        capacity: int,
        num_classes: int,
        alpha: float = 0.6,
        beta: float = 0.4,
        beta_increment: float = 0.001,
        epsilon: float = 0.01,
        min_class_quota: float = 0.05
    ):
        """
        Args:
            capacity: Total buffer capacity
            num_classes: Number of attack classes
            alpha: Prioritization exponent (0=uniform, 1=full prioritization)
            beta: Importance sampling exponent
            beta_increment: Beta annealing rate
            epsilon: Small constant to prevent zero priority
            min_class_quota: Minimum fraction of batch from minority classes
        """
        self.capacity = capacity
        self.num_classes = num_classes
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        self.epsilon = epsilon
        self.min_class_quota = min_class_quota
        
        # Main buffer (sum tree)
        self.tree = SumTree(capacity)
        
        # Per-class indices for quota enforcement
        self.class_indices = defaultdict(list)
        self.class_counters = np.zeros(num_classes, dtype=np.int32)
        
        # Track samples by index for class management
        self.index_to_class = {}
        
        logger.info(
            f"PrioritizedReplayBuffer initialized: capacity={capacity}, "
            f"num_classes={num_classes}, alpha={alpha}, beta={beta}"
        )
    
    def __len__(self) -> int:
        """Return current buffer size"""
        return self.tree.n_entries
    
    def add(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        class_label: int
    ):
        """
        Add experience to buffer with maximum priority
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Terminal flag
            class_label: True class label for quota tracking
        """
        # Set initial priority to maximum
        max_priority = np.max(self.tree.tree[-self.tree.capacity:])
        if max_priority == 0:
            max_priority = 1.0
        
        experience = (state, action, reward, next_state, done, class_label)
        
        # Add to sum tree
        self.tree.add(max_priority, experience)
        
        # Track class membership
        current_idx = (self.tree.data_pointer - 1) % self.capacity
        
        # Remove old class association if overwriting
        if current_idx in self.index_to_class:
            old_class = self.index_to_class[current_idx]
            if current_idx in self.class_indices[old_class]:
                self.class_indices[old_class].remove(current_idx)
                self.class_counters[old_class] -= 1
        
        # Add new class association
        self.class_indices[class_label].append(current_idx)
        self.class_counters[class_label] += 1
        self.index_to_class[current_idx] = class_label
    
    def sample(self, batch_size: int) -> Tuple:
        """
        Sample batch with importance sampling weights and class quotas
        
        Args:
            batch_size: Number of samples
        
        Returns:
            states: State batch [batch_size, state_dim]
            actions: Action batch [batch_size]
            rewards: Reward batch [batch_size]
            next_states: Next state batch [batch_size, state_dim]
            dones: Done batch [batch_size]
            class_labels: Class label batch [batch_size]
            indices: Tree indices for priority update [batch_size]
            weights: Importance sampling weights [batch_size]
        """
        if len(self) == 0:
            raise ValueError("Cannot sample from empty buffer")
        
        batch = []
        indices = []
        priorities = []
        
        # Calculate quota sizes
        min_quota_size = max(1, int(batch_size * self.min_class_quota))
        
        # Sample minority classes first (enforce quota)
        minority_samples = 0
        for class_id in range(self.num_classes):
            if self.class_counters[class_id] < 100:  # Minority class threshold
                n_samples = min(min_quota_size, self.class_counters[class_id])
                
                if n_samples > 0:
                    # Sample from this class's indices
                    class_idx_sample = np.random.choice(
                        self.class_indices[class_id],
                        size=n_samples,
                        replace=False
                    )
                    
                    for idx in class_idx_sample:
                        tree_idx = idx + self.capacity - 1
                        priority = self.tree.tree[tree_idx]
                        data = self.tree.data[idx]
                        
                        # Skip if data is None or invalid (not yet filled)
                        if data is None or not isinstance(data, tuple):
                            continue
                        
                        batch.append(data)
                        indices.append(tree_idx)
                        priorities.append(priority)
                        minority_samples += 1
        
        # Fill remaining batch with priority-based sampling
        remaining = batch_size - minority_samples
        
        if remaining > 0:
            segment = self.tree.total() / remaining
            
            for i in range(remaining):
                s = np.random.uniform(segment * i, segment * (i + 1))
                idx, priority, data = self.tree.get(s)
                
                # Skip if data is None or invalid (not yet filled)
                if data is None or not isinstance(data, tuple):
                    # Retry with a different sample
                    retries = 0
                    while retries < 10:
                        s = np.random.uniform(segment * i, segment * (i + 1))
                        idx, priority, data = self.tree.get(s)
                        if data is not None and isinstance(data, tuple):
                            break
                        retries += 1
                    
                    if data is None or not isinstance(data, tuple):
                        continue
                
                batch.append(data)
                indices.append(idx)
                priorities.append(priority)
        
        # Handle edge case where we couldn't sample enough valid data
        if len(batch) == 0:
            raise ValueError("Could not sample any valid data from buffer")
        
        # Compute importance sampling weights
        priorities = np.array(priorities)
        sampling_probs = priorities / (self.tree.total() + 1e-8)  # Add epsilon to prevent division by zero
        
        # IS weights: (1 / (N * P(i)))^beta
        # Add epsilon to prevent division by zero
        weights = np.power(len(self) * sampling_probs + 1e-8, -self.beta)
        weights /= (weights.max() + 1e-8)  # Normalize by max for stability
        
        # Anneal beta
        self.beta = min(1.0, self.beta + self.beta_increment)
        
        # Unpack batch
        states = []
        actions = []
        rewards = []
        next_states = []
        dones = []
        class_labels = []
        
        for experience in batch:
            state, action, reward, next_state, done, class_label = experience
            states.append(state)
            actions.append(action)
            rewards.append(reward)
            next_states.append(next_state)
            dones.append(done)
            class_labels.append(class_label)
        
        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.int64),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32),
            np.array(class_labels, dtype=np.int64),
            np.array(indices, dtype=np.int32),
            np.array(weights, dtype=np.float32)
        )
    
    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """
        Update priorities based on TD errors
        
        Args:
            indices: Tree indices
            td_errors: TD error magnitudes
        """
        for idx, td_error in zip(indices, td_errors):
            # Priority = |TD error| + epsilon
            priority = (np.abs(td_error) + self.epsilon) ** self.alpha
            self.tree.update(idx, priority)
    
    def add_hard_negatives(
        self,
        misclassified_samples: List[Tuple],
        boost_factor: float = 2.0
    ):
        """
        Add hard negative samples with boosted priority
        
        Args:
            misclassified_samples: List of (state, action, reward, next_state, done, class_label)
            boost_factor: Priority multiplier for hard negatives
        """
        for sample in misclassified_samples:
            state, action, reward, next_state, done, class_label = sample
            
            # Add with boosted priority
            max_priority = np.max(self.tree.tree[-self.tree.capacity:])
            if max_priority == 0:
                max_priority = 1.0
            
            boosted_priority = max_priority * boost_factor
            
            experience = (state, action, reward, next_state, done, class_label)
            self.tree.add(boosted_priority, experience)
            
            # Track class
            current_idx = (self.tree.data_pointer - 1) % self.capacity
            self.class_indices[class_label].append(current_idx)
            self.class_counters[class_label] += 1
            self.index_to_class[current_idx] = class_label
    
    def get_class_distribution(self) -> Dict[int, int]:
        """Return current class distribution in buffer"""
        return {int(k): int(v) for k, v in enumerate(self.class_counters)}
    
    def clear(self):
        """Clear buffer"""
        self.tree = SumTree(self.capacity)
        self.class_indices = defaultdict(list)
        self.class_counters = np.zeros(self.num_classes, dtype=np.int32)
        self.index_to_class = {}
        logger.info("Buffer cleared")


class MultiBufferManager:
    """
    Manages separate replay buffers for each specialist
    """
    
    def __init__(
        self,
        num_specialists: int,
        capacity_per_specialist: int,
        num_classes_per_specialist: int = 2,
        **buffer_kwargs
    ):
        """
        Args:
            num_specialists: Number of specialist agents
            capacity_per_specialist: Buffer capacity per specialist
            num_classes_per_specialist: Classes per specialist (typically 2: benign vs attack)
            **buffer_kwargs: Additional arguments for PrioritizedReplayBuffer
        """
        self.num_specialists = num_specialists
        
        # Create buffer for each specialist
        self.buffers = {}
        
        for specialist_id in range(num_specialists):
            self.buffers[specialist_id] = PrioritizedReplayBuffer(
                capacity=capacity_per_specialist,
                num_classes=num_classes_per_specialist,
                **buffer_kwargs
            )
        
        logger.info(
            f"MultiBufferManager created with {num_specialists} buffers, "
            f"{capacity_per_specialist} capacity each"
        )
    
    def add(
        self,
        specialist_id: int,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        class_label: int
    ):
        """Add experience to specific specialist's buffer"""
        if specialist_id in self.buffers:
            self.buffers[specialist_id].add(
                state, action, reward, next_state, done, class_label
            )
    
    def sample(self, specialist_id: int, batch_size: int) -> Tuple:
        """Sample from specific specialist's buffer"""
        if specialist_id in self.buffers:
            return self.buffers[specialist_id].sample(batch_size)
        else:
            raise ValueError(f"Specialist {specialist_id} not found")
    
    def update_priorities(
        self,
        specialist_id: int,
        indices: np.ndarray,
        td_errors: np.ndarray
    ):
        """Update priorities in specific specialist's buffer"""
        if specialist_id in self.buffers:
            self.buffers[specialist_id].update_priorities(indices, td_errors)
    
    def get_buffer_sizes(self) -> Dict[int, int]:
        """Get size of each buffer"""
        return {sp_id: len(buf) for sp_id, buf in self.buffers.items()}
    
    def get_total_size(self) -> int:
        """Get total size across all buffers"""
        return sum(len(buf) for buf in self.buffers.values())


def create_replay_buffer(
    capacity: int,
    num_classes: int,
    alpha: float = 0.6,
    beta: float = 0.4,
    beta_increment: float = 0.001,
    epsilon: float = 0.01,
    min_class_quota: float = 0.05
) -> PrioritizedReplayBuffer:
    """
    Factory function to create prioritized replay buffer
    
    Args:
        capacity: Buffer capacity
        num_classes: Number of classes
        alpha: Prioritization exponent
        beta: Importance sampling exponent
        beta_increment: Beta annealing rate
        epsilon: Small constant for zero priority prevention
        min_class_quota: Minimum fraction for minority classes
    
    Returns:
        buffer: PrioritizedReplayBuffer instance
    """
    buffer = PrioritizedReplayBuffer(
        capacity=capacity,
        num_classes=num_classes,
        alpha=alpha,
        beta=beta,
        beta_increment=beta_increment,
        epsilon=epsilon,
        min_class_quota=min_class_quota
    )
    
    logger.info(f"Created replay buffer with capacity {capacity}")
    
    return buffer
