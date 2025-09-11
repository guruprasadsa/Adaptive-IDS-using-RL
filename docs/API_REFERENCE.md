# Adaptive IDS RL Trainer - API Reference

## Command Line Interface

### Basic Usage
```bash
python trainrl.py [OPTIONS]
```

## Command Line Arguments

### Data Configuration

#### `--data-dir`
- **Type**: `str`
- **Default**: `'C:/AIML/Projects/adaptive-ids/data'`
- **Description**: Path to directory containing CSV files for training
- **Example**: `--data-dir "C:/path/to/network/data"`

#### `--binary`
- **Type**: `flag`
- **Default**: `False`
- **Description**: Enable binary classification mode (Benign vs Attack)
- **Example**: `--binary`

### Model Configuration

#### `--algo`
- **Type**: `str`
- **Choices**: `['dqn', 'a3c']`
- **Default**: `'dqn'`
- **Description**: Reinforcement learning algorithm to use
- **Example**: `--algo dqn`

#### `--hidden-dims`
- **Type**: `str`
- **Default**: `'256,128'`
- **Description**: Hidden layer dimensions (comma-separated)
- **Example**: `--hidden-dims "512,256,128"`

#### `--dropout`
- **Type**: `float`
- **Default**: `0.2`
- **Range**: `[0.0, 1.0]`
- **Description**: Dropout rate for regularization
- **Example**: `--dropout 0.3`

#### `--sequence`
- **Type**: `flag`
- **Default**: `False`
- **Description**: Enable sequence modeling with LSTM
- **Example**: `--sequence`

#### `--seq-len`
- **Type**: `int`
- **Default**: `4`
- **Description**: Sequence length for LSTM (when --sequence is enabled)
- **Example**: `--seq-len 8`

### Training Configuration

#### `--epochs`
- **Type**: `int`
- **Default**: `20`
- **Description**: Number of training epochs
- **Example**: `--epochs 50`

#### `--batch-size`
- **Type**: `int`
- **Default**: `512`
- **Description**: Training batch size
- **Example**: `--batch-size 1024`

#### `--lr`
- **Type**: `float`
- **Default**: `2e-4`
- **Description**: Learning rate for optimizer
- **Example**: `--lr 1e-4`

#### `--weight-decay`
- **Type**: `float`
- **Default**: `1e-5`
- **Description**: L2 regularization strength
- **Example**: `--weight-decay 1e-4`

### Reinforcement Learning Parameters

#### `--gamma`
- **Type**: `float`
- **Default**: `0.99`
- **Range**: `[0.0, 1.0]`
- **Description**: Discount factor for future rewards
- **Example**: `--gamma 0.95`

#### `--replay-size`
- **Type**: `int`
- **Default**: `50000`
- **Description**: Experience replay buffer capacity
- **Example**: `--replay-size 100000`

#### `--target-sync-freq`
- **Type**: `int`
- **Default**: `1000`
- **Description**: Frequency of target network synchronization (steps)
- **Example**: `--target-sync-freq 2000`

#### `--eps-start`
- **Type**: `float`
- **Default**: `1.0`
- **Range**: `[0.0, 1.0]`
- **Description**: Initial exploration rate (epsilon)
- **Example**: `--eps-start 0.9`

#### `--eps-end`
- **Type**: `float`
- **Default**: `0.05`
- **Range**: `[0.0, 1.0]`
- **Description**: Final exploration rate (epsilon)
- **Example**: `--eps-end 0.01`

#### `--eps-decay-steps`
- **Type**: `int`
- **Default**: `100000`
- **Description**: Number of steps to decay epsilon from start to end
- **Example**: `--eps-decay-steps 200000`

### Reward Shaping

#### `--r_fp`
- **Type**: `float`
- **Default**: `-1.0`
- **Description**: Reward for false positive predictions
- **Example**: `--r_fp -2.0`

#### `--r_fn`
- **Type**: `float`
- **Default**: `-5.0`
- **Description**: Reward for false negative predictions
- **Example**: `--r_fn -10.0`

#### `--r_tp_benign`
- **Type**: `float`
- **Default**: `1.0`
- **Description**: Reward for correct benign predictions
- **Example**: `--r_tp_benign 1.5`

#### `--r_tp_attack`
- **Type**: `float`
- **Default**: `2.0`
- **Description**: Reward for correct attack predictions
- **Example**: `--r_tp_attack 3.0`

### System Configuration

#### `--device`
- **Type**: `str`
- **Choices**: `['auto', 'cuda', 'cpu']`
- **Default**: `'auto'`
- **Description**: Device to use for training
- **Example**: `--device cuda`

#### `--compile`
- **Type**: `flag`
- **Default**: `False`
- **Description**: Enable torch.compile optimization
- **Example**: `--compile`

#### `--amp`
- **Type**: `flag`
- **Default**: `False`
- **Description**: Enable automatic mixed precision training
- **Example**: `--amp`

#### `--num-workers`
- **Type**: `int`
- **Default**: `0`
- **Description**: Number of DataLoader worker processes
- **Example**: `--num-workers 4`

#### `--low-mem`
- **Type**: `flag`
- **Default**: `False`
- **Description**: Enable aggressive memory optimizations
- **Example**: `--low-mem`

### I/O Configuration

#### `--log-dir`
- **Type**: `str`
- **Default**: `'runs'`
- **Description**: Directory for TensorBoard logs
- **Example**: `--log-dir "logs/experiment1"`

#### `--ckpt-dir`
- **Type**: `str`
- **Default**: `'checkpoints'`
- **Description**: Directory for model checkpoints
- **Example**: `--ckpt-dir "models/dqn_v1"`

#### `--resume`
- **Type**: `str`
- **Default**: `None`
- **Description**: Path to checkpoint file to resume training from
- **Example**: `--resume "checkpoints/best_model.pth"`

#### `--seed`
- **Type**: `int`
- **Default**: `42`
- **Description**: Random seed for reproducibility
- **Example**: `--seed 123`

## Python API

### Core Classes

#### `DQN_MLP`
```python
class DQN_MLP(nn.Module):
    def __init__(self, input_dim: int, output_dim: int, 
                 hidden_dims: List[int] = [256, 128], 
                 dropout: float = 0.2):
        """
        Dueling Deep Q-Network with MLP architecture.
        
        Args:
            input_dim: Number of input features
            output_dim: Number of output actions
            hidden_dims: List of hidden layer dimensions
            dropout: Dropout rate for regularization
        """
```

**Methods:**
- `forward(x: torch.Tensor) -> torch.Tensor`: Forward pass returning Q-values

#### `ActorCritic`
```python
class ActorCritic(nn.Module):
    def __init__(self, input_dim: int, action_dim: int,
                 hidden_dims: List[int] = [256, 128],
                 use_lstm: bool = False, seq_len: int = 1,
                 dropout: float = 0.2):
        """
        Actor-Critic network for A3C algorithm.
        
        Args:
            input_dim: Number of input features
            action_dim: Number of possible actions
            hidden_dims: List of hidden layer dimensions
            use_lstm: Whether to use LSTM for sequence modeling
            seq_len: Sequence length for LSTM
            dropout: Dropout rate for regularization
        """
```

**Methods:**
- `forward(x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]`: Returns (logits, values)

#### `ReplayBuffer`
```python
class ReplayBuffer:
    def __init__(self, capacity: int, state_shape: Tuple[int]):
        """
        Experience replay buffer for DQN training.
        
        Args:
            capacity: Maximum number of experiences to store
            state_shape: Shape of state observations
        """
```

**Methods:**
- `push_batch(states, actions, rewards, next_states, dones)`: Add batch of experiences
- `sample(batch_size: int) -> Tuple`: Sample random batch of experiences
- `__len__() -> int`: Return current buffer size

#### `MemmapDataset`
```python
class MemmapDataset(Dataset):
    def __init__(self, X_path: str, y_path: str, meta_path: str, 
                 indices: Optional[np.ndarray] = None):
        """
        PyTorch Dataset that reads from memory-mapped files.
        
        Args:
            X_path: Path to memory-mapped features file
            y_path: Path to labels numpy file
            meta_path: Path to metadata pickle file
            indices: Optional subset of indices to use
        """
```

**Methods:**
- `__len__() -> int`: Return dataset size
- `__getitem__(idx: int) -> Tuple[torch.Tensor, torch.Tensor]`: Get sample by index

### Utility Functions

#### `two_pass_memmap`
```python
def two_pass_memmap(data_dir: str, cache_dir: str, binary: bool,
                   chunksize: int = 200_000, low_mem: bool = False) -> Tuple[str, str, str]:
    """
    Two-pass preprocessing pipeline that creates memory-mapped files.
    
    Args:
        data_dir: Directory containing CSV files
        cache_dir: Directory to store processed files
        binary: Whether to use binary classification
        chunksize: Size of chunks for processing
        low_mem: Whether to use low-memory optimizations
        
    Returns:
        Tuple of (X_path, y_path, meta_path)
    """
```

#### `compute_metrics`
```python
def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, 
                   label_classes: List[str], binary: bool = False) -> Dict:
    """
    Compute comprehensive classification metrics.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        label_classes: List of class names
        binary: Whether this is binary classification
        
    Returns:
        Dictionary containing various metrics
    """
```

#### `set_seed`
```python
def set_seed(seed: int) -> None:
    """
    Set random seeds for reproducibility.
    
    Args:
        seed: Random seed value
    """
```

### Training Functions

#### `train_dqn_loop`
```python
def train_dqn_loop(model: nn.Module, target_model: nn.Module,
                  optimizer: torch.optim.Optimizer,
                  scheduler: Optional[torch.optim.lr_scheduler._LRScheduler],
                  replay: ReplayBuffer, train_loader: DataLoader,
                  val_loader: DataLoader, le: LabelEncoder,
                  cfg: argparse.Namespace, device: torch.device,
                  meta: Dict, cache_dir: str) -> None:
    """
    Main DQN training loop.
    
    Args:
        model: Main DQN model
        target_model: Target DQN model
        optimizer: Optimizer for training
        scheduler: Learning rate scheduler
        replay: Experience replay buffer
        train_loader: Training data loader
        val_loader: Validation data loader
        le: Label encoder
        cfg: Configuration object
        device: Training device
        meta: Metadata dictionary
        cache_dir: Cache directory path
    """
```

#### `train_a3c_loop`
```python
def train_a3c_loop(model: nn.Module, optimizer: torch.optim.Optimizer,
                  train_loader: DataLoader, val_loader: DataLoader,
                  le: LabelEncoder, cfg: argparse.Namespace,
                  device: torch.device, meta: Dict) -> None:
    """
    Main A3C training loop.
    
    Args:
        model: Actor-Critic model
        optimizer: Optimizer for training
        train_loader: Training data loader
        val_loader: Validation data loader
        le: Label encoder
        cfg: Configuration object
        device: Training device
        meta: Metadata dictionary
    """
```

## Configuration Object

### `argparse.Namespace` Structure
```python
cfg = argparse.Namespace(
    # Data
    data_dir='C:/AIML/Projects/adaptive-ids/data',
    binary=False,
    
    # Model
    algo='dqn',
    hidden_dims='256,128',
    dropout=0.2,
    sequence=False,
    seq_len=4,
    
    # Training
    epochs=20,
    batch_size=512,
    lr=2e-4,
    weight_decay=1e-5,
    
    # RL Parameters
    gamma=0.99,
    replay_size=50000,
    target_sync_freq=1000,
    eps_start=1.0,
    eps_end=0.05,
    eps_decay_steps=100000,
    
    # Rewards
    r_fp=-1.0,
    r_fn=-5.0,
    r_tp_benign=1.0,
    r_tp_attack=2.0,
    
    # System
    device='auto',
    compile=False,
    amp=False,
    num_workers=0,
    low_mem=False,
    
    # I/O
    log_dir='runs',
    ckpt_dir='checkpoints',
    resume=None,
    seed=42
)
```

## File Formats

### Checkpoint Format
```python
checkpoint = {
    'model_state_dict': OrderedDict,  # Model parameters
    'meta': {
        'n_features': int,            # Number of features
        'feature_names': List[str],   # Feature names
        'means': np.ndarray,          # Feature means (float32)
        'stds': np.ndarray,           # Feature stds (float32)
        'total_rows': int             # Total number of samples
    },
    'label_classes': List[str],       # Class names
    'cfg': Dict                       # Training configuration
}
```

### Metadata Format
```python
meta = {
    'n_features': int,              # Number of features
    'feature_names': List[str],     # List of feature names
    'means': np.ndarray,            # Global feature means
    'stds': np.ndarray,             # Global feature stds
    'label_classes': List[str],     # Class labels
    'total_rows': int               # Total number of samples
}
```

### Metrics Format
```python
metrics = {
    'accuracy': float,              # Overall accuracy
    'macro_f1': float,              # Macro-averaged F1 score
    'weighted_f1': float,           # Weighted F1 score
    'per_class': {
        'ClassName': {
            'precision': float,
            'recall': float,
            'f1': float,
            'support': int
        }
    }
}
```

## Environment Variables

### `MODEL_CHECKPOINT`
- **Description**: Override default checkpoint path for inference
- **Example**: `export MODEL_CHECKPOINT="/path/to/model.pth"`

### `CUDA_VISIBLE_DEVICES`
- **Description**: Specify which GPUs to use
- **Example**: `export CUDA_VISIBLE_DEVICES="0,1"`

### `PYTORCH_CUDA_ALLOC_CONF`
- **Description**: Configure CUDA memory allocation
- **Example**: `export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512"`

## Error Codes

### Exit Codes
- `0`: Success
- `1`: General error
- `2`: File not found error
- `3`: CUDA out of memory
- `4`: Invalid configuration

### Common Exceptions

#### `FileNotFoundError`
```python
# Raised when CSV files not found in data directory
raise FileNotFoundError(f'No CSVs under {data_dir}')
```

#### `ValueError`
```python
# Raised when label column not found
raise ValueError('Label column not found')

# Raised when no rows found
raise ValueError('No rows found')
```

#### `RuntimeError`
```python
# Raised on CUDA errors
RuntimeError: CUDA out of memory
```

## Integration Examples

### Loading Trained Model
```python
import torch
import pickle

# Load checkpoint
checkpoint = torch.load('checkpoints/best_model.pth', map_location='cpu')

# Extract components
model_state = checkpoint['model_state_dict']
meta = checkpoint['meta']
label_classes = checkpoint['label_classes']
config = checkpoint['cfg']

# Reconstruct model
from trainrl import DQN_MLP
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
    predicted_classes = torch.argmax(predictions, dim=1)
```

### Custom Training Loop
```python
from trainrl import DQN_MLP, ReplayBuffer, MemmapDataset
import torch
import torch.nn as nn

# Initialize components
model = DQN_MLP(input_dim=100, output_dim=2)
target_model = DQN_MLP(input_dim=100, output_dim=2)
replay = ReplayBuffer(capacity=10000, state_shape=(100,))
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
criterion = nn.SmoothL1Loss()

# Training loop
for epoch in range(epochs):
    for batch_idx, (states, actions) in enumerate(train_loader):
        # Your custom training logic here
        pass
```

---

This API reference provides comprehensive documentation for all public interfaces, configuration options, and integration patterns available in the Adaptive IDS RL Trainer.