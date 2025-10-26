"""
Drift Detection Module

Implements multiple drift detection algorithms:
- ADWIN (Adaptive Windowing) for confidence drift
- DDM (Drift Detection Method) for performance drift
- PSI (Population Stability Index) for feature drift
- JS Divergence for distribution drift

Exposes Prometheus metrics for monitoring and alerting.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
import logging
from prometheus_client import Gauge, Counter, Histogram
from scipy.stats import entropy
from scipy.spatial.distance import jensenshannon

logger = logging.getLogger(__name__)


# Prometheus metrics
drift_score_gauge = Gauge(
    'ids_drift_score',
    'Current drift score by detector type',
    ['detector_type']
)

drift_alert_counter = Counter(
    'ids_drift_alerts_total',
    'Total number of drift alerts triggered',
    ['detector_type', 'severity']
)

feature_psi_gauge = Gauge(
    'ids_feature_psi',
    'PSI score per feature',
    ['feature_name']
)

confidence_drift_gauge = Gauge(
    'ids_confidence_drift',
    'Confidence distribution drift score'
)


@dataclass
class DriftMetrics:
    """Container for drift detection metrics"""
    timestamp: datetime
    adwin_drift: bool
    ddm_drift: bool
    psi_drift: bool
    js_drift: bool
    adwin_score: float
    ddm_score: float
    psi_scores: Dict[str, float]
    js_score: float
    severity: str  # 'low', 'medium', 'high', 'critical'


class ADWINDetector:
    """
    Adaptive Windowing drift detector for confidence scores.
    Detects changes in data distribution by maintaining dynamic windows.
    """
    
    def __init__(self, delta: float = 0.002):
        """
        Args:
            delta: Confidence parameter (smaller = more sensitive)
        """
        self.delta = delta
        self.window = deque(maxlen=1000)
        self.drift_detected = False
        self.drift_score = 0.0
        
    def add_sample(self, value: float) -> bool:
        """
        Add a new sample and check for drift.
        
        Args:
            value: Confidence score or metric value
            
        Returns:
            True if drift detected
        """
        self.window.append(value)
        
        if len(self.window) < 10:
            return False
            
        # Split window and compare distributions
        n = len(self.window)
        window_array = np.array(self.window)
        
        # Test multiple split points
        drift_detected = False
        max_diff = 0.0
        
        for i in range(5, n - 5):
            w1 = window_array[:i]
            w2 = window_array[i:]
            
            # Compute means and variances
            mean1, mean2 = np.mean(w1), np.mean(w2)
            var1, var2 = np.var(w1), np.var(w2)
            
            # ADWIN test statistic
            n1, n2 = len(w1), len(w2)
            m = 1.0 / (1.0 / n1 + 1.0 / n2)
            
            epsilon_cut = np.sqrt((2.0 / m) * np.log(2.0 / self.delta))
            
            diff = abs(mean1 - mean2)
            max_diff = max(max_diff, diff)
            
            if diff > epsilon_cut:
                drift_detected = True
                # Clear old data when drift detected
                self.window = deque(list(window_array[i:]), maxlen=1000)
                break
        
        self.drift_detected = drift_detected
        self.drift_score = max_diff
        
        if drift_detected:
            logger.warning(f"ADWIN drift detected! Score: {max_diff:.4f}")
            drift_alert_counter.labels(
                detector_type='adwin',
                severity='high' if max_diff > 0.5 else 'medium'
            ).inc()
        
        drift_score_gauge.labels(detector_type='adwin').set(max_diff)
        
        return drift_detected


class DDMDetector:
    """
    Drift Detection Method - monitors error rate and variance.
    Useful for detecting performance degradation.
    """
    
    def __init__(self, warning_level: float = 2.0, drift_level: float = 3.0):
        """
        Args:
            warning_level: Standard deviations for warning threshold
            drift_level: Standard deviations for drift threshold
        """
        self.warning_level = warning_level
        self.drift_level = drift_level
        
        self.error_count = 0
        self.sample_count = 0
        self.min_error_rate = float('inf')
        self.min_std = float('inf')
        
        self.in_warning = False
        self.drift_detected = False
        self.drift_score = 0.0
        
    def add_sample(self, is_error: bool) -> Tuple[bool, bool]:
        """
        Add a new sample (correct or error).
        
        Args:
            is_error: True if prediction was incorrect
            
        Returns:
            (warning_detected, drift_detected)
        """
        self.sample_count += 1
        if is_error:
            self.error_count += 1
            
        if self.sample_count < 30:
            return False, False
            
        # Calculate error rate and standard deviation
        error_rate = self.error_count / self.sample_count
        std = np.sqrt(error_rate * (1 - error_rate) / self.sample_count)
        
        # Update minimum values
        if error_rate + std < self.min_error_rate + self.min_std:
            self.min_error_rate = error_rate
            self.min_std = std
            
        # Calculate drift score (standard deviations from minimum)
        if self.min_std > 0:
            self.drift_score = (error_rate - self.min_error_rate) / self.min_std
        else:
            self.drift_score = 0.0
            
        # Check thresholds
        self.in_warning = self.drift_score > self.warning_level
        self.drift_detected = self.drift_score > self.drift_level
        
        # Store return values before potential reset
        warning_to_return = self.in_warning
        drift_to_return = self.drift_detected
        
        if self.drift_detected:
            logger.warning(f"DDM drift detected! Score: {self.drift_score:.2f}σ")
            drift_alert_counter.labels(
                detector_type='ddm',
                severity='critical'
            ).inc()
            # Reset after drift
            self.reset()
        elif self.in_warning:
            logger.info(f"DDM warning level reached: {self.drift_score:.2f}σ")
            
        drift_score_gauge.labels(detector_type='ddm').set(self.drift_score)
        
        return warning_to_return, drift_to_return
        
    def reset(self):
        """Reset detector state"""
        self.error_count = 0
        self.sample_count = 0
        self.min_error_rate = float('inf')
        self.min_std = float('inf')
        self.in_warning = False
        self.drift_detected = False


class PSIDetector:
    """
    Population Stability Index detector for feature drift.
    Compares current distribution against baseline.
    """
    
    def __init__(self, n_bins: int = 10, threshold: float = 0.2):
        """
        Args:
            n_bins: Number of bins for histogram
            threshold: PSI threshold (0.1=small, 0.2=medium, 0.25+=large drift)
        """
        self.n_bins = n_bins
        self.threshold = threshold
        self.baseline_dist: Optional[np.ndarray] = None
        self.bin_edges: Optional[np.ndarray] = None
        self.feature_names: List[str] = []
        
    def set_baseline(self, features: np.ndarray, feature_names: List[str]):
        """
        Set baseline distribution from reference data.
        
        Args:
            features: (n_samples, n_features) array
            feature_names: Names of features
        """
        self.feature_names = feature_names
        n_features = features.shape[1]
        
        self.baseline_dist = []
        self.bin_edges = []
        
        for i in range(n_features):
            # Create histogram bins
            hist, edges = np.histogram(features[:, i], bins=self.n_bins)
            # Add small epsilon to avoid division by zero
            hist = hist + 1e-10
            hist = hist / hist.sum()
            
            self.baseline_dist.append(hist)
            self.bin_edges.append(edges)
            
        self.baseline_dist = np.array(self.baseline_dist)
        logger.info(f"PSI baseline set for {n_features} features")
        
    def calculate_psi(self, current_features: np.ndarray) -> Dict[str, float]:
        """
        Calculate PSI for each feature.
        
        Args:
            current_features: (n_samples, n_features) array
            
        Returns:
            Dictionary of feature_name -> PSI score
        """
        if self.baseline_dist is None:
            raise ValueError("Baseline not set. Call set_baseline first.")
            
        psi_scores = {}
        
        for i in range(current_features.shape[1]):
            # Get current distribution
            current_hist, _ = np.histogram(
                current_features[:, i],
                bins=self.bin_edges[i]
            )
            current_hist = current_hist + 1e-10
            current_hist = current_hist / current_hist.sum()
            
            # Calculate PSI
            baseline = self.baseline_dist[i]
            psi = np.sum((current_hist - baseline) * np.log(current_hist / baseline))
            
            feature_name = self.feature_names[i] if i < len(self.feature_names) else f"feature_{i}"
            psi_scores[feature_name] = float(psi)
            
            # Update Prometheus metric
            feature_psi_gauge.labels(feature_name=feature_name).set(psi)
            
            # Alert on high drift
            if psi > self.threshold:
                logger.warning(f"High PSI for {feature_name}: {psi:.4f}")
                drift_alert_counter.labels(
                    detector_type='psi',
                    severity='high' if psi > 0.25 else 'medium'
                ).inc()
                
        return psi_scores


class JSDivergenceDetector:
    """
    Jensen-Shannon Divergence detector for distribution drift.
    More symmetric and bounded version of KL divergence.
    """
    
    def __init__(self, threshold: float = 0.1, window_size: int = 1000):
        """
        Args:
            threshold: JS divergence threshold (0-1, sqrt of JS distance)
            window_size: Size of sliding window
        """
        self.threshold = threshold
        self.window_size = window_size
        self.baseline_window = deque(maxlen=window_size)
        self.current_window = deque(maxlen=window_size)
        self.is_baseline_set = False
        
    def add_baseline_sample(self, confidence_dist: np.ndarray):
        """Add sample to baseline window"""
        self.baseline_window.append(confidence_dist)
        if len(self.baseline_window) >= self.window_size // 2:
            self.is_baseline_set = True
            
    def add_current_sample(self, confidence_dist: np.ndarray) -> Tuple[bool, float]:
        """
        Add sample to current window and check for drift.
        
        Args:
            confidence_dist: Confidence distribution (e.g., softmax output)
            
        Returns:
            (drift_detected, js_score)
        """
        if not self.is_baseline_set:
            return False, 0.0
            
        self.current_window.append(confidence_dist)
        
        if len(self.current_window) < 100:
            return False, 0.0
            
        # Aggregate distributions
        baseline_agg = np.mean(self.baseline_window, axis=0) + 1e-10
        baseline_agg = baseline_agg / baseline_agg.sum()
        
        current_agg = np.mean(self.current_window, axis=0) + 1e-10
        current_agg = current_agg / current_agg.sum()
        
        # Calculate JS divergence
        js_score = jensenshannon(baseline_agg, current_agg)
        
        drift_detected = js_score > self.threshold
        
        if drift_detected:
            logger.warning(f"JS divergence drift detected: {js_score:.4f}")
            drift_alert_counter.labels(
                detector_type='js_divergence',
                severity='high' if js_score > 0.2 else 'medium'
            ).inc()
            # Update baseline to current window
            self.baseline_window = deque(list(self.current_window), maxlen=self.window_size)
            self.current_window.clear()
            
        confidence_drift_gauge.set(js_score)
        
        return drift_detected, float(js_score)


class DriftDetectionSystem:
    """
    Unified drift detection system combining multiple detectors.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: Configuration dict with detector parameters
        """
        config = config or {}
        
        # Initialize detectors
        self.adwin = ADWINDetector(
            delta=config.get('adwin_delta', 0.002)
        )
        
        self.ddm = DDMDetector(
            warning_level=config.get('ddm_warning', 2.0),
            drift_level=config.get('ddm_drift', 3.0)
        )
        
        self.psi = PSIDetector(
            n_bins=config.get('psi_bins', 10),
            threshold=config.get('psi_threshold', 0.2)
        )
        
        self.js = JSDivergenceDetector(
            threshold=config.get('js_threshold', 0.1),
            window_size=config.get('js_window', 1000)
        )
        
        self.metrics_history: List[DriftMetrics] = []
        
    def initialize_baseline(self, features: np.ndarray, feature_names: List[str],
                          confidences: np.ndarray):
        """
        Initialize baseline distributions.
        
        Args:
            features: Baseline feature matrix
            feature_names: Feature names
            confidences: Baseline confidence distributions
        """
        self.psi.set_baseline(features, feature_names)
        
        for conf in confidences:
            self.js.add_baseline_sample(conf)
            
        logger.info("Drift detection baseline initialized")
        
    def check_drift(self, confidence: float, is_error: bool,
                   features: Optional[np.ndarray] = None,
                   confidence_dist: Optional[np.ndarray] = None) -> DriftMetrics:
        """
        Check for drift across all detectors.
        
        Args:
            confidence: Prediction confidence score
            is_error: Whether prediction was incorrect
            features: Feature vector (for PSI)
            confidence_dist: Full confidence distribution (for JS)
            
        Returns:
            DriftMetrics object
        """
        # ADWIN on confidence scores
        adwin_drift = self.adwin.add_sample(confidence)
        
        # DDM on errors
        _, ddm_drift = self.ddm.add_sample(is_error)
        
        # PSI on features (if provided)
        psi_drift = False
        psi_scores = {}
        if features is not None and self.psi.baseline_dist is not None:
            psi_scores = self.psi.calculate_psi(features.reshape(1, -1))
            psi_drift = any(score > self.psi.threshold for score in psi_scores.values())
            
        # JS divergence on confidence distributions
        js_drift = False
        js_score = 0.0
        if confidence_dist is not None:
            js_drift, js_score = self.js.add_current_sample(confidence_dist)
            
        # Determine overall severity
        drift_count = sum([adwin_drift, ddm_drift, psi_drift, js_drift])
        if drift_count >= 3:
            severity = 'critical'
        elif drift_count == 2:
            severity = 'high'
        elif drift_count == 1:
            severity = 'medium'
        else:
            severity = 'low'
            
        metrics = DriftMetrics(
            timestamp=datetime.now(UTC),
            adwin_drift=adwin_drift,
            ddm_drift=ddm_drift,
            psi_drift=psi_drift,
            js_drift=js_drift,
            adwin_score=self.adwin.drift_score,
            ddm_score=self.ddm.drift_score,
            psi_scores=psi_scores,
            js_score=js_score,
            severity=severity
        )
        
        self.metrics_history.append(metrics)
        
        # Keep only recent history
        if len(self.metrics_history) > 10000:
            self.metrics_history = self.metrics_history[-5000:]
            
        return metrics
        
    def get_summary(self) -> Dict:
        """Get summary of recent drift metrics"""
        if not self.metrics_history:
            return {}
            
        recent = self.metrics_history[-100:]
        
        return {
            'total_samples': len(self.metrics_history),
            'recent_samples': len(recent),
            'adwin_drift_rate': sum(m.adwin_drift for m in recent) / len(recent),
            'ddm_drift_rate': sum(m.ddm_drift for m in recent) / len(recent),
            'psi_drift_rate': sum(m.psi_drift for m in recent) / len(recent),
            'js_drift_rate': sum(m.js_drift for m in recent) / len(recent),
            'current_severity': recent[-1].severity,
            'avg_adwin_score': np.mean([m.adwin_score for m in recent]),
            'avg_ddm_score': np.mean([m.ddm_score for m in recent]),
            'avg_js_score': np.mean([m.js_score for m in recent]),
        }
