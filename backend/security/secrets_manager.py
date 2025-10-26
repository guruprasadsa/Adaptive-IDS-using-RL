"""
Secrets Management for Adaptive IDS
Provides centralized secrets management with rotation support
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class Secret:
    """Represents a secret with metadata"""
    
    def __init__(
        self,
        key: str,
        value: str,
        created_at: datetime,
        expires_at: Optional[datetime] = None,
        rotatable: bool = True,
        description: str = ''
    ):
        self.key = key
        self.value = value
        self.created_at = created_at
        self.expires_at = expires_at
        self.rotatable = rotatable
        self.description = description
    
    def is_expired(self) -> bool:
        """Check if secret is expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without value)"""
        return {
            'key': self.key,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'rotatable': self.rotatable,
            'description': self.description,
            'is_expired': self.is_expired()
        }


class SecretsManager:
    """Manages encrypted secrets with rotation support"""
    
    def __init__(
        self,
        secrets_file: str = 'secrets.enc',
        master_key_file: str = 'master.key',
        master_password: Optional[str] = None
    ):
        """
        Initialize secrets manager
        
        Args:
            secrets_file: Path to encrypted secrets file
            master_key_file: Path to master key file
            master_password: Optional master password for key derivation
        """
        self.secrets_file = Path(secrets_file)
        self.master_key_file = Path(master_key_file)
        self.master_password = master_password or os.getenv('SECRETS_MASTER_PASSWORD')
        
        # Initialize encryption
        self.cipher = self._init_cipher()
        
        # Load secrets
        self.secrets: Dict[str, Secret] = {}
        self._load_secrets()
        
        logger.info(f"Secrets Manager initialized: {len(self.secrets)} secrets loaded")
    
    def _init_cipher(self) -> Fernet:
        """Initialize Fernet cipher with master key"""
        # Try to load existing master key
        if self.master_key_file.exists():
            with open(self.master_key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new master key
            if self.master_password:
                # Derive key from password
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'adaptive-ids-salt',  # In production, use random salt
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
            else:
                # Generate random key
                key = Fernet.generate_key()
            
            # Save master key
            self.master_key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.master_key_file, 'wb') as f:
                f.write(key)
            
            # Secure permissions
            os.chmod(self.master_key_file, 0o600)
            
            logger.info("Generated new master key")
        
        return Fernet(key)
    
    def _load_secrets(self):
        """Load secrets from encrypted file"""
        if not self.secrets_file.exists():
            logger.info("No existing secrets file found")
            return
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt
            decrypted_data = self.cipher.decrypt(encrypted_data)
            secrets_data = json.loads(decrypted_data)
            
            # Parse secrets
            for key, data in secrets_data.items():
                self.secrets[key] = Secret(
                    key=key,
                    value=data['value'],
                    created_at=datetime.fromisoformat(data['created_at']),
                    expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
                    rotatable=data.get('rotatable', True),
                    description=data.get('description', '')
                )
            
            logger.info(f"Loaded {len(self.secrets)} secrets from file")
        
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            raise
    
    def _save_secrets(self):
        """Save secrets to encrypted file"""
        try:
            # Prepare data
            secrets_data = {}
            for key, secret in self.secrets.items():
                secrets_data[key] = {
                    'value': secret.value,
                    'created_at': secret.created_at.isoformat(),
                    'expires_at': secret.expires_at.isoformat() if secret.expires_at else None,
                    'rotatable': secret.rotatable,
                    'description': secret.description
                }
            
            # Serialize and encrypt
            json_data = json.dumps(secrets_data, indent=2)
            encrypted_data = self.cipher.encrypt(json_data.encode())
            
            # Save to file
            self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Secure permissions
            os.chmod(self.secrets_file, 0o600)
            
            logger.info(f"Saved {len(self.secrets)} secrets to file")
        
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise
    
    def set_secret(
        self,
        key: str,
        value: str,
        ttl_days: Optional[int] = None,
        rotatable: bool = True,
        description: str = ''
    ):
        """
        Set or update a secret
        
        Args:
            key: Secret key
            value: Secret value
            ttl_days: Optional expiration in days
            rotatable: Whether secret can be rotated
            description: Optional description
        """
        expires_at = None
        if ttl_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        
        secret = Secret(
            key=key,
            value=value,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            rotatable=rotatable,
            description=description
        )
        
        self.secrets[key] = secret
        self._save_secrets()
        
        logger.info(f"Set secret: {key}")
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value
        
        Args:
            key: Secret key
            default: Default value if not found
        
        Returns:
            Secret value or default
        """
        secret = self.secrets.get(key)
        
        if not secret:
            return default
        
        if secret.is_expired():
            logger.warning(f"Secret '{key}' has expired")
            return default
        
        return secret.value
    
    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret
        
        Args:
            key: Secret key
        
        Returns:
            True if deleted, False if not found
        """
        if key in self.secrets:
            del self.secrets[key]
            self._save_secrets()
            logger.info(f"Deleted secret: {key}")
            return True
        
        return False
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate a secret with a new value
        
        Args:
            key: Secret key
            new_value: New secret value
        
        Returns:
            True if rotated, False if not rotatable or not found
        """
        secret = self.secrets.get(key)
        
        if not secret:
            logger.warning(f"Secret '{key}' not found for rotation")
            return False
        
        if not secret.rotatable:
            logger.warning(f"Secret '{key}' is not rotatable")
            return False
        
        # Update secret
        secret.value = new_value
        secret.created_at = datetime.now(timezone.utc)
        
        self._save_secrets()
        
        logger.info(f"Rotated secret: {key}")
        return True
    
    def list_secrets(self) -> Dict[str, Dict[str, Any]]:
        """
        List all secrets (without values)
        
        Returns:
            Dictionary of secret metadata
        """
        return {key: secret.to_dict() for key, secret in self.secrets.items()}
    
    def get_expired_secrets(self) -> list[str]:
        """
        Get list of expired secret keys
        
        Returns:
            List of expired secret keys
        """
        return [key for key, secret in self.secrets.items() if secret.is_expired()]
    
    def cleanup_expired_secrets(self) -> int:
        """
        Remove expired secrets
        
        Returns:
            Number of secrets removed
        """
        expired_keys = self.get_expired_secrets()
        
        for key in expired_keys:
            del self.secrets[key]
        
        if expired_keys:
            self._save_secrets()
            logger.info(f"Cleaned up {len(expired_keys)} expired secrets")
        
        return len(expired_keys)


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def init_secrets_manager(
    secrets_file: str = 'secrets.enc',
    master_key_file: str = 'master.key',
    master_password: Optional[str] = None
):
    """Initialize the global secrets manager"""
    global _secrets_manager
    _secrets_manager = SecretsManager(secrets_file, master_key_file, master_password)


def get_secrets_manager() -> Optional[SecretsManager]:
    """Get the global secrets manager instance"""
    return _secrets_manager


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to get a secret
    
    Args:
        key: Secret key
        default: Default value if not found
    
    Returns:
        Secret value or default
    """
    manager = get_secrets_manager()
    if manager:
        return manager.get_secret(key, default)
    
    # Fallback to environment variable
    return os.getenv(key, default)
