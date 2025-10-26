"""
End-to-end smoke test for production pipeline.

Sends a synthetic packet into the raw.packets topic and verifies that within
~60 seconds an alert is created in Postgres (via feature_extractor -> model -> alerting).

Run:
  python -m backend.tests.verify_production_pipeline
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from confluent_kafka import Producer
import psycopg2

ROOT = Path(__file__).resolve().parents[1]

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
PACKETS_TOPIC = os.getenv("PACKETS_TOPIC", "raw.packets")

DB = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", "55432")),
    "dbname": os.getenv("POSTGRES_DB", "adaptive_ids"),
    "user": os.getenv("POSTGRES_USER", "adaptive_ids"),
    "password": os.getenv("POSTGRES_PASSWORD", "adaptive_ids_password"),
}


def get_alert_count_for_src(src_ip: str) -> int:
    conn = psycopg2.connect(**DB)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE src_ip = %s OR description ILIKE %s
                """,
                (src_ip, f"%{src_ip}%"),
            )
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def produce_packet(src_ip: str, dst_ip: str = "10.0.0.1", src_port: int = 54321, dst_port: int = 80, proto: str = "TCP") -> None:
    payload = {
        "ts": time.time(),
        "raw_len": 1500,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": dst_port,
        "proto": proto,
    }
    key = f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{proto}"

    producer = Producer({
        "bootstrap.servers": KAFKA_BROKERS,
        "compression.type": "lz4",
    })
    producer.produce(PACKETS_TOPIC, key=key.encode(), value=json.dumps(payload).encode())
    producer.flush()


def main() -> None:
    test_src = "192.0.2.123"  # RFC 5737 TEST-NET-1; safe synthetic src

    before = get_alert_count_for_src(test_src)
    print(f"Existing alerts for src {test_src}: {before}")

    print("Producing synthetic packet to raw.packets...")
    produce_packet(test_src)

    print("Waiting up to 90s for pipeline (feature aggregation + inference + alerting)...")
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(5)
        after = get_alert_count_for_src(test_src)
        if after > before:
            print(f"SUCCESS: Alert count increased from {before} to {after}")
            return

    raise SystemExit("FAIL: No new alert detected for test packet within 90s")


if __name__ == "__main__":
    main()
