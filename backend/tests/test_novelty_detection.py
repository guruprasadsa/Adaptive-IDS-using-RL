"""
Tests for Novelty Detection System

Tests:
- IsolationForest detector
- Autoencoder detector
- Novelty integration
- Review queue workflow
- Specialist scaffolding
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import pytest
import numpy as np
import tempfile
import shutil
from datetime import datetime, UTC
import json

from model.novelty.detector import NoveltyDetector, NoveltyResult
from model.novelty.isolation_forest import IsolationForestDetector
from model.novelty.autoencoder import AutoencoderDetector
from model.novelty.integration import NoveltyIntegration, create_novelty_detector
from model.novelty.scaffold_specialist import SpecialistScaffolder


class TestNoveltyDetectors:
    """Test novelty detection algorithms."""
    
    @pytest.fixture
    def normal_data(self):
        """Generate normal traffic features."""
        np.random.seed(42)
        # Normal traffic: centered around [0.5, 0.5, ...] with small variance
        return np.random.normal(0.5, 0.1, (1000, 85))
    
    @pytest.fixture
    def novel_data(self):
        """Generate novel attack patterns."""
        np.random.seed(43)
        # Novel traffic: different distribution
        return np.random.normal(0.8, 0.15, (100, 85))
    
    def test_isolation_forest_detector(self, normal_data, novel_data):
        """Test IsolationForest novelty detection."""
        # Create and train detector
        detector = IsolationForestDetector(
            threshold=0.5,
            contamination=0.01,
            n_estimators=50,
            random_state=42
        )
        
        assert not detector.is_fitted
        
        # Fit on normal data
        detector.fit(normal_data)
        assert detector.is_fitted
        
        # Test on normal data (should have low novelty scores)
        normal_scores = detector.predict_novelty(normal_data[:100])
        assert len(normal_scores) == 100
        assert 0 <= normal_scores.min() <= normal_scores.max() <= 1
        assert normal_scores.mean() < 0.65  # Most should be normal (relaxed threshold)
        
        # Test on novel data (should have high novelty scores)
        novel_scores = detector.predict_novelty(novel_data)
        assert len(novel_scores) == 100
        assert novel_scores.mean() > normal_scores.mean()  # Novel should score higher
        
        # Test detection with threshold
        results = detector.detect(novel_data[:10])
        assert len(results) == 10
        assert all(isinstance(r, NoveltyResult) for r in results)
        
        # At least some should be flagged as novel
        novel_count = sum(1 for r in results if r.is_novel)
        assert novel_count > 0
        
        print(f"IsolationForest: {novel_count}/10 samples flagged as novel")
    
    def test_autoencoder_detector(self, normal_data, novel_data):
        """Test Autoencoder novelty detection."""
        # Create and train detector
        detector = AutoencoderDetector(
            threshold=0.5,
            encoding_dims=[32, 16],
            epochs=10,  # Quick training for test
            batch_size=64,
            device='cpu'
        )
        
        assert not detector.is_fitted
        
        # Fit on normal data
        detector.fit(normal_data)
        assert detector.is_fitted
        assert detector.model is not None
        assert len(detector.train_loss_history) == 10
        
        # Test on normal data
        normal_scores = detector.predict_novelty(normal_data[:100])
        assert len(normal_scores) == 100
        assert 0 <= normal_scores.min() <= normal_scores.max() <= 1
        
        # Test on novel data
        novel_scores = detector.predict_novelty(novel_data)
        assert len(novel_scores) == 100
        assert novel_scores.mean() > normal_scores.mean()
        
        # Test detection
        results = detector.detect(novel_data[:10])
        assert len(results) == 10
        novel_count = sum(1 for r in results if r.is_novel)
        assert novel_count > 0
        
        print(f"Autoencoder: {novel_count}/10 samples flagged as novel")
    
    def test_detector_save_load_isolation_forest(self, normal_data, tmp_path):
        """Test IsolationForest save/load."""
        # Train detector
        detector1 = IsolationForestDetector(threshold=0.6, random_state=42)
        detector1.fit(normal_data)
        
        # Get predictions
        scores1 = detector1.predict_novelty(normal_data[:10])
        
        # Save
        save_dir = tmp_path / "detector"
        detector1.save(str(save_dir))
        
        assert (save_dir / "isolation_forest.pkl").exists()
        assert (save_dir / "metadata.json").exists()
        
        # Load
        detector2 = IsolationForestDetector()
        detector2.load(str(save_dir))
        
        # Should produce same predictions
        scores2 = detector2.predict_novelty(normal_data[:10])
        np.testing.assert_array_almost_equal(scores1, scores2, decimal=5)
    
    def test_detector_save_load_autoencoder(self, normal_data, tmp_path):
        """Test Autoencoder save/load."""
        # Train detector
        detector1 = AutoencoderDetector(
            threshold=0.6,
            epochs=5,
            device='cpu'
        )
        detector1.fit(normal_data)
        
        # Get predictions
        scores1 = detector1.predict_novelty(normal_data[:10])
        
        # Save
        save_dir = tmp_path / "detector"
        detector1.save(str(save_dir))
        
        assert (save_dir / "autoencoder.pt").exists()
        assert (save_dir / "metadata.json").exists()
        
        # Load
        detector2 = AutoencoderDetector()
        detector2.load(str(save_dir))
        
        # Should produce same predictions
        scores2 = detector2.predict_novelty(normal_data[:10])
        np.testing.assert_array_almost_equal(scores1, scores2, decimal=4)


class TestNoveltyIntegration:
    """Test novelty detection integration."""
    
    @pytest.fixture
    def detector(self):
        """Create fitted detector."""
        np.random.seed(42)
        normal_data = np.random.normal(0.5, 0.1, (500, 85))
        
        detector = IsolationForestDetector(threshold=0.5, random_state=42)
        detector.fit(normal_data)
        return detector
    
    @pytest.fixture
    def temp_review_queue(self, tmp_path):
        """Temporary review queue directory."""
        return tmp_path / "review_queue"
    
    def test_novelty_integration_init(self, detector, temp_review_queue):
        """Test integration initialization."""
        integration = NoveltyIntegration(
            detector=detector,
            review_queue_path=str(temp_review_queue),
            enable_auto_specialist=False
        )
        
        assert integration.detector == detector
        assert integration.review_queue_path.exists()
        assert integration.stats['total_checked'] == 0
    
    def test_check_novelty(self, detector, temp_review_queue):
        """Test novelty checking."""
        integration = NoveltyIntegration(
            detector=detector,
            review_queue_path=str(temp_review_queue)
        )
        
        # Generate test data
        np.random.seed(44)
        normal_features = np.random.normal(0.5, 0.1, (50, 85))
        novel_features = np.random.normal(0.9, 0.2, (10, 85))
        
        # Check normal data
        results, novel_indices = integration.check_novelty(normal_features)
        assert len(results) == 50
        assert integration.stats['total_checked'] == 50
        
        # Check novel data
        results, novel_indices = integration.check_novelty(novel_features)
        assert len(results) == 10
        assert len(novel_indices) > 0  # Should detect some novel samples
        assert integration.stats['total_checked'] == 60
        assert integration.stats['novel_detected'] >= len(novel_indices)
    
    def test_route_to_review_queue(self, detector, temp_review_queue):
        """Test routing to review queue."""
        integration = NoveltyIntegration(
            detector=detector,
            review_queue_path=str(temp_review_queue)
        )
        
        # Generate novel data
        np.random.seed(45)
        features = np.random.normal(0.9, 0.2, (20, 85))
        
        # Detect novelty
        results, novel_indices = integration.check_novelty(
            features,
            flow_ids=np.array([f"flow_{i}" for i in range(20)])
        )
        
        # Route to queue
        if novel_indices:
            review_file = integration.route_to_review_queue(
                features, results, novel_indices
            )
            
            assert review_file is not None
            assert Path(review_file).exists()
            
            # Verify file content
            with open(review_file, 'r') as f:
                data = json.load(f)
            
            assert 'timestamp' in data
            assert 'samples' in data
            assert len(data['samples']) == len(novel_indices)
            assert all(not s['reviewed'] for s in data['samples'])
            assert all(s['label'] is None for s in data['samples'])
            
            print(f"Routed {len(novel_indices)} samples to {review_file}")
    
    def test_create_detector_factory(self):
        """Test detector factory function."""
        # IsolationForest
        detector1 = create_novelty_detector(
            "isolation_forest",
            {"threshold": 0.6, "n_estimators": 50}
        )
        assert isinstance(detector1, IsolationForestDetector)
        assert detector1.threshold == 0.6
        
        # Autoencoder
        detector2 = create_novelty_detector(
            "autoencoder",
            {"threshold": 0.7, "epochs": 10}
        )
        assert isinstance(detector2, AutoencoderDetector)
        assert detector2.threshold == 0.7
        
        # Unknown type
        with pytest.raises(ValueError):
            create_novelty_detector("unknown_type")


class TestSpecialistScaffolder:
    """Test specialist scaffolding tool."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure."""
        project_root = tmp_path / "project"
        specialists_dir = project_root / "backend" / "model" / "specialists"
        specialists_dir.mkdir(parents=True)
        return project_root
    
    def test_scaffolder_init(self, temp_project):
        """Test scaffolder initialization."""
        scaffolder = SpecialistScaffolder(project_root=str(temp_project))
        assert scaffolder.project_root == temp_project
        assert scaffolder.specialists_dir.exists()
    
    def test_create_specialist(self, temp_project):
        """Test specialist creation."""
        scaffolder = SpecialistScaffolder(project_root=str(temp_project))
        
        specialist_dir = scaffolder.create_specialist(
            attack_class="dns_tunneling",
            description="Detects DNS tunneling attacks",
            state_dim=85,
            action_dim=4,
            hidden_dims=[128, 64],
            learning_rate=0.0001
        )
        
        # Verify directory structure
        assert specialist_dir.exists()
        assert (specialist_dir / "config.yaml").exists()
        assert (specialist_dir / "train.py").exists()
        assert (specialist_dir / "README.md").exists()
        assert (specialist_dir / "metadata.json").exists()
        assert (specialist_dir / "models").exists()
        
        # Verify config content
        import yaml
        with open(specialist_dir / "config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        assert config['specialist']['name'] == 'dns_tunneling'
        assert config['model']['state_dim'] == 85
        assert config['model']['hidden_dims'] == [128, 64]
        assert config['model']['learning_rate'] == 0.0001
        
        # Verify metadata
        with open(specialist_dir / "metadata.json", 'r') as f:
            metadata = json.load(f)
        
        assert metadata['attack_class'] == 'dns_tunneling'
        assert metadata['status'] == 'untrained'
        assert 'created_at' in metadata
        
        print(f"Created specialist at {specialist_dir}")
    
    def test_sanitize_name(self, temp_project):
        """Test name sanitization."""
        scaffolder = SpecialistScaffolder(project_root=str(temp_project))
        
        assert scaffolder._sanitize_name("SQL Injection") == "sql_injection"
        assert scaffolder._sanitize_name("DNS-Tunneling") == "dns_tunneling"
        assert scaffolder._sanitize_name("Cross Site Scripting") == "cross_site_scripting"
        assert scaffolder._sanitize_name("  test__attack  ") == "test_attack"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
