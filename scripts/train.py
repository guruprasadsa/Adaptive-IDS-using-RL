#!/usr/bin/env python3
"""
Training script for Adaptive IDS

This script provides a command-line interface for training the Adaptive IDS model.
"""

import argparse
import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adaptive_ids.models.trainer import ModelTrainer


def main():
    """Main entry point for the training script."""
    parser = argparse.ArgumentParser(description='Train Adaptive IDS Model')
    
    # Data arguments
    parser.add_argument('--data-dir', type=str, default='data/',
                       help='Directory containing training data')
    parser.add_argument('--binary', action='store_true',
                       help='Use binary classification (benign vs attack)')
    
    # Model arguments
    parser.add_argument('--epochs', type=int, default=30,
                       help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=512,
                       help='Batch size for training')
    parser.add_argument('--lr', type=float, default=2e-4,
                       help='Learning rate')
    parser.add_argument('--hidden-dims', type=str, default='256,128',
                       help='Hidden layer dimensions (comma-separated)')
    parser.add_argument('--dropout', type=float, default=0.2,
                       help='Dropout rate')
    
    # Training arguments
    parser.add_argument('--device', choices=['auto', 'cuda', 'cpu'], default='auto',
                       help='Device to use for training')
    parser.add_argument('--amp', action='store_true',
                       help='Use automatic mixed precision')
    parser.add_argument('--compile', action='store_true',
                       help='Compile model with torch.compile')
    
    # Output arguments
    parser.add_argument('--log-dir', type=str, default='runs/',
                       help='Directory for TensorBoard logs')
    parser.add_argument('--ckpt-dir', type=str, default='checkpoints/',
                       help='Directory for model checkpoints')
    parser.add_argument('--resume', type=str, default=None,
                       help='Path to checkpoint to resume from')
    
    # Other arguments
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--low-mem', action='store_true',
                       help='Use aggressive memory optimizations')
    
    args = parser.parse_args()
    
    # Parse hidden dimensions
    hidden_dims = [int(x.strip()) for x in args.hidden_dims.split(',') if x.strip()]
    
    # Create trainer
    trainer = ModelTrainer(
        data_dir=args.data_dir,
        binary=args.binary,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        hidden_dims=hidden_dims,
        dropout=args.dropout,
        device=args.device,
        amp=args.amp,
        compile_model=args.compile,
        log_dir=args.log_dir,
        ckpt_dir=args.ckpt_dir,
        seed=args.seed,
        low_mem=args.low_mem
    )
    
    # Train the model
    if args.resume:
        trainer.resume_training(args.resume)
    else:
        trainer.train()


if __name__ == '__main__':
    main()
