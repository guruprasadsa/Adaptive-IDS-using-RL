"""
API package for Adaptive IDS

Contains Flask API endpoints and utilities.
"""

from .app import create_app
from .routes import api_bp

__all__ = ["create_app", "api_bp"]
