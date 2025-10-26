# Training & Evaluation Scripts

This directory contains scripts for training and evaluating the Hybrid Multi-Agent RL IDS system.

## Overview

- **`train.py`**: Main training pipeline with curriculum learning, early stopping, and checkpointing
- **`eval.py`**: Comprehensive model evaluation with metrics, visualizations, and calibration analysis
- **`etl_features.py`**: Data preprocessing and feature extraction pipeline

## Prerequisites

Ensure all dependencies are installed:
```bash
pip install -r backend/requirements.txt
```

Required data:
- Preprocessed datasets in `data/processed/`:
  - `X_train.npy`, `y_train.npy`
  - `X_val.npy`, `y_val.npy`
  - `X_test.npy`, `y_test.npy`
  - `taxonomy.json`
  - `metadata.json`

If not available, run ETL pipeline first:
```bash
python backend/scripts/etl_features.py
```

## Training

### Basic Usage

Train with default parameters:
```bash
python backend/scripts/train.py
```

This will:
- Train for 50 epochs
- Use curriculum learning (4-phase difficulty progression)
- Apply early stopping (patience=10)
- Save checkpoints every 5 epochs
- Log metrics to TensorBoard

### Custom Hyperparameters

```bash
python backend/scripts/train.py \
    --num-epochs 100 \
    --lr-router 0.001 \
    --lr-specialist 0.0005 \
    --batch-size 128 \
    --gamma 0.99 \
    --entropy-coef 0.01 \
    --n-step 3 \
    --target-update-freq 100 \
    --use-noisy \
    --buffer-capacity 10000 \
    --warmup-epochs 5 \
    --patience 10 \
    --save-freq 5
```

### Parameters

**Learning Rates**:
- `--lr-router`: Router learning rate (default: 0.001)
- `--lr-specialist`: Specialist learning rate (default: 0.0005)

**RL Hyperparameters**:
- `--gamma`: Discount factor (default: 0.99)
- `--entropy-coef`: Entropy coefficient for exploration (default: 0.01)
- `--n-step`: N-step TD returns (default: 3)
- `--target-update-freq`: Target network update frequency (default: 100)
- `--use-noisy`: Enable NoisyNets for exploration (flag)

**Training Parameters**:
- `--num-epochs`: Number of training epochs (default: 50)
- `--batch-size`: Mini-batch size (default: 128)
- `--buffer-capacity`: Replay buffer capacity per specialist (default: 10000)

**Curriculum Learning**:
- `--warmup-epochs`: Curriculum warmup duration (default: 5)

**Early Stopping & Checkpoints**:
- `--patience`: Early stopping patience (default: 10)
- `--save-freq`: Checkpoint save frequency (default: 5)

**Other**:
- `--no-cuda`: Disable GPU training (flag)
- `--seed`: Random seed for reproducibility (default: 42)

### Monitoring Training

View training progress in TensorBoard:
```bash
tensorboard --logdir backend/model/output/logs
```

Navigate to `http://localhost:6006` to view:
- Router loss, accuracy
- Specialist loss per class
- Validation F1 score
- Learning curves

### Checkpoints

Checkpoints are saved to `backend/model/output/checkpoints/`:
- `best_model.pt`: Model with best validation F1
- `checkpoint_epoch_X.pt`: Last 5 epoch checkpoints

Each checkpoint contains:
- Router state dict
- All specialist state dicts
- Optimizer state dicts
- Training metrics
- Current epoch

## Evaluation

### Basic Usage

Evaluate best model on test set:
```bash
python backend/scripts/eval.py
```

Evaluate specific checkpoint:
```bash
python backend/scripts/eval.py --checkpoint backend/model/output/checkpoints/checkpoint_epoch_30.pt
```

### Parameters

- `--checkpoint`: Path to model checkpoint (default: `best_model.pt`)
- `--batch-size`: Batch size for prediction (default: 256)
- `--no-cuda`: Disable GPU (flag)

### Outputs

Evaluation results saved to `backend/model/output/evaluation/`:

**Metrics** (`test_metrics.json`):
```json
{
  "accuracy": 0.9923,
  "macro_f1": 0.9567,
  "tpr": 0.9912,
  "fpr": 0.0087,
  "calibration": {
    "ece": 0.0234,
    "mce": 0.0451
  },
  "per_class": {
    "Benign": {"precision": 0.995, "recall": 0.993, "f1-score": 0.994},
    ...
  }
}
```

**Visualizations**:
- `confusion_matrix.png`: Multi-class confusion matrix
- `roc_curves.png`: ROC curves for first 6 classes
- `pr_curves.png`: Precision-Recall curves
- `test_calibration_reliability.png`: Calibration plot
- `test_calibration_confidence_hist.png`: Confidence distribution

### Performance Targets

The model should achieve:
- ✅ **TPR ≥ 99%**: True Positive Rate (attack detection)
- ✅ **FPR < 1%**: False Positive Rate (false alarms)
- ✅ **Macro F1 ≥ 0.95**: Balanced multi-class performance
- ✅ **ECE < 0.05**: Expected Calibration Error (confidence reliability)

## Example Workflow

Complete training and evaluation pipeline:

```bash
# 1. Prepare data (if not already done)
python backend/scripts/etl_features.py

# 2. Train model
python backend/scripts/train.py \
    --num-epochs 50 \
    --batch-size 128 \
    --patience 10

# 3. Monitor training (in separate terminal)
tensorboard --logdir backend/model/output/logs

# 4. Evaluate best model
python backend/scripts/eval.py

# 5. Review results
cat backend/model/output/evaluation/test_metrics.json
```

## Training Tips

### Curriculum Learning

The curriculum scheduler introduces attack classes gradually:
- **Phase 1 (epochs 0-4)**: Benign, PortScan (easiest)
- **Phase 2 (epochs 5-9)**: + DoS variants
- **Phase 3 (epochs 10-14)**: + BruteForce, WebAttack
- **Phase 4 (epochs 15-19)**: + DDoS, complex attacks
- **Phase 5 (epochs 20+)**: All 18 classes

This improves convergence and prevents specialists from overfitting to complex patterns early.

### Early Stopping

Training stops automatically if validation F1 doesn't improve for `--patience` epochs. This prevents overfitting and saves compute time.

### Hyperparameter Tuning

Recommended ranges for tuning:
- Router LR: 0.0001 - 0.01
- Specialist LR: 0.00001 - 0.001
- Entropy coef: 0.001 - 0.1
- N-step: 1 - 5
- Batch size: 64 - 512

### GPU Utilization

For multi-GPU systems, training script can be extended with:
```python
if torch.cuda.device_count() > 1:
    router = nn.DataParallel(router)
```

### Memory Optimization

If running out of memory:
1. Reduce `--batch-size` (try 64 or 32)
2. Reduce `--buffer-capacity` (try 5000)
3. Use `--no-cuda` to train on CPU (slower but uses RAM)

## Troubleshooting

### Training Issues

**Loss not decreasing**:
- Increase learning rate
- Check data preprocessing (normalization)
- Verify labels are correct

**Loss exploding (NaN)**:
- Decrease learning rate
- Check gradient clipping is enabled (max_norm=10.0 in code)
- Inspect input data for outliers

**Overfitting (train F1 >> val F1)**:
- Increase entropy coefficient
- Reduce model capacity
- Add dropout (modify architecture)

### Evaluation Issues

**FPR too high (>1%)**:
- Adjust specialist decision threshold (currently 0.5)
- Post-training calibration with temperature scaling
- Collect more benign samples for training

**TPR too low (<99%)**:
- Train for more epochs
- Increase model capacity
- Check for class imbalance in training data

**Poor calibration (ECE > 0.05)**:
- Use temperature scaling (already implemented)
- Increase training data
- Reduce model complexity

## Advanced Usage

### Resume Training

Modify `train.py` to load checkpoint and continue:
```python
checkpoint = torch.load('checkpoint_epoch_30.pt')
router.load_state_dict(checkpoint['router_state_dict'])
# ... load specialists and optimizers
start_epoch = checkpoint['epoch'] + 1
```

### Export for Production

Convert trained model for deployment:
```python
# Save lightweight model (no optimizer states)
torch.save({
    'router': router.state_dict(),
    'specialists': {sp_id: sp.online_net.state_dict() for sp_id, sp in specialists.items()},
    'taxonomy': taxonomy
}, 'production_model.pt')
```

### Ensemble Models

Combine multiple checkpoints for ensemble prediction:
```python
models = [load_model(f'checkpoint_epoch_{i}.pt') for i in range(40, 51, 2)]
predictions = [predict(model, X_test) for model in models]
ensemble_pred = np.mean(predictions, axis=0).argmax(axis=1)
```

## File Structure

```
backend/scripts/
├── train.py              # Main training script (650 lines)
├── eval.py               # Evaluation script (450 lines)
├── etl_features.py       # Data preprocessing (450 lines)
└── README.md             # This file

backend/model/output/
├── checkpoints/          # Model checkpoints
│   ├── best_model.pt
│   └── checkpoint_epoch_*.pt
├── logs/                 # TensorBoard logs
│   └── train_*/
└── evaluation/           # Evaluation results
    ├── test_metrics.json
    ├── confusion_matrix.png
    ├── roc_curves.png
    └── pr_curves.png
```

## References

- **A3C Paper**: Mnih et al. (2016) - "Asynchronous Methods for Deep RL"
- **DQN Paper**: Mnih et al. (2015) - "Human-level control through deep RL"
- **Prioritized Replay**: Schaul et al. (2015) - "Prioritized Experience Replay"
- **Curriculum Learning**: Bengio et al. (2009) - "Curriculum Learning"
- **Calibration**: Guo et al. (2017) - "On Calibration of Modern Neural Networks"

## Support

For issues or questions:
1. Check `backend/model/TEST_SUMMARY.md` for component tests
2. Review training logs in TensorBoard
3. Validate data preprocessing with `backend/scripts/etl_features.py --validate`
4. Run component tests: `python backend/model/run_tests.py`
