"""
Test script for pcap_producer.py
Validates producer functionality without requiring live capture.
"""

import os
import sys
import json
from unittest.mock import Mock, MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensors.pcap_producer import PacketCaptureProducer


def test_producer_initialization():
    """Test that producer can be initialized with config."""
    print("Testing producer initialization...")
    
    producer = PacketCaptureProducer(
        kafka_brokers="localhost:9092",
        topic="test.packets",
        interface="eth0",
        bpf_filter="tcp port 80"
    )
    
    assert producer.kafka_brokers == "localhost:9092"
    assert producer.topic == "test.packets"
    assert producer.interface == "eth0"
    assert producer.bpf_filter == "tcp port 80"
    assert producer.packets_captured == 0
    assert producer.packets_produced == 0
    
    print("✓ Producer initialization successful")


def test_packet_metadata_extraction():
    """Test packet metadata extraction logic."""
    print("\nTesting packet metadata extraction...")
    
    producer = PacketCaptureProducer(
        kafka_brokers="localhost:9092",
        topic="test.packets"
    )
    
    # Mock a TCP packet
    mock_packet = Mock()
    mock_packet.sniff_timestamp = "1729468800.123456"
    mock_packet.length = "1500"
    mock_packet.ip = Mock()
    mock_packet.ip.src = "192.168.1.100"
    mock_packet.ip.dst = "10.0.0.50"
    mock_packet.transport_layer = "TCP"
    mock_packet.tcp = Mock()
    mock_packet.tcp.srcport = "54321"
    mock_packet.tcp.dstport = "80"
    
    metadata = producer._extract_packet_metadata(mock_packet)
    
    assert metadata is not None
    assert metadata['ts'] == 1729468800.123456
    assert metadata['src_ip'] == "192.168.1.100"
    assert metadata['dst_ip'] == "10.0.0.50"
    assert metadata['src_port'] == 54321
    assert metadata['dst_port'] == 80
    assert metadata['proto'] == "TCP"
    assert metadata['raw_len'] == 1500
    
    print("✓ TCP packet metadata extraction successful")
    print(f"  Metadata: {json.dumps(metadata, indent=2)}")
    
    # Mock a UDP packet
    mock_packet2 = Mock()
    mock_packet2.sniff_timestamp = "1729468801.234567"
    mock_packet2.length = "512"
    mock_packet2.ip = Mock()
    mock_packet2.ip.src = "192.168.1.101"
    mock_packet2.ip.dst = "8.8.8.8"
    mock_packet2.transport_layer = "UDP"
    
    # Need to check if tcp exists (returns False)
    def mock_hasattr(obj, attr):
        if attr == 'tcp':
            return False
        elif attr == 'udp':
            return True
        elif attr == 'ip':
            return True
        elif attr == 'ipv6':
            return False
        return object.__getattribute__(obj, attr) is not None
    
    # Create UDP mock properly
    with patch('builtins.hasattr', side_effect=mock_hasattr):
        mock_packet2.udp = Mock()
        mock_packet2.udp.srcport = "12345"
        mock_packet2.udp.dstport = "53"
        
        metadata2 = producer._extract_packet_metadata(mock_packet2)
    
    metadata2 = producer._extract_packet_metadata(mock_packet2)
    
    assert metadata2 is not None
    assert metadata2['proto'] == "UDP"
    assert metadata2['dst_port'] == 53  # DNS
    
    print("✓ UDP packet metadata extraction successful")
    print(f"  Metadata: {json.dumps(metadata2, indent=2)}")


def test_produce_packet_logic():
    """Test packet production logic (without actual Kafka)."""
    print("\nTesting packet production logic...")
    
    producer = PacketCaptureProducer(
        kafka_brokers="localhost:9092",
        topic="test.packets"
    )
    
    metadata = {
        'ts': 1729468800.123456,
        'src_ip': "192.168.1.100",
        'dst_ip': "10.0.0.50",
        'src_port': 54321,
        'dst_port': 80,
        'proto': "TCP",
        'raw_len': 1500
    }
    
    # Mock the Kafka producer
    with patch.object(producer.producer, 'produce') as mock_produce:
        with patch.object(producer.producer, 'poll'):
            producer._produce_packet(metadata)
            
            # Verify produce was called
            assert mock_produce.called
            call_args = mock_produce.call_args
            
            # Check topic
            assert call_args[1]['topic'] == "test.packets"
            
            # Check key (5-tuple)
            key = call_args[1]['key'].decode('utf-8')
            expected_key = "192.168.1.100:54321:10.0.0.50:80:TCP"
            assert key == expected_key
            
            # Check value (JSON)
            value = json.loads(call_args[1]['value'].decode('utf-8'))
            assert value == metadata
            
            print("✓ Packet production logic successful")
            print(f"  Key: {key}")
            print(f"  Value: {json.dumps(value, indent=2)}")


def test_delivery_callback():
    """Test delivery callback handling."""
    print("\nTesting delivery callbacks...")
    
    producer = PacketCaptureProducer(
        kafka_brokers="localhost:9092",
        topic="test.packets"
    )
    
    # Test successful delivery
    producer._delivery_callback(None, Mock())
    assert producer.packets_produced == 1
    assert producer.packets_failed == 0
    
    print("✓ Success callback handled correctly")
    
    # Test failed delivery
    mock_err = Mock()
    mock_err.__str__ = lambda self: "Connection error"
    producer._delivery_callback(mock_err, Mock())
    assert producer.packets_produced == 1
    assert producer.packets_failed == 1
    
    print("✓ Error callback handled correctly")


def test_ipv6_support():
    """Test IPv6 packet extraction."""
    print("\nTesting IPv6 support...")
    
    producer = PacketCaptureProducer(
        kafka_brokers="localhost:9092",
        topic="test.packets"
    )
    
    # Mock an IPv6 TCP packet
    mock_packet = Mock()
    mock_packet.sniff_timestamp = "1729468800.123456"
    mock_packet.length = "1500"
    mock_packet.ipv6 = Mock()
    mock_packet.ipv6.src = "2001:db8::1"
    mock_packet.ipv6.dst = "2001:db8::2"
    mock_packet.transport_layer = "TCP"
    mock_packet.tcp = Mock()
    mock_packet.tcp.srcport = "54321"
    mock_packet.tcp.dstport = "443"
    
    metadata = producer._extract_packet_metadata(mock_packet)
    
    assert metadata is not None
    assert metadata['src_ip'] == "2001:db8::1"
    assert metadata['dst_ip'] == "2001:db8::2"
    assert metadata['proto'] == "TCP"
    
    print("✓ IPv6 packet extraction successful")
    print(f"  Metadata: {json.dumps(metadata, indent=2)}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Packet Capture Producer Tests")
    print("=" * 60)
    
    try:
        test_producer_initialization()
        test_packet_metadata_extraction()
        test_produce_packet_logic()
        test_delivery_callback()
        test_ipv6_support()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
