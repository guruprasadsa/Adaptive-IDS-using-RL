#!/usr/bin/env python3
"""
Security Setup Script for Adaptive IDS
Initializes API keys, secrets, and performs initial security configuration
"""

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from security.api_keys import get_api_key_manager
from security.secrets_manager import init_secrets_manager, get_secrets_manager
from security.audit import init_audit_logger


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_secrets(master_password: str):
    """Initialize secrets manager and set initial secrets"""
    logger.info("Setting up secrets manager...")
    
    # Initialize secrets manager
    init_secrets_manager(
        secrets_file='backend/security/secrets.enc',
        master_key_file='backend/security/master.key',
        master_password=master_password
    )
    
    manager = get_secrets_manager()
    
    # Prompt for initial secrets
    jwt_secret = getpass.getpass("Enter JWT secret (or press Enter to generate): ")
    if not jwt_secret:
        import secrets as python_secrets
        jwt_secret = python_secrets.token_urlsafe(64)
        logger.info(f"Generated JWT secret: {jwt_secret[:20]}...")
    
    manager.set_secret(
        key='jwt_secret',
        value=jwt_secret,
        ttl_days=365,
        rotatable=True,
        description='JWT signing secret for authentication tokens'
    )
    
    # Database password
    db_password = os.getenv('POSTGRES_PASSWORD', 'adaptive_ids_password')
    manager.set_secret(
        key='database_password',
        value=db_password,
        ttl_days=180,
        rotatable=True,
        description='PostgreSQL database password'
    )
    
    # SMTP password (if configured)
    smtp_password = os.getenv('SMTP_PASSWORD')
    if smtp_password:
        manager.set_secret(
            key='smtp_password',
            value=smtp_password,
            ttl_days=90,
            rotatable=True,
            description='SMTP server password for email alerts'
        )
    
    logger.info("✓ Secrets manager configured successfully")
    logger.info(f"  - Total secrets: {len(manager.list_secrets())}")


def setup_api_keys():
    """Generate initial API keys for services"""
    logger.info("Generating API keys for services...")
    
    manager = get_api_key_manager()
    
    # Model service API key
    model_key, model_api_key = manager.generate_key(
        service_name='model-service',
        scopes=['predictions.write', 'features.read', 'health.read'],
        ttl_days=90
    )
    
    logger.info(f"\n{'='*80}")
    logger.info("Model Service API Key:")
    logger.info(f"  Key: {model_key}")
    logger.info(f"  Key ID: {model_api_key.key_id}")
    logger.info(f"  Scopes: {', '.join(model_api_key.scopes)}")
    logger.info(f"  Expires: {model_api_key.expires_at}")
    logger.info(f"\nAdd to model service .env:")
    logger.info(f"  MODEL_SERVICE_API_KEY={model_key}")
    logger.info(f"{'='*80}\n")
    
    # Alerting service API key
    alert_key, alert_api_key = manager.generate_key(
        service_name='alerting-service',
        scopes=['alerts.write', 'predictions.read', 'health.read'],
        ttl_days=90
    )
    
    logger.info(f"\n{'='*80}")
    logger.info("Alerting Service API Key:")
    logger.info(f"  Key: {alert_key}")
    logger.info(f"  Key ID: {alert_api_key.key_id}")
    logger.info(f"  Scopes: {', '.join(alert_api_key.scopes)}")
    logger.info(f"  Expires: {alert_api_key.expires_at}")
    logger.info(f"\nAdd to alerting service .env:")
    logger.info(f"  ALERTING_SERVICE_API_KEY={alert_key}")
    logger.info(f"{'='*80}\n")
    
    # Feature extractor API key
    feature_key, feature_api_key = manager.generate_key(
        service_name='feature-extractor',
        scopes=['features.write', 'packets.read', 'health.read'],
        ttl_days=90
    )
    
    logger.info(f"\n{'='*80}")
    logger.info("Feature Extractor API Key:")
    logger.info(f"  Key: {feature_key}")
    logger.info(f"  Key ID: {feature_api_key.key_id}")
    logger.info(f"  Scopes: {', '.join(feature_api_key.scopes)}")
    logger.info(f"  Expires: {feature_api_key.expires_at}")
    logger.info(f"\nAdd to feature extractor .env:")
    logger.info(f"  FEATURE_EXTRACTOR_API_KEY={feature_key}")
    logger.info(f"{'='*80}\n")
    
    logger.info("✓ API keys generated successfully")


def setup_audit_logging():
    """Initialize audit logging"""
    logger.info("Setting up audit logging...")
    
    pg_dsn = os.getenv(
        'PG_DSN',
        'host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
    )
    
    audit_log_file = 'logs/audit.log'
    os.makedirs('logs', exist_ok=True)
    
    init_audit_logger(
        pg_dsn=pg_dsn,
        log_file_path=audit_log_file
    )
    
    logger.info("✓ Audit logging configured successfully")
    logger.info(f"  - Database: PostgreSQL")
    logger.info(f"  - Log file: {audit_log_file}")


def apply_database_migration():
    """Apply security database migration"""
    logger.info("Applying database migrations...")
    
    import psycopg2
    
    pg_dsn = os.getenv(
        'PG_DSN',
        'host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
    )
    
    migration_file = Path('backend/db/migrations/002_security_features.sql')
    
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return
    
    try:
        conn = psycopg2.connect(pg_dsn)
        cursor = conn.cursor()
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        cursor.execute(migration_sql)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        logger.info("✓ Database migrations applied successfully")
    
    except Exception as e:
        logger.error(f"Failed to apply migrations: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='Setup security features for Adaptive IDS')
    parser.add_argument(
        '--master-password',
        help='Master password for secrets encryption (will prompt if not provided)'
    )
    parser.add_argument(
        '--skip-secrets',
        action='store_true',
        help='Skip secrets manager setup'
    )
    parser.add_argument(
        '--skip-api-keys',
        action='store_true',
        help='Skip API key generation'
    )
    parser.add_argument(
        '--skip-migration',
        action='store_true',
        help='Skip database migration'
    )
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("Adaptive IDS Security Setup")
    logger.info("="*80)
    logger.info("")
    
    # Get master password
    master_password = args.master_password
    if not master_password and not args.skip_secrets:
        master_password = getpass.getpass("Enter master password for secrets encryption: ")
        confirm_password = getpass.getpass("Confirm master password: ")
        
        if master_password != confirm_password:
            logger.error("Passwords do not match!")
            sys.exit(1)
    
    # Apply database migration
    if not args.skip_migration:
        try:
            apply_database_migration()
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            logger.warning("Continuing with remaining setup...")
    
    # Setup secrets
    if not args.skip_secrets:
        try:
            setup_secrets(master_password)
        except Exception as e:
            logger.error(f"Secrets setup failed: {e}")
            sys.exit(1)
    
    # Setup API keys
    if not args.skip_api_keys:
        try:
            setup_api_keys()
        except Exception as e:
            logger.error(f"API key setup failed: {e}")
            sys.exit(1)
    
    # Setup audit logging
    try:
        setup_audit_logging()
    except Exception as e:
        logger.warning(f"Audit logging setup failed: {e}")
    
    logger.info("\n" + "="*80)
    logger.info("✓ Security setup completed successfully!")
    logger.info("="*80)
    logger.info("\nNext steps:")
    logger.info("  1. Update .env files with generated API keys")
    logger.info("  2. Generate TLS certificates: cd backend/security && ./generate_certs.sh")
    logger.info("  3. Restart services with security features enabled")
    logger.info("  4. Test authentication and authorization")
    logger.info("")


if __name__ == '__main__':
    main()
