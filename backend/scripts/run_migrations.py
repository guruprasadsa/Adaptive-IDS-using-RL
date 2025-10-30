#!/usr/bin/env python3
"""
Database Migration Runner
Applies SQL migration scripts to the database in order.
"""
import os
import sys
from pathlib import Path
import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def get_db_connection():
    """Get database connection from environment."""
    dsn = os.getenv(
        'PG_DSN',
        'host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
    )
    return psycopg2.connect(dsn)

def create_migrations_table(conn):
    """Create migrations tracking table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                success BOOLEAN NOT NULL DEFAULT TRUE,
                error_message TEXT
            );
        """)
        conn.commit()
    logger.info("Migrations tracking table ready")

def get_applied_migrations(conn):
    """Get list of already applied migrations."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT migration_name FROM schema_migrations 
            WHERE success = TRUE
            ORDER BY applied_at
        """)
        return {row[0] for row in cur.fetchall()}

def apply_migration(conn, migration_file: Path):
    """Apply a single migration file."""
    migration_name = migration_file.name
    
    logger.info(f"Applying migration: {migration_name}")
    
    try:
        # Read migration SQL
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Execute migration
        with conn.cursor() as cur:
            cur.execute(sql)
            
            # Record migration
            cur.execute("""
                INSERT INTO schema_migrations (migration_name, success)
                VALUES (%s, TRUE)
                ON CONFLICT (migration_name) 
                DO UPDATE SET applied_at = NOW(), success = TRUE
            """, (migration_name,))
        
        conn.commit()
        logger.info(f"✅ Migration {migration_name} applied successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration {migration_name} failed: {e}")
        
        # Record failure
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO schema_migrations (migration_name, success, error_message)
                    VALUES (%s, FALSE, %s)
                    ON CONFLICT (migration_name)
                    DO UPDATE SET applied_at = NOW(), success = FALSE, error_message = EXCLUDED.error_message
                """, (migration_name, str(e)))
            conn.commit()
        except Exception:
            pass
        
        return False

def run_migrations(migrations_dir: Path, dry_run: bool = False):
    """Run all pending migrations."""
    # Get all migration files
    migration_files = sorted(migrations_dir.glob('*.sql'))
    migration_files = [f for f in migration_files if not f.name.endswith('_rollback.sql')]
    
    if not migration_files:
        logger.info("No migration files found")
        return
    
    logger.info(f"Found {len(migration_files)} migration files")
    
    # Connect to database
    try:
        conn = get_db_connection()
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    try:
        # Create migrations table
        create_migrations_table(conn)
        
        # Get applied migrations
        applied = get_applied_migrations(conn)
        logger.info(f"Already applied: {len(applied)} migrations")
        
        # Apply pending migrations
        pending = [f for f in migration_files if f.name not in applied]
        
        if not pending:
            logger.info("✅ All migrations are up to date")
            return
        
        logger.info(f"Pending migrations: {len(pending)}")
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            for f in pending:
                logger.info(f"  Would apply: {f.name}")
            return
        
        # Apply each pending migration
        success_count = 0
        for migration_file in pending:
            if apply_migration(conn, migration_file):
                success_count += 1
            else:
                logger.error(f"Migration failed, stopping")
                break
        
        logger.info(f"\n✅ Applied {success_count}/{len(pending)} pending migrations")
        
    finally:
        conn.close()

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run database migrations')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show pending migrations without applying them'
    )
    parser.add_argument(
        '--migrations-dir',
        type=Path,
        default=Path(__file__).parent.parent / 'db' / 'migrations',
        help='Directory containing migration files'
    )
    
    args = parser.parse_args()
    
    if not args.migrations_dir.exists():
        logger.error(f"Migrations directory not found: {args.migrations_dir}")
        sys.exit(1)
    
    logger.info(f"Migrations directory: {args.migrations_dir}")
    
    run_migrations(args.migrations_dir, dry_run=args.dry_run)

if __name__ == '__main__':
    main()

