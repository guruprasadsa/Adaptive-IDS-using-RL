"""
backend/api/middleware.py
Middleware for request/response processing, compression, and rate limiting
"""

import logging
import os
import time
from functools import wraps
from typing import Any, Callable

from flask import Request, Response, g, jsonify, request

logger = logging.getLogger(__name__)


class RequestLogger:
    """Middleware for logging API requests and responses"""

    @staticmethod
    def log_request():
        """Log incoming request details"""
        g.start_time = time.time()
        
        if os.getenv('FLASK_DEBUG') == 'True':
            logger.info(
                f"Request: {request.method} {request.path} "
                f"from {request.remote_addr}"
            )

    @staticmethod
    def log_response(response: Response) -> Response:
        """Log response details with timing"""
        if hasattr(g, 'start_time'):
            duration = (time.time() - g.start_time) * 1000  # Convert to ms
            
            if os.getenv('FLASK_DEBUG') == 'True':
                logger.info(
                    f"Response: {request.method} {request.path} "
                    f"Status: {response.status_code} "
                    f"Duration: {duration:.2f}ms"
                )
            
            # Add timing header
            response.headers['X-Response-Time'] = f"{duration:.2f}ms"
        
        return response


class ErrorHandler:
    """Centralized error handling middleware"""

    @staticmethod
    def handle_404(error):
        """Handle 404 errors"""
        return jsonify({
            'error': 'not_found',
            'message': 'The requested resource was not found',
            'path': request.path
        }), 404

    @staticmethod
    def handle_405(error):
        """Handle method not allowed errors"""
        return jsonify({
            'error': 'method_not_allowed',
            'message': f'Method {request.method} is not allowed for this endpoint',
            'allowed_methods': error.valid_methods if hasattr(error, 'valid_methods') else None
        }), 405

    @staticmethod
    def handle_500(error):
        """Handle internal server errors"""
        logger.exception(f"Internal server error: {error}")
        return jsonify({
            'error': 'internal_server_error',
            'message': 'An unexpected error occurred'
        }), 500

    @staticmethod
    def handle_exception(error):
        """Handle uncaught exceptions"""
        logger.exception(f"Unhandled exception: {error}")
        return jsonify({
            'error': 'internal_server_error',
            'message': 'An unexpected error occurred'
        }), 500


def setup_error_handlers(app):
    """Register error handlers with Flask app"""
    app.register_error_handler(404, ErrorHandler.handle_404)
    app.register_error_handler(405, ErrorHandler.handle_405)
    app.register_error_handler(500, ErrorHandler.handle_500)
    app.register_error_handler(Exception, ErrorHandler.handle_exception)


def setup_request_logging(app):
    """Register request logging middleware"""
    app.before_request(RequestLogger.log_request)
    app.after_request(RequestLogger.log_response)


def validate_json(required_fields: list = None):
    """
    Decorator to validate JSON request body
    
    Args:
        required_fields: List of required field names
    
    Usage:
        @app.route('/api/endpoint', methods=['POST'])
        @validate_json(['field1', 'field2'])
        def endpoint():
            data = request.get_json()
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    'error': 'validation_error',
                    'message': 'Request must be JSON'
                }), 400
            
            try:
                data = request.get_json()
            except Exception:
                return jsonify({
                    'error': 'validation_error',
                    'message': 'Invalid JSON in request body'
                }), 400
            
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({
                        'error': 'validation_error',
                        'message': f'Missing required fields: {", ".join(missing_fields)}'
                    }), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def cache_control(max_age: int = 0, public: bool = False, private: bool = False):
    """
    Decorator to add cache control headers
    
    Args:
        max_age: Maximum age in seconds
        public: Whether response can be cached by any cache
        private: Whether response should only be cached by browser
    
    Usage:
        @app.route('/api/data')
        @cache_control(max_age=300, public=True)
        def get_data():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)
            
            if isinstance(response, tuple):
                response_obj = response[0]
                if hasattr(response_obj, 'headers'):
                    cache_parts = []
                    if public:
                        cache_parts.append('public')
                    elif private:
                        cache_parts.append('private')
                    if max_age > 0:
                        cache_parts.append(f'max-age={max_age}')
                    else:
                        cache_parts.append('no-cache')
                    
                    response_obj.headers['Cache-Control'] = ', '.join(cache_parts)
                return response
            
            if hasattr(response, 'headers'):
                cache_parts = []
                if public:
                    cache_parts.append('public')
                elif private:
                    cache_parts.append('private')
                if max_age > 0:
                    cache_parts.append(f'max-age={max_age}')
                else:
                    cache_parts.append('no-cache')
                
                response.headers['Cache-Control'] = ', '.join(cache_parts)
            
            return response
        
        return decorated_function
    return decorator


def add_security_headers(response: Response) -> Response:
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def setup_security_headers(app):
    """Register security headers middleware"""
    app.after_request(add_security_headers)
