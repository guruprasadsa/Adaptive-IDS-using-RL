"""
Unit tests for Feature Extractor
Tests flow aggregation, feature computation, and normalization with real CSV data
"""

import pytest
import os
import sys
import json
import time
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from stream.feature_extractor import (
    PacketStats,
    FlowRecord,
    OnlineStandardScaler,
    FeatureExtractor
)


class TestPacketStats:
    """Test PacketStats dataclass"""
    
    def test_initialization(self):
        """Test PacketStats initialization"""
        stats = PacketStats()
        assert stats.count == 0
        assert stats.bytes == 0
        assert len(stats.iat_times) == 0
        assert len(stats.pkt_sizes) == 0
        assert stats.last_timestamp is None
    
    def test_add_single_packet(self):
        """Test adding single packet"""
        stats = PacketStats()
        stats.add_packet(size=100, timestamp=1.0)
        
        assert stats.count == 1
        assert stats.bytes == 100
        assert stats.pkt_sizes == [100]
        assert stats.last_timestamp == 1.0
        assert len(stats.iat_times) == 0  # No IAT for first packet
    
    def test_add_multiple_packets(self):
        """Test adding multiple packets and IAT calculation"""
        stats = PacketStats()
        stats.add_packet(size=100, timestamp=1.0)
        stats.add_packet(size=200, timestamp=1.5)
        stats.add_packet(size=150, timestamp=2.0)
        
        assert stats.count == 3
        assert stats.bytes == 450
        assert stats.pkt_sizes == [100, 200, 150]
        assert stats.iat_times == [0.5, 0.5]
        assert stats.last_timestamp == 2.0
    
    def test_tcp_flags(self):
        """Test TCP flag tracking"""
        stats = PacketStats()
        flags = {'SYN': 1, 'ACK': 1}
        stats.add_packet(size=60, timestamp=1.0, flags=flags)
        
        assert stats.syn_count == 1
        assert stats.ack_count == 1
        assert stats.fin_count == 0


class TestFlowRecord:
    """Test FlowRecord functionality"""
    
    def test_initialization(self):
        """Test FlowRecord initialization"""
        flow = FlowRecord(
            flow_id="192.168.1.1:1234:10.0.0.1:80:TCP",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=1.0
        )
        
        assert flow.flow_id == "192.168.1.1:1234:10.0.0.1:80:TCP"
        assert flow.total_packets == 0
        assert flow.forward.count == 0
        assert flow.backward.count == 0
    
    def test_add_forward_packet(self):
        """Test adding forward packet"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=1.0
        )
        
        packet = {
            'ts': 1.5,
            'raw_len': 100,
            'src_ip': '192.168.1.1',
            'dst_ip': '10.0.0.1'
        }
        
        flow.add_packet(packet, is_forward=True)
        
        assert flow.total_packets == 1
        assert flow.total_bytes == 100
        assert flow.forward.count == 1
        assert flow.backward.count == 0
        assert flow.last_seen == 1.5
    
    def test_add_backward_packet(self):
        """Test adding backward packet"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=1.0
        )
        
        packet = {
            'ts': 2.0,
            'raw_len': 200,
            'src_ip': '10.0.0.1',
            'dst_ip': '192.168.1.1'
        }
        
        flow.add_packet(packet, is_forward=False)
        
        assert flow.total_packets == 1
        assert flow.total_bytes == 200
        assert flow.forward.count == 0
        assert flow.backward.count == 1
    
    def test_bidirectional_flow(self):
        """Test bidirectional flow with multiple packets"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=1.0
        )
        
        # Add 3 forward packets
        for i in range(3):
            flow.add_packet({'ts': 1.0 + i * 0.1, 'raw_len': 100}, is_forward=True)
        
        # Add 2 backward packets
        for i in range(2):
            flow.add_packet({'ts': 1.5 + i * 0.1, 'raw_len': 200}, is_forward=False)
        
        assert flow.total_packets == 5
        assert flow.total_bytes == 700
        assert flow.forward.count == 3
        assert flow.backward.count == 2
    
    def test_flow_expiration_active_timeout(self):
        """Test flow expiration by active timeout"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=10.0
        )
        
        # Check expiration after 60 seconds (active timeout)
        assert flow.is_expired(61.5, active_timeout=60.0, idle_timeout=15.0)
    
    def test_flow_expiration_idle_timeout(self):
        """Test flow expiration by idle timeout"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=10.0
        )
        
        # Check expiration after 15 seconds idle
        assert flow.is_expired(25.5, active_timeout=60.0, idle_timeout=15.0)
    
    def test_compute_features_length(self):
        """Test that compute_features returns correct number of features"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=1.0,
            last_seen=2.0
        )
        
        # Add some packets
        flow.add_packet({'ts': 1.0, 'raw_len': 100}, is_forward=True)
        flow.add_packet({'ts': 1.5, 'raw_len': 200}, is_forward=False)
        
        features = flow.compute_features()
        
        # Should return exactly 41 features
        assert len(features) == 41
        assert all(isinstance(f, float) for f in features)
    
    def test_compute_features_values(self):
        """Test specific feature values"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=0.0,
            last_seen=2.0
        )
        
        # Add packets: 2 forward, 1 backward
        flow.add_packet({'ts': 0.0, 'raw_len': 100}, is_forward=True)
        flow.add_packet({'ts': 1.0, 'raw_len': 150}, is_forward=True)
        flow.add_packet({'ts': 2.0, 'raw_len': 200}, is_forward=False)
        
        features = flow.compute_features()
        
        # Feature 0: Duration
        assert features[0] == 2.0
        
        # Feature 1-2: Forward/Backward packet count
        assert features[1] == 2.0
        assert features[2] == 1.0
        
        # Feature 3-4: Forward/Backward bytes
        assert features[3] == 250.0
        assert features[4] == 200.0
        
        # Feature 5-8: Forward packet length stats
        assert features[5] == 100.0  # min
        assert features[6] == 150.0  # max
        assert features[7] == 125.0  # mean
        
        # Feature 13-14: Total flow packets/bytes per second
        assert features[13] == 3.0 / 2.0     # total_packets / duration
        assert features[14] == 450.0 / 2.0   # total_bytes / duration


class TestOnlineStandardScaler:
    """Test OnlineStandardScaler"""
    
    def test_initialization(self):
        """Test scaler initialization"""
        scaler = OnlineStandardScaler(n_features=10)
        assert scaler.n_features == 10
        assert scaler.n_samples == 0
        assert len(scaler.mean) == 10
        assert len(scaler.std) == 10
    
    def test_partial_fit_single_sample(self):
        """Test fitting with single sample"""
        scaler = OnlineStandardScaler(n_features=3)
        X = np.array([1.0, 2.0, 3.0])
        scaler.partial_fit(X)
        
        assert scaler.n_samples == 1
        np.testing.assert_array_almost_equal(scaler.mean, [1.0, 2.0, 3.0])
    
    def test_partial_fit_multiple_samples(self):
        """Test fitting with multiple samples"""
        scaler = OnlineStandardScaler(n_features=2)
        
        # Add samples incrementally
        scaler.partial_fit(np.array([1.0, 2.0]))
        scaler.partial_fit(np.array([3.0, 4.0]))
        scaler.partial_fit(np.array([5.0, 6.0]))
        
        assert scaler.n_samples == 3
        np.testing.assert_array_almost_equal(scaler.mean, [3.0, 4.0])
    
    def test_transform(self):
        """Test transformation"""
        scaler = OnlineStandardScaler(n_features=2)
        
        # Fit with known data: [0, 0], [2, 4], [4, 8]
        # Mean: [2, 4], Std: [2, 4]
        X = np.array([[0, 0], [2, 4], [4, 8]])
        scaler.partial_fit(X)
        
        # Transform new data
        X_new = np.array([2.0, 4.0])
        X_transformed = scaler.transform(X_new)
        
        # Should be close to [0, 0] (at mean)
        np.testing.assert_array_almost_equal(X_transformed[0], [0.0, 0.0], decimal=1)
    
    def test_save_load(self):
        """Test saving and loading scaler state"""
        scaler = OnlineStandardScaler(n_features=3)
        
        # Fit with data
        X = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        scaler.partial_fit(X)
        
        # Save to temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scaler.pkl"
            scaler.save(path)
            
            # Load and verify
            loaded_scaler = OnlineStandardScaler.load(path)
            assert loaded_scaler.n_features == 3
            assert loaded_scaler.n_samples == 3
            np.testing.assert_array_almost_equal(loaded_scaler.mean, scaler.mean)
            np.testing.assert_array_almost_equal(loaded_scaler.std, scaler.std)


class TestFeatureExtractor:
    """Test FeatureExtractor class"""
    
    def test_create_flow_id(self):
        """Test flow ID creation and direction detection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = FeatureExtractor(
                kafka_brokers="localhost:9092",
                input_topic="test-input",
                output_topic="test-output",
                state_dir=tmpdir
            )
            
            # Test with IPs: 10.0.0.1 < 192.168.1.1
            # So canonical flow_id will be 10.0.0.1:80:192.168.1.1:1234:TCP
            packet1 = {
                'src_ip': '192.168.1.1',
                'dst_ip': '10.0.0.1',
                'src_port': 1234,
                'dst_port': 80,
                'proto': 'TCP'
            }
            flow_id1, is_forward1 = extractor._create_flow_id(packet1)
            assert is_forward1 is False  # This is backward direction
            assert flow_id1 == "10.0.0.1:80:192.168.1.1:1234:TCP"
            
            # Test backward direction (same flow, reversed)
            packet2 = {
                'src_ip': '10.0.0.1',
                'dst_ip': '192.168.1.1',
                'src_port': 80,
                'dst_port': 1234,
                'proto': 'TCP'
            }
            flow_id2, is_forward2 = extractor._create_flow_id(packet2)
            assert is_forward2 is True  # This is forward direction
            
            # Same flow ID for both directions
            assert flow_id1 == flow_id2
    
    def test_process_packet_creates_flow(self):
        """Test that processing packet creates flow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = FeatureExtractor(
                kafka_brokers="localhost:9092",
                input_topic="test-input",
                output_topic="test-output",
                state_dir=tmpdir
            )
            
            packet = {
                'ts': 1.0,
                'src_ip': '192.168.1.1',
                'dst_ip': '10.0.0.1',
                'src_port': 1234,
                'dst_port': 80,
                'proto': 'TCP',
                'raw_len': 100
            }
            
            extractor._process_packet(packet)
            
            assert len(extractor.flows) == 1
            assert extractor.flows_created == 1
            assert extractor.packets_processed == 1
    
    def test_process_bidirectional_packets(self):
        """Test processing bidirectional packets into same flow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = FeatureExtractor(
                kafka_brokers="localhost:9092",
                input_topic="test-input",
                output_topic="test-output",
                state_dir=tmpdir
            )
            
            # Forward packet
            packet1 = {
                'ts': 1.0,
                'src_ip': '192.168.1.1',
                'dst_ip': '10.0.0.1',
                'src_port': 1234,
                'dst_port': 80,
                'proto': 'TCP',
                'raw_len': 100
            }
            
            # Backward packet
            packet2 = {
                'ts': 1.5,
                'src_ip': '10.0.0.1',
                'dst_ip': '192.168.1.1',
                'src_port': 80,
                'dst_port': 1234,
                'proto': 'TCP',
                'raw_len': 200
            }
            
            extractor._process_packet(packet1)
            extractor._process_packet(packet2)
            
            # Should have only 1 flow
            assert len(extractor.flows) == 1
            assert extractor.flows_created == 1
            
            # Get the flow
            flow = list(extractor.flows.values())[0]
            assert flow.forward.count == 1
            assert flow.backward.count == 1
            assert flow.total_packets == 2


class TestFeatureComputationWithRealData:
    """Test feature computation with representative flows from real datasets"""
    
    def test_http_flow(self):
        """Test HTTP flow feature computation"""
        flow = FlowRecord(
            flow_id="192.168.10.50:49161:192.168.10.51:80:TCP",
            src_ip="192.168.10.50",
            dst_ip="192.168.10.51",
            src_port=49161,
            dst_port=80,
            protocol="TCP",
            start_time=0.0,
            last_seen=5.0
        )
        
        # Simulate HTTP request/response pattern
        # Client sends requests (forward)
        timestamps_fwd = [0.0, 0.1, 0.2]
        sizes_fwd = [60, 120, 80]
        
        for ts, size in zip(timestamps_fwd, sizes_fwd):
            flow.add_packet({'ts': ts, 'raw_len': size}, is_forward=True)
        
        # Server sends responses (backward)
        timestamps_bwd = [0.15, 0.25, 0.35, 0.45]
        sizes_bwd = [1460, 1460, 1460, 800]
        
        for ts, size in zip(timestamps_bwd, sizes_bwd):
            flow.add_packet({'ts': ts, 'raw_len': size}, is_forward=False)
        
        features = flow.compute_features()
        
        # Validate feature count
        assert len(features) == 41
        
        # Validate duration
        assert features[0] == pytest.approx(0.45, rel=1e-2)
        
        # Validate packet counts
        assert features[1] == 3.0  # Forward packets
        assert features[2] == 4.0  # Backward packets
        
        # Validate byte counts
        assert features[3] == 260.0  # Forward bytes
        assert features[4] == 5180.0  # Backward bytes
    
    def test_ddos_flow(self):
        """Test DDoS-like flow (many packets, small size, high rate)"""
        flow = FlowRecord(
            flow_id="172.16.0.1:0:192.168.10.50:0:ICMP",
            src_ip="172.16.0.1",
            dst_ip="192.168.10.50",
            src_port=0,
            dst_port=0,
            protocol="ICMP",
            start_time=0.0,
            last_seen=0.0  # Will be updated by add_packet
        )
        
        # Many small packets in quick succession (flood)
        for i in range(100):
            ts = i * 0.01  # 10ms intervals (0.0 to 0.99)
            flow.add_packet({'ts': ts, 'raw_len': 64}, is_forward=True)
        
        features = flow.compute_features()
        
        # Duration is 0.99 seconds (last packet at 0.99, start at 0.0)
        duration = features[0]
        assert duration == pytest.approx(0.99, rel=1e-2)
        
        # High packet rate (100 packets in 0.99 seconds ~ 101 packets/sec)
        assert features[14] > 90    # Packets per second
        
        # Small consistent packet sizes
        assert features[5] == 64.0  # Min forward packet length
        assert features[6] == 64.0  # Max forward packet length
    
    def test_port_scan_flow(self):
        """Test port scan-like flow (SYN packets only)"""
        flow = FlowRecord(
            flow_id="172.16.0.1:12345:192.168.10.50:22:TCP",
            src_ip="172.16.0.1",
            dst_ip="192.168.10.50",
            src_port=12345,
            dst_port=22,
            protocol="TCP",
            start_time=0.0,
            last_seen=0.0  # Will be updated by add_packet
        )
        
        # Single SYN packet (port scan probe)
        flow.add_packet({'ts': 0.0, 'raw_len': 60}, is_forward=True)
        
        features = flow.compute_features()
        
        # Only forward packets
        assert features[1] == 1.0
        assert features[2] == 0.0
        
        # Duration will be 0.0 - 0.0 = 0, but compute_features uses max(duration, 1e-6)
        assert features[0] == pytest.approx(1e-6, rel=1e-2)
    
    def test_ssh_flow(self):
        """Test SSH flow (bidirectional, encrypted, similar sizes)"""
        flow = FlowRecord(
            flow_id="192.168.1.100:22:172.16.0.1:54321:TCP",
            src_ip="192.168.1.100",
            dst_ip="172.16.0.1",
            src_port=22,
            dst_port=54321,
            protocol="TCP",
            start_time=0.0,
            last_seen=10.0
        )
        
        # Simulate SSH session with balanced bidirectional traffic
        for i in range(50):
            ts = i * 0.2
            # Alternating direction
            is_fwd = i % 2 == 0
            size = 100 + (i % 50)  # Varying sizes
            flow.add_packet({'ts': ts, 'raw_len': size}, is_forward=is_fwd)
        
        features = flow.compute_features()
        
        # Balanced packet ratio
        packet_ratio = features[40]
        assert 0.4 < packet_ratio < 0.6  # Should be close to 0.5
    
    def test_multiple_flows_normalization(self):
        """Test scaler with multiple diverse flows"""
        scaler = OnlineStandardScaler(n_features=41)
        
        # Create multiple flows with different characteristics
        flows = []
        
        # Flow 1: HTTP
        flow1 = FlowRecord(
            flow_id="f1", src_ip="1.1.1.1", dst_ip="2.2.2.2",
            src_port=1, dst_port=80, protocol="TCP",
            start_time=0.0, last_seen=5.0
        )
        for i in range(10):
            flow1.add_packet({'ts': i * 0.5, 'raw_len': 100 + i * 10}, is_forward=True)
        flows.append(flow1)
        
        # Flow 2: Large transfer
        flow2 = FlowRecord(
            flow_id="f2", src_ip="3.3.3.3", dst_ip="4.4.4.4",
            src_port=2, dst_port=443, protocol="TCP",
            start_time=0.0, last_seen=30.0
        )
        for i in range(50):
            flow2.add_packet({'ts': i * 0.6, 'raw_len': 1460}, is_forward=False)
        flows.append(flow2)
        
        # Flow 3: DDoS-like
        flow3 = FlowRecord(
            flow_id="f3", src_ip="5.5.5.5", dst_ip="6.6.6.6",
            src_port=0, dst_port=0, protocol="ICMP",
            start_time=0.0, last_seen=1.0
        )
        for i in range(100):
            flow3.add_packet({'ts': i * 0.01, 'raw_len': 64}, is_forward=True)
        flows.append(flow3)
        
        # Compute features and normalize
        feature_vectors = []
        for flow in flows:
            features = flow.compute_features()
            assert len(features) == 41
            feature_vectors.append(features)
        
        # Fit scaler
        X = np.array(feature_vectors)
        scaler.partial_fit(X)
        
        # Transform
        X_normalized = scaler.transform(X)
        
        # Verify normalization
        assert X_normalized.shape == (3, 41)
        
        # Mean should be close to 0, std close to 1
        assert np.abs(np.mean(X_normalized)) < 0.5
        assert 0.5 < np.std(X_normalized) < 1.5


class TestEndToEnd:
    """End-to-end integration tests"""
    
    def test_feature_version_hash(self):
        """Test that feature version creates consistent hashes"""
        version1 = "v1.0-cic41"
        version2 = "v1.0-cic41"
        version3 = "v2.0-cic41"
        
        assert version1 == version2
        assert version1 != version3
    
    def test_deterministic_feature_order(self):
        """Test that features are computed in deterministic order"""
        flow = FlowRecord(
            flow_id="test",
            src_ip="1.1.1.1",
            dst_ip="2.2.2.2",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=0.0,
            last_seen=1.0
        )
        
        # Add same packets
        for i in range(5):
            flow.add_packet({'ts': i * 0.2, 'raw_len': 100}, is_forward=True)
        
        # Compute features multiple times
        features1 = flow.compute_features()
        features2 = flow.compute_features()
        
        # Should be identical
        assert features1 == features2
    
    @pytest.mark.parametrize("timeout", [
        (60.0, 15.0),   # Default
        (120.0, 30.0),  # Longer
        (30.0, 10.0),   # Shorter
    ])
    def test_different_timeouts(self, timeout):
        """Test flow expiration with different timeout values"""
        active, idle = timeout
        
        flow = FlowRecord(
            flow_id="test",
            src_ip="1.1.1.1",
            dst_ip="2.2.2.2",
            src_port=1234,
            dst_port=80,
            protocol="TCP",
            start_time=0.0,
            last_seen=10.0
        )
        
        # Not expired yet
        assert not flow.is_expired(10.0, active_timeout=active, idle_timeout=idle)
        
        # Expired by idle timeout
        assert flow.is_expired(10.0 + idle + 1.0, active_timeout=active, idle_timeout=idle)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
