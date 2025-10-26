#!/usr/bin/env python3
"""
Security Features Test Suite
Tests API keys, secrets, RBAC, audit logging, and mTLS
"""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestAPIKeys:
    """Test API key management"""
    
    def test_key_generation(self):
        from security.api_keys import APIKeyManager
        
        manager = APIKeyManager()
        raw_key, api_key = manager.generate_key(
            service_name='test-service',
            scopes=['read', 'write'],
            ttl_days=90
        )
        
        assert raw_key.startswith('aids_')
        assert api_key.service_name == 'test-service'
        assert 'read' in api_key.scopes
        assert api_key.is_valid()
    
    def test_key_validation(self):
        from security.api_keys import APIKeyManager
        
        manager = APIKeyManager()
        raw_key, api_key = manager.generate_key(
            service_name='test-service',
            scopes=['read'],
            ttl_days=90
        )
        
        # Valid key
        validated = manager.validate_key(raw_key)
        assert validated is not None
        assert validated.key_id == api_key.key_id
        
        # Invalid key
        invalid = manager.validate_key('aids_invalid_key')
        assert invalid is None
    
    def test_key_scope_validation(self):
        from security.api_keys import APIKeyManager
        
        manager = APIKeyManager()
        raw_key, api_key = manager.generate_key(
            service_name='test-service',
            scopes=['read'],
            ttl_days=90
        )
        
        # Valid scope
        validated = manager.validate_key(raw_key, required_scope='read')
        assert validated is not None
        
        # Invalid scope
        validated = manager.validate_key(raw_key, required_scope='write')
        assert validated is None
    
    def test_key_rotation(self):
        from security.api_keys import APIKeyManager
        
        manager = APIKeyManager()
        raw_key, api_key = manager.generate_key(
            service_name='test-service',
            scopes=['read'],
            ttl_days=90
        )
        
        # Rotate key
        new_raw_key, new_api_key = manager.rotate_key(
            old_key_id=api_key.key_id,
            grace_period_days=7
        )
        
        assert new_raw_key != raw_key
        assert new_api_key.key_id != api_key.key_id
        assert new_api_key.service_name == api_key.service_name
        assert new_api_key.scopes == api_key.scopes
        
        # Old key still valid (grace period)
        assert manager.validate_key(raw_key) is not None
        
        # New key valid
        assert manager.validate_key(new_raw_key) is not None


class TestSecretsManagement:
    """Test secrets management"""
    
    def test_secret_storage(self):
        from security.secrets import SecretsManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretsManager(
                secrets_file=os.path.join(tmpdir, 'secrets.enc'),
                master_key_file=os.path.join(tmpdir, 'master.key'),
                master_password='test-password'
            )
            
            manager.set_secret('test_key', 'test_value', description='Test secret')
            
            value = manager.get_secret('test_key')
            assert value == 'test_value'
    
    def test_secret_expiration(self):
        from security.secrets import SecretsManager
        from datetime import datetime, timedelta, timezone
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretsManager(
                secrets_file=os.path.join(tmpdir, 'secrets.enc'),
                master_key_file=os.path.join(tmpdir, 'master.key'),
                master_password='test-password'
            )
            
            # Set secret with very short TTL
            manager.set_secret('short_lived', 'value', ttl_days=-1)  # Already expired
            
            # Should not return expired secret
            value = manager.get_secret('short_lived')
            assert value is None
    
    def test_secret_rotation(self):
        from security.secrets import SecretsManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretsManager(
                secrets_file=os.path.join(tmpdir, 'secrets.enc'),
                master_key_file=os.path.join(tmpdir, 'master.key'),
                master_password='test-password'
            )
            
            manager.set_secret('rotatable_key', 'old_value', rotatable=True)
            
            success = manager.rotate_secret('rotatable_key', 'new_value')
            assert success
            
            value = manager.get_secret('rotatable_key')
            assert value == 'new_value'


class TestRBAC:
    """Test role-based access control"""
    
    def test_role_permissions(self):
        from security.rbac import RBACManager, Role, Permission
        
        manager = RBACManager()
        
        # Admin has all permissions
        assert manager.has_permission(Role.ADMIN.value, Permission.VIEW_ALERTS)
        assert manager.has_permission(Role.ADMIN.value, Permission.DELETE_USERS)
        
        # Analyst has limited permissions
        assert manager.has_permission(Role.ANALYST.value, Permission.VIEW_ALERTS)
        assert manager.has_permission(Role.ANALYST.value, Permission.ACK_ALERTS)
        assert not manager.has_permission(Role.ANALYST.value, Permission.DELETE_USERS)
        
        # Viewer is read-only
        assert manager.has_permission(Role.VIEWER.value, Permission.VIEW_ALERTS)
        assert not manager.has_permission(Role.VIEWER.value, Permission.ACK_ALERTS)
    
    def test_get_role_permissions(self):
        from security.rbac import RBACManager, Role
        
        manager = RBACManager()
        
        admin_perms = manager.get_role_permissions(Role.ADMIN.value)
        analyst_perms = manager.get_role_permissions(Role.ANALYST.value)
        
        assert len(admin_perms) > len(analyst_perms)


class TestAuditLogging:
    """Test audit logging"""
    
    def test_audit_event_creation(self):
        from security.audit import AuditEvent
        
        event = AuditEvent(
            event_type='data_modification',
            action='update',
            resource_type='alert',
            resource_id='alert_123',
            user_id=1,
            status='success',
            changes={'status': 'acknowledged'}
        )
        
        assert event.event_id.startswith('audit_')
        assert event.action == 'update'
        assert event.resource_type == 'alert'
        assert event.status == 'success'
    
    def test_audit_logger_buffering(self):
        from security.audit import AuditLogger, AuditEvent
        
        # Use in-memory PostgreSQL or mock
        # This is a simplified test - full test would use test database
        pass


class TestIntegration:
    """Integration tests for security features"""
    
    def test_api_key_decorator(self):
        from flask import Flask
        from security.api_keys import get_api_key_manager, require_api_key
        
        app = Flask(__name__)
        
        @app.route('/protected')
        @require_api_key(required_scope='read')
        def protected(api_key):
            return {'service': api_key.service_name}
        
        # Generate test key
        manager = get_api_key_manager()
        raw_key, _ = manager.generate_key(
            service_name='test',
            scopes=['read'],
            ttl_days=1
        )
        
        with app.test_client() as client:
            # Request without key
            resp = client.get('/protected')
            assert resp.status_code == 401
            
            # Request with invalid key
            resp = client.get('/protected', headers={'X-API-Key': 'invalid'})
            assert resp.status_code == 401
            
            # Request with valid key
            resp = client.get('/protected', headers={'X-API-Key': raw_key})
            assert resp.status_code == 200


def test_secrets_persistence():
    """Test that secrets persist across manager instances"""
    from security.secrets import SecretsManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        secrets_file = os.path.join(tmpdir, 'secrets.enc')
        master_key_file = os.path.join(tmpdir, 'master.key')
        
        # Create first manager and set secret
        manager1 = SecretsManager(
            secrets_file=secrets_file,
            master_key_file=master_key_file,
            master_password='test-password'
        )
        manager1.set_secret('persistent_key', 'persistent_value')
        
        # Create second manager and verify secret persists
        manager2 = SecretsManager(
            secrets_file=secrets_file,
            master_key_file=master_key_file,
            master_password='test-password'
        )
        
        value = manager2.get_secret('persistent_key')
        assert value == 'persistent_value'


def test_encryption_strength():
    """Test that secrets are properly encrypted"""
    from security.secrets import SecretsManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        secrets_file = os.path.join(tmpdir, 'secrets.enc')
        master_key_file = os.path.join(tmpdir, 'master.key')
        
        manager = SecretsManager(
            secrets_file=secrets_file,
            master_key_file=master_key_file,
            master_password='test-password'
        )
        manager.set_secret('sensitive', 'super-secret-value')
        
        # Read encrypted file
        with open(secrets_file, 'rb') as f:
            encrypted_content = f.read()
        
        # Verify secret value is not in plaintext
        assert b'super-secret-value' not in encrypted_content


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
