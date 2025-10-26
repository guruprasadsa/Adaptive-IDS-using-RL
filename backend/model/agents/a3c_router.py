"""
A3C (Asynchronous Advantage Actor-Critic) Router
Learns to select which specialist DQN agent to invoke for a given flow
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.multiprocessing as mp
from torch.distributions import Categorical
import numpy as np
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SharedFeatureExtractor(nn.Module):
    """
    Shared convolutional/dense feature extractor for flow features
    Used by both actor and critic networks
    """
    
    def __init__(self, input_dim: int = 41, hidden_dims: list = [128, 64]):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        
        # Build sequential feature extraction layers
        layers = []
        in_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            in_dim = hidden_dim
        
        self.feature_net = nn.Sequential(*layers)
        self.output_dim = hidden_dims[-1]
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Flow features [batch, input_dim]
        Returns:
            Shared features [batch, output_dim]
        """
        return self.feature_net(x)


class ActorNetwork(nn.Module):
    """
    Policy network that outputs specialist selection probabilities
    """
    
    def __init__(self, feature_dim: int, num_specialists: int):
        super().__init__()
        
        self.feature_dim = feature_dim
        self.num_specialists = num_specialists
        
        # Policy head
        self.policy_head = nn.Sequential(
            nn.Linear(feature_dim, 32),
            nn.ReLU(),
            nn.Linear(32, num_specialists)
        )
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        Args:
            features: Shared features [batch, feature_dim]
        Returns:
            Logits for specialist selection [batch, num_specialists]
        """
        logits = self.policy_head(features)
        return logits


class CriticNetwork(nn.Module):
    """
    Value network that estimates state value V(s)
    """
    
    def __init__(self, feature_dim: int):
        super().__init__()
        
        self.feature_dim = feature_dim
        
        # Value head
        self.value_head = nn.Sequential(
            nn.Linear(feature_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        Args:
            features: Shared features [batch, feature_dim]
        Returns:
            State values [batch, 1]
        """
        value = self.value_head(features)
        return value


class A3CRouter(nn.Module):
    """
    Complete A3C model combining shared features, actor, and critic
    """
    
    def __init__(
        self,
        input_dim: int = 41,
        num_specialists: int = 18,
        hidden_dims: list = [128, 64],
        entropy_coef: float = 0.01
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.num_specialists = num_specialists
        self.entropy_coef = entropy_coef
        
        # Shared feature extractor
        self.feature_extractor = SharedFeatureExtractor(input_dim, hidden_dims)
        
        # Actor and critic networks
        feature_dim = self.feature_extractor.output_dim
        self.actor = ActorNetwork(feature_dim, num_specialists)
        self.critic = CriticNetwork(feature_dim)
        
        logger.info(
            f"A3CRouter initialized: input_dim={input_dim}, "
            f"num_specialists={num_specialists}, hidden_dims={hidden_dims}"
        )
    
    def forward(
        self,
        state: torch.Tensor,
        action: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass through router
        
        Args:
            state: Flow features [batch, input_dim]
            action: Selected specialist indices [batch] (optional, for training)
        
        Returns:
            action: Selected specialist [batch] (if action not provided)
            log_prob: Log probability of action [batch]
            entropy: Policy entropy [batch]
            value: State value [batch]
        """
        # Extract shared features
        features = self.feature_extractor(state)
        
        # Get policy logits and value
        logits = self.actor(features)
        value = self.critic(features).squeeze(-1)
        
        # Create categorical distribution
        dist = Categorical(logits=logits)
        
        # Sample action if not provided (inference mode)
        if action is None:
            action = dist.sample()
        
        # Compute log probability and entropy
        log_prob = dist.log_prob(action)
        entropy = dist.entropy()
        
        return action, log_prob, entropy, value
    
    def select_specialist(self, state: torch.Tensor) -> int:
        """
        Select specialist for a single flow (inference)
        
        Args:
            state: Flow features [input_dim]
        
        Returns:
            specialist_idx: Index of selected specialist
        """
        with torch.no_grad():
            state = state.unsqueeze(0)  # Add batch dimension
            action, _, _, _ = self.forward(state)
            return action.item()
    
    def get_action_probs(self, state: torch.Tensor) -> torch.Tensor:
        """
        Get action probabilities (for analysis)
        
        Args:
            state: Flow features [batch, input_dim] or [input_dim]
        
        Returns:
            probs: Action probabilities [batch, num_specialists] or [num_specialists]
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)
            squeeze = True
        else:
            squeeze = False
        
        with torch.no_grad():
            features = self.feature_extractor(state)
            logits = self.actor(features)
            probs = F.softmax(logits, dim=-1)
        
        if squeeze:
            probs = probs.squeeze(0)
        
        return probs


class A3CLoss:
    """
    Combined loss for A3C: actor loss + critic loss + entropy bonus
    """
    
    def __init__(
        self,
        actor_coef: float = 1.0,
        critic_coef: float = 0.5,
        entropy_coef: float = 0.01
    ):
        self.actor_coef = actor_coef
        self.critic_coef = critic_coef
        self.entropy_coef = entropy_coef
    
    def compute_loss(
        self,
        log_probs: torch.Tensor,
        advantages: torch.Tensor,
        values: torch.Tensor,
        returns: torch.Tensor,
        entropy: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute A3C loss
        
        Args:
            log_probs: Log probabilities of actions [batch]
            advantages: Advantage estimates [batch]
            values: Value predictions [batch]
            returns: Target returns [batch]
            entropy: Policy entropy [batch]
        
        Returns:
            total_loss: Combined loss
            loss_dict: Dictionary of individual loss components
        """
        # Actor loss (policy gradient with advantage)
        actor_loss = -(log_probs * advantages.detach()).mean()
        
        # Critic loss (MSE between value and return)
        critic_loss = F.mse_loss(values, returns)
        
        # Entropy bonus (encourage exploration)
        entropy_loss = -entropy.mean()
        
        # Combined loss
        total_loss = (
            self.actor_coef * actor_loss +
            self.critic_coef * critic_loss +
            self.entropy_coef * entropy_loss
        )
        
        loss_dict = {
            'total_loss': total_loss.item(),
            'actor_loss': actor_loss.item(),
            'critic_loss': critic_loss.item(),
            'entropy': -entropy_loss.item(),
            'mean_value': values.mean().item(),
            'mean_advantage': advantages.mean().item()
        }
        
        return total_loss, loss_dict
    
    def compute_advantages(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        next_values: torch.Tensor,
        dones: torch.Tensor,
        gamma: float = 0.99,
        gae_lambda: float = 0.95
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute advantages using Generalized Advantage Estimation (GAE)
        
        Args:
            rewards: Rewards [batch]
            values: Value estimates [batch]
            next_values: Next state values [batch]
            dones: Done flags [batch]
            gamma: Discount factor
            gae_lambda: GAE lambda parameter
        
        Returns:
            advantages: Computed advantages [batch]
            returns: Computed returns [batch]
        """
        batch_size = rewards.size(0)
        advantages = torch.zeros_like(rewards)
        returns = torch.zeros_like(rewards)
        
        # Compute TD errors
        td_errors = rewards + gamma * next_values * (1 - dones) - values
        
        # Compute GAE advantages
        gae = 0
        for t in reversed(range(batch_size)):
            gae = td_errors[t] + gamma * gae_lambda * (1 - dones[t]) * gae
            advantages[t] = gae
        
        # Compute returns
        returns = advantages + values
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return advantages, returns


class A3CWorker(mp.Process):
    """
    Asynchronous worker for distributed A3C training
    Each worker has its own environment and local model
    """
    
    def __init__(
        self,
        worker_id: int,
        global_model: A3CRouter,
        optimizer: torch.optim.Optimizer,
        data_loader,
        num_epochs: int,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        device: str = 'cpu'
    ):
        super().__init__()
        
        self.worker_id = worker_id
        self.global_model = global_model
        self.optimizer = optimizer
        self.data_loader = data_loader
        self.num_epochs = num_epochs
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.device = device
        
        # Local model (copy of global)
        self.local_model = A3CRouter(
            input_dim=global_model.input_dim,
            num_specialists=global_model.num_specialists,
            hidden_dims=[128, 64],
            entropy_coef=global_model.entropy_coef
        ).to(device)
        
        # Loss computer
        self.loss_fn = A3CLoss(
            actor_coef=1.0,
            critic_coef=0.5,
            entropy_coef=global_model.entropy_coef
        )
        
        logger.info(f"A3C Worker {worker_id} initialized")
    
    def run(self):
        """Main training loop for worker"""
        logger.info(f"Worker {self.worker_id} starting training")
        
        for epoch in range(self.num_epochs):
            # Sync local model with global
            self.local_model.load_state_dict(self.global_model.state_dict())
            
            for batch_idx, (states, labels) in enumerate(self.data_loader):
                states = states.to(self.device)
                labels = labels.to(self.device)
                
                # Forward pass
                actions, log_probs, entropy, values = self.local_model(states)
                
                # Compute next values (for GAE)
                with torch.no_grad():
                    # Simulate next state (for now, use same state)
                    # In real implementation, this would come from trajectory
                    _, _, _, next_values = self.local_model(states)
                
                # Dummy rewards (based on specialist correctness)
                # In real implementation, this comes from specialist feedback
                rewards = (actions == labels).float()
                dones = torch.ones_like(rewards)  # Episodic
                
                # Compute advantages and returns
                advantages, returns = self.loss_fn.compute_advantages(
                    rewards, values, next_values, dones, self.gamma, self.gae_lambda
                )
                
                # Compute loss
                loss, loss_dict = self.loss_fn.compute_loss(
                    log_probs, advantages, values, returns, entropy
                )
                
                # Backward pass (on local model)
                self.optimizer.zero_grad()
                loss.backward()
                
                # Clip gradients
                torch.nn.utils.clip_grad_norm_(self.local_model.parameters(), 40.0)
                
                # Update global model
                for global_param, local_param in zip(
                    self.global_model.parameters(),
                    self.local_model.parameters()
                ):
                    if global_param.grad is None:
                        global_param.grad = local_param.grad.clone()
                    else:
                        global_param.grad += local_param.grad
                
                # Optimizer step on global model
                self.optimizer.step()
                
                if batch_idx % 10 == 0:
                    logger.info(
                        f"Worker {self.worker_id} Epoch {epoch} Batch {batch_idx}: "
                        f"Loss={loss_dict['total_loss']:.4f}"
                    )
        
        logger.info(f"Worker {self.worker_id} finished training")


def create_a3c_model(
    input_dim: int = 41,
    num_specialists: int = 18,
    hidden_dims: list = None,
    entropy_coef: float = 0.01,
    device: str = 'cpu'
) -> A3CRouter:
    """
    Factory function to create A3C router model
    
    Args:
        input_dim: Input feature dimension
        num_specialists: Number of specialist agents
        hidden_dims: Hidden layer dimensions
        entropy_coef: Entropy regularization coefficient
        device: Device to place model on
    
    Returns:
        model: A3CRouter model
    """
    if hidden_dims is None:
        hidden_dims = [128, 64]
    
    model = A3CRouter(
        input_dim=input_dim,
        num_specialists=num_specialists,
        hidden_dims=hidden_dims,
        entropy_coef=entropy_coef
    ).to(device)
    
    # Share memory for multiprocessing
    model.share_memory()
    
    logger.info(f"Created A3C model with {sum(p.numel() for p in model.parameters())} parameters")
    
    return model
