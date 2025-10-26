# Training Performance Fixes

## Problem Analysis

Your training showed severe underperformance:
- **Validation F1**: 0.22 (should be >0.70)
- **Validation Accuracy**: 32-36% (should be >80%)
- **Router Entropy**: 0.13-0.20 (VERY LOW - indicates collapse)
- **Early Stopping**: Triggered at epoch 16 (no improvement)

### Root Causes Identified

1. **Router Collapse**: Router was routing all samples to just 1-2 specialists
   - Low entropy (0.13-0.20) indicates deterministic routing
   - Router wasn't exploring different specialists
   - Balanced sampling made collapse worse (all batches look similar)

2. **Weak Reward Signal**: Binary rewards (0 or 1) weren't teaching router effectively
   - No incentive to route to correct specialist
   - No penalty for routing to wrong specialist
   - No confidence weighting

3. **Poor Specialist Training**: Specialists only saw their own class
   - Couldn't distinguish their class from others
   - Binary classification needs both positives AND negatives

4. **Insufficient Exploration**: Low epsilon (0.3 -> 0.05) didn't force enough diversity

---

## Fixes Implemented

### 1. **Improved Reward Structure** ⭐ CRITICAL

**Before:**
```python
# Simple binary reward
rewards = is_correct.float()  # 0 or 1
```

**After:**
```python
# Multi-objective reward
correctness_reward = is_correct.float() * 2.0      # Main signal (scaled up)
routing_bonus = is_positive_class.float() * 1.0     # Reward routing to right specialist
confidence_bonus = (sp_confidence - 0.5).clamp(min=0) * 0.5  # Reward confidence
incorrect_penalty = (~is_correct).float() * -1.0    # Penalize mistakes

rewards = correctness_reward + routing_bonus + confidence_bonus + incorrect_penalty
```

**Impact**: Router now learns WHICH specialist to use, not just "is specialist correct"

### 2. **Tripled Entropy Coefficient** ⭐ CRITICAL

**Before:**
```python
entropy_coef = 0.1  # Too low with balanced sampling
```

**After:**
```python
effective_entropy_coef = args.entropy_coef * 3.0  # 0.2 * 3 = 0.6
```

**Impact**: Forces router to maintain diverse routing distribution

### 3. **Increased Exploration** ⭐ IMPORTANT

**Before:**
```python
epsilon_start = 0.3  # Too conservative
epsilon_end = 0.05
```

**After:**
```python
epsilon_start = 0.5  # Start with 50% random routing
epsilon_end = 0.1    # Keep some randomness
```

**Impact**: Forces router to try all specialists during early training

### 4. **Balanced Specialist Training** ⭐ CRITICAL

**Before:**
```python
# Only train on own class
sp_mask = (labels == sp_id)
sp_states = states[sp_mask]
sp_labels = torch.ones(...)  # All positive
```

**After:**
```python
# Train on positive AND negative samples
positive_mask = (labels == sp_id)
negative_mask = (labels != sp_id)

# Sample 2x negatives for each positive
num_negatives = min(negative_mask.sum(), num_positives * 2)
# Combine balanced positive/negative samples
```

**Impact**: Specialists learn to distinguish their class from others

### 5. **Adaptive Batch Sampling**

**Before:**
```python
# Fixed batch size
sample_size = 32
```

**After:**
```python
# Scale with buffer size
sample_size = min(64, max(32, buffer_size // 10))
```

**Impact**: Better utilization of replay buffer as training progresses

### 6. **Enhanced Diagnostics**

Added logging for:
- **Routing entropy**: Detect collapse early
- **Unique specialists used**: Track diversity
- **Routing distribution**: See which specialists are active
- **Per-epoch summaries**: Understand training dynamics

---

## Usage

### Quick Start (Recommended)

```bash
train_optimized.bat
```

This runs training with all fixes enabled:
- `--use-amp`: Mixed precision (faster on RTX 3050)
- `--use-balanced-sampling`: Handle class imbalance
- `--entropy-coef 0.2`: High entropy (tripled to 0.6 internally)
- `--batch-size 512`: Optimized for 4GB VRAM
- `--warmup-epochs 3`: Faster curriculum
- Lower learning rates (0.0005/0.0003): More stable

### Manual Training

```bash
cd backend\scripts
python train.py \
    --use-amp \
    --use-balanced-sampling \
    --entropy-coef 0.2 \
    --batch-size 512 \
    --num-epochs 30 \
    --lr-router 0.0005 \
    --lr-specialist 0.0003
```

### Diagnostic Script

Before training, analyze your data:

```bash
cd backend\scripts
python diagnose_training.py
```

This checks:
- Class distribution and imbalance
- Feature quality (NaN, Inf, variance)
- Feature normalization
- Hyperparameter recommendations

---

## Expected Results

With these fixes, you should see:

### Training Progress
- **Routing Entropy**: 1.5 - 2.5 (good diversity)
- **Unique Specialists**: 8-10 (using most specialists)
- **Policy Entropy**: 0.3 - 0.5 (healthy exploration)
- **Training F1**: 0.6+ by epoch 10

### Validation Performance
- **Validation F1**: 0.70 - 0.85
- **Validation Accuracy**: 75 - 90%
- **Per-class F1**: 0.5+ for minority classes

### What to Watch

✅ **Good signs:**
- Routing entropy > 1.5
- 7+ unique specialists used
- Validation F1 increasing steadily
- Specialist rewards > 0.5

⚠️ **Warning signs:**
- Routing entropy < 1.0 → Increase `--entropy-coef`
- Only 1-3 specialists used → Increase exploration
- Validation F1 not improving → Check class distribution
- Specialist rewards < 0.3 → Specialists not learning

---

## Monitoring Training

### TensorBoard

```bash
tensorboard --logdir=backend/model/output/logs
```

Key metrics to watch:
- `train/train_router_acc`: Router selecting correct specialist
- `val/val_macro_f1`: Overall performance
- `train/policy_entropy`: Router exploration level

### Log Files

Check `backend/model/output/logs/` for:
- Routing distribution per epoch
- Specialist training progress
- Early stopping counters

---

## Troubleshooting

### Issue: Router still collapsing (entropy < 1.0)

**Solution:**
```bash
# Increase entropy coefficient
python train.py --entropy-coef 0.3  # Will be tripled to 0.9
```

### Issue: Low validation F1 despite high training F1

**Solution:**
- Overfitting detected
- Add dropout: Modify specialist network architecture
- Reduce model capacity: Use smaller `--hidden-dims`
- More regularization: Increase `--n-step` for specialists

### Issue: Out of memory (CUDA OOM)

**Solution:**
```bash
# Reduce batch size
python train.py --batch-size 256

# Train specialists less frequently
python train.py --train-specialist-every 4

# Reduce buffer capacity
python train.py --buffer-capacity 3000
```

### Issue: Training too slow

**Solution:**
```bash
# Ensure AMP is enabled
python train.py --use-amp

# Reduce checkpoint frequency
python train.py --save-freq 10

# Use fewer data workers (if CPU bottleneck)
# Edit train.py: num_workers = 0
```

---

## Technical Details

### Entropy Tripling Rationale

With balanced sampling, each batch has similar class distribution. This makes it easier for the router to "cheat" by routing most samples to one specialist. Tripling entropy coefficient forces the router to maintain diversity in its routing policy, preventing collapse.

**Math:**
```python
# Policy loss with entropy bonus
policy_loss = -log_prob * advantage - entropy_coef * entropy

# Higher entropy_coef makes entropy term more important
# Router must maintain high entropy to minimize loss
```

### Multi-Objective Rewards

The reward structure teaches multiple objectives:

1. **Correctness (2.0)**: Specialist makes correct prediction
2. **Routing (1.0)**: Router sends sample to correct specialist
3. **Confidence (0.5)**: Specialist is confident in prediction
4. **Penalty (-1.0)**: Discourage incorrect predictions

This multi-objective approach guides the router to learn routing policy, not just classification.

### Balanced Specialist Training

Binary classifiers need balanced data:

```
Specialist 0 (Benign):
  Positive: Label=0 → Action=1
  Negative: Label≠0 → Action=0
  
Ratio: 1:2 (positives:negatives)
```

Without negatives, specialist learns to always predict "attack", achieving 100% accuracy on its own class but failing on others.

---

## Next Steps

1. **Run diagnostics**: `python backend/scripts/diagnose_training.py`
2. **Start training**: `train_optimized.bat`
3. **Monitor progress**: TensorBoard + logs
4. **Evaluate**: `python backend/scripts/eval.py` after training
5. **Iterate**: Adjust hyperparameters based on results

---

## References

- **A3C Paper**: [Asynchronous Methods for Deep RL](https://arxiv.org/abs/1602.01783)
- **DQN Paper**: [Playing Atari with Deep RL](https://arxiv.org/abs/1312.5602)
- **Entropy Regularization**: [Soft Actor-Critic](https://arxiv.org/abs/1801.01290)
- **Curriculum Learning**: [Curriculum Learning](https://ronan.collobert.com/pub/matos/2009_curriculum_icml.pdf)

---

**Created**: 2025-10-23  
**Version**: 2.0  
**Status**: ✅ Ready for training
