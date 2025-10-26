"""
Security module for Adaptive IDS
Provides mTLS, API key authentication, secrets management, and audit logging
"""

from .api_keys import APIKeyManager, require_api_key
from .mtls import MTLSManager, verify_client_cert
from .secrets_manager import SecretsManager
from .audit import AuditLogger, audit_log
from .rbac import RBACManager, require_role, require_permission

__all__ = [
    'APIKeyManager',
    'require_api_key',
    'MTLSManager',
    'verify_client_cert',
    'SecretsManager',
    'AuditLogger',
    'audit_log',
    'RBACManager',
    'require_role',
    'require_permission',
]
