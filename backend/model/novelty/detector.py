"""
Base Novelty Detector Interface

Provides abstract base class for novelty detection methods.
"""

import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


@dataclass
class NoveltyResult:
    """Result from novelty detection"""
    is_novel: bool
    novelty_score: float  # Higher = more novel
    confidence: float  # Detector's confidence in the score
    timestamp: datetime
    flow_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class NoveltyDetector(ABC):
    """
    Abstract base class for novelty detectors.
    
    Detectors identify patterns that don't fit any known specialist agent,
    flagging them for review and potential new specialist creation.
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        min_samples_fit: int = 1000,
        name: str = "NoveltyDetector"
    ):
        """
        Args:
            threshold: Novelty score threshold (0-1, higher = stricter)
            min_samples_fit: Minimum samples needed before detection is reliable
            name: Detector name for logging
        """
        self.threshold = threshold
        self.min_samples_fit = min_samples_fit
        self.name = name
        self.is_fitted = False
        self.samples_seen = 0
        
        logger.info(f"Initialized {self.name} with threshold={threshold}")
    
    @abstractmethod
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> 'NoveltyDetector':
        """
        Fit the detector on normal (known) traffic patterns.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Optional labels (for semi-supervised methods)
            
        Returns:
            self
        """
        pass
    
    @abstractmethod
    def predict_novelty(self, X: np.ndarray) -> np.ndarray:
        """
        Predict novelty scores for samples.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Novelty scores (n_samples,) - higher = more novel
        """
        pass
    
    def detect(
        self,
        X: np.ndarray,
        flow_ids: Optional[np.ndarray] = None
    ) -> list[NoveltyResult]:
        """
        Detect novelty in samples and return structured results.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            flow_ids: Optional flow identifiers
            
        Returns:
            List of NoveltyResult objects
        """
        if not self.is_fitted:
            logger.warning(f"{self.name} not fitted, cannot detect novelty")
            return [
                NoveltyResult(
                    is_novel=False,
                    novelty_score=0.0,
                    confidence=0.0,
                    timestamp=datetime.now(UTC),
                    metadata={'error': 'detector_not_fitted'}
                )
                for _ in range(len(X))
            ]
        
        scores = self.predict_novelty(X)
        self.samples_seen += len(X)
        
        # Calculate confidence based on training sample count
        confidence = min(1.0, self.samples_seen / self.min_samples_fit)
        
        results = []
        for i, score in enumerate(scores):
            is_novel = score > self.threshold
            
            result = NoveltyResult(
                is_novel=is_novel,
                novelty_score=float(score),
                confidence=confidence,
                timestamp=datetime.now(UTC),
                flow_id=flow_ids[i] if flow_ids is not None else None,
                metadata={
                    'detector': self.name,
                    'threshold': self.threshold,
                    'samples_seen': self.samples_seen
                }
            )
            results.append(result)
            
            if is_novel:
                logger.info(
                    f"Novel pattern detected: score={score:.3f}, "
                    f"flow_id={result.flow_id}"
                )
        
        return results
    
    @abstractmethod
    def save(self, path: str) -> None:
        """Save detector state to disk"""
        pass
    
    @abstractmethod
    def load(self, path: str) -> 'NoveltyDetector':
        """Load detector state from disk"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            'name': self.name,
            'is_fitted': self.is_fitted,
            'samples_seen': self.samples_seen,
            'threshold': self.threshold,
            'min_samples_fit': self.min_samples_fit
        }
