"""
Training Diagnostic Script
Analyzes the current training state to identify issues
"""

import sys
from pathlib import Path
import numpy as np
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def analyze_data_distribution():
    """Analyze class distribution in training data"""
    print("="*70)
    print("DATA DISTRIBUTION ANALYSIS")
    print("="*70)
    
    data_dir = Path(__file__).parent.parent.parent / 'data' / 'processed'
    
    # Load data
    y_train = np.load(data_dir / 'y_train.npy')
    y_val = np.load(data_dir / 'y_val.npy')
    
    with open(data_dir / 'taxonomy.json', 'r') as f:
        taxonomy = json.load(f)
    
    num_classes = taxonomy['num_classes']
    class_names = taxonomy['classes']
    
    print(f"\nNumber of classes: {num_classes}")
    print(f"\nTraining set size: {len(y_train)}")
    print(f"Validation set size: {len(y_val)}")
    
    # Training distribution
    print("\n" + "-"*70)
    print("TRAINING DISTRIBUTION:")
    print("-"*70)
    train_counts = np.bincount(y_train, minlength=num_classes)
    for i in range(num_classes):
        class_name = class_names[i] if i < len(class_names) else f"Class_{i}"
        percentage = (train_counts[i] / len(y_train)) * 100
        print(f"  {class_name:20s}: {train_counts[i]:8d} ({percentage:5.2f}%)")
    
    # Validation distribution
    print("\n" + "-"*70)
    print("VALIDATION DISTRIBUTION:")
    print("-"*70)
    val_counts = np.bincount(y_val, minlength=num_classes)
    for i in range(num_classes):
        class_name = class_names[i] if i < len(class_names) else f"Class_{i}"
        percentage = (val_counts[i] / len(y_val)) * 100
        print(f"  {class_name:20s}: {val_counts[i]:8d} ({percentage:5.2f}%)")
    
    # Compute imbalance ratio
    print("\n" + "-"*70)
    print("IMBALANCE ANALYSIS:")
    print("-"*70)
    max_count = train_counts.max()
    min_count = train_counts[train_counts > 0].min() if (train_counts > 0).any() else 1
    imbalance_ratio = max_count / min_count
    print(f"  Max samples: {max_count}")
    print(f"  Min samples: {min_count}")
    print(f"  Imbalance ratio: {imbalance_ratio:.2f}x")
    
    # Recommend strategies
    print("\n" + "-"*70)
    print("RECOMMENDATIONS:")
    print("-"*70)
    if imbalance_ratio > 100:
        print("  ⚠️  SEVERE CLASS IMBALANCE DETECTED!")
        print("  → Use --use-balanced-sampling")
        print("  → Consider focal loss or class weights")
        print("  → May need to oversample minority classes")
    elif imbalance_ratio > 10:
        print("  ⚠️  Moderate class imbalance detected")
        print("  → Use --use-balanced-sampling recommended")
        print("  → Class weights should help")
    else:
        print("  ✓ Class distribution is relatively balanced")


def analyze_feature_quality():
    """Analyze feature quality"""
    print("\n" + "="*70)
    print("FEATURE QUALITY ANALYSIS")
    print("="*70)
    
    data_dir = Path(__file__).parent.parent.parent / 'data' / 'processed'
    
    # Load features
    X_train = np.load(data_dir / 'X_train.npy')
    X_val = np.load(data_dir / 'X_val.npy')
    
    print(f"\nFeature dimension: {X_train.shape[1]}")
    
    # Check for NaN/Inf
    print("\n" + "-"*70)
    print("DATA QUALITY:")
    print("-"*70)
    nan_count = np.isnan(X_train).sum()
    inf_count = np.isinf(X_train).sum()
    print(f"  NaN values: {nan_count}")
    print(f"  Inf values: {inf_count}")
    
    if nan_count > 0 or inf_count > 0:
        print("  ⚠️  WARNING: Data contains NaN or Inf values!")
        print("  → Clean data before training")
    else:
        print("  ✓ No NaN or Inf values detected")
    
    # Check feature variance
    print("\n" + "-"*70)
    print("FEATURE VARIANCE:")
    print("-"*70)
    feature_std = X_train.std(axis=0)
    zero_variance = (feature_std < 1e-6).sum()
    low_variance = ((feature_std > 1e-6) & (feature_std < 0.01)).sum()
    
    print(f"  Zero variance features: {zero_variance}")
    print(f"  Low variance features: {low_variance}")
    
    if zero_variance > X_train.shape[1] * 0.1:
        print("  ⚠️  WARNING: Many zero-variance features!")
        print("  → Consider feature selection")
    
    # Check feature scale
    print("\n" + "-"*70)
    print("FEATURE SCALE:")
    print("-"*70)
    feature_mean = X_train.mean(axis=0)
    feature_std = X_train.std(axis=0)
    
    print(f"  Mean range: [{feature_mean.min():.4f}, {feature_mean.max():.4f}]")
    print(f"  Std range: [{feature_std.min():.4f}, {feature_std.max():.4f}]")
    
    if feature_mean.max() > 10 or feature_std.max() > 10:
        print("  ⚠️  WARNING: Features not normalized!")
        print("  → Data should be standardized (mean=0, std=1)")
    else:
        print("  ✓ Features appear to be normalized")


def suggest_hyperparameters():
    """Suggest hyperparameters based on data analysis"""
    print("\n" + "="*70)
    print("HYPERPARAMETER SUGGESTIONS")
    print("="*70)
    
    data_dir = Path(__file__).parent.parent.parent / 'data' / 'processed'
    y_train = np.load(data_dir / 'y_train.npy')
    
    train_size = len(y_train)
    num_classes = len(np.unique(y_train))
    
    # Batch size
    print("\n" + "-"*70)
    print("BATCH SIZE:")
    print("-"*70)
    if train_size < 10000:
        suggested_batch = 64
    elif train_size < 100000:
        suggested_batch = 256
    else:
        suggested_batch = 512
    
    print(f"  Suggested: {suggested_batch}")
    print(f"  For 4GB VRAM: Start with 256, increase if stable")
    
    # Learning rate
    print("\n" + "-"*70)
    print("LEARNING RATE:")
    print("-"*70)
    print(f"  Router: 0.0001 - 0.001 (start conservative)")
    print(f"  Specialist: 0.0001 - 0.0005 (start conservative)")
    print(f"  Use learning rate scheduler for better convergence")
    
    # Entropy coefficient
    print("\n" + "-"*70)
    print("ENTROPY COEFFICIENT:")
    print("-"*70)
    print(f"  Suggested: 0.2 - 0.5 (HIGH to prevent router collapse)")
    print(f"  Monitor routing entropy in logs")
    print(f"  If routing entropy < 1.0, increase entropy coefficient")
    
    # Training epochs
    print("\n" + "-"*70)
    print("TRAINING DURATION:")
    print("-"*70)
    print(f"  Start with 30 epochs")
    print(f"  Use early stopping (patience=10)")
    print(f"  Monitor validation F1, not just accuracy")


if __name__ == '__main__':
    try:
        analyze_data_distribution()
        analyze_feature_quality()
        suggest_hyperparameters()
        
        print("\n" + "="*70)
        print("DIAGNOSTIC COMPLETE")
        print("="*70)
        
    except Exception as e:
        print(f"\nError during diagnostics: {e}")
        import traceback
        traceback.print_exc()
