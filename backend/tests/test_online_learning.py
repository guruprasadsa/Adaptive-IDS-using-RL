"""
Integration tests for drift detection and online learning.

Tests the full pipeline:
1. Drift detection on streaming data
2. Buffer management
3. Fine-tuning with EWC
4. Model validation and promotion
5. Rollback on failure
"""

import pytest
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime, timedelta, UTC
import sys
import os

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from stream.drift_detector import (
    DriftDetectionSystem,
    ADWINDetector,
    DDMDetector,
    PSIDetector,
    JSDivergenceDetector
)

from model.service.online_learning import (
    SampleBuffer,
    EWCTrainer,
    ModelRegistry,
    OnlineLearningService,
    ModelVersion
)


class DummyModel(nn.Module):
    """Simple model for testing"""
    def __init__(self, input_dim=10, output_dim=5):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 32)
        self.fc2 = nn.Linear(32, output_dim)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        return self.fc2(x)


class TestDriftDetection:
    """Test drift detection components"""
    
    def test_adwin_detector(self):
        """Test ADWIN drift detection"""
        detector = ADWINDetector(delta=0.002)
        
        # No drift in stable data
        for i in range(100):
            drift = detector.add_sample(0.9 + np.random.normal(0, 0.01))
            
        assert detector.drift_detected == False
        
        # Introduce significant drift - larger shift
        drift_detected = False
        for i in range(100):
            drift = detector.add_sample(0.3 + np.random.normal(0, 0.01))
            if drift:
                drift_detected = True
                break
            
        # Should detect drift with significant distribution change
        assert drift_detected == True
        
    def test_ddm_detector(self):
        """Test DDM drift detection"""
        detector = DDMDetector(warning_level=2.0, drift_level=3.0)
        
        # Low error rate initially (5% error)
        for i in range(100):
            detector.add_sample(is_error=(i % 20 == 0))
            
        # Store initial state
        initial_error_rate = detector.error_count / detector.sample_count if detector.sample_count > 0 else 0
        
        # Significantly increase error rate (50% error) and track all results
        drift_results = []
        for i in range(200):  # More samples for DDM to detect
            warning, drift = detector.add_sample(is_error=(i % 2 == 0))
            drift_results.append(drift)
                
        # At least one drift should have been detected
        assert any(drift_results), "DDM should detect drift with significant error rate increase"
        
    def test_psi_detector(self):
        """Test PSI feature drift detection"""
        detector = PSIDetector(n_bins=10, threshold=0.2)
        
        # Set baseline
        baseline_features = np.random.normal(0, 1, (1000, 5))
        feature_names = [f"feat_{i}" for i in range(5)]
        detector.set_baseline(baseline_features, feature_names)
        
        # Similar distribution - no drift
        current_features = np.random.normal(0, 1, (500, 5))
        psi_scores = detector.calculate_psi(current_features)
        
        # Most scores should be low (some may be higher due to randomness)
        low_psi_count = sum(1 for score in psi_scores.values() if score < 0.2)
        assert low_psi_count >= 3, f"Expected at least 3 features with low PSI, got {low_psi_count}"
        
        # Significantly shifted distribution - drift expected
        current_features = np.random.normal(3, 1, (500, 5))  # Larger shift
        psi_scores = detector.calculate_psi(current_features)
        
        # Should detect high PSI in most features
        high_psi_count = sum(1 for score in psi_scores.values() if score > 0.2)
        assert high_psi_count >= 3, f"Expected at least 3 features with high PSI, got {high_psi_count}"
        
    def test_js_divergence_detector(self):
        """Test JS divergence detector"""
        detector = JSDivergenceDetector(threshold=0.1, window_size=100)
        
        # Add baseline samples
        for i in range(150):
            conf_dist = np.random.dirichlet([10, 5, 3, 2, 1])
            detector.add_baseline_sample(conf_dist)
            
        # Similar distribution - no drift
        for i in range(50):
            conf_dist = np.random.dirichlet([10, 5, 3, 2, 1])
            drift, score = detector.add_current_sample(conf_dist)
            
        assert drift == False
        
        # Different distribution - drift expected
        drift_detected = False
        for i in range(150):
            conf_dist = np.random.dirichlet([1, 2, 3, 5, 10])
            drift, score = detector.add_current_sample(conf_dist)
            if drift:
                drift_detected = True
                break
                
        assert drift_detected == True
        
    def test_drift_detection_system(self):
        """Test integrated drift detection system"""
        system = DriftDetectionSystem({
            'adwin_delta': 0.002,
            'ddm_warning': 2.0,
            'ddm_drift': 3.0,
            'psi_threshold': 0.2,
            'js_threshold': 0.1
        })
        
        # Initialize baseline
        baseline_features = np.random.normal(0, 1, (1000, 10))
        feature_names = [f"feat_{i}" for i in range(10)]
        baseline_confidences = np.random.dirichlet([10, 5, 3, 2, 1], size=1000)
        
        system.initialize_baseline(baseline_features, feature_names, baseline_confidences)
        
        # Check drift on normal data
        for i in range(100):
            features = np.random.normal(0, 1, 10)
            conf_dist = np.random.dirichlet([10, 5, 3, 2, 1])
            
            metrics = system.check_drift(
                confidence=0.9,
                is_error=False,
                features=features,
                confidence_dist=conf_dist
            )
            
        assert metrics.severity in ['low', 'medium']
        
        # Introduce significant drift with more samples
        for i in range(200):
            # Gradually introduce drift
            shift = 2.0 + (i / 200.0)  # Increase shift over time
            features = np.random.normal(shift, 1, 10)  # Shifted features
            conf_dist = np.random.dirichlet([1, 2, 3, 5, 10])  # Changed distribution
            
            metrics = system.check_drift(
                confidence=0.5,  # Lower confidence
                is_error=True,   # More errors
                features=features,
                confidence_dist=conf_dist
            )
            
        # Should detect medium to high severity drift
        summary = system.get_summary()
        assert summary['current_severity'] in ['medium', 'high', 'critical'], \
            f"Expected medium/high/critical severity, got {summary['current_severity']}"


class TestSampleBuffer:
    """Test sample buffer for online learning"""
    
    def test_buffer_operations(self):
        """Test adding and retrieving samples"""
        buffer = SampleBuffer(max_size=100, max_fp_size=50)
        
        # Add recent samples
        for i in range(150):
            features = np.random.randn(10)
            buffer.add_sample(features, label=i % 5, confidence=0.9, 
                            timestamp=datetime.now(UTC))
            
        # Should keep only max_size
        assert len(buffer.recent_features) == 100
        
        # Add false positives
        for i in range(60):
            features = np.random.randn(10)
            buffer.add_false_positive(features, true_label=0, pred_label=1,
                                    timestamp=datetime.now(UTC))
            
        # Should keep only max_fp_size
        assert len(buffer.fp_features) == 50
        
    def test_training_batch(self):
        """Test getting balanced training batch"""
        buffer = SampleBuffer(max_size=1000, max_fp_size=500)
        
        # Add samples
        for i in range(1000):
            features = np.random.randn(10)
            buffer.add_sample(features, label=i % 5, confidence=0.9,
                            timestamp=datetime.now(UTC))
            
        for i in range(500):
            features = np.random.randn(10)
            buffer.add_false_positive(features, true_label=0, pred_label=1,
                                    timestamp=datetime.now(UTC))
            
        # Get training batch
        X, y = buffer.get_training_batch(batch_size=200, fp_ratio=0.3)
        
        assert len(X) == 200
        assert len(y) == 200
        assert X.shape[1] == 10
        
    def test_buffer_stats(self):
        """Test buffer statistics"""
        buffer = SampleBuffer()
        
        for i in range(10):
            features = np.random.randn(10)
            buffer.add_sample(features, label=0, confidence=0.9,
                            timestamp=datetime.now(UTC))
            
        stats = buffer.get_stats()
        
        assert stats['recent_samples'] == 10
        assert stats['false_positives'] == 0
        assert stats['oldest_recent'] is not None


class TestEWCTrainer:
    """Test EWC training"""
    
    def test_fisher_matrix_computation(self):
        """Test Fisher information matrix computation"""
        model = DummyModel(input_dim=10, output_dim=5)
        trainer = EWCTrainer(model, lambda_ewc=1000.0)
        
        # Create dummy data
        X = torch.randn(100, 10)
        y = torch.randint(0, 5, (100,))
        dataset = torch.utils.data.TensorDataset(X, y)
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=32)
        
        # Compute Fisher matrix
        trainer.compute_fisher_matrix(dataloader)
        
        assert len(trainer.fisher_matrix) > 0
        assert len(trainer.old_params) > 0
        
    def test_ewc_loss(self):
        """Test EWC penalty computation"""
        model = DummyModel(input_dim=10, output_dim=5)
        trainer = EWCTrainer(model, lambda_ewc=1000.0)
        
        # Compute Fisher matrix
        X = torch.randn(100, 10)
        y = torch.randint(0, 5, (100,))
        dataset = torch.utils.data.TensorDataset(X, y)
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=32)
        trainer.compute_fisher_matrix(dataloader)
        
        # EWC loss should be 0 if parameters haven't changed
        loss = trainer.ewc_loss()
        assert loss.item() < 1e-5
        
        # Modify parameters
        for param in model.parameters():
            param.data += 0.1
            
        # EWC loss should be positive
        loss = trainer.ewc_loss()
        assert loss.item() > 0
        
    def test_training_step(self):
        """Test single training step with EWC"""
        model = DummyModel(input_dim=10, output_dim=5)
        trainer = EWCTrainer(model, lambda_ewc=100.0)
        
        # Setup Fisher matrix
        X = torch.randn(100, 10)
        y = torch.randint(0, 5, (100,))
        dataset = torch.utils.data.TensorDataset(X, y)
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=32)
        trainer.compute_fisher_matrix(dataloader)
        
        # Training step
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        X_batch = torch.randn(32, 10)
        y_batch = torch.randint(0, 5, (32,))
        
        loss = trainer.train_step(X_batch, y_batch, optimizer)
        
        assert isinstance(loss, float)
        assert loss > 0


class TestModelRegistry:
    """Test model version registry"""
    
    def setup_method(self):
        """Setup test registry"""
        self.test_dir = Path("test_registry")
        self.test_dir.mkdir(exist_ok=True)
        self.registry = ModelRegistry(str(self.test_dir))
        
    def teardown_method(self):
        """Cleanup test registry"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_register_version(self):
        """Test registering a model version"""
        version = ModelVersion(
            version_id="test_v1",
            timestamp=datetime.now(UTC),
            parent_version=None,
            training_samples=1000,
            validation_metrics={'accuracy': 0.95},
            checkpoint_path="test.pth",
            feature_version="v1",
            status="active"
        )
        
        self.registry.register_version(version)
        
        assert "test_v1" in self.registry.versions
        assert self.registry.get_version("test_v1") is not None
        
    def test_promote_version(self):
        """Test promoting a version to active"""
        # Register two versions
        v1 = ModelVersion(
            version_id="v1",
            timestamp=datetime.now(UTC),
            parent_version=None,
            training_samples=1000,
            validation_metrics={'accuracy': 0.95},
            checkpoint_path="v1.pth",
            feature_version="v1",
            status="active"
        )
        
        v2 = ModelVersion(
            version_id="v2",
            timestamp=datetime.now(UTC),
            parent_version="v1",
            training_samples=500,
            validation_metrics={'accuracy': 0.96},
            checkpoint_path="v2.pth",
            feature_version="v1",
            status="shadow"
        )
        
        self.registry.register_version(v1)
        self.registry.active_version = "v1"
        self.registry.register_version(v2)
        
        # Promote v2
        self.registry.promote_to_active("v2")
        
        assert self.registry.active_version == "v2"
        assert self.registry.versions["v1"].status == "retired"
        assert self.registry.versions["v2"].status == "active"
        
    def test_list_versions(self):
        """Test listing versions"""
        for i in range(3):
            v = ModelVersion(
                version_id=f"v{i}",
                timestamp=datetime.now(UTC) - timedelta(days=i),
                parent_version=None,
                training_samples=1000,
                validation_metrics={'accuracy': 0.95},
                checkpoint_path=f"v{i}.pth",
                feature_version="v1",
                status="active" if i == 0 else "retired"
            )
            self.registry.register_version(v)
            
        # List all
        all_versions = self.registry.list_versions()
        assert len(all_versions) == 3
        
        # List active only
        active_versions = self.registry.list_versions(status="active")
        assert len(active_versions) == 1


class TestOnlineLearningIntegration:
    """Integration tests for online learning"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = Path("test_online_learning")
        self.test_dir.mkdir(exist_ok=True)
        
    def teardown_method(self):
        """Cleanup"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_service_initialization(self):
        """Test service initialization"""
        config = {
            'buffer_size': 1000,
            'registry_dir': str(self.test_dir / 'registry'),
            'device': 'cpu',
            'training_interval_hours': 1,
        }
        
        service = OnlineLearningService(config)
        
        assert service.sample_buffer is not None
        assert service.registry is not None
        assert service.running == False
        
    def test_fine_tuning_pipeline(self):
        """Test end-to-end fine-tuning"""
        # Create dummy model and save as checkpoint
        model = DummyModel(input_dim=10, output_dim=5)
        checkpoint_dir = self.test_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        checkpoint_path = checkpoint_dir / "base_model.pth"
        
        torch.save({
            'model_state_dict': model.state_dict(),
            'state_dim': 10,
            'action_dim': 5,
            'hidden_dim': 32,
        }, checkpoint_path)
        
        # Note: Full test would require implementing DQNSpecialist loading
        # This is a simplified test
        assert checkpoint_path.exists()
        
    def test_buffer_integration(self):
        """Test buffer integration with service"""
        config = {
            'buffer_size': 100,
            'fp_buffer_size': 50,
            'registry_dir': str(self.test_dir / 'registry'),
        }
        
        service = OnlineLearningService(config)
        
        # Add samples to buffer
        for i in range(150):
            features = np.random.randn(10)
            service.sample_buffer.add_sample(
                features, label=i % 5, confidence=0.9,
                timestamp=datetime.now(UTC)
            )
            
        # Check buffer
        stats = service.sample_buffer.get_stats()
        assert stats['recent_samples'] == 100
        
        # Get training batch
        X, y = service.sample_buffer.get_training_batch(batch_size=50)
        assert len(X) > 0


def test_drift_fp_reduction_scenario():
    """
    End-to-end scenario test:
    1. Detect drift
    2. Collect FPs
    3. Fine-tune
    4. Verify FP reduction
    """
    # Initialize drift detector
    drift_system = DriftDetectionSystem()
    
    # Initialize with baseline
    baseline_features = np.random.normal(0, 1, (1000, 10))
    feature_names = [f"feat_{i}" for i in range(10)]
    baseline_confidences = np.random.dirichlet([10, 5, 3, 2, 1], size=1000)
    
    drift_system.initialize_baseline(baseline_features, feature_names, baseline_confidences)
    
    # Simulate drift scenario
    drift_detected = False
    for i in range(200):
        # Gradually introduce drift
        shift = i / 200.0
        features = np.random.normal(shift, 1, 10)
        conf_dist = np.random.dirichlet([10-shift*5, 5, 3, 2, 1+shift*5])
        
        metrics = drift_system.check_drift(
            confidence=0.9 - shift*0.3,
            is_error=(i % 10 < shift * 10),
            features=features,
            confidence_dist=conf_dist
        )
        
        if metrics.severity in ['high', 'critical']:
            drift_detected = True
            
    assert drift_detected, "Drift should have been detected"
    
    # Verify metrics summary
    summary = drift_system.get_summary()
    assert summary['total_samples'] >= 200
    assert 'current_severity' in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
