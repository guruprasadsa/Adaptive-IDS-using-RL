"""
Unit tests for Prioritized Experience Replay Buffer
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from model.replay.prioritized_buffer import (
    SumTree,
    PrioritizedReplayBuffer,
    MultiBufferManager,
    create_replay_buffer
)


class TestSumTree:
    """Test sum tree data structure"""
    
    def test_initialization(self):
        """Test sum tree initialization"""
        tree = SumTree(capacity=100)
        
        assert tree.capacity == 100
        assert len(tree.tree) == 2 * 100 - 1
        assert len(tree.data) == 100
        assert tree.n_entries == 0
    
    def test_add_single(self):
        """Test adding single element"""
        tree = SumTree(capacity=10)
        
        tree.add(priority=1.0, data='sample1')
        
        assert tree.n_entries == 1
        assert tree.total() == 1.0
    
    def test_add_multiple(self):
        """Test adding multiple elements"""
        tree = SumTree(capacity=10)
        
        for i in range(5):
            tree.add(priority=float(i + 1), data=f'sample{i}')
        
        assert tree.n_entries == 5
        assert tree.total() == 1.0 + 2.0 + 3.0 + 4.0 + 5.0
    
    def test_add_overflow(self):
        """Test adding beyond capacity (should wrap)"""
        tree = SumTree(capacity=5)
        
        for i in range(10):
            tree.add(priority=1.0, data=f'sample{i}')
        
        assert tree.n_entries == 5  # Capped at capacity
    
    def test_update(self):
        """Test priority update"""
        tree = SumTree(capacity=10)
        
        tree.add(priority=1.0, data='sample1')
        initial_total = tree.total()
        
        # Update the first element's priority
        tree.update(idx=tree.capacity - 1, priority=5.0)
        
        assert tree.total() == initial_total + 4.0  # Changed from 1.0 to 5.0
    
    def test_get(self):
        """Test retrieval by priority value"""
        tree = SumTree(capacity=10)
        
        tree.add(priority=1.0, data='A')
        tree.add(priority=2.0, data='B')
        tree.add(priority=3.0, data='C')
        
        # Get sample with priority value 0.5 (should get first)
        idx, priority, data = tree.get(0.5)
        assert data == 'A'
        
        # Get sample with priority value 2.5 (should get second or third)
        idx, priority, data = tree.get(2.5)
        assert data in ['B', 'C']


class TestPrioritizedReplayBuffer:
    """Test prioritized replay buffer"""
    
    def test_initialization(self):
        """Test buffer initialization"""
        buffer = PrioritizedReplayBuffer(
            capacity=1000,
            num_classes=18,
            alpha=0.6,
            beta=0.4
        )
        
        assert buffer.capacity == 1000
        assert buffer.num_classes == 18
        assert buffer.alpha == 0.6
        assert buffer.beta == 0.4
        assert len(buffer) == 0
    
    def test_add_experience(self):
        """Test adding experiences"""
        buffer = PrioritizedReplayBuffer(capacity=100, num_classes=5)
        
        state = np.random.randn(41)
        action = 0
        reward = 1.0
        next_state = np.random.randn(41)
        done = False
        class_label = 2
        
        buffer.add(state, action, reward, next_state, done, class_label)
        
        assert len(buffer) == 1
        assert buffer.class_counters[2] == 1
    
    def test_add_multiple_classes(self):
        """Test adding experiences from multiple classes"""
        buffer = PrioritizedReplayBuffer(capacity=100, num_classes=5)
        
        for i in range(50):
            state = np.random.randn(41)
            class_label = i % 5
            
            buffer.add(
                state=state,
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=class_label
            )
        
        assert len(buffer) == 50
        
        # Check class distribution
        class_dist = buffer.get_class_distribution()
        for class_id in range(5):
            assert class_dist[class_id] == 10  # Each class has 10 samples
    
    def test_sample(self):
        """Test sampling from buffer"""
        buffer = PrioritizedReplayBuffer(capacity=100, num_classes=5)
        
        # Add some experiences
        for i in range(50):
            buffer.add(
                state=np.random.randn(41),
                action=i % 2,
                reward=float(i),
                next_state=np.random.randn(41),
                done=i % 10 == 0,
                class_label=i % 5
            )
        
        # Sample batch
        batch_size = 16
        states, actions, rewards, next_states, dones, labels, indices, weights = buffer.sample(batch_size)
        
        assert states.shape == (batch_size, 41)
        assert actions.shape == (batch_size,)
        assert rewards.shape == (batch_size,)
        assert next_states.shape == (batch_size, 41)
        assert dones.shape == (batch_size,)
        assert labels.shape == (batch_size,)
        assert indices.shape == (batch_size,)
        assert weights.shape == (batch_size,)
        
        # Weights should be normalized
        assert weights.max() == 1.0
        assert weights.min() > 0
    
    def test_update_priorities(self):
        """Test priority updates"""
        buffer = PrioritizedReplayBuffer(capacity=100, num_classes=5)
        
        # Add experiences
        for i in range(20):
            buffer.add(
                state=np.random.randn(41),
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=i % 5
            )
        
        # Sample and update priorities
        states, actions, rewards, next_states, dones, labels, indices, weights = buffer.sample(10)
        
        # Create fake TD errors
        td_errors = np.random.randn(10)
        
        # Update should not raise error
        buffer.update_priorities(indices, td_errors)
    
    def test_beta_annealing(self):
        """Test beta annealing over time"""
        buffer = PrioritizedReplayBuffer(
            capacity=100,
            num_classes=5,
            beta=0.4,
            beta_increment=0.01
        )
        
        # Add experiences
        for i in range(50):
            buffer.add(
                state=np.random.randn(41),
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=i % 5
            )
        
        initial_beta = buffer.beta
        
        # Sample multiple times
        for _ in range(10):
            buffer.sample(8)
        
        # Beta should have increased
        assert buffer.beta > initial_beta
        assert buffer.beta <= 1.0  # Should be capped at 1.0
    
    def test_minority_class_quota(self):
        """Test that minority classes get minimum representation"""
        buffer = PrioritizedReplayBuffer(
            capacity=1000,
            num_classes=5,
            min_class_quota=0.05
        )
        
        # Add imbalanced data (class 0 is majority, class 4 is minority)
        for i in range(500):
            class_label = 0 if i < 450 else 4  # 450 samples class 0, 50 samples class 4
            
            buffer.add(
                state=np.random.randn(41),
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=class_label
            )
        
        # Sample and check class distribution
        batch_size = 100
        states, actions, rewards, next_states, dones, labels, indices, weights = buffer.sample(batch_size)
        
        # Count minority class samples
        minority_count = np.sum(labels == 4)
        
        # Should have at least some minority samples due to quota
        assert minority_count > 0
    
    def test_hard_negatives(self):
        """Test adding hard negative samples"""
        buffer = PrioritizedReplayBuffer(capacity=100, num_classes=5)
        
        # Add regular samples
        for i in range(20):
            buffer.add(
                state=np.random.randn(41),
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=i % 5
            )
        
        # Add hard negatives
        hard_negatives = [
            (np.random.randn(41), 1, -1.0, np.random.randn(41), False, 3)
            for _ in range(5)
        ]
        
        buffer.add_hard_negatives(hard_negatives, boost_factor=2.0)
        
        assert len(buffer) == 25
    
    def test_clear(self):
        """Test buffer clearing"""
        buffer = PrioritizedReplayBuffer(capacity=100, num_classes=5)
        
        # Add samples
        for i in range(20):
            buffer.add(
                state=np.random.randn(41),
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=i % 5
            )
        
        assert len(buffer) > 0
        
        buffer.clear()
        
        assert len(buffer) == 0


class TestMultiBufferManager:
    """Test multi-buffer manager"""
    
    def test_initialization(self):
        """Test manager initialization"""
        manager = MultiBufferManager(
            num_specialists=5,
            capacity_per_specialist=100,
            num_classes_per_specialist=2
        )
        
        assert manager.num_specialists == 5
        assert len(manager.buffers) == 5
    
    def test_add_to_specific_buffer(self):
        """Test adding to specific specialist's buffer"""
        manager = MultiBufferManager(
            num_specialists=3,
            capacity_per_specialist=100
        )
        
        # Add to specialist 0
        manager.add(
            specialist_id=0,
            state=np.random.randn(41),
            action=0,
            reward=1.0,
            next_state=np.random.randn(41),
            done=False,
            class_label=0
        )
        
        # Add to specialist 2
        manager.add(
            specialist_id=2,
            state=np.random.randn(41),
            action=1,
            reward=0.5,
            next_state=np.random.randn(41),
            done=True,
            class_label=1
        )
        
        sizes = manager.get_buffer_sizes()
        
        assert sizes[0] == 1
        assert sizes[1] == 0
        assert sizes[2] == 1
    
    def test_sample_from_specific_buffer(self):
        """Test sampling from specific buffer"""
        manager = MultiBufferManager(
            num_specialists=3,
            capacity_per_specialist=100
        )
        
        # Add samples to specialist 1
        for i in range(20):
            manager.add(
                specialist_id=1,
                state=np.random.randn(41),
                action=i % 2,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=i % 2
            )
        
        # Sample from specialist 1
        batch = manager.sample(specialist_id=1, batch_size=8)
        
        assert len(batch) == 8  # Should return 8 elements
        states = batch[0]
        assert states.shape == (8, 41)
    
    def test_update_priorities_specific_buffer(self):
        """Test updating priorities in specific buffer"""
        manager = MultiBufferManager(
            num_specialists=2,
            capacity_per_specialist=50
        )
        
        # Add samples
        for i in range(20):
            manager.add(
                specialist_id=0,
                state=np.random.randn(41),
                action=0,
                reward=1.0,
                next_state=np.random.randn(41),
                done=False,
                class_label=0
            )
        
        # Sample
        states, actions, rewards, next_states, dones, labels, indices, weights = manager.sample(0, 10)
        
        # Update priorities
        td_errors = np.random.randn(10)
        manager.update_priorities(specialist_id=0, indices=indices, td_errors=td_errors)
    
    def test_get_total_size(self):
        """Test getting total size across all buffers"""
        manager = MultiBufferManager(
            num_specialists=3,
            capacity_per_specialist=100
        )
        
        # Add to different buffers
        for i in range(10):
            manager.add(0, np.random.randn(41), 0, 1.0, np.random.randn(41), False, 0)
        
        for i in range(15):
            manager.add(1, np.random.randn(41), 0, 1.0, np.random.randn(41), False, 0)
        
        for i in range(5):
            manager.add(2, np.random.randn(41), 0, 1.0, np.random.randn(41), False, 0)
        
        total = manager.get_total_size()
        assert total == 30


class TestFactoryFunction:
    """Test factory function"""
    
    def test_create_replay_buffer(self):
        """Test buffer factory"""
        buffer = create_replay_buffer(
            capacity=1000,
            num_classes=18,
            alpha=0.6,
            beta=0.4
        )
        
        assert isinstance(buffer, PrioritizedReplayBuffer)
        assert buffer.capacity == 1000
        assert buffer.num_classes == 18


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
