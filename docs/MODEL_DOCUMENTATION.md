# Adaptive IDS RL Trainer - Model Documentation

## Overview

The Adaptive IDS RL Trainer is a memory-optimized reinforcement learning system designed for intrusion detection on network traffic data. It implements Deep Q-Network (DQN) and Actor-Critic (A3C) algorithms specifically optimized for systems with ~16GB RAM constraints.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Features](#key-features)
3. [Model Components](#model-components)
4. [Data Processing Pipeline](#data-processing-pipeline)
5. [Training Algorithms](#training-algorithms)
6. [Memory Optimization](#memory-optimization)
7. [Usage Guide](#usage-guide)
8. [Configuration Parameters](#configuration-parameters)
9. [Performance Metrics](#performance-metrics)
10. [Troubleshooting](#troubleshooting)

## Architecture Overview

The system follows a modular architecture with the following main components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Adaptive IDS RL Trainer                  │
├─────────────────────────────────────────────────────────────┤
│  Data Processing Pipeline                                   │
│  ├── CSV Streaming Reader (Two-pass)                       │
│  ├── Feature Extraction & Normalization                    │
│  ├── Memory-mapped Storage                                  │
│  └── Stratified Data Splitting                             │
├─────────────────────────────────────────────────────────────┤
│  RL Models                                                  │
│  ├── DQN with Dueling Architecture                         │
│  ├── Double DQN Target Network                             │
│  ├── Actor-Critic (A3C) with LSTM Support                  │
│  └── Experience Replay Buffer                              │
├─────────────────────────────────────────────────────────────┤
│  Training Infrastructure                                    │
│  ├── Mixed Precision Training (AMP)                        │
│  ├── Model Compilation (torch.compile)                     │
│  ├── TensorBoard Logging                                   │
│  └── Checkpointing System                                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 🚀 Performance Optimizations
- **Memory-mapped I/O**: Processes datasets larger than RAM using numpy memmap
- **Two-pass preprocessing**: Computes statistics without loading full dataset
- **Mixed precision training**: Uses automatic mixed precision (AMP) for faster training
- **Model compilation**: Leverages `torch.compile` for optimized execution
- **Chunked processing**: Processes data in configurable chunks to manage memory

### 🧠 Advanced RL Algorithms
- **Double DQN**: Reduces overestimation bias in Q-learning
- **Dueling DQN**: Separates value and advantage estimation
- **Experience Replay**: Stores and samples past experiences for stable learning
- **Target Network**: Provides stable learning targets
- **Epsilon-greedy exploration**: Balances exploration vs exploitation

### 🔧 Flexibility & Robustness
- **Binary/Multi-class support**: Handles both binary (Benign/Attack) and multi-class classification
- **Sequence modeling**: Optional LSTM support for temporal patterns
- **Reward shaping**: Configurable rewards for different prediction outcomes
- **Low-memory mode**: Aggressive optimizations for resource-constrained environments

## Model Components

### 1. DQN_MLP (Deep Q-Network)

```python
class DQN_MLP(nn.Module):
    def __init__(self, input_dim, output_dim, hidden_dims=[256,128], dropout=0.2):
        # Dueling architecture with separate value and advantage streams
```

**Architecture Details:**
- **Feature Network**: Shared feature extraction layers with BatchNorm and Dropout
- **Value Stream**: Estimates state value V(s)
- **Advantage Stream**: Estimates action advantages A(s,a)
- **Q-values**: Combined as Q(s,a) = V(s) + A(s,a) - mean(A(s,·))

**Key Benefits:**
- Better learning stability through dueling architecture
- Improved sample efficiency
- Robust to hyperparameter choices

### 2. ActorCritic (A3C)

```python
class ActorCritic(nn.Module):
    def __init__(self, input_dim, action_dim, hidden_dims=[256,128], 
                 use_lstm=False, seq_len=1, dropout=0.2):
```

**Architecture Details:**
- **Actor Network**: Outputs action probabilities π(a|s)
- **Critic Network**: Estimates state value V(s)
- **LSTM Support**: Optional recurrent layers for sequence modeling
- **Shared Features**: Common feature extraction for efficiency

### 3. Experience Replay Buffer

```python
class ReplayBuffer:
    def __init__(self, capacity: int, state_shape: Tuple[int]):
        # Circular buffer for storing (s, a, r, s', done) tuples
```

**Features:**
- Circular buffer implementation for memory efficiency
- Batch sampling for training stability
- Configurable capacity based on available memory

## Data Processing Pipeline

### Phase 1: Two-Pass Preprocessing

#### Pass 1: Statistics Computation
```python
def two_pass_memmap(data_dir, cache_dir, binary, chunksize=200_000):
    # First pass: compute global statistics without loading full dataset
    for csv_file in csv_files:
        for chunk in pd.read_csv(csv_file, chunksize=chunksize):
            # Accumulate sums and sum-of-squares for mean/std calculation
            # Collect unique labels
            # Identify numeric features
```

**Operations:**
- Column sanitization and identifier removal
- Feature type inference (numeric vs categorical)
- Global statistics computation (mean, std)
- Label collection and encoding preparation

#### Pass 2: Normalization and Storage
```python
# Second pass: normalize and store in memory-mapped files
X_mm = np.memmap(X_path, dtype='float32', mode='w+', shape=(total_rows, n_features))
for chunk in data_chunks:
    # Normalize: (x - mean) / std
    # Handle missing values with feature means
    # Store in memmap
```

**Operations:**
- Z-score normalization using global statistics
- Missing value imputation with feature means
- Memory-mapped storage for efficient access
- Label encoding (binary or multi-class)

### Phase 2: Data Splitting

```python
# Stratified splitting to maintain class distribution
sss = StratifiedShuffleSplit(n_splits=1, test_size=0.10, random_state=seed)
train_idx, test_idx = next(sss.split(indices, labels))
```

**Strategy:**
- 80% Training, 10% Validation, 10% Test
- Stratified sampling maintains class balance
- Reproducible splits with fixed random seed

## Training Algorithms

### Deep Q-Network (DQN) Training

#### Algorithm Flow:
1. **Experience Collection**: Interact with environment using ε-greedy policy
2. **Reward Computation**: Calculate rewards based on prediction accuracy
3. **Experience Storage**: Store (s, a, r, s') tuples in replay buffer
4. **Batch Learning**: Sample mini-batches and update Q-network
5. **Target Network Update**: Periodically sync target network

#### Reward Structure:
```python
# Reward mapping for different outcomes
rewards = {
    'correct_benign': cfg.r_tp_benign,    # Default: +1.0
    'correct_attack': cfg.r_tp_attack,    # Default: +2.0
    'false_positive': cfg.r_fp,           # Default: -1.0
    'false_negative': cfg.r_fn,           # Default: -5.0
}
```

#### Loss Function:
```python
# Smooth L1 Loss (Huber Loss) for stable training
loss = F.smooth_l1_loss(q_values, target_q_values)
```

### Actor-Critic (A3C) Training

#### Algorithm Flow:
1. **Policy Sampling**: Sample actions from policy π(a|s)
2. **Advantage Estimation**: A(s,a) = R - V(s)
3. **Policy Update**: Maximize expected return with entropy regularization
4. **Value Update**: Minimize value prediction error

#### Loss Components:
```python
actor_loss = -(log_prob * advantage.detach()).mean()
critic_loss = advantage.pow(2).mean()
entropy_loss = -entropy.mean()
total_loss = actor_loss + 0.5 * critic_loss + 0.01 * entropy_loss
```

## Memory Optimization

### Low-Memory Mode Features

When `--low-mem` flag is enabled:

```python
if cfg.low_mem:
    cfg.batch_size = min(cfg.batch_size, 256)      # Reduce batch size
    cfg.num_workers = 0                            # Disable multiprocessing
    cfg.replay_size = min(cfg.replay_size, 30000)  # Smaller replay buffer
```

### Memory-Mapped Dataset

```python
class MemmapDataset(Dataset):
    def __init__(self, X_path, y_path, meta_path, indices=None):
        # Lazy loading of memory-mapped arrays
        self.X_mm = None  # Opened on first access
        
    def __getitem__(self, idx):
        self._ensure_open()  # Open memmap if needed
        # Copy data to avoid PyTorch warnings about non-writable arrays
        x = np.array(self.X_mm[i], dtype=np.float32, copy=True)
```

### Garbage Collection Hints

```python
if low_mem:
    import gc
    gc.collect()  # Explicit garbage collection in tight loops
```

## Usage Guide

### Basic Training Command

```bash
python trainrl.py \
    --data-dir "C:/AIML/Projects/adaptive-ids/data/data_2017" \
    --binary \
    --device cuda \
    --epochs 30 \
    --batch-size 512 \
    --algo dqn
```

### Advanced Configuration

```bash
python trainrl.py \
    --data-dir "C:/path/to/data" \
    --binary \
    --device cuda \
    --epochs 50 \
    --batch-size 1024 \
    --lr 1e-4 \
    --hidden-dims "512,256,128" \
    --dropout 0.3 \
    --replay-size 100000 \
    --r_fp -2.0 \
    --r_fn -10.0 \
    --amp \
    --compile \
    --low-mem
```

### Resume Training

```bash
python trainrl.py \
    --resume "checkpoints/best_model.pth" \
    --epochs 20
```

## Configuration Parameters

### Data Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--data-dir` | str | `C:/AIML/Projects/adaptive-ids/data` | Path to CSV data directory |
| `--binary` | flag | False | Enable binary classification (Benign/Attack) |

### Model Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--algo` | str | `dqn` | Algorithm choice: `dqn` or `a3c` |
| `--hidden-dims` | str | `256,128` | Hidden layer dimensions (comma-separated) |
| `--dropout` | float | 0.2 | Dropout rate for regularization |
| `--sequence` | flag | False | Enable sequence modeling with LSTM |
| `--seq-len` | int | 4 | Sequence length for LSTM |

### Training Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--epochs` | int | 20 | Number of training epochs |
| `--batch-size` | int | 512 | Training batch size |
| `--lr` | float | 2e-4 | Learning rate |
| `--weight-decay` | float | 1e-5 | L2 regularization strength |

### RL-Specific Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--gamma` | float | 0.99 | Discount factor for future rewards |
| `--replay-size` | int | 50000 | Experience replay buffer size |
| `--eps-start` | float | 1.0 | Initial exploration rate |
| `--eps-end` | float | 0.05 | Final exploration rate |
| `--eps-decay-steps` | int | 100000 | Steps to decay exploration |

### Reward Shaping
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--r_fp` | float | -1.0 | Reward for false positive |
| `--r_fn` | float | -5.0 | Reward for false negative |
| `--r_tp_benign` | float | 1.0 | Reward for correct benign prediction |
| `--r_tp_attack` | float | 2.0 | Reward for correct attack prediction |

### System Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--device` | str | `auto` | Device: `auto`, `cuda`, or `cpu` |
| `--compile` | flag | False | Enable torch.compile optimization |
| `--amp` | flag | False | Enable automatic mixed precision |
| `--low-mem` | flag | False | Enable aggressive memory optimizations |
| `--num-workers` | int | 0 | DataLoader worker processes |

## Performance Metrics

### Classification Metrics

The model reports comprehensive metrics:

```json
{
  "accuracy": 0.9234,
  "macro_f1": 0.8567,
  "weighted_f1": 0.9123,
  "per_class": {
    "Benign": {
      "precision": 0.9456,
      "recall": 0.9234,
      "f1": 0.9344,
      "support": 15234
    },
    "Attack": {
      "precision": 0.8234,
      "recall": 0.8567,
      "f1": 0.8398,
      "support": 3456
    }
  }
}
```

### Training Metrics

Logged to TensorBoard:
- Training loss per epoch
- Validation F1 score
- Learning rate schedule
- Exploration rate (epsilon)
- Replay buffer size

### Memory Usage

Typical memory consumption:
- **Normal mode**: 8-12 GB RAM
- **Low-memory mode**: 4-6 GB RAM
- **Disk usage**: 2-5x dataset size for memmaps

## Troubleshooting

### Common Issues

#### 1. Out of Memory Errors
```bash
# Solution: Enable low-memory mode
python trainrl.py --low-mem --batch-size 256
```

#### 2. CUDA Out of Memory
```bash
# Solution: Reduce batch size or use CPU
python trainrl.py --batch-size 128 --device cpu
```

#### 3. CSV Reading Errors
```bash
# Solution: Check data directory and file formats
# Ensure CSV files have proper headers and numeric data
```

#### 4. Label Column Not Found
```bash
# Error: Label column not found
# Solution: Ensure CSV has one of: Label, label, labelname, LabelName, class, Class
```

### Performance Optimization Tips

1. **Use SSD storage** for memmap files to improve I/O performance
2. **Enable compilation** with `--compile` for 10-20% speedup
3. **Use mixed precision** with `--amp` to reduce memory usage
4. **Tune batch size** based on available GPU memory
5. **Adjust replay buffer size** based on available RAM

### Debugging

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Monitor system resources:
```bash
# Windows
tasklist /fi "imagename eq python.exe"

# Linux/Mac
htop
nvidia-smi  # For GPU monitoring
```

## File Structure

After training, the following files are generated:

```
checkpoints/
├── cache/
│   ├── X_mem.dat          # Memory-mapped features
│   ├── y_mem.npy          # Labels array
│   └── meta.pkl           # Metadata (feature names, stats)
├── best_model.pth         # Best model checkpoint
├── final_model.pth        # Final model checkpoint
├── confusion_test.png     # Confusion matrix visualization
└── metrics_test.json      # Test set metrics

runs/
└── [timestamp]/           # TensorBoard logs
    ├── events.out.tfevents.*
    └── ...
```

## Model Checkpoints

Checkpoint contents:
```python
{
    'model_state_dict': model.state_dict(),
    'meta': {
        'n_features': int,
        'feature_names': List[str],
        'means': np.ndarray,
        'stds': np.ndarray,
        'total_rows': int
    },
    'label_classes': List[str],
    'cfg': dict  # Training configuration
}
```

## Integration with Inference

The trained model can be loaded for inference:

```python
import torch
import pickle

# Load checkpoint
checkpoint = torch.load('checkpoints/best_model.pth')
model_state = checkpoint['model_state_dict']
meta = checkpoint['meta']
label_classes = checkpoint['label_classes']

# Reconstruct model
model = DQN_MLP(
    input_dim=meta['n_features'],
    output_dim=len(label_classes),
    hidden_dims=[256, 128],
    dropout=0.2
)
model.load_state_dict(model_state)
model.eval()

# Make predictions
with torch.no_grad():
    predictions = model(input_tensor)
```

## Future Enhancements

### Planned Features
1. **Distributed Training**: Multi-GPU and multi-node support
2. **Online Learning**: Continuous adaptation to new threats
3. **Attention Mechanisms**: Transformer-based architectures
4. **Adversarial Training**: Robustness against adversarial attacks
5. **Federated Learning**: Privacy-preserving collaborative training

### Research Directions
1. **Meta-Learning**: Few-shot adaptation to new attack types
2. **Causal Inference**: Understanding attack causality
3. **Explainable AI**: Interpretable decision making
4. **Graph Neural Networks**: Network topology awareness

---

## References

1. Mnih, V., et al. "Human-level control through deep reinforcement learning." Nature 518.7540 (2015): 529-533.
2. Van Hasselt, H., Guez, A., & Silver, D. "Deep reinforcement learning with double q-learning." AAAI 2016.
3. Wang, Z., et al. "Dueling network architectures for deep reinforcement learning." ICML 2016.
4. Mnih, V., et al. "Asynchronous methods for deep reinforcement learning." ICML 2016.

---

**Last Updated**: December 2024  
**Version**: 1.0  
**Author**: Adaptive IDS Team