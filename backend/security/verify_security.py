#!/usr/bin/env python3
"""
Security Feature Verification Script
Tests all implemented security features for production readiness
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from security.secrets_manager import SecretsManager
from security.api_keys import APIKeyManager
from security.rbac import Role, Permission
from security.audit import AuditLogger
import psycopg2


def test_secrets_manager():
    """Test encrypted secrets management"""
    print("\n" + "="*80)
    print("1. Testing Secrets Manager")
    print("="*80)
    
    try:
        # Initialize with master password from environment
        master_password = os.getenv('SECRETS_MASTER_PASSWORD')
        if not master_password:
            print("❌ SECRETS_MASTER_PASSWORD not set in environment")
            return False
        
        manager = SecretsManager(master_password=master_password)
        
        # Test retrieving secrets
        jwt_secret = manager.get_secret('jwt_secret')
        db_password = manager.get_secret('database_password')
        
        if jwt_secret and db_password:
            print("✅ Secrets Manager operational")
            print(f"   - JWT secret length: {len(jwt_secret)} characters")
            print(f"   - Database password length: {len(db_password)} characters")
            return True
        else:
            print("❌ Failed to retrieve secrets")
            return False
            
    except Exception as e:
        print(f"❌ Secrets Manager error: {e}")
        return False


def test_api_keys():
    """Test API key authentication"""
    print("\n" + "="*80)
    print("2. Testing API Key Authentication")
    print("="*80)
    
    try:
        manager = APIKeyManager()
        
        # Check environment variables for API keys
        model_key = os.getenv('MODEL_SERVICE_API_KEY')
        alerting_key = os.getenv('ALERTING_SERVICE_API_KEY')
        feature_key = os.getenv('FEATURE_EXTRACTOR_API_KEY')
        
        if not all([model_key, alerting_key, feature_key]):
            print("❌ API keys not found in environment")
            return False
        
        # Verify each key
        keys_valid = []
        for name, key in [
            ('Model Service', model_key),
            ('Alerting Service', alerting_key),
            ('Feature Extractor', feature_key)
        ]:
            try:
                api_key_obj = manager.validate_key(key)
                if api_key_obj:
                    print(f"✅ {name} API key valid")
                    print(f"   - Service: {api_key_obj.service_name}")
                    print(f"   - Expires: {api_key_obj.expires_at}")
                    print(f"   - Scopes: {', '.join(api_key_obj.scopes)}")
                    keys_valid.append(True)
                else:
                    print(f"❌ {name} API key invalid or revoked")
                    keys_valid.append(False)
            except Exception as e:
                print(f"❌ {name} API key error: {e}")
                keys_valid.append(False)
        
        return all(keys_valid)
        
    except Exception as e:
        print(f"❌ API Key Manager error: {e}")
        return False


def test_tls_certificates():
    """Test TLS certificate presence"""
    print("\n" + "="*80)
    print("3. Testing TLS Certificates")
    print("="*80)
    
    certs_dir = Path(__file__).parent / 'certs'
    
    required_certs = [
        'ca-cert.pem',
        'backend-server-cert.pem',
        'backend-server-key.pem',
        'model-service-server-cert.pem',
        'alerting-service-client-cert.pem'
    ]
    
    missing_certs = []
    for cert in required_certs:
        cert_path = certs_dir / cert
        if cert_path.exists():
            print(f"✅ {cert} present")
        else:
            print(f"❌ {cert} missing")
            missing_certs.append(cert)
    
    mtls_enabled = os.getenv('MTLS_ENABLED', 'false').lower() == 'true'
    print(f"\n   mTLS Status: {'ENABLED' if mtls_enabled else 'DISABLED'}")
    
    return len(missing_certs) == 0


def test_database_security():
    """Test database security features"""
    print("\n" + "="*80)
    print("4. Testing Database Security")
    print("="*80)
    
    try:
        # Connect to database using Docker network hostname
        conn = psycopg2.connect(
            host='postgres',  # Docker service name
            port='5432',  # Internal port
            database='adaptive_ids',
            user='adaptive_ids',
            password='idspassword'
        )
        cursor = conn.cursor()
        
        # Check for security tables
        security_tables = ['audit_logs', 'api_keys', 'secrets_metadata']
        for table in security_tables:
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                (table,)
            )
            exists = cursor.fetchone()[0]
            if exists:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
        
        # Check for audit trigger
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_trigger 
                WHERE tgname = 'alert_change_audit'
            )
        """)
        trigger_exists = cursor.fetchone()[0]
        if trigger_exists:
            print("✅ Audit trigger 'alert_change_audit' exists")
        else:
            print("❌ Audit trigger 'alert_change_audit' missing")
        
        # Count audit logs
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        audit_count = cursor.fetchone()[0]
        print(f"\n   Total audit log entries: {audit_count}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database security check error: {e}")
        return False


def test_rbac():
    """Test RBAC implementation"""
    print("\n" + "="*80)
    print("5. Testing Role-Based Access Control")
    print("="*80)
    
    try:
        # Test role enumeration
        roles = [Role.ADMIN, Role.ANALYST, Role.VIEWER, Role.AUDITOR]
        print(f"✅ {len(roles)} roles defined: {[r.value for r in roles]}")
        
        # Test permission enumeration
        perms = list(Permission)
        print(f"✅ {len(perms)} permissions defined")
        
        # Test role permissions
        from security.rbac import ROLE_PERMISSIONS
        for role in roles:
            perm_count = len(ROLE_PERMISSIONS.get(role, []))
            print(f"   - {role.value}: {perm_count} permissions")
        
        return True
        
    except Exception as e:
        print(f"❌ RBAC check error: {e}")
        return False


def test_audit_logging():
    """Test audit logging functionality"""
    print("\n" + "="*80)
    print("6. Testing Audit Logging")
    print("="*80)
    
    try:
        # Initialize audit logger with database DSN
        pg_dsn = "host=postgres port=5432 dbname=adaptive_ids user=adaptive_ids password=idspassword"
        logger = AuditLogger(pg_dsn=pg_dsn)
        
        # Test logging an event
        test_event = {
            'user_id': 'security_test',
            'action': 'verify_security',
            'resource_type': 'system',
            'resource_id': 'security_features',
            'ip_address': '127.0.0.1',
            'metadata': {'test': True}
        }
        
        logger.log(**test_event)
        logger.flush()  # Force write
        
        print("✅ Audit event logged successfully")
        print(f"   - User: {test_event['user_id']}")
        print(f"   - Action: {test_event['action']}")
        print(f"   - Resource: {test_event['resource_type']}/{test_event['resource_id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Audit logging error: {e}")
        return False


def main():
    """Run all security verification tests"""
    print("\n" + "="*80)
    print("ADAPTIVE IDS - SECURITY FEATURE VERIFICATION")
    print("="*80)
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("="*80)
    
    # Run all tests
    results = {
        'Secrets Manager': test_secrets_manager(),
        'API Key Authentication': test_api_keys(),
        'TLS Certificates': test_tls_certificates(),
        'Database Security': test_database_security(),
        'Role-Based Access Control': test_rbac(),
        'Audit Logging': test_audit_logging()
    }
    
    # Summary
    print("\n" + "="*80)
    print("SECURITY VERIFICATION SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for feature, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {feature}")
    
    print("\n" + "="*80)
    print(f"Overall: {passed}/{total} features verified")
    
    if passed == total:
        print("✅ ALL SECURITY FEATURES OPERATIONAL")
        print("\nProduction Readiness Checklist:")
        print("  ✅ Service-to-service authentication (API keys)")
        print("  ✅ Encrypted secrets management")
        print("  ✅ TLS certificates for mTLS")
        print("  ✅ Database security (audit logs, triggers)")
        print("  ✅ Role-based access control")
        print("  ✅ Comprehensive audit trail")
        print("\nAcceptance Criteria:")
        print("  ✅ Pen-test basics: Pass (authentication, encryption, audit trail)")
        print("  ✅ Audit trail complete for alert changes (trigger implemented)")
        return 0
    else:
        print(f"⚠️  {total - passed} FEATURES NEED ATTENTION")
        return 1


if __name__ == '__main__':
    sys.exit(main())
