"""
backend/api/auth.py
JWT-based authentication module for Adaptive IDS
Provides user registration, login, logout, token refresh, and user info endpoints
"""

import hashlib
import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Dict, Iterable, Optional, Tuple

import jwt
import psycopg2
from flask import Blueprint, jsonify, request
from flask_bcrypt import Bcrypt
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask-Bcrypt (will be set from app context)
bcrypt = None


def init_bcrypt(app):
    """Initialize bcrypt with Flask app"""
    global bcrypt
    bcrypt = Bcrypt(app)


# Auth blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# Configuration
def _get_config() -> Dict[str, Any]:
    """Get authentication configuration from environment variables"""
    return {
        'JWT_SECRET': os.getenv('JWT_SECRET', 'dev-jwt-secret-change-in-production'),
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'ACCESS_TOKEN_TTL': int(os.getenv('ACCESS_TOKEN_TTL', '900')),  # 15 minutes
        'REFRESH_TOKEN_TTL': int(os.getenv('REFRESH_TOKEN_TTL', '604800')),  # 7 days
        'JWT_ALGORITHM': 'HS256',
        'JWT_LEEWAY': 30,  # 30 seconds clock skew tolerance
    }


def _db_config() -> Dict[str, Any]:
    """Get database configuration"""
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '55432')),
        'dbname': os.getenv('POSTGRES_DB', 'adaptive_ids'),
        'user': os.getenv('POSTGRES_USER', 'adaptive_ids'),
        'password': os.getenv('POSTGRES_PASSWORD', 'adaptive@ids.1234'),
    }


@contextmanager
def get_db_cursor() -> Iterable[RealDictCursor]:
    """Context manager for database connections"""
    connection = psycopg2.connect(**_db_config())
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# Password utilities
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    if bcrypt is None:
        raise RuntimeError("Bcrypt not initialized")
    return bcrypt.generate_password_hash(password).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash"""
    if bcrypt is None:
        raise RuntimeError("Bcrypt not initialized")
    return bcrypt.check_password_hash(password_hash, password)


# Token utilities
def hash_token(token: str) -> str:
    """Hash a refresh token using SHA-256 for storage"""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def jwt_encode(payload: Dict[str, Any], ttl: int) -> str:
    """
    Encode a JWT token with the given payload and TTL
    
    Args:
        payload: Token payload dictionary
        ttl: Time to live in seconds
    
    Returns:
        Encoded JWT token string
    """
    config = _get_config()
    now = datetime.now(timezone.utc)
    payload_with_time = {
        **payload,
        'iat': now,
        'exp': now + timedelta(seconds=ttl),
    }
    return jwt.encode(
        payload_with_time,
        config['JWT_SECRET'],
        algorithm=config['JWT_ALGORITHM']
    )


def jwt_decode(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload or None if invalid/expired
    """
    config = _get_config()
    try:
        payload = jwt.decode(
            token,
            config['JWT_SECRET'],
            algorithms=[config['JWT_ALGORITHM']],
            leeway=config['JWT_LEEWAY']
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


# Validation utilities
def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username format
    
    Returns:
        (is_valid, error_message)
    """
    if len(username) < 3 or len(username) > 64:
        return False, "Username must be between 3 and 64 characters"
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, hyphens, and underscores"
    return True, None


# Authentication decorator
def require_auth(f):
    """
    Decorator to require valid JWT authentication for a route
    Extracts user_id from token and adds it to kwargs
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'unauthorized', 'message': 'Missing authorization header'}), 401
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'error': 'unauthorized', 'message': 'Invalid authorization header format'}), 401
        
        token = parts[1]
        payload = jwt_decode(token)
        
        if not payload:
            return jsonify({'error': 'unauthorized', 'message': 'Invalid or expired token'}), 401
        
        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({'error': 'unauthorized', 'message': 'Invalid token payload'}), 401
        
        # Check if user is active
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    "SELECT is_active FROM users WHERE id = %s",
                    (user_id,)
                )
                row = cur.fetchone()
                if not row or not row['is_active']:
                    return jsonify({'error': 'unauthorized', 'message': 'User account is inactive'}), 401
        except Exception as e:
            logger.error(f"Database error checking user status: {e}")
            return jsonify({'error': 'internal_error'}), 500
        
        # Add user_id to kwargs
        kwargs['user_id'] = user_id
        return f(*args, **kwargs)
    
    return decorated_function


# Auth routes
@auth_bp.route('/register', methods=['POST'])
def register():
    """
    POST /api/auth/register
    Register a new user account
    
    Request JSON:
        {
            "username": "string",
            "email": "string",
            "password": "string"
        }
    
    Response 201:
        {
            "user": {
                "id": int,
                "username": "string",
                "email": "string",
                "role": "string",
                "created_at": "ISO8601"
            }
        }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validate input
        if not username or not email or not password:
            return jsonify({'error': 'validation_error', 'message': 'Username, email, and password are required'}), 400
        
        # Validate username
        is_valid, error = validate_username(username)
        if not is_valid:
            return jsonify({'error': 'validation_error', 'message': error}), 400
        
        # Validate email
        if not validate_email(email):
            return jsonify({'error': 'validation_error', 'message': 'Invalid email format'}), 400
        
        # Validate password
        is_valid, error = validate_password(password)
        if not is_valid:
            return jsonify({'error': 'validation_error', 'message': error}), 400
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert user
        with get_db_cursor() as cur:
            # Check if username or email already exists
            cur.execute(
                "SELECT id FROM users WHERE username = %s OR email = %s",
                (username, email)
            )
            if cur.fetchone():
                return jsonify({'error': 'conflict', 'message': 'Username or email already exists'}), 409
            
            # Insert new user
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id, username, email, role, created_at
                """,
                (username, email, password_hash, 'analyst')
            )
            row = cur.fetchone()
        
        user = {
            'id': row['id'],
            'username': row['username'],
            'email': row['email'],
            'role': row['role'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        }
        
        logger.info(f"New user registered: {username} ({email})")
        return jsonify({'user': user}), 201
    
    except Exception as e:
        logger.exception(f"Registration error: {e}")
        return jsonify({'error': 'internal_error', 'message': 'An error occurred during registration'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    POST /api/auth/login
    Authenticate user and return tokens
    
    Request JSON:
        {
            "email_or_username": "string",
            "password": "string"
        }
    
    Response 200:
        {
            "access_token": "string",
            "refresh_token": "string",
            "user": {
                "id": int,
                "username": "string",
                "email": "string",
                "role": "string"
            }
        }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        
        email_or_username = data.get('email_or_username', '').strip()
        password = data.get('password', '')
        
        if not email_or_username or not password:
            return jsonify({'error': 'validation_error', 'message': 'Email/username and password are required'}), 400
        
        # Find user by email or username
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT id, username, email, password_hash, role, is_active
                FROM users
                WHERE (email = %s OR username = %s) AND is_active = TRUE
                """,
                (email_or_username.lower(), email_or_username)
            )
            user_row = cur.fetchone()
            
            if not user_row:
                return jsonify({'error': 'unauthorized', 'message': 'Invalid credentials'}), 401
            
            # Verify password
            if not verify_password(password, user_row['password_hash']):
                return jsonify({'error': 'unauthorized', 'message': 'Invalid credentials'}), 401
            
            user_id = user_row['id']
            
            # Update last login
            cur.execute(
                "UPDATE users SET last_login = NOW() WHERE id = %s",
                (user_id,)
            )
            
            # Generate tokens
            config = _get_config()
            access_token = jwt_encode({'user_id': user_id}, config['ACCESS_TOKEN_TTL'])
            refresh_token = jwt_encode({'user_id': user_id, 'type': 'refresh'}, config['REFRESH_TOKEN_TTL'])
            
            # Store refresh token hash
            token_hash = hash_token(refresh_token)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=config['REFRESH_TOKEN_TTL'])
            
            cur.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, token_hash, expires_at)
            )
        
        user = {
            'id': user_row['id'],
            'username': user_row['username'],
            'email': user_row['email'],
            'role': user_row['role'],
        }
        
        logger.info(f"User logged in: {user_row['username']}")
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user,
        }), 200
    
    except Exception as e:
        logger.exception(f"Login error: {e}")
        return jsonify({'error': 'internal_error', 'message': 'An error occurred during login'}), 500


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user(user_id: int):
    """
    GET /api/auth/me
    Get current authenticated user information
    
    Headers:
        Authorization: Bearer <access_token>
    
    Response 200:
        {
            "id": int,
            "username": "string",
            "email": "string",
            "role": "string",
            "created_at": "ISO8601",
            "last_login": "ISO8601"
        }
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT id, username, email, role, created_at, last_login
                FROM users
                WHERE id = %s AND is_active = TRUE
                """,
                (user_id,)
            )
            row = cur.fetchone()
            
            if not row:
                return jsonify({'error': 'not_found', 'message': 'User not found'}), 404
        
        user = {
            'id': row['id'],
            'username': row['username'],
            'email': row['email'],
            'role': row['role'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'last_login': row['last_login'].isoformat() if row['last_login'] else None,
        }
        
        return jsonify(user), 200
    
    except Exception as e:
        logger.exception(f"Get current user error: {e}")
        return jsonify({'error': 'internal_error'}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    POST /api/auth/refresh
    Refresh access token using refresh token
    
    Request JSON:
        {
            "refresh_token": "string"
        }
    
    Response 200:
        {
            "access_token": "string"
        }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        refresh_token_str = data.get('refresh_token', '')
        
        if not refresh_token_str:
            return jsonify({'error': 'validation_error', 'message': 'Refresh token is required'}), 400
        
        # Decode refresh token
        payload = jwt_decode(refresh_token_str)
        if not payload or payload.get('type') != 'refresh':
            return jsonify({'error': 'unauthorized', 'message': 'Invalid refresh token'}), 401
        
        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({'error': 'unauthorized', 'message': 'Invalid token payload'}), 401
        
        # Verify refresh token exists and is not revoked
        token_hash = hash_token(refresh_token_str)
        
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT id, expires_at, revoked_at
                FROM refresh_tokens
                WHERE user_id = %s AND token_hash = %s
                """,
                (user_id, token_hash)
            )
            token_row = cur.fetchone()
            
            if not token_row:
                return jsonify({'error': 'unauthorized', 'message': 'Refresh token not found'}), 401
            
            if token_row['revoked_at']:
                return jsonify({'error': 'unauthorized', 'message': 'Refresh token has been revoked'}), 401
            
            # Check if token is expired (double-check)
            if token_row['expires_at'] < datetime.now(timezone.utc):
                return jsonify({'error': 'unauthorized', 'message': 'Refresh token has expired'}), 401
            
            # Check if user is active
            cur.execute(
                "SELECT is_active FROM users WHERE id = %s",
                (user_id,)
            )
            user_row = cur.fetchone()
            if not user_row or not user_row['is_active']:
                return jsonify({'error': 'unauthorized', 'message': 'User account is inactive'}), 401
        
        # Generate new access token
        config = _get_config()
        access_token = jwt_encode({'user_id': user_id}, config['ACCESS_TOKEN_TTL'])
        
        logger.info(f"Access token refreshed for user_id: {user_id}")
        
        return jsonify({'access_token': access_token}), 200
    
    except Exception as e:
        logger.exception(f"Token refresh error: {e}")
        return jsonify({'error': 'internal_error', 'message': 'An error occurred during token refresh'}), 500


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout(user_id: int):
    """
    POST /api/auth/logout
    Logout user and revoke refresh token
    
    Headers:
        Authorization: Bearer <access_token>
    
    Request JSON (optional):
        {
            "refresh_token": "string"
        }
    
    Response 200:
        {
            "ok": true
        }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        refresh_token_str = data.get('refresh_token', '')
        
        # If refresh token provided, revoke it
        if refresh_token_str:
            token_hash = hash_token(refresh_token_str)
            
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = NOW()
                    WHERE user_id = %s AND token_hash = %s AND revoked_at IS NULL
                    """,
                    (user_id, token_hash)
                )
                revoked_count = cur.rowcount
                
                if revoked_count > 0:
                    logger.info(f"Refresh token revoked for user_id: {user_id}")
        
        return jsonify({'ok': True}), 200
    
    except Exception as e:
        logger.exception(f"Logout error: {e}")
        return jsonify({'error': 'internal_error', 'message': 'An error occurred during logout'}), 500
