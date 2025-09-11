"""
Flask application factory for Adaptive IDS API

This module contains the Flask application factory and configuration
for the Adaptive IDS web API.
"""

import os
import logging
from pathlib import Path
from flask import Flask
from flask_cors import CORS

from .routes import api_bp
from ..models.dqn import DQN_MLP


def create_app(config=None):
    """
    Create and configure the Flask application.
    
    Args:
        config: Configuration object or dictionary
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Configure CORS
    CORS(app)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Resolve important paths
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    PROJECT_ROOT = BASE_DIR
    FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
    DEFAULT_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "best_model.pth"
    
    # Store paths in app config
    app.config.update({
        'PROJECT_ROOT': PROJECT_ROOT,
        'FRONTEND_DIST': FRONTEND_DIST,
        'DEFAULT_CHECKPOINT': DEFAULT_CHECKPOINT,
        'CHECKPOINT_PATHS': [
            PROJECT_ROOT / "checkpoints" / "best_model.pth",
            PROJECT_ROOT / "checkpoints" / "dqn_ids_binary_kaggle_v1" / "best_model.pth",
            PROJECT_ROOT / "runs" / "best_model.pth",
        ]
    })
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Add route to serve frontend
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Serve the frontend application."""
        from flask import send_from_directory, jsonify
        
        dist_dir = app.config['FRONTEND_DIST']
        if path and (dist_dir / path).exists():
            return send_from_directory(str(dist_dir), path)
        else:
            index_file = dist_dir / 'index.html'
            if index_file.exists():
                return send_from_directory(str(dist_dir), 'index.html')
            return jsonify({"error": "Frontend build not found"}), 404
    
    return app


def main():
    """Main entry point for running the Flask application."""
    app = create_app()
    
    # Load model on startup
    logger = logging.getLogger(__name__)
    logger.info("Loading model...")
    
    # Try to load model (this would be implemented in a model service)
    # For now, just log that we're starting
    logger.info("Starting Adaptive IDS API server...")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    main()
