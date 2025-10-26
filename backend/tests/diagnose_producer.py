"""
Quick diagnostic for packet producer issues
"""
import os
import subprocess
import sys

print("=" * 60)
print("Packet Producer Diagnostics")
print("=" * 60)

# Check if running in venv
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("✓ Running in virtual environment")
else:
    print("✗ NOT running in virtual environment")
    print("  Run: .venv\\Scripts\\activate")

# Check environment
from dotenv import load_dotenv
load_dotenv('backend/.env')

kafka_brokers = os.getenv('KAFKA_BROKERS')
packets_topic = os.getenv('PACKETS_TOPIC')
pcap_iface = os.getenv('PCAP_IFACE')

print(f"\nEnvironment Variables:")
print(f"  KAFKA_BROKERS: {kafka_brokers}")
print(f"  PACKETS_TOPIC: {packets_topic}")
print(f"  PCAP_IFACE: {pcap_iface}")

# Test Kafka connection
print(f"\nTesting Kafka connection to {kafka_brokers}...")
try:
    from confluent_kafka import Producer
    conf = {'bootstrap.servers': kafka_brokers}
    producer = Producer(conf)
    # Get metadata
    metadata = producer.list_topics(timeout=5)
    print(f"✓ Connected to Kafka")
    print(f"  Broker: {metadata.brokers}")
    if packets_topic in metadata.topics:
        print(f"✓ Topic '{packets_topic}' exists")
        topic_metadata = metadata.topics[packets_topic]
        print(f"  Partitions: {len(topic_metadata.partitions)}")
    else:
        print(f"✗ Topic '{packets_topic}' does NOT exist")
except Exception as e:
    print(f"✗ Kafka connection failed: {e}")

# Check pyshark
print(f"\nChecking pyshark...")
try:
    import pyshark
    print(f"✓ pyshark installed")
except ImportError:
    print(f"✗ pyshark not installed")

# Test tshark
print(f"\nTesting tshark...")
try:
    result = subprocess.run(['tshark', '-v'], capture_output=True, timeout=3)
    if result.returncode == 0:
        print(f"✓ tshark working")
    else:
        print(f"✗ tshark returned error")
except FileNotFoundError:
    print(f"✗ tshark not found in PATH")
except Exception as e:
    print(f"✗ tshark test failed: {e}")

# List interfaces
print(f"\nAvailable interfaces:")
try:
    result = subprocess.run(['tshark', '-D'], capture_output=True, text=True, timeout=3)
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        for line in lines[:10]:  # Show first 10
            print(f"  {line}")
        if pcap_iface:
            print(f"\n  Configured interface: {pcap_iface}")
    else:
        print(f"  Failed to list interfaces")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("If producer is running but not producing messages:")
print("1. Check producer terminal for errors")
print("2. Verify PCAP_IFACE matches an available interface")
print("3. Generate network traffic (ping, browse web)")
print("4. Check if producer needs admin/elevated permissions")
print("=" * 60)
