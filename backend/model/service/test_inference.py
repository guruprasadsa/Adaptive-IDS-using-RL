"""
Unit tests for Model Inference Service

Tests cover:
- Model loading and validation
- Inference with dummy model
- Kafka integration (mocked)
- API endpoints
- Metrics collection
"""
import os
import sys
import json
import time
import pytest
import asyncio
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

import torch
import torch.nn as nn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from schemas.models import FlowFeatures, Prediction


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def dummy_model():
    """Create a simple dummy model for testing"""
    class DummyModel(nn.Module):
        def __init__(self, input_dim=41, num_classes=15):
            super().__init__()
            self.fc1 = nn.Linear(input_dim, 128)
            self.fc2 = nn.Linear(128, 64)
            self.fc3 = nn.Linear(64, num_classes)
            self.relu = nn.ReLU()
        
        def forward(self, x):
            x = self.relu(self.fc1(x))
            x = self.relu(self.fc2(x))
            x = self.fc3(x)
            return x
    
    return DummyModel()


@pytest.fixture
def dummy_model_path(tmp_path, dummy_model):
    """Save dummy model to temporary path"""
    model_path = tmp_path / "dummy_model.pth"
    torch.save(dummy_model.state_dict(), model_path)
    return str(model_path)


@pytest.fixture
def dummy_label_classes(tmp_path):
    """Create dummy label classes file"""
    classes = [
        "BENIGN", "Bot", "DDoS", "DoS GoldenEye", "DoS Hulk",
        "DoS Slowhttptest", "DoS slowloris", "FTP-Patator",
        "Heartbleed", "Infiltration", "PortScan", "SSH-Patator",
        "Web Attack - Brute Force", "Web Attack - Sql Injection", "Web Attack - XSS"
    ]
    label_path = tmp_path / "label_classes.json"
    with open(label_path, 'w') as f:
        json.dump(classes, f)
    return str(label_path)


@pytest.fixture
def dummy_config(tmp_path):
    """Create dummy config file"""
    config = {
        "binary": False,
        "hidden_dims": "128,64",
        "num_classes": 15,
        "feature_dim": 41
    }
    config_path = tmp_path / "config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f)
    return str(config_path)


@pytest.fixture
def sample_flow_features():
    """Create sample flow features for testing"""
    return FlowFeatures(
        flow_id="192.168.1.100:54321:192.168.1.1:80:TCP",
        timestamp=int(time.time() * 1000),
        src_ip="192.168.1.100",
        dst_ip="192.168.1.1",
        src_port=54321,
        dst_port=80,
        protocol="TCP",
        features=np.random.randn(41).tolist(),
        feature_version="v1.0",
        schema_version=1
    )


@pytest.fixture
def mock_env_vars(dummy_model_path, dummy_label_classes, dummy_config, tmp_path):
    """Set up environment variables for testing"""
    env_vars = {
        'KAFKA_BROKERS': 'localhost:9092',
        'FEATURES_TOPIC': 'test.features',
        'PRED_TOPIC': 'test.predictions',
        'MODEL_PATH': dummy_model_path,
        'LABEL_CLASSES_PATH': dummy_label_classes,
        'CONFIG_PATH': dummy_config,
        'DEVICE': 'cpu',
        'BATCH_SIZE': '32',
        'MAX_BATCH_WAIT_MS': '50',
        'CONFIDENCE_THRESHOLD': '0.5',
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


# ============================================================================
# Model Manager Tests
# ============================================================================

class TestModelManager:
    """Tests for ModelManager class"""
    
    def test_model_loading(self, mock_env_vars):
        """Test model loading from checkpoint"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        assert manager.ready
        assert manager.model is not None
        assert manager.device is not None
        assert manager.num_classes == 15
        assert len(manager.label_classes) == 15
    
    def test_inference_single_sample(self, mock_env_vars):
        """Test inference on single sample"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        # Create sample input
        features = np.random.randn(1, 41).astype(np.float32)
        
        # Run inference
        predictions = manager.predict_batch(features)
        
        assert len(predictions) == 1
        assert 'class_idx' in predictions[0]
        assert 'class_name' in predictions[0]
        assert 'confidence' in predictions[0]
        assert 0.0 <= predictions[0]['confidence'] <= 1.0
        assert 0 <= predictions[0]['class_idx'] < 15
    
    def test_inference_batch(self, mock_env_vars):
        """Test inference on batch"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        # Create batch input
        batch_size = 32
        features = np.random.randn(batch_size, 41).astype(np.float32)
        
        # Run inference
        start_time = time.time()
        predictions = manager.predict_batch(features)
        inference_time = time.time() - start_time
        
        assert len(predictions) == batch_size
        
        # Check performance target (< 100ms for 32 samples on CPU)
        assert inference_time < 0.1, f"Inference took {inference_time:.3f}s, expected < 0.1s"
        
        # Verify all predictions
        for pred in predictions:
            assert 'class_idx' in pred
            assert 'confidence' in pred
            assert 'all_class_probs' in pred
            assert 0.0 <= pred['confidence'] <= 1.0
    
    def test_inference_large_batch(self, mock_env_vars):
        """Test inference throughput on large batch"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        # Test sustained throughput
        batch_size = 128
        num_batches = 10
        total_samples = batch_size * num_batches
        
        start_time = time.time()
        for _ in range(num_batches):
            features = np.random.randn(batch_size, 41).astype(np.float32)
            predictions = manager.predict_batch(features)
            assert len(predictions) == batch_size
        
        total_time = time.time() - start_time
        throughput = total_samples / total_time
        
        # Should achieve > 5k samples/sec on CPU
        assert throughput > 5000, f"Throughput: {throughput:.0f} samples/sec, expected > 5000"
        
        print(f"\nThroughput: {throughput:.0f} samples/sec")
    
    def test_calibration(self, mock_env_vars):
        """Test temperature scaling calibration"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        # Test different temperature values
        features = np.random.randn(10, 41).astype(np.float32)
        
        # Lower temperature should make predictions more confident
        manager.calibration_temp = 0.5
        predictions_low_temp = manager.predict_batch(features)
        
        # Higher temperature should make predictions less confident
        manager.calibration_temp = 2.0
        predictions_high_temp = manager.predict_batch(features)
        
        # Check that calibration affects confidence
        avg_conf_low = np.mean([p['confidence'] for p in predictions_low_temp])
        avg_conf_high = np.mean([p['confidence'] for p in predictions_high_temp])
        
        assert avg_conf_low > avg_conf_high, "Lower temperature should increase confidence"
    
    def test_get_info(self, mock_env_vars):
        """Test model info retrieval"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        info = manager.get_info()
        
        assert info['ready'] is True
        assert 'model_version' in info
        assert 'feature_version' in info
        assert 'num_classes' in info
        assert info['num_classes'] == 15
        assert 'label_classes' in info


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestAPIEndpoints:
    """Tests for FastAPI endpoints"""
    
    @pytest.fixture
    def client(self, mock_env_vars):
        """Create test client"""
        from model.service.app import app
        
        # Create an async mock coroutine for consume_and_infer
        async def mock_consume():
            """Mock coroutine that does nothing"""
            while True:
                await asyncio.sleep(1)
        
        # Mock the lifespan to avoid actual model loading and Kafka
        with patch('model.service.app.model_manager') as mock_model:
            with patch('model.service.app.inference_worker') as mock_worker:
                mock_model.ready = True
                mock_model.device = torch.device('cpu')
                mock_worker.running = True
                # Make consume_and_infer return an actual coroutine
                mock_worker.consume_and_infer = AsyncMock(side_effect=mock_consume)
                
                # Create test client
                with TestClient(app, raise_server_exceptions=False) as test_client:
                    # Patch the global instances for the test
                    app.state.model_manager = mock_model
                    app.state.inference_worker = mock_worker
                    yield test_client
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data['service'] == "Adaptive IDS Model Service"
        assert 'version' in data
    
    def test_health_endpoint_healthy(self, client):
        """Test health endpoint when service is healthy"""
        with patch('model.service.app.model_manager') as mock_model:
            with patch('model.service.app.inference_worker') as mock_worker:
                mock_model.ready = True
                mock_worker.running = True
                
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data['status'] == 'healthy'
    
    def test_health_endpoint_unhealthy(self, client):
        """Test health endpoint when model not ready"""
        with patch('model.service.app.model_manager') as mock_model:
            mock_model.ready = False
            
            response = client.get("/health")
            assert response.status_code == 503
            data = response.json()
            assert data['status'] == 'unhealthy'
    
    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert 'text/plain' in response.headers['content-type']
        
        # Check for expected metrics
        content = response.text
        assert 'ids_inferences_total' in content
        assert 'ids_inference_latency_seconds' in content
    
    def test_model_info_endpoint(self, client):
        """Test model info endpoint"""
        with patch('model.service.app.model_manager') as mock_model:
            mock_model.get_info.return_value = {
                'ready': True,
                'model_version': 'v1.0',
                'num_classes': 15
            }
            
            response = client.get("/model/info")
            assert response.status_code == 200
            data = response.json()
            assert data['ready'] is True
            assert 'model_version' in data
    
    def test_predict_endpoint(self, client, sample_flow_features):
        """Test direct prediction endpoint"""
        with patch('model.service.app.model_manager') as mock_model:
            mock_model.ready = True
            mock_model.predict_batch.return_value = [{
                'class_idx': 0,
                'class_name': 'BENIGN',
                'confidence': 0.95,
                'all_class_probs': {'BENIGN': 0.95, 'DDoS': 0.05},
                'inference_latency_ms': 5.0
            }]
            
            response = client.post("/predict", json=sample_flow_features.to_dict())
            assert response.status_code == 200
            
            data = response.json()
            assert 'class_idx' in data
            assert 'class_name' in data
            assert 'confidence' in data
            assert data['class_name'] == 'BENIGN'


# ============================================================================
# Integration Tests
# ============================================================================

class TestInferenceWorker:
    """Tests for Kafka integration (mocked)"""
    
    @pytest.fixture
    def mock_kafka(self):
        """Mock Kafka consumer and producer"""
        with patch('model.service.app.Consumer') as mock_consumer:
            with patch('model.service.app.Producer') as mock_producer:
                yield mock_consumer, mock_producer
    
    def test_worker_initialization(self, mock_env_vars, mock_kafka):
        """Test worker initialization"""
        from model.service.app import InferenceWorker
        
        worker = InferenceWorker()
        worker.start()
        
        assert worker.running
        assert worker.consumer is not None
        assert worker.producer is not None
    
    def test_batch_processing(self, mock_env_vars):
        """Test micro-batch processing"""
        from model.service.app import InferenceWorker, model_manager
        
        # Load model
        model_manager.load_model()
        
        worker = InferenceWorker()
        
        # Add samples to batch
        for i in range(5):
            flow_features = FlowFeatures(
                flow_id=f"flow_{i}",
                timestamp=int(time.time() * 1000),
                src_ip="192.168.1.100",
                dst_ip="192.168.1.1",
                src_port=54321 + i,
                dst_port=80,
                protocol="TCP",
                features=np.random.randn(41).tolist(),
                feature_version="v1.0"
            )
            worker.batch_buffer.append(flow_features.features)
            worker.batch_metadata.append(flow_features)
        
        # Mock producer
        worker.producer = Mock()
        worker.producer.produce = Mock()
        worker.producer.poll = Mock()
        
        # Process batch synchronously by running the coroutine
        asyncio.run(worker._process_batch())
        
        # Verify batch was processed
        assert len(worker.batch_buffer) == 0
        assert len(worker.batch_metadata) == 0
        assert worker.producer.produce.call_count == 5


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance and latency tests"""
    
    def test_p95_latency(self, mock_env_vars):
        """Test P95 latency < 100ms for batch of 64"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        # Run multiple batches and collect latencies
        batch_size = 64
        num_iterations = 50
        latencies = []
        
        for _ in range(num_iterations):
            features = np.random.randn(batch_size, 41).astype(np.float32)
            
            start_time = time.time()
            predictions = manager.predict_batch(features)
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            latencies.append(latency)
        
        # Calculate P95
        p95_latency = np.percentile(latencies, 95)
        avg_latency = np.mean(latencies)
        
        print(f"\nAvg latency: {avg_latency:.2f}ms")
        print(f"P95 latency: {p95_latency:.2f}ms")
        
        assert p95_latency < 100, f"P95 latency {p95_latency:.2f}ms exceeds 100ms target"
    
    def test_sustained_throughput(self, mock_env_vars):
        """Test sustained throughput > 5k samples/sec"""
        from model.service.app import ModelManager
        
        manager = ModelManager()
        manager.load_model()
        
        # Simulate sustained load
        batch_size = 128
        duration_sec = 5
        total_samples = 0
        
        start_time = time.time()
        while time.time() - start_time < duration_sec:
            features = np.random.randn(batch_size, 41).astype(np.float32)
            predictions = manager.predict_batch(features)
            total_samples += len(predictions)
        
        elapsed = time.time() - start_time
        throughput = total_samples / elapsed
        
        print(f"\nSustained throughput: {throughput:.0f} samples/sec over {elapsed:.1f}s")
        
        assert throughput > 5000, f"Throughput {throughput:.0f} samples/sec below 5k target"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
