"""
Role-Based Access Control (RBAC) for Adaptive IDS
Provides role definitions, permission checks, and authorization decorators
"""

import logging
from enum import Enum
from functools import wraps
from typing import Dict, List, Set

from flask import jsonify, request

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles in the system"""
    ADMIN = 'admin'
    ANALYST = 'analyst'
    VIEWER = 'viewer'
    AUDITOR = 'auditor'


class Permission(str, Enum):
    """System permissions"""
    # Alert permissions
    VIEW_ALERTS = 'view_alerts'
    CREATE_ALERTS = 'create_alerts'
    UPDATE_ALERTS = 'update_alerts'
    DELETE_ALERTS = 'delete_alerts'
    ACK_ALERTS = 'ack_alerts'
    MARK_FALSE_POSITIVE = 'mark_false_positive'
    
    # Incident permissions
    VIEW_INCIDENTS = 'view_incidents'
    CREATE_INCIDENTS = 'create_incidents'
    UPDATE_INCIDENTS = 'update_incidents'
    DELETE_INCIDENTS = 'delete_incidents'
    
    # Model permissions
    VIEW_MODELS = 'view_models'
    DEPLOY_MODELS = 'deploy_models'
    TRAIN_MODELS = 'train_models'
    
    # User management
    VIEW_USERS = 'view_users'
    CREATE_USERS = 'create_users'
    UPDATE_USERS = 'update_users'
    DELETE_USERS = 'delete_users'
    
    # System configuration
    VIEW_CONFIG = 'view_config'
    UPDATE_CONFIG = 'update_config'
    
    # Audit logs
    VIEW_AUDIT_LOGS = 'view_audit_logs'
    
    # Integration management
    MANAGE_INTEGRATIONS = 'manage_integrations'


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Full access to everything
        Permission.VIEW_ALERTS,
        Permission.CREATE_ALERTS,
        Permission.UPDATE_ALERTS,
        Permission.DELETE_ALERTS,
        Permission.ACK_ALERTS,
        Permission.MARK_FALSE_POSITIVE,
        Permission.VIEW_INCIDENTS,
        Permission.CREATE_INCIDENTS,
        Permission.UPDATE_INCIDENTS,
        Permission.DELETE_INCIDENTS,
        Permission.VIEW_MODELS,
        Permission.DEPLOY_MODELS,
        Permission.TRAIN_MODELS,
        Permission.VIEW_USERS,
        Permission.CREATE_USERS,
        Permission.UPDATE_USERS,
        Permission.DELETE_USERS,
        Permission.VIEW_CONFIG,
        Permission.UPDATE_CONFIG,
        Permission.VIEW_AUDIT_LOGS,
        Permission.MANAGE_INTEGRATIONS,
    },
    Role.ANALYST: {
        # Alert and incident management
        Permission.VIEW_ALERTS,
        Permission.UPDATE_ALERTS,
        Permission.ACK_ALERTS,
        Permission.MARK_FALSE_POSITIVE,
        Permission.VIEW_INCIDENTS,
        Permission.CREATE_INCIDENTS,
        Permission.UPDATE_INCIDENTS,
        Permission.VIEW_MODELS,
        Permission.VIEW_CONFIG,
    },
    Role.VIEWER: {
        # Read-only access
        Permission.VIEW_ALERTS,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_MODELS,
        Permission.VIEW_CONFIG,
    },
    Role.AUDITOR: {
        # Audit and compliance access
        Permission.VIEW_ALERTS,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_MODELS,
        Permission.VIEW_CONFIG,
        Permission.VIEW_AUDIT_LOGS,
    },
}


class RBACManager:
    """Manages role-based access control"""
    
    def __init__(self):
        """Initialize RBAC manager"""
        self.role_permissions = ROLE_PERMISSIONS
        logger.info("RBAC Manager initialized")
    
    def has_permission(self, role: str, permission: Permission) -> bool:
        """
        Check if a role has a specific permission
        
        Args:
            role: User role
            permission: Permission to check
        
        Returns:
            True if role has permission
        """
        try:
            role_enum = Role(role)
            return permission in self.role_permissions.get(role_enum, set())
        except ValueError:
            logger.warning(f"Unknown role: {role}")
            return False
    
    def get_role_permissions(self, role: str) -> Set[Permission]:
        """
        Get all permissions for a role
        
        Args:
            role: User role
        
        Returns:
            Set of permissions
        """
        try:
            role_enum = Role(role)
            return self.role_permissions.get(role_enum, set())
        except ValueError:
            return set()
    
    def add_permission_to_role(self, role: Role, permission: Permission):
        """
        Add a permission to a role (for dynamic RBAC)
        
        Args:
            role: Role to modify
            permission: Permission to add
        """
        if role not in self.role_permissions:
            self.role_permissions[role] = set()
        
        self.role_permissions[role].add(permission)
        logger.info(f"Added permission '{permission}' to role '{role}'")
    
    def remove_permission_from_role(self, role: Role, permission: Permission):
        """
        Remove a permission from a role
        
        Args:
            role: Role to modify
            permission: Permission to remove
        """
        if role in self.role_permissions:
            self.role_permissions[role].discard(permission)
            logger.info(f"Removed permission '{permission}' from role '{role}'")


# Global RBAC manager instance
_rbac_manager = RBACManager()


def get_rbac_manager() -> RBACManager:
    """Get the global RBAC manager instance"""
    return _rbac_manager


def require_role(*allowed_roles: str):
    """
    Decorator to require specific role(s) for a route
    
    Args:
        allowed_roles: One or more allowed roles
    
    Usage:
        @app.route('/api/admin/endpoint')
        @require_auth
        @require_role('admin')
        def admin_endpoint(user_id: int):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user_id from kwargs (added by require_auth decorator)
            user_id = kwargs.get('user_id')
            
            if not user_id:
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Authentication required'
                }), 401
            
            # Get user role from database
            from ..api.auth import get_db_cursor
            
            try:
                with get_db_cursor() as cur:
                    cur.execute(
                        "SELECT role FROM users WHERE id = %s",
                        (user_id,)
                    )
                    row = cur.fetchone()
                    
                    if not row:
                        return jsonify({
                            'error': 'unauthorized',
                            'message': 'User not found'
                        }), 401
                    
                    user_role = row['role']
                    
                    # Check if user has required role
                    if user_role not in allowed_roles:
                        logger.warning(
                            f"Access denied: user_id={user_id}, "
                            f"role={user_role}, required={allowed_roles}"
                        )
                        return jsonify({
                            'error': 'forbidden',
                            'message': 'Insufficient permissions'
                        }), 403
                    
                    # Add role to kwargs
                    kwargs['user_role'] = user_role
                    return f(*args, **kwargs)
            
            except Exception as e:
                logger.error(f"Error checking user role: {e}")
                return jsonify({
                    'error': 'internal_error',
                    'message': 'Failed to verify permissions'
                }), 500
        
        return decorated_function
    return decorator


def require_permission(*required_permissions: Permission):
    """
    Decorator to require specific permission(s) for a route
    
    Args:
        required_permissions: One or more required permissions
    
    Usage:
        @app.route('/api/alerts/<alert_id>/ack')
        @require_auth
        @require_permission(Permission.ACK_ALERTS)
        def ack_alert(user_id: int, alert_id: str):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user_id from kwargs (added by require_auth decorator)
            user_id = kwargs.get('user_id')
            
            if not user_id:
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Authentication required'
                }), 401
            
            # Get user role from database
            from ..api.auth import get_db_cursor
            
            try:
                with get_db_cursor() as cur:
                    cur.execute(
                        "SELECT role FROM users WHERE id = %s",
                        (user_id,)
                    )
                    row = cur.fetchone()
                    
                    if not row:
                        return jsonify({
                            'error': 'unauthorized',
                            'message': 'User not found'
                        }), 401
                    
                    user_role = row['role']
                    
                    # Check permissions
                    manager = get_rbac_manager()
                    for permission in required_permissions:
                        if not manager.has_permission(user_role, permission):
                            logger.warning(
                                f"Permission denied: user_id={user_id}, "
                                f"role={user_role}, required={permission}"
                            )
                            return jsonify({
                                'error': 'forbidden',
                                'message': f'Missing required permission: {permission.value}'
                            }), 403
                    
                    # Add role to kwargs
                    kwargs['user_role'] = user_role
                    return f(*args, **kwargs)
            
            except Exception as e:
                logger.error(f"Error checking permissions: {e}")
                return jsonify({
                    'error': 'internal_error',
                    'message': 'Failed to verify permissions'
                }), 500
        
        return decorated_function
    return decorator
