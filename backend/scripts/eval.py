"""
Model Evaluation Script
Comprehensive evaluation of trained Hybrid RL IDS model
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_curve, auc, precision_recall_curve
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.agents.a3c_router import A3CRouter
from model.agents.dqn_specialist import DQNSpecialist, create_specialists
from model.utils.calibration import evaluate_calibration

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_test_data(data_dir: Path) -> Tuple:
    """Load test data"""
    logger.info(f"Loading test data from {data_dir}")
    
    X_test = np.load(data_dir / 'X_test.npy')
    y_test = np.load(data_dir / 'y_test.npy')
    
    with open(data_dir / 'taxonomy.json', 'r') as f:
        taxonomy = json.load(f)
    
    logger.info(f"Test set: {X_test.shape}")
    
    return X_test, y_test, taxonomy


def load_trained_model(
    checkpoint_path: Path,
    num_classes: int,
    input_dim: int,
    specialist_names: list,
    device: str
) -> Tuple[A3CRouter, Dict[int, DQNSpecialist]]:
    """Load trained model from checkpoint"""
    
    logger.info(f"Loading model from {checkpoint_path}")
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    # Create router
    router = A3CRouter(
        input_dim=input_dim,
        num_specialists=num_classes,
        hidden_dims=[128, 64],
        entropy_coef=0.01
    ).to(device)
    router.load_state_dict(checkpoint['router_state_dict'])
    router.eval()
    
    # Create specialists
    specialists = create_specialists(
        num_specialists=num_classes,
        specialist_names=specialist_names,
        input_dim=input_dim,
        hidden_dims=[128, 64],
        use_noisy=False,  # No noise during eval
        device=device
    )
    
    # Load specialist weights
    for sp_id, sp_state_dict in checkpoint['specialist_state_dicts'].items():
        specialists[int(sp_id)].online_net.load_state_dict(sp_state_dict)
        specialists[int(sp_id)].online_net.eval()
    
    logger.info("Model loaded successfully")
    
    return router, specialists


def predict(
    router: A3CRouter,
    specialists: Dict[int, DQNSpecialist],
    X: np.ndarray,
    device: str,
    batch_size: int = 256
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate predictions
    
    Returns:
        predictions: Predicted class labels
        probabilities: Prediction probabilities (num_samples, num_classes)
    """
    
    predictions = []
    all_probs = []
    
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            batch = torch.FloatTensor(X[i:i+batch_size]).to(device)
            
            # Router selects specialists
            specialist_actions, _, _, _ = router(batch)
            
            # Get specialist predictions and probabilities
            batch_preds = torch.zeros(len(batch), dtype=torch.long, device=device)
            batch_probs = torch.zeros(len(batch), len(specialists), device=device)
            
            for j in range(len(batch)):
                sp_id = specialist_actions[j].item()
                
                if sp_id in specialists:
                    sp_q_values = specialists[sp_id].compute_q_values(batch[j:j+1])
                    sp_probs = torch.softmax(sp_q_values, dim=1)
                    
                    # If specialist says attack (prob > 0.5), use specialist ID
                    if sp_probs[0, 1] > 0.5:
                        batch_preds[j] = sp_id
                        batch_probs[j, sp_id] = sp_probs[0, 1]
                    else:
                        batch_preds[j] = 0  # Benign
                        batch_probs[j, 0] = sp_probs[0, 0]
                else:
                    batch_preds[j] = 0  # Default to benign
                    batch_probs[j, 0] = 1.0
            
            predictions.append(batch_preds.cpu().numpy())
            all_probs.append(batch_probs.cpu().numpy())
    
    predictions = np.concatenate(predictions)
    probabilities = np.concatenate(all_probs, axis=0)
    
    return predictions, probabilities


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, class_names: list) -> dict:
    """Compute comprehensive metrics"""
    
    logger.info("Computing metrics...")
    
    # Overall metrics
    accuracy = np.mean(y_true == y_pred)
    
    # Per-class metrics
    report = classification_report(
        y_true, y_pred,
        target_names=class_names,
        output_dict=True,
        zero_division=0
    )
    
    # Extract key metrics
    metrics = {
        'accuracy': accuracy,
        'macro_precision': report['macro avg']['precision'],
        'macro_recall': report['macro avg']['recall'],
        'macro_f1': report['macro avg']['f1-score'],
        'weighted_precision': report['weighted avg']['precision'],
        'weighted_recall': report['weighted avg']['recall'],
        'weighted_f1': report['weighted avg']['f1-score'],
    }
    
    # TPR and FPR
    # TPR = recall for attack classes (non-benign)
    attack_mask = y_true != 0
    if attack_mask.sum() > 0:
        tpr = np.mean(y_pred[attack_mask] == y_true[attack_mask])
        metrics['tpr'] = tpr
    else:
        metrics['tpr'] = 0.0
    
    # FPR = false positives / total negatives
    benign_mask = y_true == 0
    if benign_mask.sum() > 0:
        fpr = np.mean(y_pred[benign_mask] != 0)
        metrics['fpr'] = fpr
    else:
        metrics['fpr'] = 0.0
    
    # Per-class metrics
    per_class_metrics = {}
    for i, class_name in enumerate(class_names):
        if str(i) in report:
            per_class_metrics[class_name] = {
                'precision': report[str(i)]['precision'],
                'recall': report[str(i)]['recall'],
                'f1-score': report[str(i)]['f1-score'],
                'support': report[str(i)]['support']
            }
    
    metrics['per_class'] = per_class_metrics
    
    logger.info(f"Accuracy: {accuracy:.4f}")
    logger.info(f"Macro F1: {metrics['macro_f1']:.4f}")
    logger.info(f"TPR: {metrics['tpr']:.4f}")
    logger.info(f"FPR: {metrics['fpr']:.4f}")
    
    return metrics


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list,
    save_path: Path
):
    """Plot confusion matrix"""
    
    logger.info("Generating confusion matrix...")
    
    cm = confusion_matrix(y_true, y_pred)
    
    plt.figure(figsize=(12, 10))
    sns.heatmap(
        cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=class_names, yticklabels=class_names,
        cbar_kws={'label': 'Count'}
    )
    plt.xlabel('Predicted', fontsize=12, fontweight='bold')
    plt.ylabel('True', fontsize=12, fontweight='bold')
    plt.title('Confusion Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved confusion matrix to {save_path}")


def plot_roc_curves(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    class_names: list,
    save_path: Path
):
    """Plot ROC curves for each class"""
    
    logger.info("Generating ROC curves...")
    
    n_classes = len(class_names)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    for i in range(min(n_classes, 6)):  # Plot first 6 classes
        # Binary labels for this class
        y_binary = (y_true == i).astype(int)
        y_score = y_probs[:, i]
        
        # Compute ROC curve
        fpr, tpr, _ = roc_curve(y_binary, y_score)
        roc_auc = auc(fpr, tpr)
        
        # Plot
        axes[i].plot(fpr, tpr, color='darkorange', lw=2,
                     label=f'ROC curve (AUC = {roc_auc:.3f})')
        axes[i].plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        axes[i].set_xlim([0.0, 1.0])
        axes[i].set_ylim([0.0, 1.05])
        axes[i].set_xlabel('False Positive Rate')
        axes[i].set_ylabel('True Positive Rate')
        axes[i].set_title(f'ROC: {class_names[i]}')
        axes[i].legend(loc='lower right')
        axes[i].grid(alpha=0.3)
    
    # Hide unused subplots
    for i in range(n_classes, len(axes)):
        axes[i].axis('off')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved ROC curves to {save_path}")


def plot_pr_curves(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    class_names: list,
    save_path: Path
):
    """Plot Precision-Recall curves"""
    
    logger.info("Generating PR curves...")
    
    n_classes = len(class_names)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    for i in range(min(n_classes, 6)):
        # Binary labels for this class
        y_binary = (y_true == i).astype(int)
        y_score = y_probs[:, i]
        
        # Compute PR curve
        precision, recall, _ = precision_recall_curve(y_binary, y_score)
        pr_auc = auc(recall, precision)
        
        # Plot
        axes[i].plot(recall, precision, color='darkorange', lw=2,
                     label=f'PR curve (AUC = {pr_auc:.3f})')
        axes[i].set_xlim([0.0, 1.0])
        axes[i].set_ylim([0.0, 1.05])
        axes[i].set_xlabel('Recall')
        axes[i].set_ylabel('Precision')
        axes[i].set_title(f'PR Curve: {class_names[i]}')
        axes[i].legend(loc='lower left')
        axes[i].grid(alpha=0.3)
    
    # Hide unused subplots
    for i in range(n_classes, len(axes)):
        axes[i].axis('off')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved PR curves to {save_path}")


def save_metrics_json(metrics: dict, save_path: Path):
    """Save metrics to JSON"""
    
    with open(save_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"Saved metrics to {save_path}")


def main(args):
    """Main evaluation function"""
    
    logger.info("="*70)
    logger.info("Model Evaluation")
    logger.info("="*70)
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() and not args.no_cuda else 'cpu')
    logger.info(f"Using device: {device}")
    
    # Setup directories
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / 'data' / 'processed'
    output_dir = project_root / 'backend' / 'model' / 'output'
    eval_dir = output_dir / 'evaluation'
    eval_dir.mkdir(exist_ok=True, parents=True)
    
    # Load test data
    X_test, y_test, taxonomy = load_test_data(data_dir)
    class_names = taxonomy['classes']
    num_classes = taxonomy['num_classes']
    input_dim = X_test.shape[1]
    
    # Load model
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else output_dir / 'checkpoints' / 'best_model.pt'
    router, specialists = load_trained_model(
        checkpoint_path, num_classes, input_dim, class_names, device
    )
    
    # Generate predictions
    logger.info("Generating predictions...")
    y_pred, y_probs = predict(router, specialists, X_test, device, batch_size=args.batch_size)
    
    # Compute metrics
    metrics = compute_metrics(y_test, y_pred, class_names)
    
    # Check FPR constraint
    if metrics['fpr'] >= 0.01:
        logger.warning(f"FPR={metrics['fpr']:.4f} exceeds target (<1%)")
    else:
        logger.info(f"✅ FPR={metrics['fpr']:.4f} meets target (<1%)")
    
    # Check TPR constraint
    if metrics['tpr'] >= 0.99:
        logger.info(f"✅ TPR={metrics['tpr']:.4f} meets target (≥99%)")
    else:
        logger.warning(f"TPR={metrics['tpr']:.4f} below target (≥99%)")
    
    # Plot confusion matrix
    plot_confusion_matrix(y_test, y_pred, class_names, eval_dir / 'confusion_matrix.png')
    
    # Plot ROC curves
    plot_roc_curves(y_test, y_probs, class_names, eval_dir / 'roc_curves.png')
    
    # Plot PR curves
    plot_pr_curves(y_test, y_probs, class_names, eval_dir / 'pr_curves.png')
    
    # Evaluate calibration
    calibration_metrics = evaluate_calibration(
        y_probs, y_test,
        save_dir=str(eval_dir),
        prefix='test_'
    )
    metrics['calibration'] = calibration_metrics
    
    # Save metrics
    save_metrics_json(metrics, eval_dir / 'test_metrics.json')
    
    # Print summary
    logger.info("="*70)
    logger.info("EVALUATION SUMMARY")
    logger.info("="*70)
    logger.info(f"Accuracy:        {metrics['accuracy']:.4f}")
    logger.info(f"Macro F1:        {metrics['macro_f1']:.4f}")
    logger.info(f"TPR:             {metrics['tpr']:.4f} (target: ≥0.99)")
    logger.info(f"FPR:             {metrics['fpr']:.4f} (target: <0.01)")
    logger.info(f"ECE:             {metrics['calibration']['ece']:.4f}")
    logger.info("="*70)
    
    logger.info(f"\nResults saved to: {eval_dir}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate Hybrid RL IDS')
    
    parser.add_argument('--checkpoint', type=str, default=None,
                        help='Path to checkpoint (default: best_model.pt)')
    parser.add_argument('--batch-size', type=int, default=256,
                        help='Batch size for prediction')
    parser.add_argument('--no-cuda', action='store_true',
                        help='Disable CUDA')
    
    args = parser.parse_args()
    
    main(args)
