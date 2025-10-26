"""
Novelty Detection Integration

Integrates novelty detection into the inference pipeline:
1. Check if flow is novel (unknown pattern)
2. If novel: route to review queue
3. If labeled: trigger specialist creation
4. Hot-load new specialist into router
"""

import numpy as np
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import json
from datetime import datetime

from .detector import NoveltyDetector, NoveltyResult
from .isolation_forest import IsolationForestDetector
from .autoencoder import AutoencoderDetector

logger = logging.getLogger(__name__)


class NoveltyIntegration:
    """
    Manages novelty detection in the inference pipeline.
    """
    
    def __init__(
        self,
        detector: NoveltyDetector,
        review_queue_path: str = None,
        enable_auto_specialist: bool = False
    ):
        """
        Args:
            detector: Fitted novelty detector (IsolationForest or Autoencoder)
            review_queue_path: Path to save novel flows for review
            enable_auto_specialist: Auto-create specialists from labeled data
        """
        self.detector = detector
        self.enable_auto_specialist = enable_auto_specialist
        
        # Review queue setup
        if review_queue_path is None:
            review_queue_path = Path(__file__).parent.parent.parent / "data" / "review_queue"
        
        self.review_queue_path = Path(review_queue_path)
        self.review_queue_path.mkdir(parents=True, exist_ok=True)
        
        # Stats tracking
        self.stats = {
            'total_checked': 0,
            'novel_detected': 0,
            'routed_to_review': 0,
            'specialists_created': 0
        }
        
        logger.info(
            f"Initialized NoveltyIntegration with detector={detector.name}, "
            f"review_queue={self.review_queue_path}"
        )
    
    def check_novelty(
        self,
        features: np.ndarray,
        flow_ids: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[list[NoveltyResult], list[int]]:
        """
        Check features for novelty.
        
        Args:
            features: Feature matrix (n_samples, n_features)
            flow_ids: Optional flow identifiers
            metadata: Optional metadata dict
            
        Returns:
            (novelty_results, novel_indices) where novel_indices are 
            indices of novel samples in the input array
        """
        self.stats['total_checked'] += len(features)
        
        # Run detection
        results = self.detector.detect(features, flow_ids)
        
        # Find novel samples
        novel_indices = [i for i, r in enumerate(results) if r.is_novel]
        self.stats['novel_detected'] += len(novel_indices)
        
        if novel_indices:
            logger.info(
                f"Detected {len(novel_indices)} novel samples out of {len(features)} "
                f"(scores: {[results[i].novelty_score for i in novel_indices]})"
            )
        
        return results, novel_indices
    
    def route_to_review_queue(
        self,
        features: np.ndarray,
        novelty_results: list[NoveltyResult],
        novel_indices: list[int],
        original_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save novel flows to review queue for human labeling.
        
        Args:
            features: Full feature matrix
            novelty_results: Novelty detection results
            novel_indices: Indices of novel samples
            original_data: Optional original flow data (packets, metadata, etc.)
            
        Returns:
            Path to saved review file
        """
        if not novel_indices:
            return None
        
        # Create review batch
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_file = self.review_queue_path / f"novel_batch_{timestamp}.json"
        
        review_data = {
            'timestamp': datetime.now().isoformat(),
            'detector': self.detector.name,
            'count': len(novel_indices),
            'samples': []
        }
        
        for idx in novel_indices:
            result = novelty_results[idx]
            
            sample_data = {
                'index': int(idx),
                'flow_id': result.flow_id,
                'novelty_score': float(result.novelty_score),
                'confidence': float(result.confidence),
                'features': features[idx].tolist(),
                'label': None,  # To be filled by human reviewer
                'reviewed': False,
                'reviewed_at': None,
                'reviewer': None
            }
            
            # Add original data if available
            if original_data and idx < len(original_data.get('flows', [])):
                sample_data['flow_data'] = original_data['flows'][idx]
            
            review_data['samples'].append(sample_data)
        
        # Save to queue
        with open(review_file, 'w') as f:
            json.dump(review_data, f, indent=2)
        
        self.stats['routed_to_review'] += len(novel_indices)
        
        logger.info(f"Routed {len(novel_indices)} novel samples to review queue: {review_file}")
        
        return str(review_file)
    
    def check_review_queue_for_labeled_data(self) -> list[Dict[str, Any]]:
        """
        Check review queue for labeled batches ready for specialist creation.
        
        Returns:
            List of labeled batches with attack class and sample count
        """
        labeled_batches = []
        
        for review_file in self.review_queue_path.glob("novel_batch_*.json"):
            with open(review_file, 'r') as f:
                data = json.load(f)
            
            # Check if all samples are reviewed and labeled
            samples = data['samples']
            if not samples:
                continue
            
            reviewed_count = sum(1 for s in samples if s.get('reviewed', False))
            if reviewed_count < len(samples):
                continue  # Not fully reviewed yet
            
            # Group by attack class
            labels = [s.get('label') for s in samples if s.get('label')]
            if not labels:
                continue
            
            # Find majority label (assuming single attack class per batch)
            from collections import Counter
            label_counts = Counter(labels)
            majority_label, count = label_counts.most_common(1)[0]
            
            if majority_label and majority_label != 'benign':
                labeled_batches.append({
                    'file': str(review_file),
                    'attack_class': majority_label,
                    'sample_count': count,
                    'reviewed_at': data.get('reviewed_at'),
                    'data': data
                })
        
        return labeled_batches
    
    def trigger_specialist_creation(
        self,
        attack_class: str,
        labeled_data: Dict[str, Any],
        description: Optional[str] = None
    ) -> Optional[Path]:
        """
        Trigger creation of new specialist agent for labeled attack class.
        
        Args:
            attack_class: Attack class name
            labeled_data: Labeled training data
            description: Optional description
            
        Returns:
            Path to created specialist directory or None
        """
        if not self.enable_auto_specialist:
            logger.info(
                f"Auto-specialist creation disabled. "
                f"Manual creation required for '{attack_class}'"
            )
            return None
        
        logger.info(f"Triggering specialist creation for '{attack_class}'")
        
        try:
            from .scaffold_specialist import SpecialistScaffolder
            
            # Prepare training data
            samples = labeled_data['samples']
            features = np.array([s['features'] for s in samples])
            labels = np.array([1 if s['label'] == attack_class else 0 for s in samples])
            
            # Save as CSV for training
            import pandas as pd
            df = pd.DataFrame(features)
            df['label'] = labels
            
            data_dir = Path(__file__).parent.parent.parent / "data" / "labeled"
            data_dir.mkdir(parents=True, exist_ok=True)
            
            data_path = data_dir / f"{attack_class}_training.csv"
            df.to_csv(data_path, index=False)
            
            logger.info(f"Saved training data: {data_path} ({len(df)} samples)")
            
            # Create specialist
            scaffolder = SpecialistScaffolder()
            specialist_dir = scaffolder.create_specialist(
                attack_class=attack_class,
                description=description or f"Auto-generated specialist for {attack_class}",
                training_data_path=str(data_path)
            )
            
            self.stats['specialists_created'] += 1
            
            logger.info(f"Created specialist at {specialist_dir}")
            
            return specialist_dir
            
        except Exception as e:
            logger.error(f"Failed to create specialist for {attack_class}: {e}", exc_info=True)
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get novelty detection statistics."""
        stats = self.stats.copy()
        stats['novelty_rate'] = (
            stats['novel_detected'] / stats['total_checked']
            if stats['total_checked'] > 0 else 0.0
        )
        stats['detector_stats'] = self.detector.get_stats()
        return stats


def create_novelty_detector(
    detector_type: str = "isolation_forest",
    config: Optional[Dict[str, Any]] = None
) -> NoveltyDetector:
    """
    Factory function to create novelty detector.
    
    Args:
        detector_type: 'isolation_forest' or 'autoencoder'
        config: Detector configuration dict
        
    Returns:
        Configured NoveltyDetector instance
    """
    if config is None:
        config = {}
    
    if detector_type == "isolation_forest":
        return IsolationForestDetector(**config)
    elif detector_type == "autoencoder":
        return AutoencoderDetector(**config)
    else:
        raise ValueError(f"Unknown detector type: {detector_type}")
