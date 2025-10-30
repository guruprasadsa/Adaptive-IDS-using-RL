"""
Multi-Agent IDS Model (Router + Specialists)

Architecture:
- Router: Routes flows to appropriate specialist based on learned policy
- 10 Specialists: Each specialized for detecting a specific attack class
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Tuple
import numpy as np


class DQNSpecialist(nn.Module):
    """
    Dueling DQN specialist for a specific attack class.
    Separates value and advantage streams for better Q-value estimation.
    """
    def __init__(self, input_dim: int, hidden_dims: List[int] = [128, 64]):
        super().__init__()
        
        # Shared feature extraction
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_dim = hidden_dim
        
        self.feature_net = nn.Sequential(*layers)
        
        # Value stream: estimates state value V(s)
        self.value_stream = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.ReLU(),
            nn.Linear(prev_dim // 2, 1)
        )
        
        # Advantage stream: estimates advantage A(s,a) for each action
        # For binary classification: 2 actions (normal, attack)
        self.advantage_stream = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.ReLU(),
            nn.Linear(prev_dim // 2, 2)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through dueling architecture.
        Q(s,a) = V(s) + (A(s,a) - mean(A(s,a')))
        """
        features = self.feature_net(x)
        value = self.value_stream(features)
        advantages = self.advantage_stream(features)
        
        # Combine value and advantage
        q_values = value + (advantages - advantages.mean(dim=1, keepdim=True))
        return q_values


class RouterNetwork(nn.Module):
    """
    Router network that decides which specialist to use for each flow.
    Uses Actor-Critic architecture from A3C.
    """
    def __init__(self, input_dim: int, num_specialists: int, hidden_dims: List[int] = [128, 64]):
        super().__init__()
        
        # Shared feature extractor
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_dim = hidden_dim
        
        self.feature_extractor = nn.Sequential(*layers)
        
        # Actor: routing policy (which specialist to use)
        # Checkpoint has: 64 -> 32 -> num_specialists  
        self.actor = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.ReLU(),
            nn.Linear(prev_dim // 2, num_specialists)
        )
        
        # Critic: value function (how good is the current state)
        # Checkpoint has: 64 -> 32 -> 1
        self.critic = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.ReLU(),
            nn.Linear(prev_dim // 2, 1)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            routing_logits: (batch, num_specialists) - routing decision logits
            value: (batch, 1) - state value estimate
        """
        features = self.feature_extractor(x)
        routing_logits = self.actor(features)
        value = self.critic(features)
        return routing_logits, value


class MultiAgentIDS(nn.Module):
    """
    Complete Multi-Agent IDS:
    1. Router selects specialist
    2. Selected specialist makes attack/benign decision
    3. Combine results into multi-class prediction
    """
    def __init__(
        self, 
        input_dim: int, 
        num_specialists: int = 10,
        specialist_hidden_dims: List[int] = [128, 64],
        router_hidden_dims: List[int] = [128, 64],
        label_classes: List[str] = None
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.num_specialists = num_specialists
        self.label_classes = label_classes or [f"Class_{i}" for i in range(num_specialists)]
        
        # Router network
        self.router = RouterNetwork(input_dim, num_specialists, router_hidden_dims)
        
        # Specialist networks (one per attack class)
        self.specialists = nn.ModuleList([
            DQNSpecialist(input_dim, specialist_hidden_dims)
            for _ in range(num_specialists)
        ])
    
    def forward(self, x: torch.Tensor, use_routing: bool = True) -> torch.Tensor:
        """
        Forward pass through router + specialists.
        
        Args:
            x: Input features (batch, input_dim)
            use_routing: If True, use router to select specialist.
                        If False, run all specialists and aggregate.
        
        Returns:
            class_logits: (batch, num_specialists) - multi-class logits
        """
        batch_size = x.size(0)
        
        if use_routing:
            # Get routing decisions
            routing_logits, _ = self.router(x)
            routing_probs = F.softmax(routing_logits, dim=1)
            
            # Get specialist predictions (binary: benign vs attack)
            specialist_outputs = []
            for specialist in self.specialists:
                q_values = specialist(x)  # (batch, 2) - [benign_q, attack_q]
                # Take attack probability (higher Q-value for attack = more likely)
                attack_prob = F.softmax(q_values, dim=1)[:, 1:2]  # (batch, 1)
                specialist_outputs.append(attack_prob)
            
            # Stack: (batch, num_specialists)
            specialist_probs = torch.cat(specialist_outputs, dim=1)
            
            # Combine routing and specialist confidences
            # class_prob[i] = routing_prob[i] * specialist_attack_prob[i]
            class_probs = routing_probs * specialist_probs
            
            # Convert to logits for compatibility with loss functions
            class_logits = torch.log(class_probs + 1e-8)
            
        else:
            # Run all specialists and aggregate
            specialist_outputs = []
            for specialist in self.specialists:
                q_values = specialist(x)
                attack_logit = q_values[:, 1:2]  # Attack Q-value
                specialist_outputs.append(attack_logit)
            
            class_logits = torch.cat(specialist_outputs, dim=1)
        
        return class_logits
    
    def load_checkpoint(self, checkpoint: Dict):
        """Load from multi-agent checkpoint"""
        # Load router
        router_state = {}
        for key, value in checkpoint['router_state_dict'].items():
            # Map checkpoint keys to model structure
            # Checkpoint: feature_extractor.feature_net.X, actor.policy_head.X, critic.value_head.X
            # Model: feature_extractor.X, actor.X, critic.X
            if key.startswith('feature_extractor.feature_net.'):
                # Keep feature_extractor prefix, remove feature_net
                new_key = key.replace('feature_extractor.feature_net.', 'feature_extractor.')
                router_state[new_key] = value
            elif key.startswith('actor.policy_head.'):
                # Remove policy_head
                new_key = key.replace('actor.policy_head.', 'actor.')
                router_state[new_key] = value
            elif key.startswith('critic.value_head.'):
                # Remove value_head
                new_key = key.replace('critic.value_head.', 'critic.')
                router_state[new_key] = value
        
        self.router.load_state_dict(router_state, strict=True)
        
        # Load specialists
        specialist_states = checkpoint['specialist_state_dicts']
        for idx, specialist_state in specialist_states.items():
            if idx < self.num_specialists:
                self.specialists[idx].load_state_dict(specialist_state, strict=True)
    
    def predict_with_routing(self, x: torch.Tensor, temperature: float = 3.0) -> Dict[str, torch.Tensor]:
        """
        Make predictions and return routing information.
        
        Args:
            x: Input features tensor
            temperature: Temperature for routing softmax (higher = more exploration)
                        Default 3.0 to encourage diversity (was effectively 1.0)
        
        Returns dict with:
            - class_probs: Final class probabilities
            - routing_probs: Router's specialist selection probabilities
            - specialist_confidences: Each specialist's attack confidence
        """
        # Get routing decisions with temperature scaling
        routing_logits, value = self.router(x)
        
        # Apply temperature to make routing more exploratory
        # Higher temperature = flatter distribution = more diverse routing
        routing_probs = F.softmax(routing_logits / temperature, dim=1)
        
        # Get specialist predictions with temperature scaling
        specialist_confidences = []
        specialist_temp = max(1.5, temperature / 2.0)  # Use milder temperature for specialists
        
        for specialist in self.specialists:
            q_values = specialist(x)
            # Apply temperature to specialist Q-values too
            attack_prob = F.softmax(q_values / specialist_temp, dim=1)[:, 1]  # Attack probability
            specialist_confidences.append(attack_prob)
        
        specialist_confidences = torch.stack(specialist_confidences, dim=1)
        
        # Combined probabilities
        class_probs = routing_probs * specialist_confidences
        
        # Normalize to sum to 1
        class_probs = class_probs / (class_probs.sum(dim=1, keepdim=True) + 1e-8)
        
        return {
            'class_probs': class_probs,
            'routing_probs': routing_probs,
            'specialist_confidences': specialist_confidences,
            'value_estimate': value
        }


def create_multi_agent_model(checkpoint_path: str, device: str = 'cpu', label_classes: List[str] = None) -> MultiAgentIDS:
    """
    Factory function to create and load multi-agent model from checkpoint.
    
    Args:
        checkpoint_path: Path to saved checkpoint
        device: Device to load model on
        label_classes: Optional list of label class names
        
    Returns:
        Loaded MultiAgentIDS model
    """
    import torch
    
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Infer dimensions from checkpoint
    router_state = checkpoint['router_state_dict']
    first_layer_key = 'feature_extractor.feature_net.0.weight'
    input_dim = router_state[first_layer_key].shape[1]
    
    num_specialists = len(checkpoint['specialist_state_dicts'])
    
    # Use provided labels or defaults
    if label_classes is None:
        label_classes = [f"Class_{i}" for i in range(num_specialists)]
    
    # Create model
    model = MultiAgentIDS(
        input_dim=input_dim,
        num_specialists=num_specialists,
        specialist_hidden_dims=[128, 64],
        router_hidden_dims=[128, 64],
        label_classes=label_classes
    )
    
    # Load weights
    model.load_checkpoint(checkpoint)
    
    # Move to device
    model = model.to(device)
    model.eval()
    
    return model
