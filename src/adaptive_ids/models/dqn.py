"""
DQN (Deep Q-Network) model for Adaptive IDS

This module contains the DQN_MLP class which implements a dueling DQN architecture
for intrusion detection using reinforcement learning.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


def kaiming_init(m):
    """Initialize weights using Kaiming normal initialization."""
    if isinstance(m, nn.Linear):
        nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
        if m.bias is not None:
            nn.init.zeros_(m.bias)


class DQN_MLP(nn.Module):
    """
    Dueling DQN MLP network for intrusion detection.
    
    This network uses a dueling architecture that separates the estimation
    of state value and action advantages, which can lead to better learning
    in environments with many similar-valued actions.
    
    Args:
        input_dim (int): Number of input features
        output_dim (int): Number of output actions/classes
        hidden_dims (list): List of hidden layer dimensions
        dropout (float): Dropout rate for regularization
    """
    
    def __init__(self, input_dim, output_dim, hidden_dims=[256, 128], dropout=0.2):
        super().__init__()
        
        # Feature extraction layers
        feature_layers = []
        last_dim = input_dim
        for h_dim in hidden_dims:
            feature_layers.append(nn.Linear(last_dim, h_dim))
            feature_layers.append(nn.BatchNorm1d(h_dim))
            feature_layers.append(nn.ReLU())
            feature_layers.append(nn.Dropout(dropout))
            last_dim = h_dim
        self.feature_net = nn.Sequential(*feature_layers)

        # Advantage stream - estimates relative advantage of each action
        self.advantage_net = nn.Sequential(
            nn.Linear(last_dim, last_dim // 2),
            nn.ReLU(),
            nn.Linear(last_dim // 2, output_dim)
        )

        # Value stream - estimates the value of the current state
        self.value_net = nn.Sequential(
            nn.Linear(last_dim, last_dim // 2),
            nn.ReLU(),
            nn.Linear(last_dim // 2, 1)
        )
        
        # Initialize weights
        self.apply(kaiming_init)

    def forward(self, x):
        """
        Forward pass through the network.
        
        Args:
            x (torch.Tensor): Input tensor of shape (batch_size, input_dim)
                             or (batch_size, seq_len, input_dim) for sequence data
                             
        Returns:
            torch.Tensor: Q-values for each action of shape (batch_size, output_dim)
        """
        # Handle sequence data by flattening
        if x.dim() == 3:
            B, S, F = x.shape
            x = x.view(B, S * F)
        
        # Extract features
        features = self.feature_net(x)
        
        # Compute advantage and value
        advantages = self.advantage_net(features)
        value = self.value_net(features)
        
        # Combine value and advantages for Q-values
        # Subtract mean advantage to ensure identifiability
        qvals = value + (advantages - advantages.mean(dim=1, keepdim=True))
        
        return qvals


class ActorCritic(nn.Module):
    """
    Actor-Critic network for A3C algorithm.
    
    This network can be used with LSTM for sequential data processing
    or as a standard feedforward network.
    
    Args:
        input_dim (int): Number of input features
        action_dim (int): Number of possible actions
        hidden_dims (list): List of hidden layer dimensions
        use_lstm (bool): Whether to use LSTM for sequence processing
        seq_len (int): Sequence length for LSTM
        dropout (float): Dropout rate for regularization
    """
    
    def __init__(self, input_dim, action_dim, hidden_dims=[256, 128], 
                 use_lstm=False, seq_len=1, dropout=0.2):
        super().__init__()
        self.use_lstm = use_lstm
        self.seq_len = seq_len
        
        if use_lstm:
            self.feat = nn.Linear(input_dim, hidden_dims[0])
            self.lstm = nn.LSTM(hidden_dims[0], hidden_dims[1], batch_first=True)
            lstm_out = hidden_dims[1]
        else:
            # Standard feedforward layers
            layers = []
            last_dim = input_dim
            for h_dim in hidden_dims:
                layers.append(nn.Linear(last_dim, h_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout))
                last_dim = h_dim
            self.feature_net = nn.Sequential(*layers)
            lstm_out = hidden_dims[-1]
        
        # Actor head - policy network
        self.actor = nn.Sequential(
            nn.Linear(lstm_out, lstm_out // 2),
            nn.ReLU(),
            nn.Linear(lstm_out // 2, action_dim)
        )
        
        # Critic head - value network
        self.critic = nn.Sequential(
            nn.Linear(lstm_out, lstm_out // 2),
            nn.ReLU(),
            nn.Linear(lstm_out // 2, 1)
        )
        
        self.apply(kaiming_init)

    def forward(self, x):
        """
        Forward pass through the Actor-Critic network.
        
        Args:
            x (torch.Tensor): Input tensor
            
        Returns:
            tuple: (action_logits, state_value)
        """
        if self.use_lstm:
            # Process through LSTM
            x = self.feat(x)
            lstm_out, _ = self.lstm(x)
            # Use the last timestep output
            features = lstm_out[:, -1, :]
        else:
            # Process through feedforward network
            features = self.feature_net(x)
        
        # Compute actor and critic outputs
        action_logits = self.actor(features)
        state_value = self.critic(features)
        
        return action_logits, state_value
