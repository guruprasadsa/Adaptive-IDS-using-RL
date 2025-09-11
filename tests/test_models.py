"""
Tests for Adaptive IDS models

This module contains unit tests for the DQN model and related components.
"""

import pytest
import torch
import numpy as np

from adaptive_ids.models.dqn import DQN_MLP, ActorCritic


class TestDQNMLP:
    """Test cases for DQN_MLP model."""
    
    def test_dqn_initialization(self):
        """Test DQN model initialization."""
        model = DQN_MLP(input_dim=10, output_dim=2, hidden_dims=[64, 32])
        
        assert model is not None
        assert hasattr(model, 'feature_net')
        assert hasattr(model, 'advantage_net')
        assert hasattr(model, 'value_net')
    
    def test_dqn_forward_pass(self):
        """Test DQN forward pass."""
        model = DQN_MLP(input_dim=10, output_dim=2, hidden_dims=[64, 32])
        
        # Test with 2D input
        x = torch.randn(32, 10)
        output = model(x)
        
        assert output.shape == (32, 2)
        assert not torch.isnan(output).any()
        assert not torch.isinf(output).any()
    
    def test_dqn_sequence_input(self):
        """Test DQN with sequence input."""
        model = DQN_MLP(input_dim=10, output_dim=2, hidden_dims=[64, 32])
        
        # Test with 3D input (batch, sequence, features)
        x = torch.randn(32, 5, 10)
        output = model(x)
        
        assert output.shape == (32, 2)
        assert not torch.isnan(output).any()
        assert not torch.isinf(output).any()
    
    def test_dqn_different_sizes(self):
        """Test DQN with different input/output sizes."""
        model = DQN_MLP(input_dim=78, output_dim=5, hidden_dims=[256, 128, 64])
        
        x = torch.randn(16, 78)
        output = model(x)
        
        assert output.shape == (16, 5)


class TestActorCritic:
    """Test cases for ActorCritic model."""
    
    def test_actor_critic_initialization(self):
        """Test ActorCritic model initialization."""
        model = ActorCritic(input_dim=10, action_dim=3, hidden_dims=[64, 32])
        
        assert model is not None
        assert hasattr(model, 'feature_net')
        assert hasattr(model, 'actor')
        assert hasattr(model, 'critic')
    
    def test_actor_critic_forward_pass(self):
        """Test ActorCritic forward pass."""
        model = ActorCritic(input_dim=10, action_dim=3, hidden_dims=[64, 32])
        
        x = torch.randn(32, 10)
        action_logits, state_value = model(x)
        
        assert action_logits.shape == (32, 3)
        assert state_value.shape == (32, 1)
        assert not torch.isnan(action_logits).any()
        assert not torch.isnan(state_value).any()
    
    def test_actor_critic_lstm(self):
        """Test ActorCritic with LSTM."""
        model = ActorCritic(
            input_dim=10, 
            action_dim=3, 
            hidden_dims=[64, 32],
            use_lstm=True,
            seq_len=5
        )
        
        x = torch.randn(32, 5, 10)  # (batch, seq, features)
        action_logits, state_value = model(x)
        
        assert action_logits.shape == (32, 3)
        assert state_value.shape == (32, 1)
        assert not torch.isnan(action_logits).any()
        assert not torch.isnan(state_value).any()


class TestModelIntegration:
    """Integration tests for models."""
    
    def test_model_device_consistency(self):
        """Test that models work on different devices."""
        if torch.cuda.is_available():
            device = torch.device('cuda')
            model = DQN_MLP(input_dim=10, output_dim=2).to(device)
            
            x = torch.randn(32, 10, device=device)
            output = model(x)
            
            assert output.device == device
            assert output.shape == (32, 2)
    
    def test_model_gradient_flow(self):
        """Test that gradients flow properly through the model."""
        model = DQN_MLP(input_dim=10, output_dim=2)
        x = torch.randn(32, 10, requires_grad=True)
        
        output = model(x)
        loss = output.sum()
        loss.backward()
        
        # Check that gradients are computed
        assert x.grad is not None
        assert not torch.isnan(x.grad).any()
        
        # Check that model parameters have gradients
        for param in model.parameters():
            if param.requires_grad:
                assert param.grad is not None
                assert not torch.isnan(param.grad).any()


if __name__ == '__main__':
    pytest.main([__file__])
