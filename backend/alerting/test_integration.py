"""
Integration Test Script
Sends test predictions to Kafka and verifies alerts are created.
"""
import os
import sys
import json
import time
import uuid
from pathlib import Path

from confluent_kafka import Producer, Consumer

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_test_prediction(class_name='DDoS', confidence=0.95):
    """Create a test prediction message."""
    return {
        'flow_id': f'test-flow-{uuid.uuid4()}',
        'timestamp': int(time.time() * 1000),
        'class_idx': 5,
        'class_name': class_name,
        'confidence': confidence,
        'model_version': 'test-v1.0',
        'feature_version': 'test-v1.0',
        'src_ip': f'192.168.1.{100 + int(time.time()) % 155}',
        'dst_ip': '10.0.0.1',
        'src_port': 10000 + int(time.time()) % 55535,
        'dst_port': 80,
        'protocol': 'TCP',
        'schema_version': 1
    }


def send_test_prediction(kafka_brokers='localhost:9092', topic='predictions'):
    """Send a test prediction to Kafka."""
    producer_config = {
        'bootstrap.servers': kafka_brokers,
        'acks': 'all',
    }
    
    producer = Producer(producer_config)
    
    # Create test predictions
    test_cases = [
        ('DDoS', 0.95, 'HIGH severity - should create alert'),
        ('PortScan', 0.6, 'LOW severity - should create alert'),
        ('Normal', 0.9, 'INFO severity - should be suppressed'),
        ('Web Attack – Sql Injection', 0.7, 'MEDIUM severity - should create alert'),
        ('Infiltration', 0.8, 'CRITICAL severity - should create alert'),
        ('DDoS', 0.4, 'Below confidence threshold - should be suppressed'),
    ]
    
    print("=" * 60)
    print("Sending Test Predictions to Kafka")
    print("=" * 60)
    
    for class_name, confidence, description in test_cases:
        prediction = create_test_prediction(class_name, confidence)
        
        print(f"\n[{time.strftime('%H:%M:%S')}] Sending: {description}")
        print(f"  Class: {class_name}, Confidence: {confidence:.2f}")
        print(f"  Flow ID: {prediction['flow_id']}")
        
        producer.produce(
            topic,
            key=prediction['flow_id'].encode('utf-8'),
            value=json.dumps(prediction).encode('utf-8'),
            callback=lambda err, msg: print(f"  ✓ Delivered to {msg.topic()}") if not err else print(f"  ✗ Error: {err}")
        )
        
        time.sleep(0.5)  # Small delay between messages
    
    # Flush and wait
    print(f"\nFlushing producer...")
    producer.flush(timeout=10)
    
    print(f"\n✓ All test predictions sent successfully!")
    print(f"\nNext steps:")
    print(f"1. Check alerting service logs: docker compose logs alerting-service")
    print(f"2. Query alerts table:")
    print(f"   SELECT alert_id, severity, class_name, confidence, src_ip")
    print(f"   FROM alerts")
    print(f"   WHERE created_at > NOW() - INTERVAL '5 minutes'")
    print(f"   ORDER BY created_at DESC;")
    print(f"3. Check DLQ topic if any failures: kafka-console-consumer --topic alerts.dlq")


def verify_alerts(pg_dsn=None):
    """Verify alerts were created in database."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed. Skipping database verification.")
        return
    
    if pg_dsn is None:
        pg_dsn = os.getenv(
            'PG_DSN',
            'host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
        )
    
    print("\n" + "=" * 60)
    print("Verifying Alerts in Database")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(pg_dsn)
        cursor = conn.cursor()
        
        # Query recent alerts
        query = """
            SELECT 
                alert_id,
                severity,
                class_name,
                confidence,
                src_ip,
                dst_ip,
                created_at
            FROM alerts
            WHERE created_at > NOW() - INTERVAL '5 minutes'
            ORDER BY created_at DESC
            LIMIT 20
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if rows:
            print(f"\n✓ Found {len(rows)} recent alerts:\n")
            print(f"{'Alert ID':<40} {'Severity':<10} {'Class':<30} {'Confidence':<12} {'Source IP':<15}")
            print("-" * 120)
            
            for row in rows:
                alert_id, severity, class_name, confidence, src_ip, dst_ip, created_at = row
                print(f"{alert_id:<40} {severity:<10} {class_name:<30} {confidence:<12.2%} {src_ip:<15}")
        else:
            print("\n⚠ No recent alerts found in database.")
            print("Possible reasons:")
            print("  1. Alerting service is not running")
            print("  2. Predictions did not meet severity/confidence thresholds")
            print("  3. Alerts were suppressed by filters")
        
        # Query alert statistics
        cursor.execute("""
            SELECT severity, COUNT(*) as count
            FROM alerts
            WHERE created_at > NOW() - INTERVAL '1 hour'
            GROUP BY severity
            ORDER BY 
                CASE severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    WHEN 'LOW' THEN 4
                    WHEN 'INFO' THEN 5
                END
        """)
        
        stats = cursor.fetchall()
        if stats:
            print(f"\n📊 Alert Statistics (Last Hour):")
            for severity, count in stats:
                print(f"  {severity:<10} {count:>5} alerts")
        
        cursor.close()
        conn.close()
        
        print("\n✓ Database verification complete")
    
    except Exception as e:
        print(f"\n✗ Database verification failed: {e}")
        print("Make sure PostgreSQL is running and accessible.")


def check_dlq(kafka_brokers='localhost:9092', topic='alerts.dlq'):
    """Check for messages in DLQ."""
    print("\n" + "=" * 60)
    print("Checking Dead Letter Queue")
    print("=" * 60)
    
    consumer_config = {
        'bootstrap.servers': kafka_brokers,
        'group.id': f'dlq-check-{uuid.uuid4()}',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
    }
    
    consumer = Consumer(consumer_config)
    
    try:
        # Get topic metadata
        metadata = consumer.list_topics(topic=topic, timeout=5)
        
        if topic not in metadata.topics:
            print(f"\n✓ DLQ topic '{topic}' does not exist (no failures yet)")
            return
        
        consumer.subscribe([topic])
        
        messages = []
        print(f"\nPolling DLQ for messages (timeout: 5s)...")
        
        start_time = time.time()
        while time.time() - start_time < 5:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                continue
            
            try:
                dlq_msg = json.loads(msg.value().decode('utf-8'))
                messages.append(dlq_msg)
            except Exception as e:
                print(f"  ⚠ Failed to parse DLQ message: {e}")
        
        if messages:
            print(f"\n⚠ Found {len(messages)} failed deliveries in DLQ:\n")
            for i, dlq_msg in enumerate(messages, 1):
                print(f"{i}. Destination: {dlq_msg.get('destination')}")
                print(f"   Error: {dlq_msg.get('error', {}).get('message')}")
                print(f"   Retry Count: {dlq_msg.get('retry_count')}")
                print(f"   Timestamp: {dlq_msg.get('timestamp')}")
                print()
        else:
            print(f"\n✓ No messages in DLQ (all deliveries successful)")
    
    except Exception as e:
        print(f"\n✗ DLQ check failed: {e}")
    finally:
        consumer.close()


def main():
    """Main test function."""
    print("""
╔════════════════════════════════════════════════════════════╗
║   Adaptive IDS - Alerting Pipeline Integration Test       ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
    
    print(f"Configuration:")
    print(f"  Kafka Brokers: {kafka_brokers}")
    print(f"  Predictions Topic: predictions")
    print(f"  DLQ Topic: alerts.dlq")
    
    # Step 1: Send test predictions
    try:
        send_test_prediction(kafka_brokers)
    except Exception as e:
        print(f"\n✗ Failed to send predictions: {e}")
        print("Make sure Kafka is running: docker compose up -d kafka")
        return
    
    # Wait for processing
    print(f"\n⏳ Waiting 5 seconds for alerts to be processed...")
    time.sleep(5)
    
    # Step 2: Verify alerts in database
    verify_alerts()
    
    # Step 3: Check DLQ
    check_dlq(kafka_brokers)
    
    print("\n" + "=" * 60)
    print("✓ Integration test complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
