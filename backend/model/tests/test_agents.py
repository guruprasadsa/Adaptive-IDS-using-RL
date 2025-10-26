"""
Unit tests for A3C Router and DQN Specialist agents
"""

import pytest
import torch
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from model.agents.a3c_router import (
    SharedFeatureExtractor,
    ActorNetwork,
    CriticNetwork,
    A3CRouter,
    A3CLoss,
    create_a3c_model
)

from model.agents.dqn_specialist import (
    NoisyLinear,
    DuelingDQN,
    DQNSpecialist,
    compute_n_step_returns,
    create_specialists
)


class TestSharedFeatureExtractor:
    """Test shared feature extraction network"""
    
    def test_initialization(self):
        """Test feature extractor initialization"""
        extractor = SharedFeatureExtractor(input_dim=41, hidden_dims=[128, 64])
        
        assert extractor.input_dim == 41
        assert extractor.hidden_dims == [128, 64]
        assert extractor.output_dim == 64
    
    def test_forward_pass(self):
        """Test forward pass through feature extractor"""
        extractor = SharedFeatureExtractor(input_dim=41, hidden_dims=[128, 64])
        
        # Single sample
        x = torch.randn(1, 41)
        features = extractor(x)
        
        assert features.shape == (1, 64)
        assert not torch.isnan(features).any()
        assert not torch.isinf(features).any()
    
    def test_batch_processing(self):
        """Test batch processing"""
        extractor = SharedFeatureExtractor(input_dim=41, hidden_dims=[128, 64])
        
        # Batch of samples
        batch_size = 32
        x = torch.randn(batch_size, 41)
        features = extractor(x)
        
        assert features.shape == (batch_size, 64)
        assert not torch.isnan(features).any()


class TestActorNetwork:
    """Test actor (policy) network"""
    
    def test_initialization(self):
        """Test actor network initialization"""
        actor = ActorNetwork(feature_dim=64, num_specialists=18)
        
        assert actor.feature_dim == 64
        assert actor.num_specialists == 18
    
    def test_forward_pass(self):
        """Test forward pass produces correct logit shape"""
        actor = ActorNetwork(feature_dim=64, num_specialists=18)
        
        features = torch.randn(32, 64)
        logits = actor(features)
        
        assert logits.shape == (32, 18)
        assert not torch.isnan(logits).any()


class TestCriticNetwork:
    """Test critic (value) network"""
    
    def test_initialization(self):
        """Test critic network initialization"""
        critic = CriticNetwork(feature_dim=64)
        
        assert critic.feature_dim == 64
    
    def test_forward_pass(self):
        """Test forward pass produces scalar values"""
        critic = CriticNetwork(feature_dim=64)
        
        features = torch.randn(32, 64)
        values = critic(features)
        
        assert values.shape == (32, 1)
        assert not torch.isnan(values).any()


class TestA3CRouter:
    """Test complete A3C router model"""
    
    def test_initialization(self):
        """Test router initialization"""
        router = A3CRouter(
            input_dim=41,
            num_specialists=18,
            hidden_dims=[128, 64],
            entropy_coef=0.01
        )
        
        assert router.input_dim == 41
        assert router.num_specialists == 18
        assert router.entropy_coef == 0.01
    
    def test_forward_pass_inference(self):
        """Test forward pass in inference mode (action not provided)"""
        router = A3CRouter(input_dim=41, num_specialists=18)
        
        state = torch.randn(32, 41)
        action, log_prob, entropy, value = router(state)
        
        assert action.shape == (32,)
        assert log_prob.shape == (32,)
        assert entropy.shape == (32,)
        assert value.shape == (32,)
        
        # Actions should be valid indices
        assert (action >= 0).all() and (action < 18).all()
    
    def test_forward_pass_training(self):
        """Test forward pass in training mode (action provided)"""
        router = A3CRouter(input_dim=41, num_specialists=18)
        
        state = torch.randn(32, 41)
        action = torch.randint(0, 18, (32,))
        
        _, log_prob, entropy, value = router(state, action)
        
        assert log_prob.shape == (32,)
        assert entropy.shape == (32,)
        assert value.shape == (32,)
    
    def test_select_specialist(self):
        """Test specialist selection for single sample"""
        router = A3CRouter(input_dim=41, num_specialists=18)
        
        state = torch.randn(41)
        specialist_idx = router.select_specialist(state)
        
        assert isinstance(specialist_idx, int)
        assert 0 <= specialist_idx < 18
    
    def test_get_action_probs(self):
        """Test action probability computation"""
        router = A3CRouter(input_dim=41, num_specialists=18)
        
        # Single sample
        state = torch.randn(41)
        probs = router.get_action_probs(state)
        
        assert probs.shape == (18,)
        assert torch.allclose(probs.sum(), torch.tensor(1.0), atol=1e-5)
        
        # Batch
        state_batch = torch.randn(32, 41)
        probs_batch = router.get_action_probs(state_batch)
        
        assert probs_batch.shape == (32, 18)
        assert torch.allclose(probs_batch.sum(dim=1), torch.ones(32), atol=1e-5)


class TestA3CLoss:
    """Test A3C loss computation"""
    
    def test_compute_advantages(self):
        """Test GAE advantage computation"""
        loss_fn = A3CLoss(actor_coef=1.0, critic_coef=0.5, entropy_coef=0.01)
        
        batch_size = 32
        rewards = torch.randn(batch_size)
        values = torch.randn(batch_size)
        next_values = torch.randn(batch_size)
        dones = torch.zeros(batch_size)
        
        advantages, returns = loss_fn.compute_advantages(
            rewards, values, next_values, dones, gamma=0.99, gae_lambda=0.95
        )
        
        assert advantages.shape == (batch_size,)
        assert returns.shape == (batch_size,)
        
        # Advantages should be normalized (approximately)
        assert abs(advantages.mean()) < 0.5
        assert abs(advantages.std() - 1.0) < 0.5
    
    def test_compute_loss(self):
        """Test loss computation"""
        loss_fn = A3CLoss(actor_coef=1.0, critic_coef=0.5, entropy_coef=0.01)
        
        batch_size = 32
        log_probs = torch.randn(batch_size)
        advantages = torch.randn(batch_size)
        values = torch.randn(batch_size)
        returns = torch.randn(batch_size)
        entropy = torch.abs(torch.randn(batch_size))
        
        total_loss, loss_dict = loss_fn.compute_loss(
            log_probs, advantages, values, returns, entropy
        )
        
        assert isinstance(total_loss, torch.Tensor)
        assert total_loss.dim() == 0  # Scalar
        
        assert 'total_loss' in loss_dict
        assert 'actor_loss' in loss_dict
        assert 'critic_loss' in loss_dict
        assert 'entropy' in loss_dict


class TestNoisyLinear:
    """Test NoisyNet linear layer"""
    
    def test_initialization(self):
        """Test noisy linear initialization"""
        layer = NoisyLinear(in_features=64, out_features=32)
        
        assert layer.in_features == 64
        assert layer.out_features == 32
    
    def test_forward_training(self):
        """Test forward pass in training mode (with noise)"""
        layer = NoisyLinear(in_features=64, out_features=32)
        layer.train()
        
        x = torch.randn(16, 64)
        out1 = layer(x)
        
        # Reset noise and run again - should get different output
        layer.reset_noise()
        out2 = layer(x)
        
        assert out1.shape == (16, 32)
        assert out2.shape == (16, 32)
        assert not torch.allclose(out1, out2)  # Different due to noise
    
    def test_forward_eval(self):
        """Test forward pass in eval mode (no noise)"""
        layer = NoisyLinear(in_features=64, out_features=32)
        layer.eval()
        
        x = torch.randn(16, 64)
        out1 = layer(x)
        out2 = layer(x)
        
        assert torch.allclose(out1, out2)  # Same output in eval mode


class TestDuelingDQN:
    """Test Dueling DQN architecture"""
    
    def test_initialization(self):
        """Test dueling DQN initialization"""
        dqn = DuelingDQN(input_dim=41, num_actions=2, hidden_dims=[128, 64])
        
        assert dqn.input_dim == 41
        assert dqn.num_actions == 2
    
    def test_forward_pass(self):
        """Test forward pass produces Q-values"""
        dqn = DuelingDQN(input_dim=41, num_actions=2, hidden_dims=[128, 64])
        
        state = torch.randn(32, 41)
        q_values = dqn(state)
        
        assert q_values.shape == (32, 2)
        assert not torch.isnan(q_values).any()
    
    def test_reset_noise(self):
        """Test noise reset functionality"""
        dqn = DuelingDQN(input_dim=41, num_actions=2, use_noisy=True)
        dqn.train()
        
        state = torch.randn(32, 41)
        
        q1 = dqn(state)
        dqn.reset_noise()
        q2 = dqn(state)
        
        # Should be different due to noise reset
        assert not torch.allclose(q1, q2)


class TestDQNSpecialist:
    """Test DQN Specialist wrapper"""
    
    def test_initialization(self):
        """Test specialist initialization"""
        specialist = DQNSpecialist(
            specialist_id=0,
            specialist_name="DoS",
            input_dim=41,
            hidden_dims=[128, 64],
            gamma=0.99,
            n_step=3,
            device='cpu'
        )
        
        assert specialist.specialist_id == 0
        assert specialist.specialist_name == "DoS"
        assert specialist.gamma == 0.99
        assert specialist.n_step == 3
    
    def test_select_action(self):
        """Test action selection"""
        specialist = DQNSpecialist(
            specialist_id=0,
            specialist_name="DoS",
            device='cpu'
        )
        
        state = torch.randn(41)
        action = specialist.select_action(state)
        
        assert action in [0, 1]  # Binary action
    
    def test_compute_q_values(self):
        """Test Q-value computation"""
        specialist = DQNSpecialist(
            specialist_id=0,
            specialist_name="DoS",
            device='cpu'
        )
        
        states = torch.randn(32, 41)
        q_values = specialist.compute_q_values(states)
        
        assert q_values.shape == (32, 2)
    
    def test_compute_loss(self):
        """Test loss computation"""
        specialist = DQNSpecialist(
            specialist_id=0,
            specialist_name="DoS",
            device='cpu'
        )
        
        batch_size = 32
        states = torch.randn(batch_size, 41)
        actions = torch.randint(0, 2, (batch_size,))
        rewards = torch.randn(batch_size)
        next_states = torch.randn(batch_size, 41)
        dones = torch.zeros(batch_size)
        
        loss, td_errors, info = specialist.compute_loss(
            states, actions, rewards, next_states, dones
        )
        
        assert isinstance(loss, torch.Tensor)
        assert loss.dim() == 0  # Scalar
        assert td_errors.shape == (batch_size,)
        assert 'loss' in info
        assert 'mean_q' in info
    
    def test_target_network_update(self):
        """Test target network update"""
        specialist = DQNSpecialist(
            specialist_id=0,
            specialist_name="DoS",
            device='cpu',
            use_noisy=False  # Disable noise for deterministic test
        )
        
        # Put networks in eval mode for deterministic behavior
        specialist.online_net.eval()
        specialist.target_net.eval()
        
        state = torch.randn(1, 41)
        
        with torch.no_grad():
            q_online_before = specialist.online_net(state)
            q_target_before = specialist.target_net(state)
        
        # Update target network
        specialist.update_target_network()
        
        with torch.no_grad():
            q_online_after = specialist.online_net(state)
            q_target_after = specialist.target_net(state)
        
        # Online should be same, target should now match online
        assert torch.allclose(q_online_before, q_online_after)
        assert torch.allclose(q_online_after, q_target_after)


class TestNStepReturns:
    """Test N-step return computation"""
    
    def test_compute_n_step_returns(self):
        """Test N-step return calculation"""
        rewards = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        dones = np.array([0, 0, 0, 0, 1])
        
        n_step_returns = compute_n_step_returns(rewards, dones, gamma=0.9, n=3)
        
        assert n_step_returns.shape == rewards.shape
        assert n_step_returns.dtype == np.float32
        
        # First return should be sum of first 3 rewards (discounted)
        expected_first = 1.0 + 0.9 * 2.0 + 0.9**2 * 3.0
        assert abs(n_step_returns[0] - expected_first) < 1e-5


class TestFactoryFunctions:
    """Test factory functions"""
    
    def test_create_a3c_model(self):
        """Test A3C model factory"""
        model = create_a3c_model(
            input_dim=41,
            num_specialists=18,
            hidden_dims=[128, 64],
            device='cpu'
        )
        
        assert isinstance(model, A3CRouter)
        assert model.input_dim == 41
        assert model.num_specialists == 18
    
    def test_create_specialists(self):
        """Test specialist factory"""
        specialist_names = ['DoS', 'DDoS', 'PortScan']
        
        specialists = create_specialists(
            num_specialists=3,
            specialist_names=specialist_names,
            input_dim=41,
            device='cpu'
        )
        
        assert len(specialists) == 3
        assert 0 in specialists
        assert 1 in specialists
        assert 2 in specialists
        
        assert specialists[0].specialist_name == 'DoS'
        assert specialists[1].specialist_name == 'DDoS'
        assert specialists[2].specialist_name == 'PortScan'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
