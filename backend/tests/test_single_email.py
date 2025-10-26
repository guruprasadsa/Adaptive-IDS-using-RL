"""Send a single test prediction to trigger email alert."""
import json
import time
from confluent_kafka import Producer

# Create producer
producer = Producer({'bootstrap.servers': 'localhost:9092'})

# Create a HIGH severity alert that should trigger email
test_prediction = {
    'flow_id': 'test-email-single',
    'timestamp': int(time.time() * 1000),
    'class_idx': 5,
    'class_name': 'DDoS',
    'confidence': 0.95,
    'model_version': 'v1.0',
    'feature_version': 'v1.0',
    'src_ip': '192.168.1.100',
    'dst_ip': '10.0.0.1',
    'src_port': 54321,
    'dst_port': 80,
    'protocol': 'TCP'
}

print("Sending HIGH severity DDoS alert...")
print(f"  Class: {test_prediction['class_name']}")
print(f"  Confidence: {test_prediction['confidence']}")
print(f"  Expected Severity: HIGH")
print(f"  Should trigger email: YES\n")

producer.produce(
    'predictions',
    value=json.dumps(test_prediction).encode('utf-8')
)
producer.flush()

print("✓ Sent! Wait 5 seconds and check:")
print("  1. Your email inbox: guruprasadsa8@gmail.com")
print("  2. Service logs: docker compose logs -f alerting-service")
print("  3. Look for: 'Sent email notification'")
