"""
Isolation Forest Novelty Detector

Uses sklearn's IsolationForest for fast, scalable novelty detection.
Works well with high-dimensional features and doesn't require normalization.
"""

import numpy as np
import pickle
import json
from pathlib import Path
from typing import Optional
from sklearn.ensemble import IsolationForest
import logging

from .detector import NoveltyDetector

logger = logging.getLogger(__name__)


class IsolationForestDetector(NoveltyDetector):
    """
    Isolation Forest-based novelty detector.
    
    Advantages:
    - Fast training and inference
    - Works well with high-dimensional data
    - No need for normalization
    - Good for real-time detection
    
    The detector learns the structure of normal traffic patterns
    and flags samples that are isolated (novel).
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        contamination: float = 0.01,
        n_estimators: int = 100,
        max_samples: int = 256,
        random_state: int = 42,
        n_jobs: int = -1,
        **kwargs
    ):
        """
        Args:
            threshold: Novelty score threshold (0-1)
            contamination: Expected proportion of outliers in training data
            n_estimators: Number of isolation trees
            max_samples: Samples to draw for each tree
            random_state: Random seed
            n_jobs: Parallel jobs (-1 = all cores)
        """
        super().__init__(
            threshold=threshold,
            name="IsolationForest",
            **kwargs
        )
        
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        self.n_jobs = n_jobs
        
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_samples=max_samples,
            random_state=random_state,
            n_jobs=n_jobs
        )
        
        logger.info(
            f"Initialized IsolationForest with n_estimators={n_estimators}, "
            f"contamination={contamination}"
        )
    
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> 'IsolationForestDetector':
        """
        Fit the Isolation Forest on normal traffic patterns.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Ignored (unsupervised method)
            
        Returns:
            self
        """
        logger.info(f"Fitting IsolationForest on {len(X)} samples...")
        
        self.model.fit(X)
        self.is_fitted = True
        
        # Get some statistics
        train_scores = -self.model.score_samples(X)  # Invert for novelty score
        
        logger.info(
            f"Fitted IsolationForest. Training novelty scores: "
            f"mean={train_scores.mean():.3f}, "
            f"std={train_scores.std():.3f}, "
            f"max={train_scores.max():.3f}"
        )
        
        return self
    
    def predict_novelty(self, X: np.ndarray) -> np.ndarray:
        """
        Predict novelty scores for samples.
        
        Isolation Forest returns anomaly scores (negative of average path length).
        We invert and normalize to [0, 1] where higher = more novel.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Novelty scores (n_samples,) in range [0, 1]
        """
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted before prediction")
        
        # Get raw scores (negative anomaly scores)
        raw_scores = -self.model.score_samples(X)
        
        # Normalize to [0, 1] using sigmoid-like transformation
        # Higher raw score = more anomalous = more novel
        scores = 1 / (1 + np.exp(-raw_scores))
        
        return scores
    
    def save(self, path: str) -> None:
        """
        Save detector state to disk.
        
        Args:
            path: Directory path to save detector
        """
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = save_dir / "isolation_forest.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        # Save metadata
        metadata = {
            'name': self.name,
            'threshold': self.threshold,
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'max_samples': self.max_samples,
            'random_state': self.random_state,
            'is_fitted': self.is_fitted,
            'samples_seen': self.samples_seen,
            'min_samples_fit': self.min_samples_fit
        }
        
        metadata_path = save_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved IsolationForest detector to {save_dir}")
    
    def load(self, path: str) -> 'IsolationForestDetector':
        """
        Load detector state from disk.
        
        Args:
            path: Directory path to load from
            
        Returns:
            self
        """
        load_dir = Path(path)
        
        # Load model
        model_path = load_dir / "isolation_forest.pkl"
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Load metadata
        metadata_path = load_dir / "metadata.json"
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        self.threshold = metadata['threshold']
        self.contamination = metadata['contamination']
        self.n_estimators = metadata['n_estimators']
        self.max_samples = metadata['max_samples']
        self.random_state = metadata['random_state']
        self.is_fitted = metadata['is_fitted']
        self.samples_seen = metadata['samples_seen']
        self.min_samples_fit = metadata['min_samples_fit']
        
        logger.info(f"Loaded IsolationForest detector from {load_dir}")
        
        return self
