"""
Unit tests for alerts API endpoints.
Tests SSE streaming, alert queries with filters, acknowledgment, and false positive marking.
"""
import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest


# Test fixtures
@pytest.fixture
def client():
    """Create test client"""
    # Set test environment variables
    os.environ['TESTING'] = 'true'
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_PORT'] = '55432'
    os.environ['POSTGRES_DB'] = 'adaptive_ids_test'
    os.environ['KAFKA_BROKERS'] = 'localhost:9092'
    
    from api.app import app
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Create authentication headers with mock token"""
    # In a real test, we would generate a valid JWT token
    # For now, we'll mock the auth decorator
    return {
        'Authorization': 'Bearer mock-test-token',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def mock_db_service():
    """Mock database service"""
    with patch('api.app.db_service') as mock:
        yield mock


@pytest.fixture
def mock_auth():
    """Mock authentication decorator"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            # Inject mock user_id
            return f(*args, user_id=1, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    
    with patch('api.app.require_auth', decorator):
        yield


class TestAlertsQueryEndpoint:
    """Test cases for GET /api/alerts endpoint with advanced filtering"""
    
    def test_basic_alert_list(self, client, mock_db_service, mock_auth):
        """Test basic alert listing without filters"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [
                {
                    'id': 'alert-1',
                    'severity': 'HIGH',
                    'className': 'DDoS',
                    'confidence': 0.95,
                    'timestamp': '2025-10-24T10:00:00Z'
                }
            ],
            'total': 1,
            'page': 1,
            'per_page': 10,
            'total_pages': 1
        }
        
        response = client.get('/api/alerts')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['total'] == 1
        assert len(data['alerts']) == 1
        assert data['alerts'][0]['severity'] == 'HIGH'
    
    def test_alerts_with_severity_filter(self, client, mock_db_service, mock_auth):
        """Test filtering alerts by severity"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 0,
            'page': 1,
            'per_page': 10,
            'total_pages': 0
        }
        
        response = client.get('/api/alerts?severity=CRITICAL')
        
        assert response.status_code == 200
        # Verify the service was called with severity filter
        call_args = mock_db_service.fetch_alerts.call_args
        assert call_args[1]['severity'] == 'CRITICAL'
    
    def test_alerts_with_class_filter(self, client, mock_db_service, mock_auth):
        """Test filtering alerts by attack class"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 0,
            'page': 1,
            'per_page': 10,
            'total_pages': 0
        }
        
        response = client.get('/api/alerts?class_name=DDoS')
        
        assert response.status_code == 200
        call_args = mock_db_service.fetch_alerts.call_args
        assert call_args[1]['class_name'] == 'DDoS'
    
    def test_alerts_with_confidence_range(self, client, mock_db_service, mock_auth):
        """Test filtering alerts by confidence range"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 0,
            'page': 1,
            'per_page': 10,
            'total_pages': 0
        }
        
        response = client.get('/api/alerts?min_confidence=0.8&max_confidence=1.0')
        
        assert response.status_code == 200
        call_args = mock_db_service.fetch_alerts.call_args
        assert call_args[1]['min_confidence'] == 0.8
        assert call_args[1]['max_confidence'] == 1.0
    
    def test_alerts_with_ip_filters(self, client, mock_db_service, mock_auth):
        """Test filtering alerts by source/destination IP"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 0,
            'page': 1,
            'per_page': 10,
            'total_pages': 0
        }
        
        response = client.get('/api/alerts?srcIp=192.168.1.100&dstIp=10.0.0.1')
        
        assert response.status_code == 200
        call_args = mock_db_service.fetch_alerts.call_args
        assert call_args[1]['src_ip'] == '192.168.1.100'
        assert call_args[1]['dst_ip'] == '10.0.0.1'
    
    def test_alerts_with_time_range(self, client, mock_db_service, mock_auth):
        """Test filtering alerts by time range"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 0,
            'page': 1,
            'per_page': 10,
            'total_pages': 0
        }
        
        start_time = '2025-10-24T00:00:00Z'
        end_time = '2025-10-24T23:59:59Z'
        response = client.get(f'/api/alerts?startTime={start_time}&endTime={end_time}')
        
        assert response.status_code == 200
        call_args = mock_db_service.fetch_alerts.call_args
        assert call_args[1]['start_time'] == start_time
        assert call_args[1]['end_time'] == end_time
    
    def test_alerts_with_combined_filters(self, client, mock_db_service, mock_auth):
        """Test filtering alerts with multiple filters combined"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 0,
            'page': 1,
            'per_page': 10,
            'total_pages': 0
        }
        
        response = client.get(
            '/api/alerts?severity=HIGH&class_name=DDoS&min_confidence=0.9&srcIp=192.168.1.100'
        )
        
        assert response.status_code == 200
        call_args = mock_db_service.fetch_alerts.call_args
        assert call_args[1]['severity'] == 'HIGH'
        assert call_args[1]['class_name'] == 'DDoS'
        assert call_args[1]['min_confidence'] == 0.9
        assert call_args[1]['src_ip'] == '192.168.1.100'
    
    def test_alerts_pagination(self, client, mock_db_service, mock_auth):
        """Test alert pagination"""
        mock_db_service.fetch_alerts.return_value = {
            'alerts': [],
            'total': 50,
            'page': 2,
            'per_page': 20,
            'total_pages': 3
        }
        
        response = client.get('/api/alerts?page=2&per_page=20')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['page'] == 2
        assert data['per_page'] == 20
        assert data['total_pages'] == 3
    
    def test_alerts_database_error(self, client, mock_db_service, mock_auth):
        """Test handling of database errors"""
        mock_db_service.fetch_alerts.side_effect = Exception("Database connection failed")
        
        response = client.get('/api/alerts')
        
        assert response.status_code == 503
        data = json.loads(response.data)
        assert 'error' in data


class TestAlertAcknowledgmentEndpoint:
    """Test cases for PATCH /api/alerts/{id}/ack endpoint"""
    
    def test_acknowledge_alert_success(self, client, mock_db_service, mock_auth):
        """Test successful alert acknowledgment"""
        mock_db_service.update_alert_status.return_value = {
            'id': 'alert-1',
            'status': 'investigating',
            'severity': 'HIGH',
            'className': 'DDoS'
        }
        
        response = client.patch(
            '/api/alerts/alert-1/ack',
            data=json.dumps({'notes': 'Investigating this alert'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['alert']['status'] == 'investigating'
        assert 'acknowledged successfully' in data['message']
    
    def test_acknowledge_alert_with_notes(self, client, mock_db_service, mock_auth):
        """Test acknowledging alert with analyst notes"""
        mock_db_service.update_alert_status.return_value = {
            'id': 'alert-1',
            'status': 'investigating',
            'notes': 'Checking source IP reputation'
        }
        
        response = client.post(
            '/api/alerts/alert-1/ack',
            data=json.dumps({'notes': 'Checking source IP reputation'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        # Verify notes were passed to service
        call_args = mock_db_service.update_alert_status.call_args
        assert call_args[0][2] == 1  # user_id
        assert call_args[0][3] == 'Checking source IP reputation'  # notes
    
    def test_acknowledge_nonexistent_alert(self, client, mock_db_service, mock_auth):
        """Test acknowledging an alert that doesn't exist"""
        mock_db_service.update_alert_status.return_value = None
        
        response = client.patch('/api/alerts/nonexistent-id/ack')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'not found' in data['error'].lower()
    
    def test_acknowledge_database_error(self, client, mock_db_service, mock_auth):
        """Test handling database errors during acknowledgment"""
        mock_db_service.update_alert_status.side_effect = Exception("DB error")
        
        response = client.patch('/api/alerts/alert-1/ack')
        
        assert response.status_code == 503
        data = json.loads(response.data)
        assert 'error' in data


class TestFalsePositiveEndpoint:
    """Test cases for PATCH /api/alerts/{id}/false-positive endpoint"""
    
    def test_mark_false_positive_success(self, client, mock_db_service, mock_auth):
        """Test successfully marking alert as false positive"""
        mock_db_service.update_alert_status.return_value = {
            'id': 'alert-1',
            'status': 'false_positive',
            'className': 'DDoS',
            'confidence': 0.85
        }
        
        response = client.patch(
            '/api/alerts/alert-1/false-positive',
            data=json.dumps({'notes': 'Legitimate traffic spike'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['alert']['status'] == 'false_positive'
        assert 'false positive' in data['message'].lower()
    
    def test_mark_false_positive_default_notes(self, client, mock_db_service, mock_auth):
        """Test marking false positive without custom notes"""
        mock_db_service.update_alert_status.return_value = {
            'id': 'alert-1',
            'status': 'false_positive'
        }
        
        response = client.post('/api/alerts/alert-1/false-positive')
        
        assert response.status_code == 200
        # Verify default notes were used
        call_args = mock_db_service.update_alert_status.call_args
        assert 'false positive' in call_args[0][3].lower()
    
    def test_mark_false_positive_nonexistent(self, client, mock_db_service, mock_auth):
        """Test marking nonexistent alert as false positive"""
        mock_db_service.update_alert_status.return_value = None
        
        response = client.patch('/api/alerts/invalid-id/false-positive')
        
        assert response.status_code == 404
    
    def test_mark_false_positive_with_feedback(self, client, mock_db_service, mock_auth):
        """Test that false positive generates model feedback event"""
        mock_db_service.update_alert_status.return_value = {
            'id': 'alert-1',
            'status': 'false_positive',
            'className': 'PortScan',
            'confidence': 0.72
        }
        
        with patch('api.app.logging') as mock_logging:
            response = client.patch('/api/alerts/alert-1/false-positive')
            
            assert response.status_code == 200
            # Verify audit event was logged
            mock_logging.info.assert_called()
            call_args = str(mock_logging.info.call_args)
            assert 'false_positive_marked' in call_args


class TestSSEEventsEndpoint:
    """Test cases for GET /api/events SSE endpoint"""
    
    def test_sse_without_token(self, client):
        """Test SSE endpoint rejects requests without token"""
        response = client.get('/api/events')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Unauthorized' in data['error']
    
    @patch('api.app.jwt_decode')
    def test_sse_with_invalid_token(self, mock_jwt, client):
        """Test SSE endpoint rejects invalid tokens"""
        mock_jwt.return_value = None
        
        response = client.get('/api/events?token=invalid-token')
        
        assert response.status_code == 401
    
    @patch('api.app.jwt_decode')
    def test_sse_with_valid_token(self, mock_jwt, client):
        """Test SSE endpoint accepts valid tokens"""
        mock_jwt.return_value = {'user_id': 1, 'username': 'testuser'}
        
        # Mock Kafka consumer
        with patch('api.app.create_sse_stream') as mock_stream:
            mock_stream.return_value = iter([
                'event: connected\ndata: {"timestamp": "2025-10-24T10:00:00Z"}\n\n',
                'event: heartbeat\ndata: {"timestamp": 1729764000000}\n\n'
            ])
            
            response = client.get('/api/events?token=valid-token')
            
            assert response.status_code == 200
            assert response.content_type == 'text/event-stream; charset=utf-8'
    
    @patch('api.app.jwt_decode')
    def test_sse_topic_selection(self, mock_jwt, client):
        """Test SSE endpoint topic selection"""
        mock_jwt.return_value = {'user_id': 1}
        
        with patch('api.app.create_sse_stream') as mock_stream:
            mock_stream.return_value = iter([])
            
            # Test with predictions topic
            response = client.get('/api/events?token=valid-token&topic=predictions')
            assert response.status_code == 200
            
            # Verify correct topic was passed
            call_args = mock_stream.call_args
            assert call_args[1]['topic'] == 'predictions'
    
    @patch('api.app.jwt_decode')
    def test_sse_invalid_topic(self, mock_jwt, client):
        """Test SSE endpoint rejects invalid topics"""
        mock_jwt.return_value = {'user_id': 1}
        
        response = client.get('/api/events?token=valid-token&topic=invalid_topic')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid topic' in data['error']
    
    @patch('api.app.jwt_decode')
    def test_sse_fallback_mode(self, mock_jwt, client):
        """Test SSE endpoint fallback when Kafka unavailable"""
        mock_jwt.return_value = {'user_id': 1}
        
        # Mock ImportError to simulate Kafka not available
        with patch('api.app.create_sse_stream', side_effect=ImportError):
            response = client.get('/api/events?token=valid-token')
            
            # Should still return 200 with heartbeat-only mode
            assert response.status_code == 200
            assert response.content_type == 'text/event-stream; charset=utf-8'


class TestAlertDetailEndpoint:
    """Test cases for GET /api/alerts/{id} endpoint"""
    
    def test_get_alert_success(self, client, mock_db_service, mock_auth):
        """Test retrieving alert details"""
        mock_db_service.fetch_alert.return_value = {
            'id': 'alert-1',
            'severity': 'HIGH',
            'className': 'DDoS',
            'confidence': 0.95,
            'srcIp': '192.168.1.100',
            'dstIp': '10.0.0.1'
        }
        
        response = client.get('/api/alerts/alert-1')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == 'alert-1'
        assert data['severity'] == 'HIGH'
    
    def test_get_nonexistent_alert(self, client, mock_db_service, mock_auth):
        """Test retrieving nonexistent alert"""
        mock_db_service.fetch_alert.return_value = None
        
        response = client.get('/api/alerts/nonexistent-id')
        
        assert response.status_code == 404


class TestKafkaSSEConsumer:
    """Test cases for Kafka SSE consumer utility"""
    
    @patch('api.kafka_sse.Consumer')
    def test_consumer_initialization(self, mock_consumer_class):
        """Test Kafka consumer initialization"""
        from api.kafka_sse import KafkaSSEConsumer
        
        consumer = KafkaSSEConsumer(
            topic='test-topic',
            group_id='test-group',
            kafka_brokers='localhost:9092'
        )
        
        assert consumer.topic == 'test-topic'
        assert consumer.group_id == 'test-group'
        assert consumer.kafka_brokers == 'localhost:9092'
    
    @patch('api.kafka_sse.Consumer')
    def test_consumer_start_stop(self, mock_consumer_class):
        """Test starting and stopping consumer"""
        from api.kafka_sse import KafkaSSEConsumer
        
        consumer = KafkaSSEConsumer(topic='test-topic')
        
        consumer.start()
        assert consumer.running is True
        assert consumer.consumer_thread is not None
        
        consumer.stop()
        assert consumer.running is False
    
    @patch('api.kafka_sse.Consumer')
    def test_event_streaming(self, mock_consumer_class):
        """Test SSE event generation from Kafka messages"""
        from api.kafka_sse import KafkaSSEConsumer
        
        # Mock Kafka message
        mock_msg = Mock()
        mock_msg.error.return_value = None
        mock_msg.value.return_value = json.dumps({
            'alert_id': 'test-1',
            'severity': 'HIGH',
            'class_name': 'DDoS'
        }).encode('utf-8')
        
        mock_consumer = Mock()
        mock_consumer.poll.return_value = mock_msg
        mock_consumer_class.return_value = mock_consumer
        
        consumer = KafkaSSEConsumer(topic='test-topic')
        consumer.start()
        
        # Give thread time to start
        time.sleep(0.1)
        
        # Get one event
        events = consumer.stream_events(heartbeat_interval=60)
        event = next(events)
        
        assert 'event:' in event
        assert 'data:' in event
        
        consumer.stop()


# Integration tests (require running services)
@pytest.mark.integration
class TestAlertsIntegration:
    """Integration tests requiring database and Kafka"""
    
    def test_full_alert_workflow(self, client, auth_headers):
        """Test complete alert workflow: create, query, acknowledge, mark FP"""
        # This would require a test database
        pass
    
    def test_sse_real_kafka_stream(self, client, auth_headers):
        """Test SSE streaming with real Kafka messages"""
        # This would require running Kafka
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
