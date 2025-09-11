# Adaptive IDS RL Trainer - Quick Start Guide

## 🚀 Quick Start

### Prerequisites
```bash
# Required packages
pip install torch torchvision numpy pandas scikit-learn tensorboard matplotlib
```

### Basic Training (5 minutes)
```bash
# Navigate to project directory
cd C:\AIML\Projects\adaptive-ids\backend

# Train binary classifier with default settings
python trainrl.py --data-dir "C:/path/to/your/data" --binary --epochs 10
```

### Production Training (Recommended)
```bash
# Full training with optimizations
python trainrl.py \
    --data-dir "C:/AIML/Projects/adaptive-ids/data" \
    --binary \
    --device cuda \
    --epochs 30 \
    --batch-size 512 \
    --amp \
    --compile
```

## 📊 Monitor Training

### TensorBoard
```bash
# Start TensorBoard (in separate terminal)
tensorboard --logdir runs

# Open browser to: http://localhost:6006
```

### Key Metrics to Watch
- **Training Loss**: Should decrease steadily
- **Validation F1**: Should increase and stabilize
- **Attack F1** (binary mode): Focus metric for security

## 🔧 Common Configurations

### Low Memory System (8GB RAM)
```bash
python trainrl.py \
    --data-dir "C:/path/to/data" \
    --binary \
    --low-mem \
    --batch-size 256 \
    --epochs 20
```

### High Performance System (32GB+ RAM)
```bash
python trainrl.py \
    --data-dir "C:/path/to/data" \
    --binary \
    --device cuda \
    --batch-size 2048 \
    --replay-size 200000 \
    --epochs 50 \
    --amp \
    --compile
```

### Multi-class Classification
```bash
python trainrl.py \
    --data-dir "C:/path/to/data" \
    --device cuda \
    --epochs 40 \
    --hidden-dims "512,256,128"
```

## 📁 Expected Data Format

### CSV Structure
```
Label,feature1,feature2,feature3,...
Benign,0.1,0.2,0.3,...
Attack,0.8,0.9,0.7,...
BENIGN,0.05,0.1,0.15,...
DDoS,0.9,0.95,0.85,...
```

### Requirements
- ✅ CSV files with headers
- ✅ Numeric features (will be auto-detected)
- ✅ Label column (Label, label, class, etc.)
- ✅ Any number of CSV files in directory

## 🎯 Model Selection Guide

| Use Case | Algorithm | Configuration |
|----------|-----------|---------------|
| **Binary IDS** | DQN | `--binary --algo dqn` |
| **Multi-class IDS** | DQN | `--algo dqn` |
| **Sequence Detection** | DQN+LSTM | `--sequence --seq-len 4` |
| **Fast Prototyping** | A3C | `--algo a3c` |

## 📈 Performance Expectations

### Training Time (CSE-CIC-IDS2018)
- **CPU (16 cores)**: ~2-4 hours
- **GPU (RTX 3080)**: ~30-60 minutes
- **Low-mem mode**: +50% time, -60% memory

### Typical Results
- **Binary Accuracy**: 95-99%
- **Attack F1 Score**: 85-95%
- **Multi-class F1**: 80-90%

## 🛠️ Troubleshooting

### Issue: "No CSV files found"
```bash
# Check data directory
ls "C:/path/to/data"
# Ensure .csv files exist
```

### Issue: "CUDA out of memory"
```bash
# Reduce batch size
python trainrl.py --batch-size 128

# Or use CPU
python trainrl.py --device cpu
```

### Issue: "Label column not found"
```bash
# Check CSV headers - must contain one of:
# Label, label, labelname, LabelName, class, Class
```

### Issue: Training very slow
```bash
# Enable optimizations
python trainrl.py --amp --compile --device cuda
```

## 📋 Checklist for Production

- [ ] Data preprocessed and validated
- [ ] GPU available and CUDA installed
- [ ] Sufficient disk space (3x dataset size)
- [ ] TensorBoard monitoring setup
- [ ] Backup strategy for checkpoints
- [ ] Performance baseline established

## 🔄 Model Lifecycle

### 1. Initial Training
```bash
python trainrl.py --data-dir data/ --binary --epochs 30
```

### 2. Monitor & Evaluate
```bash
# Check TensorBoard metrics
# Review confusion matrix: checkpoints/confusion_test.png
# Analyze metrics: checkpoints/metrics_test.json
```

### 3. Fine-tune (if needed)
```bash
# Adjust hyperparameters
python trainrl.py --lr 1e-5 --r_fn -10.0 --epochs 10
```

### 4. Resume Training
```bash
python trainrl.py --resume checkpoints/best_model.pth --epochs 20
```

### 5. Deploy
```bash
# Model ready at: checkpoints/best_model.pth
# Use with inference system
```

## 📞 Support

### Log Files
- Training logs: Console output
- TensorBoard: `runs/` directory
- Model checkpoints: `checkpoints/` directory

### Debug Mode
```bash
# Enable verbose logging
python trainrl.py --data-dir data/ --binary -v
```

### Performance Profiling
```bash
# Monitor system resources during training
# Windows: Task Manager
# Linux: htop, nvidia-smi
```

---

**Need Help?** Check the full documentation: `MODEL_DOCUMENTATION.md`