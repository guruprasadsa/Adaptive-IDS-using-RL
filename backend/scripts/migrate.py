"""Development-only seeding script (disabled by default in production)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT_DIR / "scripts" / "mock_data.json"

# Load environment variables from .env file
load_dotenv(ROOT_DIR / ".env")

DEFAULT_DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "55432")),
    "dbname": os.getenv("POSTGRES_DB", "adaptive_ids"),
    "user": os.getenv("POSTGRES_USER", "adaptive_ids"),
    "password": os.getenv("POSTGRES_PASSWORD", "adaptive_ids_password"),
}


def load_mock_data(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("alerts", []), payload.get("incidents", [])


def get_connection():
    return psycopg2.connect(**DEFAULT_DB_CONFIG)


def upsert_alert(cursor, alert: Dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO alerts (alert_id, priority, description, source, timestamp, status, alert_type, confidence)
        VALUES (%(alert_id)s, %(priority)s, %(description)s, %(source)s, %(timestamp)s, %(status)s, %(type)s, %(confidence)s)
        ON CONFLICT (alert_id) DO UPDATE
        SET priority = EXCLUDED.priority,
            description = EXCLUDED.description,
            source = EXCLUDED.source,
            timestamp = EXCLUDED.timestamp,
            status = EXCLUDED.status,
            alert_type = EXCLUDED.alert_type,
            confidence = EXCLUDED.confidence,
            updated_at = NOW();
        """,
        alert,
    )


def upsert_incident(cursor, incident: Dict[str, Any]) -> None:
    record = incident.copy()
    record.setdefault("related_alerts", [])
    cursor.execute(
        """
        INSERT INTO incidents (
            incident_id,
            title,
            status,
            severity,
            assigned_to,
            created_at,
            last_updated_at,
            summary,
            description,
            affected_systems,
            alerts_count,
            related_alerts
        ) VALUES (%(incident_id)s, %(title)s, %(status)s, %(severity)s, %(assigned_to)s,
                  %(created_at)s, %(last_updated_at)s, %(summary)s, %(description)s,
                  %(affected_systems)s, %(alerts_count)s, %(related_alerts)s)
        ON CONFLICT (incident_id) DO UPDATE
        SET status = EXCLUDED.status,
            severity = EXCLUDED.severity,
            assigned_to = EXCLUDED.assigned_to,
            last_updated_at = EXCLUDED.last_updated_at,
            summary = EXCLUDED.summary,
            description = EXCLUDED.description,
            affected_systems = EXCLUDED.affected_systems,
            alerts_count = EXCLUDED.alerts_count,
            related_alerts = EXCLUDED.related_alerts;
        """,
        {**record, "related_alerts": Json(record["related_alerts"])},
    )


def main() -> None:
    # Intentionally no-op in production: mock/demo seed file removed
    if not DATA_FILE.exists():
        print("Seed file not found. Skipping migration (mock/demo data disabled).")
        return

    alerts, incidents = load_mock_data(DATA_FILE)
    if not alerts and not incidents:
        print("No seed records found. Skipping migration.")
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            for alert in alerts:
                upsert_alert(cur, alert)
            for incident in incidents:
                upsert_incident(cur, incident)
        conn.commit()

    print(f"Successfully migrated {len(alerts)} alerts and {len(incidents)} incidents.")


if __name__ == "__main__":
    main()
