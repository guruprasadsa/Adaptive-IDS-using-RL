"""
DQN (Deep Q-Network) Specialist Agents
One specialist per attack category using Dueling Double DQN with NoisyNets
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict, Optional
import logging
import math

logger = logging.getLogger(__name__)


def focal_loss(q_values: torch.Tensor, actions: torch.Tensor, gamma: float = 2.0, alpha: float = 0.25) -> torch.Tensor:
    """
    Focal Loss for imbalanced classification
    Focuses learning on hard-to-classify examples
    
    Args:
        q_values: [batch_size, num_actions] - Q-values from network
        actions: [batch_size] - Ground truth actions
        gamma: Focusing parameter (higher = more focus on hard examples)
        alpha: Class balancing parameter
    
    Returns:
        loss: Scalar focal loss
    """
    # Get probabilities using softmax
    probs = F.softmax(q_values, dim=1)
    
    # Get probability of correct class
    correct_probs = probs.gather(1, actions.unsqueeze(1)).squeeze(1)
    
    # Compute focal term: (1 - p_t)^gamma
    focal_weight = (1 - correct_probs) ** gamma
    
    # Compute cross entropy loss
    ce_loss = F.cross_entropy(q_values, actions, reduction='none')
    
    # Apply focal weight and alpha balancing
    focal_loss = alpha * focal_weight * ce_loss
    
    return focal_loss.mean()


class NoisyLinear(nn.Module):
    """
    Noisy linear layer for exploration (NoisyNet)
    Adds learnable parametric noise to weights and biases
    """
    
    def __init__(self, in_features: int, out_features: int, std_init: float = 0.4):
        super().__init__()
        
        self.in_features = in_features
        self.out_features = out_features
        self.std_init = std_init
        
        # Learnable parameters
        self.weight_mu = nn.Parameter(torch.Tensor(out_features, in_features))
        self.weight_sigma = nn.Parameter(torch.Tensor(out_features, in_features))
        self.register_buffer('weight_epsilon', torch.Tensor(out_features, in_features))
        
        self.bias_mu = nn.Parameter(torch.Tensor(out_features))
        self.bias_sigma = nn.Parameter(torch.Tensor(out_features))
        self.register_buffer('bias_epsilon', torch.Tensor(out_features))
        
        self.reset_parameters()
        self.reset_noise()
    
    def reset_parameters(self):
        """Initialize parameters"""
        mu_range = 1 / math.sqrt(self.in_features)
        self.weight_mu.data.uniform_(-mu_range, mu_range)
        self.weight_sigma.data.fill_(self.std_init / math.sqrt(self.in_features))
        
        self.bias_mu.data.uniform_(-mu_range, mu_range)
        self.bias_sigma.data.fill_(self.std_init / math.sqrt(self.out_features))
    
    def reset_noise(self):
        """Reset noise buffers"""
        epsilon_in = self._scale_noise(self.in_features)
        epsilon_out = self._scale_noise(self.out_features)
        
        self.weight_epsilon.copy_(epsilon_out.ger(epsilon_in))
        self.bias_epsilon.copy_(epsilon_out)
    
    def _scale_noise(self, size: int) -> torch.Tensor:
        """Generate scaled noise"""
        x = torch.randn(size)
        return x.sign().mul(x.abs().sqrt())
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass with noisy weights"""
        if self.training:
            weight = self.weight_mu + self.weight_sigma * self.weight_epsilon
            bias = self.bias_mu + self.bias_sigma * self.bias_epsilon
        else:
            weight = self.weight_mu
            bias = self.bias_mu
        
        return F.linear(x, weight, bias)


class DuelingDQN(nn.Module):
    """
    Dueling DQN architecture: separates state value V(s) and advantage A(s,a)
    Q(s,a) = V(s) + (A(s,a) - mean(A(s,a)))
    """
    
    def __init__(
        self,
        input_dim: int = 41,
        num_actions: int = 2,  # Binary classification per specialist
        hidden_dims: list = [128, 64],
        use_noisy: bool = True
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.num_actions = num_actions
        self.use_noisy = use_noisy
        
        # Shared feature extractor
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
        feature_dim = hidden_dims[-1]
        
        # Value stream V(s)
        if use_noisy:
            self.value_stream = nn.Sequential(
                NoisyLinear(feature_dim, 32),
                nn.ReLU(),
                NoisyLinear(32, 1)
            )
        else:
            self.value_stream = nn.Sequential(
                nn.Linear(feature_dim, 32),
                nn.ReLU(),
                nn.Linear(32, 1)
            )
        
        # Advantage stream A(s,a)
        if use_noisy:
            self.advantage_stream = nn.Sequential(
                NoisyLinear(feature_dim, 32),
                nn.ReLU(),
                NoisyLinear(32, num_actions)
            )
        else:
            self.advantage_stream = nn.Sequential(
                nn.Linear(feature_dim, 32),
                nn.ReLU(),
                nn.Linear(32, num_actions)
            )
        
        logger.info(
            f"DuelingDQN initialized: input_dim={input_dim}, "
            f"num_actions={num_actions}, use_noisy={use_noisy}"
        )
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through dueling architecture
        
        Args:
            state: Flow features [batch, input_dim]
        
        Returns:
            q_values: Q-values for each action [batch, num_actions]
        """
        # Extract shared features
        features = self.feature_net(state)
        
        # Compute value and advantage
        value = self.value_stream(features)  # [batch, 1]
        advantage = self.advantage_stream(features)  # [batch, num_actions]
        
        # Combine: Q(s,a) = V(s) + (A(s,a) - mean(A(s,a)))
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        
        return q_values
    
    def reset_noise(self):
        """Reset noise in NoisyNet layers"""
        if self.use_noisy:
            for module in self.modules():
                if isinstance(module, NoisyLinear):
                    module.reset_noise()


class DQNSpecialist:
    """
    Double DQN specialist for binary classification (attack category)
    Uses target network and N-step returns
    """
    
    def __init__(
        self,
        specialist_id: int,
        specialist_name: str,
        input_dim: int = 41,
        hidden_dims: list = None,
        use_noisy: bool = True,
        gamma: float = 0.99,
        n_step: int = 3,
        target_update_freq: int = 100,
        device: str = 'cpu'
    ):
        self.specialist_id = specialist_id
        self.specialist_name = specialist_name
        self.gamma = gamma
        self.n_step = n_step
        self.target_update_freq = target_update_freq
        self.device = device
        self.update_counter = 0
        
        if hidden_dims is None:
            hidden_dims = [128, 64]
        
        # Online and target networks
        self.online_net = DuelingDQN(
            input_dim=input_dim,
            num_actions=2,  # Binary: benign vs attack
            hidden_dims=hidden_dims,
            use_noisy=use_noisy
        ).to(device)
        
        self.target_net = DuelingDQN(
            input_dim=input_dim,
            num_actions=2,
            hidden_dims=hidden_dims,
            use_noisy=use_noisy
        ).to(device)
        
        # Initialize target network with online weights
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()
        
        logger.info(
            f"DQN Specialist '{specialist_name}' (ID={specialist_id}) initialized with "
            f"{sum(p.numel() for p in self.online_net.parameters())} parameters"
        )
    
    def select_action(self, state: torch.Tensor, epsilon: float = 0.0) -> int:
        """
        Select action using epsilon-greedy (for non-noisy networks)
        For NoisyNets, epsilon is ignored (noise provides exploration)
        
        Args:
            state: Flow features [input_dim]
            epsilon: Exploration rate (ignored if using NoisyNets)
        
        Returns:
            action: Selected action (0 or 1)
        """
        with torch.no_grad():
            state = state.unsqueeze(0).to(self.device)
            q_values = self.online_net(state)
            
            if self.online_net.use_noisy or np.random.random() > epsilon:
                action = q_values.argmax(dim=1).item()
            else:
                action = np.random.randint(0, 2)
        
        return action
    
    def compute_q_values(self, state: torch.Tensor) -> torch.Tensor:
        """
        Compute Q-values for given states
        
        Args:
            state: Flow features [batch, input_dim]
        
        Returns:
            q_values: Q-values [batch, 2]
        """
        return self.online_net(state)
    
    def compute_target_q_values(
        self,
        rewards: torch.Tensor,
        next_states: torch.Tensor,
        dones: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute target Q-values using Double DQN
        
        Args:
            rewards: Rewards [batch]
            next_states: Next states [batch, input_dim]
            dones: Done flags [batch]
        
        Returns:
            target_q_values: Target Q-values [batch]
        """
        with torch.no_grad():
            # Double DQN: use online network to select action
            next_q_online = self.online_net(next_states)
            next_actions = next_q_online.argmax(dim=1)
            
            # Use target network to evaluate action
            next_q_target = self.target_net(next_states)
            next_q_values = next_q_target.gather(1, next_actions.unsqueeze(1)).squeeze(1)
            
            # Compute target: r + gamma * Q_target(s', argmax_a Q_online(s', a))
            target_q = rewards + (1 - dones) * (self.gamma ** self.n_step) * next_q_values
        
        return target_q
    
    def compute_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        rewards: torch.Tensor,
        next_states: torch.Tensor,
        dones: torch.Tensor,
        weights: Optional[torch.Tensor] = None,
        class_weight: float = 1.0,
        use_focal_loss: bool = True  # NEW: Enable focal loss for imbalance
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute weighted TD loss for DQN with optional Focal Loss
        
        Args:
            states: Current states [batch, input_dim]
            actions: Actions taken [batch]
            rewards: Rewards [batch]
            next_states: Next states [batch, input_dim]
            dones: Done flags [batch]
            weights: Importance sampling weights [batch] (optional)
            class_weight: Weight for this attack class
            use_focal_loss: Whether to use focal loss (better for imbalance)
        
        Returns:
            loss: Weighted TD loss
            td_errors: TD errors for priority updates
            info: Dictionary with loss statistics
        """
        # Compute current Q-values (full output for focal loss)
        q_values_full = self.online_net(states)
        q_values = q_values_full.gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # Compute target Q-values
        target_q = self.compute_target_q_values(rewards, next_states, dones)
        
        # Compute TD errors (for prioritized replay)
        td_errors = target_q - q_values
        
        # Choose loss function based on use_focal_loss flag
        if use_focal_loss:
            # Use Focal Loss to focus on hard-to-classify samples
            # This helps with extreme imbalance by down-weighting easy examples
            focal_loss_val = focal_loss(
                q_values_full, 
                actions, 
                gamma=2.0,  # Focusing parameter (higher = more focus on hard examples)
                alpha=0.25  # Class balancing
            )
            
            # Combine focal loss with TD error magnitude for better gradient signal
            td_loss = td_errors.pow(2).mean()
            
            # Weighted combination: 30% focal loss (for imbalance) + 70% TD loss (for RL objective)
            # Reduced focal weight to prevent exploding loss values
            loss = 0.3 * focal_loss_val + 0.7 * td_loss
        else:
            # Standard MSE TD loss
            loss = td_errors.pow(2).mean()
        
        # Apply importance sampling weights if provided
        if weights is not None and not use_focal_loss:
            # Note: focal loss already handles weighting, so skip if using focal
            loss = (weights * td_errors.pow(2)).mean()
        
        # Apply class weight
        loss = loss * class_weight
        
        info = {
            'loss': loss.item(),
            'mean_q': q_values.mean().item(),
            'mean_target_q': target_q.mean().item(),
            'mean_td_error': td_errors.abs().mean().item(),
            'max_q': q_values.max().item()
        }
        
        return loss, td_errors.detach(), info
    
    def update_target_network(self):
        """Update target network with online network weights"""
        self.target_net.load_state_dict(self.online_net.state_dict())
        logger.debug(f"Specialist '{self.specialist_name}' target network updated")
    
    def maybe_update_target(self):
        """Update target network if counter threshold reached"""
        self.update_counter += 1
        if self.update_counter % self.target_update_freq == 0:
            self.update_target_network()
    
    def reset_noise(self):
        """Reset noise in NoisyNet layers"""
        self.online_net.reset_noise()
        self.target_net.reset_noise()
    
    def save_checkpoint(self, path: str):
        """Save specialist checkpoint"""
        checkpoint = {
            'specialist_id': self.specialist_id,
            'specialist_name': self.specialist_name,
            'online_net_state_dict': self.online_net.state_dict(),
            'target_net_state_dict': self.target_net.state_dict(),
            'update_counter': self.update_counter
        }
        torch.save(checkpoint, path)
        logger.info(f"Saved specialist '{self.specialist_name}' to {path}")
    
    def load_checkpoint(self, path: str):
        """Load specialist checkpoint"""
        checkpoint = torch.load(path, map_location=self.device)
        self.online_net.load_state_dict(checkpoint['online_net_state_dict'])
        self.target_net.load_state_dict(checkpoint['target_net_state_dict'])
        self.update_counter = checkpoint['update_counter']
        logger.info(f"Loaded specialist '{self.specialist_name}' from {path}")


def compute_n_step_returns(
    rewards: np.ndarray,
    dones: np.ndarray,
    gamma: float = 0.99,
    n: int = 3
) -> np.ndarray:
    """
    Compute N-step returns from reward trajectory
    
    Args:
        rewards: Reward array [T]
        dones: Done flags [T]
        gamma: Discount factor
        n: N-step horizon
    
    Returns:
        n_step_returns: N-step returns [T]
    """
    T = len(rewards)
    n_step_returns = np.zeros(T, dtype=np.float32)
    
    for t in range(T):
        n_step_return = 0.0
        discount = 1.0
        
        for k in range(n):
            if t + k >= T or dones[t + k]:
                break
            n_step_return += discount * rewards[t + k]
            discount *= gamma
        
        n_step_returns[t] = n_step_return
    
    return n_step_returns


def create_specialists(
    num_specialists: int,
    specialist_names: list,
    input_dim: int = 41,
    hidden_dims: list = None,
    use_noisy: bool = True,
    gamma: float = 0.99,
    n_step: int = 3,
    target_update_freq: int = 100,
    device: str = 'cpu'
) -> Dict[int, DQNSpecialist]:
    """
    Factory function to create multiple DQN specialists
    
    Args:
        num_specialists: Number of specialists to create
        specialist_names: List of specialist names (attack categories)
        input_dim: Input feature dimension
        hidden_dims: Hidden layer dimensions
        use_noisy: Use NoisyNets
        gamma: Discount factor
        n_step: N-step horizon
        target_update_freq: Target network update frequency
        device: Device to place models on
    
    Returns:
        specialists: Dictionary mapping specialist ID to DQNSpecialist
    """
    if hidden_dims is None:
        hidden_dims = [128, 64]
    
    specialists = {}
    
    for i in range(num_specialists):
        name = specialist_names[i] if i < len(specialist_names) else f"Specialist_{i}"
        
        specialist = DQNSpecialist(
            specialist_id=i,
            specialist_name=name,
            input_dim=input_dim,
            hidden_dims=hidden_dims,
            use_noisy=use_noisy,
            gamma=gamma,
            n_step=n_step,
            target_update_freq=target_update_freq,
            device=device
        )
        
        specialists[i] = specialist
    
    logger.info(f"Created {num_specialists} DQN specialists")
    
    return specialists
