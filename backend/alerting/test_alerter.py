"""
Test Suite for Alerting Pipeline
Unit tests for severity classification, filtering, integrations, and end-to-end flow.
"""
import os
import sys
import json
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alerting.alerter import (
    Config,
    SeverityClassifier,
    AlertFilter,
    DatabaseWriter,
    AlertDispatcher
)
from alerting.dlq import DLQProducer, RetryPolicy, with_retry
from alerting.integrations import (
    SyslogClient,
    SplunkHECClient,
    EmailClient,
    RateLimiter
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_config():
    """Create test configuration."""
    config_data = {
        'severity_mapping': {
            'DDoS': 'HIGH',
            'PortScan': 'LOW',
            'Normal': 'INFO',
            '_default': 'MEDIUM'
        },
        'confidence_thresholds': {
            'INFO': 0.0,
            'LOW': 0.5,
            'MEDIUM': 0.6,
            'HIGH': 0.7,
            'CRITICAL': 0.75
        },
        'alert_filtering': {
            'suppress_info': True,
            'suppress_classes': ['Normal'],
            'min_confidence': 0.5,
            'deduplication_window': 300,
            'deduplication_keys': ['src_ip', 'dst_ip', 'class_name']
        },
        'dlq': {
            'topic': 'alerts.dlq',
            'retry': {
                'max_attempts': 3,
                'initial_delay_ms': 100,
                'max_delay_ms': 1000,
                'backoff_multiplier': 2.0
            }
        }
    }
    
    # Create mock config
    config = Mock(spec=Config)
    config.config = config_data
    config.get = lambda *keys, default=None: _get_nested(config_data, keys, default)
    
    return config


def _get_nested(data, keys, default=None):
    """Helper to get nested dict value."""
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value


@pytest.fixture
def test_prediction():
    """Create test prediction message."""
    return {
        'flow_id': 'test-flow-12345',
        'timestamp': int(time.time() * 1000),
        'class_idx': 5,
        'class_name': 'Test Attack',
        'confidence': 0.95,
        'model_version': 'Test v1.0',
        'feature_version': 'Test v1.0',
        'src_ip': '192.168.1.100',
        'dst_ip': '10.0.0.1',
        'src_port': 12345,
        'dst_port': 80,
        'protocol': 'TCP'
    }


@pytest.fixture
def test_alert():
    """Create test alert."""
    return {
        'alert_id': str(uuid.uuid4()),
        'flow_id': 'test-flow-12345',
        'timestamp': int(time.time() * 1000),
        'class_idx': 5,
        'class_name': 'Test Attack',
        'confidence': 0.95,
        'severity': 'HIGH',
        'src_ip': '192.168.1.100',
        'dst_ip': '10.0.0.1',
        'src_port': 12345,
        'dst_port': 80,
        'protocol': 'TCP',
        'model_version': 'Test v1.0',
        'feature_version': 'Test v1.0',
        'status': 'NEW',
        'raw_payload': {},
        'tags': [],
        'destinations': [],
        'dispatch_status': {}
    }


# ============================================================================
# Severity Classifier Tests
# ============================================================================

class TestSeverityClassifier:
    """Test severity classification logic."""
    
    def test_classify_known_class(self, test_config):
        """Test classification of known attack class."""
        classifier = SeverityClassifier(test_config)
        
        # DDoS with high confidence should be HIGH
        severity = classifier.classify('DDoS', 0.95)
        assert severity == 'HIGH'
    
    def test_classify_default_class(self, test_config):
        """Test classification of unknown class uses default."""
        classifier = SeverityClassifier(test_config)
        
        severity = classifier.classify('UnknownAttack', 0.8)
        assert severity == 'MEDIUM'
    
    def test_classify_below_threshold(self, test_config):
        """Test that low confidence predictions are suppressed."""
        classifier = SeverityClassifier(test_config)
        
        # HIGH severity requires 0.7 confidence
        severity = classifier.classify('DDoS', 0.65)
        assert severity is None
    
    def test_classify_exact_threshold(self, test_config):
        """Test classification at exact threshold."""
        classifier = SeverityClassifier(test_config)
        
        # LOW severity requires 0.5 confidence
        severity = classifier.classify('PortScan', 0.5)
        assert severity == 'LOW'


# ============================================================================
# Alert Filter Tests
# ============================================================================

class TestAlertFilter:
    """Test alert filtering and deduplication."""
    
    def test_suppress_info(self, test_config, test_alert):
        """Test suppression of INFO-level alerts."""
        alert_filter = AlertFilter(test_config)
        
        test_alert['severity'] = 'INFO'
        assert alert_filter.should_alert(test_alert) is False
    
    def test_suppress_class(self, test_config, test_alert):
        """Test suppression of specific classes."""
        alert_filter = AlertFilter(test_config)
        
        test_alert['class_name'] = 'Normal'
        assert alert_filter.should_alert(test_alert) is False
    
    def test_min_confidence(self, test_config, test_alert):
        """Test global minimum confidence threshold."""
        alert_filter = AlertFilter(test_config)
        
        test_alert['confidence'] = 0.4  # Below min_confidence of 0.5
        assert alert_filter.should_alert(test_alert) is False
    
    def test_deduplication(self, test_config, test_alert):
        """Test alert deduplication."""
        alert_filter = AlertFilter(test_config)
        
        # First alert should pass
        assert alert_filter.should_alert(test_alert) is True
        
        # Duplicate alert should be suppressed
        assert alert_filter.should_alert(test_alert) is False
        
        # Alert with different src_ip should pass
        test_alert['src_ip'] = '192.168.1.200'
        assert alert_filter.should_alert(test_alert) is True
    
    def test_allow_high_severity(self, test_config, test_alert):
        """Test that high-severity alerts are allowed."""
        alert_filter = AlertFilter(test_config)
        
        test_alert['severity'] = 'HIGH'
        test_alert['confidence'] = 0.95
        assert alert_filter.should_alert(test_alert) is True


# ============================================================================
# DLQ Tests
# ============================================================================

class TestDLQ:
    """Test Dead Letter Queue functionality."""
    
    def test_retry_policy_should_retry(self):
        """Test retry policy decision logic."""
        policy = RetryPolicy(max_attempts=3)
        
        assert policy.should_retry(0) is True
        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is False
    
    def test_retry_policy_delay(self):
        """Test exponential backoff delay calculation."""
        policy = RetryPolicy(
            initial_delay_ms=1000,
            max_delay_ms=10000,
            backoff_multiplier=2.0
        )
        
        assert policy.get_delay_ms(0) == 1000
        assert policy.get_delay_ms(1) == 2000
        assert policy.get_delay_ms(2) == 4000
        assert policy.get_delay_ms(3) == 8000
        assert policy.get_delay_ms(4) == 10000  # Capped at max
    
    @patch('alerting.dlq.Producer')
    def test_dlq_write(self, mock_producer_class):
        """Test writing to DLQ."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        dlq = DLQProducer('localhost:9092')
        
        original_msg = {'alert_id': 'test-123', 'severity': 'HIGH'}
        error = Exception('Test error')
        
        result = dlq.write(
            original_message=original_msg,
            error=error,
            destination='syslog',
            retry_count=3
        )
        
        # Verify produce was called
        assert mock_producer.produce.called
        
        # Verify message structure
        call_args = mock_producer.produce.call_args
        value = json.loads(call_args.kwargs['value'].decode('utf-8'))
        assert value['destination'] == 'syslog'
        assert value['retry_count'] == 3
        assert value['original_message'] == original_msg


# ============================================================================
# Rate Limiter Tests
# ============================================================================

class TestRateLimiter:
    """Test email rate limiting."""
    
    def test_rate_limiter_allows_initial(self):
        """Test that initial sends are allowed."""
        limiter = RateLimiter(max_per_minute=5, max_per_hour=20, max_per_day=100)
        
        assert limiter.can_send() is True
    
    def test_rate_limiter_minute_limit(self):
        """Test per-minute rate limiting."""
        limiter = RateLimiter(max_per_minute=2, max_per_hour=100, max_per_day=1000)
        
        # Send 2 emails
        assert limiter.can_send() is True
        limiter.record_send()
        assert limiter.can_send() is True
        limiter.record_send()
        
        # 3rd should be blocked
        assert limiter.can_send() is False
    
    def test_rate_limiter_stats(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter(max_per_minute=5, max_per_hour=20, max_per_day=100)
        
        limiter.record_send()
        limiter.record_send()
        
        stats = limiter.get_stats()
        assert stats['last_minute'] == 2
        assert stats['last_hour'] == 2
        assert stats['last_day'] == 2


# ============================================================================
# Syslog Client Tests
# ============================================================================

class TestSyslogClient:
    """Test syslog integration."""
    
    def test_format_rfc5424(self, test_alert):
        """Test RFC5424 message formatting."""
        client = SyslogClient('localhost', 6514)
        
        message = client._format_rfc5424(
            severity='HIGH',
            message='DDoS detected',
            structured_data=None
        )
        
        # Verify RFC5424 format: <priority>version timestamp ...
        assert message.startswith('<')
        assert '1 ' in message  # Version 1
        assert 'adaptive-ids' in message
        assert 'DDoS detected' in message
    
    @patch('socket.socket')
    def test_send_udp(self, mock_socket_class, test_alert):
        """Test sending via UDP."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket
        
        client = SyslogClient('localhost', 514, protocol='UDP')
        result = client.send(test_alert)
        
        # Verify send was called
        assert mock_socket.sendto.called


# ============================================================================
# SIEM Client Tests
# ============================================================================

class TestSplunkClient:
    """Test Splunk HEC integration."""
    
    def test_format_event(self, test_alert):
        """Test Splunk HEC event formatting."""
        client = SplunkHECClient(
            url='http://localhost:8088',
            token='test-token',
            index='ids_alerts'
        )
        
        event = client._format_event(test_alert)
        
        assert event['index'] == 'ids_alerts'
        assert event['sourcetype'] == 'ids:alert'
        assert event['event']['alert_id'] == test_alert['alert_id']
        assert event['event']['severity'] == 'HIGH'
    
    @patch('requests.Session.post')
    def test_send_success(self, mock_post, test_alert):
        """Test successful send to Splunk."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        client = SplunkHECClient(
            url='http://localhost:8088',
            token='test-token'
        )
        
        result = client.send(test_alert)
        assert result is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """End-to-end integration tests."""
    
    @pytest.mark.skipif(
        not os.getenv('RUN_INTEGRATION_TESTS'),
        reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable"
    )
    def test_end_to_end_flow(self, test_prediction):
        """Test complete alert flow from prediction to database."""
        # This requires running Kafka and PostgreSQL
        # Skip in CI unless explicitly enabled
        
        from alerting.alerter import AlertingService
        
        service = AlertingService()
        service.process_prediction(test_prediction)
        
        # Verify alert was created
        assert service.metrics['alerts_created'] > 0


# ============================================================================
# Helper Test
# ============================================================================

def test_with_retry_success():
    """Test with_retry helper with successful function."""
    call_count = {'count': 0}
    
    def successful_func():
        call_count['count'] += 1
        return 'success'
    
    policy = RetryPolicy(max_attempts=3)
    result = with_retry(
        func=successful_func,
        retry_policy=policy,
        destination='test'
    )
    
    assert result == 'success'
    assert call_count['count'] == 1


def test_with_retry_eventual_success():
    """Test with_retry helper with eventual success after retries."""
    call_count = {'count': 0}
    
    def flaky_func():
        call_count['count'] += 1
        if call_count['count'] < 3:
            raise Exception('Temporary failure')
        return 'success'
    
    policy = RetryPolicy(max_attempts=3, initial_delay_ms=10)
    result = with_retry(
        func=flaky_func,
        retry_policy=policy,
        destination='test'
    )
    
    assert result == 'success'
    assert call_count['count'] == 3


def test_with_retry_all_fail():
    """Test with_retry helper when all attempts fail."""
    call_count = {'count': 0}
    
    def failing_func():
        call_count['count'] += 1
        raise Exception('Permanent failure')
    
    policy = RetryPolicy(max_attempts=3, initial_delay_ms=10)
    result = with_retry(
        func=failing_func,
        retry_policy=policy,
        destination='test'
    )
    
    assert result is None
    assert call_count['count'] == 3


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
