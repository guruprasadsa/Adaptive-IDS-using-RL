"""
Adaptive Intrusion Detection System

A reinforcement learning-based intrusion detection system that adapts to new threats
and provides real-time network traffic analysis.
"""

__version__ = "1.0.0"
__author__ = "Adaptive IDS Team"
__email__ = "team@adaptive-ids.com"

from .models.dqn import DQN_MLP
from .api.app import create_app

__all__ = ["DQN_MLP", "create_app"]
