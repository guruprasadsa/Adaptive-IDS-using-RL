"""
Novelty Detection Module

Detects unknown attack patterns that don't fit existing specialist agents
using one-class classification methods.
"""

from .detector import NoveltyDetector, NoveltyResult
from .autoencoder import AutoencoderDetector
from .isolation_forest import IsolationForestDetector

__all__ = [
    'NoveltyDetector',
    'NoveltyResult',
    'AutoencoderDetector',
    'IsolationForestDetector',
]
