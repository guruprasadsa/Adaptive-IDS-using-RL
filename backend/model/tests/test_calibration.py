"""
Unit tests for Calibration Utilities
"""

import pytest
import torch
import numpy as np
import sys
from pathlib import Path
import tempfile
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from model.utils.calibration import (
    TemperatureScaling,
    expected_calibration_error,
    maximum_calibration_error,
    plot_reliability_diagram,
    plot_confidence_histogram,
    evaluate_calibration,
    CalibratedModel
)


class TestTemperatureScaling:
    """Test temperature scaling module"""
    
    def test_initialization(self):
        """Test temperature initialization"""
        temp_scaler = TemperatureScaling(initial_temperature=1.5)
        
        assert temp_scaler.temperature.item() == 1.5
    
    def test_forward_scaling(self):
        """Test forward pass scales logits"""
        temp_scaler = TemperatureScaling(initial_temperature=2.0)
        
        logits = torch.tensor([[2.0, 1.0, 0.5]])
        scaled_logits = temp_scaler(logits)
        
        # Should be divided by temperature
        expected = logits / 2.0
        assert torch.allclose(scaled_logits, expected)
    
    def test_fit_temperature(self):
        """Test temperature fitting"""
        temp_scaler = TemperatureScaling(initial_temperature=1.0)
        
        # Create overconfident predictions
        logits = torch.randn(100, 5) * 3  # High confidence
        labels = torch.randint(0, 5, (100,))
        
        initial_temp = temp_scaler.get_temperature()
        
        temp_scaler.fit(logits, labels, lr=0.01, max_iter=20)
        
        fitted_temp = temp_scaler.get_temperature()
        
        # Temperature should have changed
        assert fitted_temp != initial_temp


class TestECE:
    """Test Expected Calibration Error"""
    
    def test_perfect_calibration(self):
        """Test ECE with perfectly calibrated predictions"""
        n_samples = 1000
        n_classes = 5
        
        # Create perfectly calibrated predictions
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.zeros((n_samples, n_classes))
        
        for i in range(n_samples):
            # Set probability to match label distribution
            probs[i] = np.random.dirichlet(np.ones(n_classes))
            probs[i, labels[i]] += 0.5  # Boost true class
            probs[i] /= probs[i].sum()
        
        ece, bin_boundaries, bin_accuracies, bin_confidences = expected_calibration_error(
            probs, labels, n_bins=10
        )
        
        # ECE should be relatively small for random but somewhat calibrated data
        assert 0 <= ece <= 1.0
        assert len(bin_boundaries) == 11  # n_bins + 1
    
    def test_overconfident_predictions(self):
        """Test ECE with overconfident predictions"""
        n_samples = 500
        n_classes = 3
        
        # Create overconfident but incorrect predictions
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.zeros((n_samples, n_classes))
        
        for i in range(n_samples):
            # High confidence in wrong class (50% of the time)
            if np.random.rand() < 0.5:
                wrong_class = (labels[i] + 1) % n_classes
                probs[i, wrong_class] = 0.95
                probs[i, labels[i]] = 0.025
                probs[i, (wrong_class + 1) % n_classes] = 0.025
            else:
                probs[i, labels[i]] = 0.95
                probs[i, (labels[i] + 1) % n_classes] = 0.025
                probs[i, (labels[i] + 2) % n_classes] = 0.025
        
        ece, _, _, _ = expected_calibration_error(probs, labels, n_bins=10)
        
        # Should have noticeable calibration error
        assert ece > 0


class TestMCE:
    """Test Maximum Calibration Error"""
    
    def test_mce_calculation(self):
        """Test MCE calculation"""
        n_samples = 500
        n_classes = 4
        
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.random.dirichlet(np.ones(n_classes), n_samples)
        
        mce = maximum_calibration_error(probs, labels, n_bins=10)
        
        assert 0 <= mce <= 1.0


class TestPlotting:
    """Test plotting functions"""
    
    def test_plot_reliability_diagram(self):
        """Test reliability diagram generation"""
        n_samples = 500
        n_classes = 5
        
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.random.dirichlet(np.ones(n_classes), n_samples)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, 'reliability.png')
            
            plot_reliability_diagram(
                probs, labels,
                save_path=save_path,
                title='Test Reliability'
            )
            
            # Check file was created
            assert os.path.exists(save_path)
    
    def test_plot_confidence_histogram(self):
        """Test confidence histogram generation"""
        n_samples = 500
        n_classes = 5
        
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.random.dirichlet(np.ones(n_classes), n_samples)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, 'confidence_hist.png')
            
            plot_confidence_histogram(
                probs, labels,
                save_path=save_path,
                title='Test Confidence'
            )
            
            # Check file was created
            assert os.path.exists(save_path)


class TestEvaluateCalibration:
    """Test comprehensive calibration evaluation"""
    
    def test_evaluate_calibration(self):
        """Test full calibration evaluation"""
        n_samples = 500
        n_classes = 5
        
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.random.dirichlet(np.ones(n_classes), n_samples)
        
        # Test without saving
        metrics = evaluate_calibration(probs, labels)
        
        assert 'ece' in metrics
        assert 'mce' in metrics
        assert 'accuracy' in metrics
        assert 'avg_confidence' in metrics
        assert 'calibration_gap' in metrics
        
        assert 0 <= metrics['ece'] <= 1.0
        assert 0 <= metrics['mce'] <= 1.0
        assert 0 <= metrics['accuracy'] <= 1.0
        assert 0 <= metrics['avg_confidence'] <= 1.0
    
    def test_evaluate_calibration_with_plots(self):
        """Test calibration evaluation with plot generation"""
        n_samples = 500
        n_classes = 5
        
        labels = np.random.randint(0, n_classes, n_samples)
        probs = np.random.dirichlet(np.ones(n_classes), n_samples)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = evaluate_calibration(
                probs, labels,
                save_dir=tmpdir,
                prefix='test_'
            )
            
            # Check plots were created
            assert os.path.exists(os.path.join(tmpdir, 'test_reliability_diagram.png'))
            assert os.path.exists(os.path.join(tmpdir, 'test_confidence_histogram.png'))


class TestCalibratedModel:
    """Test calibrated model wrapper"""
    
    def test_initialization(self):
        """Test calibrated model initialization"""
        # Create dummy model
        model = torch.nn.Linear(10, 5)
        temp_scaler = TemperatureScaling(initial_temperature=1.5)
        
        calibrated_model = CalibratedModel(model, temp_scaler)
        
        assert calibrated_model.model is model
        assert calibrated_model.temperature_scaler is temp_scaler
    
    def test_forward_pass(self):
        """Test forward pass through calibrated model"""
        model = torch.nn.Linear(10, 5)
        temp_scaler = TemperatureScaling(initial_temperature=2.0)
        
        calibrated_model = CalibratedModel(model, temp_scaler)
        
        x = torch.randn(32, 10)
        scaled_logits = calibrated_model(x)
        
        # Get unscaled logits
        with torch.no_grad():
            unscaled_logits = model(x)
        
        # Scaled should be unscaled / temperature
        expected = unscaled_logits / 2.0
        assert torch.allclose(scaled_logits, expected)
    
    def test_get_probabilities(self):
        """Test probability extraction"""
        model = torch.nn.Linear(10, 5)
        temp_scaler = TemperatureScaling(initial_temperature=2.0)
        
        calibrated_model = CalibratedModel(model, temp_scaler)
        
        x = torch.randn(32, 10)
        probs = calibrated_model.get_probabilities(x)
        
        assert probs.shape == (32, 5)
        
        # Probabilities should sum to 1
        prob_sums = probs.sum(dim=1)
        assert torch.allclose(prob_sums, torch.ones(32), atol=1e-5)
        
        # All probabilities should be in [0, 1]
        assert (probs >= 0).all()
        assert (probs <= 1).all()


class TestIntegration:
    """Integration tests for calibration workflow"""
    
    def test_calibration_workflow(self):
        """Test complete calibration workflow"""
        # Create model
        model = torch.nn.Sequential(
            torch.nn.Linear(10, 20),
            torch.nn.ReLU(),
            torch.nn.Linear(20, 5)
        )
        
        # Generate validation data
        val_logits = model(torch.randn(200, 10))
        val_labels = torch.randint(0, 5, (200,))
        
        # Fit temperature
        temp_scaler = TemperatureScaling(initial_temperature=1.0)
        temp_scaler.fit(val_logits, val_labels, lr=0.01, max_iter=20)
        
        # Create calibrated model
        calibrated_model = CalibratedModel(model, temp_scaler)
        
        # Get test predictions
        test_data = torch.randn(100, 10)
        test_labels = torch.randint(0, 5, (100,))
        
        probs = calibrated_model.get_probabilities(test_data).detach().numpy()
        
        # Evaluate calibration
        metrics = evaluate_calibration(probs, test_labels.numpy())
        
        assert 'ece' in metrics
        assert 'accuracy' in metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
