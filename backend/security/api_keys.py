"""
API Key Management for Service-to-Service Authentication
Provides API key generation, validation, and rotation
"""

import hashlib
import logging
import secrets as python_secrets
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, List, Optional, Tuple

from flask import Request, jsonify, request

logger = logging.getLogger(__name__)


class APIKey:
    """Represents an API key with metadata"""
    
    def __init__(
        self,
        key_id: str,
        key_hash: str,
        service_name: str,
        scopes: List[str],
        created_at: datetime,
        expires_at: Optional[datetime] = None,
        is_active: bool = True
    ):
        self.key_id = key_id
        self.key_hash = key_hash
        self.service_name = service_name
        self.scopes = scopes
        self.created_at = created_at
        self.expires_at = expires_at
        self.is_active = is_active
    
    def is_valid(self) -> bool:
        """Check if key is valid and not expired"""
        if not self.is_active:
            return False
        
        if self.expires_at:
            return datetime.now(timezone.utc) < self.expires_at
        
        return True
    
    def has_scope(self, scope: str) -> bool:
        """Check if key has specific scope"""
        return scope in self.scopes or '*' in self.scopes


class APIKeyManager:
    """Manages API keys for service-to-service authentication"""
    
    def __init__(self):
        """Initialize API key manager"""
        # In-memory storage (replace with database in production)
        self.keys: Dict[str, APIKey] = {}
        
        # Metrics
        self.metrics = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'expired_keys': 0,
            'invalid_keys': 0
        }
        
        logger.info("API Key Manager initialized")
    
    def generate_key(
        self,
        service_name: str,
        scopes: List[str],
        ttl_days: Optional[int] = None
    ) -> Tuple[str, APIKey]:
        """
        Generate a new API key
        
        Args:
            service_name: Name of the service
            scopes: List of scopes/permissions
            ttl_days: Optional expiration in days
        
        Returns:
            Tuple of (raw_key, api_key_object)
        """
        # Generate random API key
        raw_key = self._generate_random_key()
        key_id = f"api_key_{int(time.time())}_{python_secrets.token_hex(4)}"
        key_hash = self._hash_key(raw_key)
        
        # Calculate expiration
        expires_at = None
        if ttl_days:
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        
        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            service_name=service_name,
            scopes=scopes,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_active=True
        )
        
        # Store key
        self.keys[key_id] = api_key
        
        logger.info(
            f"Generated API key for service '{service_name}': "
            f"key_id={key_id}, scopes={scopes}, expires_at={expires_at}"
        )
        
        return raw_key, api_key
    
    def _generate_random_key(self) -> str:
        """Generate a random API key"""
        return f"aids_{python_secrets.token_urlsafe(32)}"
    
    def _hash_key(self, raw_key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    
    def validate_key(
        self,
        raw_key: str,
        required_scope: Optional[str] = None
    ) -> Optional[APIKey]:
        """
        Validate an API key
        
        Args:
            raw_key: Raw API key string
            required_scope: Optional scope requirement
        
        Returns:
            APIKey object if valid, None otherwise
        """
        self.metrics['total_validations'] += 1
        
        # Hash the key
        key_hash = self._hash_key(raw_key)
        
        # Find matching key
        for api_key in self.keys.values():
            if api_key.key_hash == key_hash:
                # Check if valid
                if not api_key.is_valid():
                    self.metrics['expired_keys'] += 1
                    logger.warning(
                        f"Expired or inactive API key used: "
                        f"service={api_key.service_name}, key_id={api_key.key_id}"
                    )
                    return None
                
                # Check scope if required
                if required_scope and not api_key.has_scope(required_scope):
                    logger.warning(
                        f"API key missing required scope '{required_scope}': "
                        f"service={api_key.service_name}, key_id={api_key.key_id}"
                    )
                    return None
                
                self.metrics['successful_validations'] += 1
                return api_key
        
        # Key not found
        self.metrics['invalid_keys'] += 1
        logger.warning("Invalid API key attempted")
        return None
    
    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key
        
        Args:
            key_id: Key ID to revoke
        
        Returns:
            True if revoked, False if not found
        """
        if key_id in self.keys:
            self.keys[key_id].is_active = False
            logger.info(f"Revoked API key: {key_id}")
            return True
        
        return False
    
    def rotate_key(
        self,
        old_key_id: str,
        grace_period_days: int = 7
    ) -> Optional[Tuple[str, APIKey]]:
        """
        Rotate an API key with grace period
        
        Args:
            old_key_id: Key ID to rotate
            grace_period_days: Days to keep old key active
        
        Returns:
            Tuple of (new_raw_key, new_api_key) if successful, None otherwise
        """
        if old_key_id not in self.keys:
            return None
        
        old_key = self.keys[old_key_id]
        
        # Generate new key with same properties
        new_raw_key, new_api_key = self.generate_key(
            service_name=old_key.service_name,
            scopes=old_key.scopes,
            ttl_days=None  # New key doesn't expire
        )
        
        # Set expiration on old key
        from datetime import timedelta
        old_key.expires_at = datetime.now(timezone.utc) + timedelta(days=grace_period_days)
        
        logger.info(
            f"Rotated API key for service '{old_key.service_name}': "
            f"old_key_id={old_key_id}, new_key_id={new_api_key.key_id}, "
            f"grace_period={grace_period_days} days"
        )
        
        return new_raw_key, new_api_key
    
    def list_keys(self, service_name: Optional[str] = None) -> List[APIKey]:
        """
        List API keys, optionally filtered by service
        
        Args:
            service_name: Optional service name filter
        
        Returns:
            List of APIKey objects
        """
        keys = list(self.keys.values())
        
        if service_name:
            keys = [k for k in keys if k.service_name == service_name]
        
        return keys
    
    def cleanup_expired_keys(self) -> int:
        """
        Remove expired keys from storage
        
        Returns:
            Number of keys cleaned up
        """
        now = datetime.now(timezone.utc)
        expired_keys = [
            key_id for key_id, key in self.keys.items()
            if key.expires_at and key.expires_at < now
        ]
        
        for key_id in expired_keys:
            del self.keys[key_id]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired API keys")
        
        return len(expired_keys)


# Global API key manager instance
_api_key_manager = APIKeyManager()


def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance"""
    return _api_key_manager


def require_api_key(required_scope: Optional[str] = None):
    """
    Decorator to require valid API key for a route
    
    Args:
        required_scope: Optional scope requirement
    
    Usage:
        @app.route('/api/internal/endpoint')
        @require_api_key(required_scope='model-service')
        def endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get API key from header
            api_key_header = request.headers.get('X-API-Key')
            
            if not api_key_header:
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Missing X-API-Key header'
                }), 401
            
            # Validate key
            manager = get_api_key_manager()
            api_key = manager.validate_key(api_key_header, required_scope)
            
            if not api_key:
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Invalid or expired API key'
                }), 401
            
            # Add API key info to kwargs
            kwargs['api_key'] = api_key
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
