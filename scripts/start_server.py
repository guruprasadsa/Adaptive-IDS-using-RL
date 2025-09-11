#!/usr/bin/env python3
"""
Server startup script for Adaptive IDS

This script provides a command-line interface for starting the Adaptive IDS API server.
"""

import argparse
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adaptive_ids.api.app import create_app


def main():
    """Main entry point for the server script."""
    parser = argparse.ArgumentParser(description='Start Adaptive IDS API Server')
    
    # Server arguments
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port to bind the server to')
    parser.add_argument('--debug', action='store_true',
                       help='Run in debug mode')
    
    # Model arguments
    parser.add_argument('--model-checkpoint', type=str, default=None,
                       help='Path to model checkpoint file')
    
    args = parser.parse_args()
    
    # Set environment variable for model checkpoint if provided
    if args.model_checkpoint:
        os.environ['MODEL_CHECKPOINT'] = args.model_checkpoint
    
    # Create and run the app
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
