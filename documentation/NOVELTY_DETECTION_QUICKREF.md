# Novelty Detection Quick Reference

## Quick Start

### 1. Train Novelty Detector

```python
from model.novelty import IsolationForestDetector

# Load normal traffic data
normal_features = load_normal_traffic()  # (n_samples, 85)

# Create and train detector
detector = IsolationForestDetector(threshold=0.5)
detector.fit(normal_features)
detector.save("models/novelty/detector")
```

### 2. Detect Novel Patterns

```python
from model.novelty import NoveltyIntegration

# Initialize integration
integration = NoveltyIntegration(
    detector=detector,
    review_queue_path="data/review_queue"
)

# Check for novelty
results, novel_indices = integration.check_novelty(features)

# Route to review queue
if novel_indices:
    integration.route_to_review_queue(features, results, novel_indices)
```

### 3. Create Specialist

```bash
# After human labeling
python backend/model/novelty/scaffold_specialist.py \
    --attack-class dns_tunneling \
    --description "Detects DNS tunneling" \
    --data data/labeled/dns_tunneling.csv
```

### 4. Train Specialist

```bash
# Train the new specialist
python backend/model/specialists/dns_tunneling/train.py
```

## Common Commands

### Test Novelty Detection
```bash
pytest backend/tests/test_novelty_detection.py -v
```

### Create Specialist (Full Options)
```bash
python backend/model/novelty/scaffold_specialist.py \
    --attack-class sql_injection \
    --description "SQL injection detector" \
    --data data/labeled/sql_injection.csv \
    --hidden-dims 256 128 64 \
    --learning-rate 0.0005 \
    --episodes 2000
```

### Check Review Queue
```python
labeled_batches = integration.check_review_queue_for_labeled_data()
for batch in labeled_batches:
    print(f"{batch['attack_class']}: {batch['sample_count']} samples")
```

## Detector Comparison

| Feature | IsolationForest | Autoencoder |
|---------|----------------|-------------|
| **Speed** | ⚡⚡⚡ Fast | ⚡⚡ Moderate |
| **Accuracy** | ⭐⭐⭐ Good | ⭐⭐⭐⭐ Better |
| **GPU Support** | ❌ No | ✅ Yes |
| **Training Time** | <1s (1K samples) | ~30s CPU, ~5s GPU |
| **Memory** | ~5 MB | ~20 MB CPU, ~200 MB GPU |
| **Best For** | Real-time, high-volume | Complex patterns |

## Configuration Presets

### Fast Detection (Dev)
```python
IsolationForestDetector(
    threshold=0.5,
    n_estimators=50,
    n_jobs=-1
)
```

### High Accuracy (Prod)
```python
IsolationForestDetector(
    threshold=0.6,
    n_estimators=200,
    max_samples=512,
    n_jobs=-1
)
```

### Deep Learning (Complex Patterns)
```python
AutoencoderDetector(
    threshold=0.65,
    encoding_dims=[128, 64, 32],
    epochs=100,
    device='cuda'
)
```

## Review Queue Workflow

1. **Novel samples detected** → Saved to `data/review_queue/novel_batch_*.json`
2. **Human reviewer** → Opens file, sets `label` field for each sample
3. **Mark reviewed** → Set `reviewed=true`, `reviewed_at=timestamp`
4. **Check for labeled data** → `integration.check_review_queue_for_labeled_data()`
5. **Create specialist** → `integration.trigger_specialist_creation(...)`
6. **Train specialist** → Run generated `train.py` script
7. **Register in router** → Add to `backend/model/router/config.yaml`

## File Locations

```
backend/model/novelty/        # Core novelty detection
backend/model/specialists/    # Specialist agents
data/review_queue/            # Novel samples for review
data/labeled/                 # Labeled training data
models/novelty/               # Saved detectors
```

## Troubleshooting

### High novelty rate (>5%)
- **Cause**: Detector not trained on representative data
- **Fix**: Retrain with more diverse normal traffic

### Low novel detection
- **Cause**: Threshold too high or contamination too low
- **Fix**: Lower threshold to 0.4-0.5, increase contamination to 0.01-0.05

### Slow inference
- **Cause**: Autoencoder on CPU
- **Fix**: Switch to IsolationForest or use GPU for Autoencoder

### Specialist creation fails
- **Cause**: Missing dependencies or incorrect data format
- **Fix**: Check `train.py` script, ensure CSV has 'label' column

## Monitoring

```python
# Get statistics
stats = integration.get_stats()

# Key metrics
novelty_rate = stats['novelty_rate']           # Should be <5%
total_checked = stats['total_checked']
novel_detected = stats['novel_detected']
specialists_created = stats['specialists_created']

# Alert conditions
if novelty_rate > 0.05:
    alert("High novelty rate - possible attack or drift")
```

## Next Steps

After implementing novelty detection:
1. ✅ Test with synthetic novel traffic
2. ⏭️ Integrate into inference pipeline
3. ⏭️ Implement hot-reload for router
4. ⏭️ Set up monitoring dashboard
5. ⏭️ Deploy to production with human review process
