"""
Model Calibration Utilities
Temperature scaling and calibration metrics for confidence calibration
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Optional
import logging
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class TemperatureScaling(nn.Module):
    """
    Temperature scaling for post-hoc calibration
    Scales logits before softmax: softmax(logits / T)
    """
    
    def __init__(self, initial_temperature: float = 1.5):
        super().__init__()
        
        # Temperature parameter (learnable)
        self.temperature = nn.Parameter(torch.ones(1) * initial_temperature)
    
    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """
        Apply temperature scaling to logits
        
        Args:
            logits: Model logits [batch, num_classes]
        
        Returns:
            scaled_logits: Temperature-scaled logits [batch, num_classes]
        """
        return logits / self.temperature
    
    def fit(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        lr: float = 0.01,
        max_iter: int = 50
    ):
        """
        Fit temperature parameter on validation set
        
        Args:
            logits: Validation logits [N, num_classes]
            labels: True labels [N]
            lr: Learning rate
            max_iter: Maximum optimization iterations
        """
        # Detach logits to avoid gradient issues
        logits = logits.detach()
        
        optimizer = torch.optim.LBFGS([self.temperature], lr=lr, max_iter=max_iter)
        
        def eval_loss():
            optimizer.zero_grad()
            loss = F.cross_entropy(self.forward(logits), labels)
            loss.backward()
            return loss
        
        logger.info(f"Fitting temperature with {len(labels)} samples...")
        optimizer.step(eval_loss)
        
        logger.info(f"Optimal temperature: {self.temperature.item():.4f}")
    
    def get_temperature(self) -> float:
        """Return current temperature value"""
        return self.temperature.item()


def expected_calibration_error(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 15
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute Expected Calibration Error (ECE)
    
    Args:
        probs: Predicted probabilities [N, num_classes]
        labels: True labels [N]
        n_bins: Number of bins for calibration
    
    Returns:
        ece: Expected calibration error
        bin_boundaries: Bin boundary values
        bin_accuracies: Accuracy in each bin
        bin_confidences: Average confidence in each bin
    """
    # Get predicted class and confidence
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    accuracies = (predictions == labels).astype(np.float32)
    
    # Create bins
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    
    # Initialize outputs
    bin_accuracies = np.zeros(n_bins)
    bin_confidences = np.zeros(n_bins)
    bin_counts = np.zeros(n_bins)
    
    # Compute per-bin statistics
    for bin_idx, (bin_lower, bin_upper) in enumerate(zip(bin_lowers, bin_uppers)):
        # Find samples in this bin
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        bin_count = np.sum(in_bin)
        
        if bin_count > 0:
            bin_accuracies[bin_idx] = np.mean(accuracies[in_bin])
            bin_confidences[bin_idx] = np.mean(confidences[in_bin])
            bin_counts[bin_idx] = bin_count
    
    # Compute ECE (weighted average of |accuracy - confidence|)
    total_count = len(labels)
    ece = np.sum(bin_counts / total_count * np.abs(bin_accuracies - bin_confidences))
    
    logger.info(f"ECE: {ece:.4f} (computed with {n_bins} bins)")
    
    return ece, bin_boundaries, bin_accuracies, bin_confidences


def maximum_calibration_error(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 15
) -> float:
    """
    Compute Maximum Calibration Error (MCE)
    
    Args:
        probs: Predicted probabilities [N, num_classes]
        labels: True labels [N]
        n_bins: Number of bins
    
    Returns:
        mce: Maximum calibration error
    """
    ece, _, bin_accuracies, bin_confidences = expected_calibration_error(
        probs, labels, n_bins
    )
    
    # MCE is the maximum gap
    mce = np.max(np.abs(bin_accuracies - bin_confidences))
    
    logger.info(f"MCE: {mce:.4f}")
    
    return mce


def plot_reliability_diagram(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 15,
    save_path: Optional[str] = None,
    title: str = "Reliability Diagram"
):
    """
    Plot reliability diagram (calibration plot)
    
    Args:
        probs: Predicted probabilities [N, num_classes]
        labels: True labels [N]
        n_bins: Number of bins
        save_path: Path to save figure (optional)
        title: Plot title
    """
    ece, bin_boundaries, bin_accuracies, bin_confidences = expected_calibration_error(
        probs, labels, n_bins
    )
    
    # Create figure
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # Plot perfect calibration line
    ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', linewidth=2)
    
    # Plot calibration curve
    bin_centers = (bin_boundaries[:-1] + bin_boundaries[1:]) / 2
    mask = bin_accuracies > 0  # Only plot non-empty bins
    
    ax.plot(
        bin_confidences[mask],
        bin_accuracies[mask],
        'o-',
        label='Model Calibration',
        linewidth=2,
        markersize=8
    )
    
    # Fill gap area
    ax.fill_between(
        bin_confidences[mask],
        bin_confidences[mask],
        bin_accuracies[mask],
        alpha=0.2,
        label=f'Calibration Gap (ECE={ece:.3f})'
    )
    
    # Formatting
    ax.set_xlabel('Confidence', fontsize=14)
    ax.set_ylabel('Accuracy', fontsize=14)
    ax.set_title(f'{title}\nECE: {ece:.4f}', fontsize=16)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved reliability diagram to {save_path}")
    
    plt.close()


def plot_confidence_histogram(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 20,
    save_path: Optional[str] = None,
    title: str = "Confidence Histogram"
):
    """
    Plot histogram of prediction confidences
    
    Args:
        probs: Predicted probabilities [N, num_classes]
        labels: True labels [N]
        n_bins: Number of histogram bins
        save_path: Path to save figure (optional)
        title: Plot title
    """
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    correct = predictions == labels
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot histogram for correct and incorrect predictions
    ax.hist(
        confidences[correct],
        bins=n_bins,
        alpha=0.5,
        label='Correct',
        color='green',
        edgecolor='black'
    )
    
    ax.hist(
        confidences[~correct],
        bins=n_bins,
        alpha=0.5,
        label='Incorrect',
        color='red',
        edgecolor='black'
    )
    
    # Formatting
    ax.set_xlabel('Confidence', fontsize=14)
    ax.set_ylabel('Count', fontsize=14)
    ax.set_title(title, fontsize=16)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add statistics
    avg_conf_correct = np.mean(confidences[correct])
    avg_conf_incorrect = np.mean(confidences[~correct])
    
    textstr = f'Avg Conf (Correct): {avg_conf_correct:.3f}\nAvg Conf (Incorrect): {avg_conf_incorrect:.3f}'
    ax.text(
        0.05, 0.95, textstr,
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    )
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved confidence histogram to {save_path}")
    
    plt.close()


def calibrate_model(
    model: nn.Module,
    val_loader: torch.utils.data.DataLoader,
    device: str = 'cpu',
    lr: float = 0.01,
    max_iter: int = 50
) -> TemperatureScaling:
    """
    Calibrate model using temperature scaling on validation set
    
    Args:
        model: Trained model
        val_loader: Validation data loader
        device: Device to run calibration on
        lr: Learning rate for temperature optimization
        max_iter: Maximum optimization iterations
    
    Returns:
        temperature_scaler: Fitted TemperatureScaling module
    """
    logger.info("Starting temperature scaling calibration...")
    
    model.eval()
    
    # Collect logits and labels from validation set
    all_logits = []
    all_labels = []
    
    with torch.no_grad():
        for states, labels in val_loader:
            states = states.to(device)
            
            # Get logits (before softmax)
            logits = model(states)
            
            all_logits.append(logits.cpu())
            all_labels.append(labels.cpu())
    
    all_logits = torch.cat(all_logits, dim=0)
    all_labels = torch.cat(all_labels, dim=0)
    
    logger.info(f"Collected {len(all_labels)} validation samples")
    
    # Fit temperature
    temperature_scaler = TemperatureScaling()
    temperature_scaler.to(device)
    
    all_logits = all_logits.to(device)
    all_labels = all_labels.to(device)
    
    temperature_scaler.fit(all_logits, all_labels, lr=lr, max_iter=max_iter)
    
    return temperature_scaler


def evaluate_calibration(
    probs: np.ndarray,
    labels: np.ndarray,
    save_dir: Optional[str] = None,
    prefix: str = ""
) -> dict:
    """
    Comprehensive calibration evaluation
    
    Args:
        probs: Predicted probabilities [N, num_classes]
        labels: True labels [N]
        save_dir: Directory to save plots (optional)
        prefix: Prefix for saved files
    
    Returns:
        metrics: Dictionary of calibration metrics
    """
    logger.info("Evaluating calibration...")
    
    # Compute metrics
    ece, _, _, _ = expected_calibration_error(probs, labels, n_bins=15)
    mce = maximum_calibration_error(probs, labels, n_bins=15)
    
    # Compute accuracy
    predictions = np.argmax(probs, axis=1)
    accuracy = np.mean(predictions == labels)
    
    # Compute average confidence
    confidences = np.max(probs, axis=1)
    avg_confidence = np.mean(confidences)
    
    metrics = {
        'ece': float(ece),
        'mce': float(mce),
        'accuracy': float(accuracy),
        'avg_confidence': float(avg_confidence),
        'calibration_gap': float(avg_confidence - accuracy)
    }
    
    logger.info(f"Calibration Metrics: ECE={ece:.4f}, MCE={mce:.4f}, Acc={accuracy:.4f}")
    
    # Plot if save directory provided
    if save_dir:
        import os
        os.makedirs(save_dir, exist_ok=True)
        
        # Reliability diagram
        reliability_path = os.path.join(save_dir, f'{prefix}reliability_diagram.png')
        plot_reliability_diagram(
            probs, labels,
            save_path=reliability_path,
            title=f'{prefix}Reliability Diagram'
        )
        
        # Confidence histogram
        histogram_path = os.path.join(save_dir, f'{prefix}confidence_histogram.png')
        plot_confidence_histogram(
            probs, labels,
            save_path=histogram_path,
            title=f'{prefix}Confidence Histogram'
        )
    
    return metrics


class CalibratedModel(nn.Module):
    """
    Wrapper that combines a model with temperature scaling
    """
    
    def __init__(self, model: nn.Module, temperature_scaler: TemperatureScaling):
        super().__init__()
        
        self.model = model
        self.temperature_scaler = temperature_scaler
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass with temperature scaling"""
        logits = self.model(x)
        scaled_logits = self.temperature_scaler(logits)
        return scaled_logits
    
    def get_probabilities(self, x: torch.Tensor) -> torch.Tensor:
        """Get calibrated probabilities"""
        scaled_logits = self.forward(x)
        probs = F.softmax(scaled_logits, dim=-1)
        return probs


if __name__ == '__main__':
    # Test calibration utilities
    logging.basicConfig(level=logging.INFO)
    
    # Simulate uncalibrated predictions
    np.random.seed(42)
    n_samples = 1000
    n_classes = 5
    
    # Generate overconfident predictions
    logits = np.random.randn(n_samples, n_classes) * 2
    probs = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    
    # Generate labels with some correlation to predictions
    predictions = np.argmax(probs, axis=1)
    labels = predictions.copy()
    
    # Introduce errors (30% incorrect)
    error_indices = np.random.choice(n_samples, size=int(0.3 * n_samples), replace=False)
    labels[error_indices] = np.random.randint(0, n_classes, size=len(error_indices))
    
    # Evaluate calibration
    metrics = evaluate_calibration(probs, labels, save_dir='./calibration_test')
    
    print("\nCalibration Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}")
