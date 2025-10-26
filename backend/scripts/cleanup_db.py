"""Cleanup script for removing development/test data from Postgres.

Removes:
- Alerts with test-like identifiers (alert_id/flow_id starting with 'test_')
- Alerts with obvious demo source IPs like 203.0.113.0/24, 198.51.100.0/24 (RFC docs ranges)
- Non-admin demo users (keeps only username/email containing 'admin')

Usage:
  python backend/scripts/cleanup_db.py

Environment overrides:
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import psycopg2

ROOT = Path(__file__).resolve().parents[1]

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

DB = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", "55432")),
    "dbname": os.getenv("POSTGRES_DB", "adaptive_ids"),
    "user": os.getenv("POSTGRES_USER", "adaptive_ids"),
    "password": os.getenv("POSTGRES_PASSWORD", "adaptive_ids_password"),
}

SQL_STATEMENTS = [
    # Remove alerts with test-like IDs or flows
    """
    DELETE FROM alerts
    WHERE alert_id ILIKE 'test_%' OR flow_id ILIKE 'test_%'
       OR source ILIKE 'test%'
       OR description ILIKE '%demo%';
    """,
    # Remove alerts with documentation-only IP ranges if present
    """
    DELETE FROM alerts
    WHERE src_ip LIKE '203.0.113.%' OR dst_ip LIKE '203.0.113.%'
       OR src_ip LIKE '198.51.100.%' OR dst_ip LIKE '198.51.100.%'
       OR src_ip LIKE '192.0.2.%' OR dst_ip LIKE '192.0.2.%';
    """,
    # Remove demo users (keep any user with username or email containing 'admin')
    """
    DELETE FROM users
    WHERE (username NOT ILIKE '%admin%' AND email NOT ILIKE '%admin%')
      AND id <> 1; -- keep id 1 just in case
    """,
]


def main() -> None:
    print("Connecting to Postgres:", DB)
    conn = psycopg2.connect(**DB)
    try:
        with conn, conn.cursor() as cur:
            total = 0
            for stmt in SQL_STATEMENTS:
                cur.execute(stmt)
                affected = cur.rowcount
                total += affected if affected is not None else 0
                print(f"Executed cleanup stmt, affected={affected}")
        print(f"Cleanup complete. Total rows affected ~ {total} (across multiple tables)")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Cleanup failed:", e)
        sys.exit(1)
