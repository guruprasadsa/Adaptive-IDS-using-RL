# Adaptive IDS RL Trainer - Technical Architecture

## System Architecture Overview

The Adaptive IDS RL Trainer implements a sophisticated reinforcement learning pipeline optimized for intrusion detection on network traffic data. The system is designed with memory efficiency, scalability, and performance as primary concerns.

## Core Components

### 1. Data Processing Engine

#### Two-Pass Streaming Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CSV Files     │───▶│   Pass 1:       │───▶│   Pass 2:       │
│   (Raw Data)    │    │   Statistics    │    │   Normalize &   │
│                 │    │   Computation   │    │   Store         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Global Stats  │    │   Memory Maps   │
                       │   (mean, std)   │    │   (X, y)        │
                       └─────────────────┘    └─────────────────┘
```

**Pass 1: Statistics Collection**
- Streams through all CSV files in chunks
- Computes running statistics (sum, sum-of-squares)
- Identifies numeric features automatically
- Collects unique labels for encoding
- Memory footprint: O(features) instead of O(samples)

**Pass 2: Normalization & Storage**
- Applies Z-score normalization using global statistics
- Stores normalized data in memory-mapped files
- Handles missing values with feature means
- Creates stratified train/validation/test splits

#### Memory-Mapped Dataset
```python
class MemmapDataset(Dataset):
    """
    Lazy-loading dataset that reads from disk-based memory maps
    - Supports datasets larger than RAM
    - Worker-safe with lazy initialization
    - Minimal memory footprint per sample
    """
```

### 2. Reinforcement Learning Models

#### Deep Q-Network (DQN) Architecture

```
Input Features (n_features)
         │
         ▼
┌─────────────────┐
│  Feature Net    │  ← Shared feature extraction
│  (BatchNorm +   │    - Linear layers with BatchNorm
│   ReLU +        │    - ReLU activations
│   Dropout)      │    - Dropout regularization
└─────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌─────────┐
│ Value   │ │Advantage│  ← Dueling architecture
│ Stream  │ │ Stream  │    - Separate value/advantage estimation
│ V(s)    │ │ A(s,a)  │    - Improved learning stability
└─────────┘ └─────────┘
    │         │
    └────┬────┘
         ▼
    Q(s,a) = V(s) + A(s,a) - mean(A(s,��))
```

**Key Features:**
- **Dueling Architecture**: Separates state value from action advantages
- **Double DQN**: Uses separate target network to reduce overestimation
- **Experience Replay**: Stores and samples past experiences
- **Epsilon-Greedy**: Balances exploration vs exploitation

#### Actor-Critic (A3C) Architecture

```
Input Features (n_features)
         │
         ▼
┌───────���─────────┐
│  Shared Net     │  ← Common feature extraction
│  (Linear +      │    - Fully connected layers
│   ReLU +        │    - Optional LSTM for sequences
│   Dropout)      │    - Shared parameters for efficiency
└─────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌─────────┐
│ Actor   │ │ Critic  │
│ π(a|s)  │ │ V(s)    │  ← Policy and value estimation
└─────────┘ └─────────┘
```

**Key Features:**
- **Policy Gradient**: Direct policy optimization
- **Value Function**: Reduces variance in policy updates
- **Entropy Regularization**: Encourages exploration
- **LSTM Support**: Handles sequential patterns in network traffic

### 3. Training Infrastructure

#### Mixed Precision Training
```python
# Automatic Mixed Precision (AMP) for memory efficiency
with torch.amp.autocast(device_type='cuda', enabled=cfg.amp):
    q_values = model(states)
    loss = criterion(q_values, targets)

scaler.scale(loss).backward()
scaler.step(optimizer)
scaler.update()
```

#### Model Compilation
```python
# torch.compile for optimized execution
if cfg.compile:
    model = torch.compile(model, mode='default')
    # 10-20% speedup on modern GPUs
```

#### Experience Replay System
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Environment   │───▶│  Replay Buffer  │───▶│   Training      │
│   Interaction   │    │  (Circular)     │    │   Batch         │
│                 │    │                 │    │                 │
│ (s,a,r,s',done) │    │ Capacity: 50k   │    │ Sample: 512     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 4. Reward Engineering

#### Reward Structure for IDS
```python
def compute_reward(prediction, ground_truth, label_encoder):
    """
    Reward shaping for intrusion detection:
    - Higher rewards for detecting attacks (security priority)
    - Severe penalty for missing attacks (false negatives)
    - Moderate penalty for false alarms (false positives)
    """
    if prediction == ground_truth:
        if is_benign(ground_truth):
            return cfg.r_tp_benign    # +1.0
        else:
            return cfg.r_tp_attack    # +2.0 (prioritize attack detection)
    else:
        if is_false_negative(prediction, ground_truth):
            return cfg.r_fn           # -5.0 (severe penalty)
        else:
            return cfg.r_fp           # -1.0 (moderate penalty)
```

### 5. Memory Optimization Strategies

#### Low-Memory Mode
```python
if cfg.low_mem:
    # Aggressive memory optimizations
    cfg.batch_size = min(cfg.batch_size, 256)      # Smaller batches
    cfg.num_workers = 0                            # No multiprocessing
    cfg.replay_size = min(cfg.replay_size, 30000)  # Smaller replay buffer
    
    # Explicit garbage collection
    import gc
    gc.collect()
```

#### Memory-Mapped Storage
- **Features**: Stored as float32 memory-mapped arrays
- **Labels**: Stored as int32 numpy arrays
- **Lazy Loading**: Data loaded only when accessed
- **Copy-on-Access**: Ensures PyTorch compatibility

### 6. Training Loop Architecture

#### DQN Training Loop
```
┌─────────────────┐
│ Initialize      │
│ - Model         │
│ - Target Model  │
│ - Replay Buffer │
│ - Optimizer     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ For each epoch: │◄─────────┐
│                 │          │
│ 1. Collect      │          │
│    experiences  │          │
│ 2. Store in     │          │
│    replay       │          │
│ 3. Sample batch │          │
│ 4. Compute loss │          │
│ 5. Update model │          │
│ 6. Sync target  │          │
│ 7. Validate     │          │
└─────────────────┘          │
         │                   │
         ▼                   │
┌─────────────────┐          │
│ Checkpoint      │          │
│ if improved     │──────────┘
└─────────────────┘
```

#### Key Training Steps:

1. **Experience Collection**:
   ```python
   # Epsilon-greedy action selection
   if random.random() < epsilon:
       action = random.choice(actions)
   else:
       action = model(state).argmax()
   ```

2. **Reward Computation**:
   ```python
   # IDS-specific reward calculation
   reward = compute_ids_reward(prediction, ground_truth)
   ```

3. **Batch Learning**:
   ```python
   # Double DQN update
   current_q = model(states).gather(1, actions)
   next_actions = model(next_states).argmax(1)
   target_q = target_model(next_states).gather(1, next_actions)
   ```

### 7. Evaluation & Metrics

#### Comprehensive Metrics Collection
```python
def compute_metrics(y_true, y_pred, label_classes):
    return {
        'accuracy': accuracy_score(y_true, y_pred),
        'macro_f1': f1_score(y_true, y_pred, average='macro'),
        'weighted_f1': f1_score(y_true, y_pred, average='weighted'),
        'per_class': {
            class_name: {
                'precision': precision,
                'recall': recall,
                'f1': f1_score,
                'support': support
            }
        }
    }
```

#### Visualization
- Confusion matrices saved as PNG
- TensorBoard integration for real-time monitoring
- JSON metrics for programmatic analysis

### 8. Checkpointing System

#### Checkpoint Contents
```python
checkpoint = {
    'model_state_dict': model.state_dict(),
    'meta': {
        'n_features': int,
        'feature_names': List[str],
        'means': np.ndarray,        # For inference normalization
        'stds': np.ndarray,         # For inference normalization
        'total_rows': int
    },
    'label_classes': List[str],     # For label decoding
    'cfg': dict                     # Training configuration
}
```

#### Checkpoint Strategy
- **Best Model**: Saved when validation metric improves
- **Final Model**: Saved at end of training
- **Resume Support**: Can restart from any checkpoint
- **Metadata Preservation**: All necessary info for inference

### 9. Performance Optimizations

#### CUDA Optimizations
```python
if device.type == 'cuda':
    torch.backends.cudnn.benchmark = True      # Optimize for fixed input sizes
    torch.set_float32_matmul_precision('high') # Enable TF32 on Ampere GPUs
```

#### DataLoader Optimizations
```python
dataloader_kwargs = {
    'batch_size': cfg.batch_size,
    'num_workers': cfg.num_workers,
    'pin_memory': True,              # Faster GPU transfers
    'persistent_workers': True       # Avoid worker respawn overhead
}
```

### 10. Scalability Considerations

#### Horizontal Scaling
- Memory-mapped data can be shared across processes
- Model parallelism possible with larger architectures
- Distributed training support (future enhancement)

#### Vertical Scaling
- Automatic batch size adjustment based on GPU memory
- Dynamic replay buffer sizing
- Adaptive chunk sizes for data processing

## Data Flow Diagram

```
Raw CSV Files
     │
     ▼
┌─────────────────┐
│ Two-Pass        │
│ Preprocessing   │
└───────���─────────┘
     │
     ▼
┌─────────────────┐
│ Memory-Mapped   │
│ Storage         │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ Stratified      │
│ Splitting       │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ DataLoaders     │
│ (Train/Val/Test)│
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ RL Training     │
│ Loop            │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ Model           │
│ Checkpoints     │
└─────────────────┘
```

## Security Considerations

### Data Privacy
- No raw data stored in memory longer than necessary
- Memory-mapped files can be encrypted at rest
- Secure deletion of temporary files

### Model Security
- Checkpoints include integrity information
- Training logs don't expose sensitive data
- Reproducible training with fixed seeds

### Deployment Security
- Model validation before deployment
- Adversarial robustness testing recommended
- Monitoring for model drift in production

## Future Architecture Enhancements

### Planned Improvements
1. **Distributed Training**: Multi-GPU and multi-node support
2. **Online Learning**: Continuous adaptation capabilities
3. **Model Compression**: Quantization and pruning for edge deployment
4. **Federated Learning**: Privacy-preserving collaborative training

### Research Directions
1. **Attention Mechanisms**: Transformer-based architectures
2. **Graph Neural Networks**: Network topology awareness
3. **Meta-Learning**: Few-shot adaptation to new attack types
4. **Causal Inference**: Understanding attack causality chains

---

This architecture provides a robust, scalable, and efficient foundation for training reinforcement learning models on large-scale network intrusion detection datasets while maintaining memory efficiency and high performance.