# Online Learning Quick Reference

## Quick Start (5 Minutes)

### 1. Start Online Learning Service

```bash
# Create config file
cat > config/online_learning.json << EOF
{
  "buffer_size": 10000,
  "fp_buffer_size": 5000,
  "registry_dir": "backend/model/registry",
  "device": "cpu",
  "training_interval_hours": 24
}
EOF

# Start service
python -c "
from backend.model.service.online_learning import create_service
import time

service = create_service('config/online_learning.json')
service.start()
print('Service started')

# Keep running
while True:
    time.sleep(60)
    status = service.get_status()
    print(f'Status: {status}')
"
```

### 2. Initialize Drift Detection

```python
from backend.stream.drift_detector import DriftDetectionSystem
import numpy as np

# Load baseline data
X_baseline = np.load('data/processed/X_train.npy')[:1000]
feature_names = [f"feat_{i}" for i in range(X_baseline.shape[1])]

# Initialize
drift_system = DriftDetectionSystem()
drift_system.initialize_baseline(
    X_baseline, 
    feature_names,
    np.random.dirichlet([1]*15, size=1000)  # Mock confidences
)
```

### 3. Integrate with Inference

```python
# In your inference service
@app.post("/predict")
async def predict(features: List[float]):
    # ... existing inference code ...
    
    # Check drift
    metrics = drift_system.check_drift(
        confidence=confidence,
        is_error=False,
        features=np.array(features),
        confidence_dist=softmax_output
    )
    
    # Add to buffer
    online_service.sample_buffer.add_sample(
        np.array(features), pred_class, confidence, datetime.utcnow()
    )
    
    return {
        "prediction": pred_class,
        "drift_severity": metrics.severity
    }
```

## Common Commands

### Check Service Status

```python
from backend.model.service.online_learning import ModelRegistry

registry = ModelRegistry('backend/model/registry')
active = registry.get_active_version()

print(f"Active Version: {active.version_id}")
print(f"Timestamp: {active.timestamp}")
print(f"Metrics: {active.validation_metrics}")
print(f"Status: {active.status}")
```

### Manual Training Trigger

```python
service.run_training_cycle()
```

### Add False Positive

```python
service.sample_buffer.add_false_positive(
    features=feature_vector,
    true_label=correct_label,
    pred_label=wrong_prediction,
    timestamp=datetime.utcnow()
)
```

### List All Model Versions

```python
versions = registry.list_versions()
for v in versions[:5]:  # Last 5
    print(f"{v.version_id}: TPR={v.validation_metrics['macro_tpr']:.3f}, "
          f"FPR={v.validation_metrics['macro_fpr']:.4f}, Status={v.status}")
```

### Rollback Model

```python
# Promote previous version
registry.promote_to_active('previous_version_id')

# Restart inference service
# systemctl restart ids-model-service
```

## Monitoring Queries

### Prometheus Queries

```promql
# Current drift scores
ids_drift_score

# Drift alert rate (last hour)
rate(ids_drift_alerts_total[1h])

# Top drifting features
topk(5, ids_feature_psi)

# Critical drift alerts
ids_drift_alerts_total{severity="critical"}
```

### Log Queries

```bash
# Drift detections
grep "drift detected" logs/drift_detector.log | tail -20

# Training cycles
grep "Training cycle" logs/online_learning.log | tail -10

# Model promotions
grep "Promoted version" logs/online_learning.log
```

## Configuration Parameters

### Drift Detection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `adwin_delta` | 0.002 | Sensitivity (lower = more sensitive) |
| `ddm_warning` | 2.0 | Warning threshold (std devs) |
| `ddm_drift` | 3.0 | Drift threshold (std devs) |
| `psi_threshold` | 0.2 | PSI drift threshold |
| `js_threshold` | 0.1 | JS divergence threshold |
| `js_window` | 1000 | Window size for JS |

### Online Learning

| Parameter | Default | Description |
|-----------|---------|-------------|
| `buffer_size` | 10000 | Recent samples buffer |
| `fp_buffer_size` | 5000 | False positive buffer |
| `batch_size` | 128 | Training batch size |
| `learning_rate` | 0.0001 | Fine-tuning LR |
| `num_epochs` | 3 | Fine-tuning epochs |
| `ewc_lambda` | 1000.0 | EWC regularization strength |
| `min_tpr` | 0.985 | Minimum TPR for promotion |
| `max_fpr` | 0.01 | Maximum FPR for promotion |
| `training_interval_hours` | 24 | Hours between training |

## Troubleshooting Quick Fixes

### Too Many Drift Alerts

```python
# Increase thresholds
drift_config = {
    'adwin_delta': 0.005,
    'psi_threshold': 0.25,
    'js_threshold': 0.15
}
```

### Model Forgetting Old Classes

```python
# Increase EWC strength
config['ewc_lambda'] = 5000.0
```

### Slow Training

```python
# Reduce batch size or epochs
config['batch_size'] = 64
config['num_epochs'] = 2
```

### Out of Memory

```python
# Use CPU or smaller batch
config['device'] = 'cpu'
config['batch_size'] = 32
```

## Testing Checklist

- [ ] Drift detector initialized with baseline
- [ ] Service started and running
- [ ] Buffer receiving samples
- [ ] Prometheus metrics exposed
- [ ] Manual training cycle succeeds
- [ ] Validation gates working
- [ ] False positives being collected
- [ ] Model registry persisting versions
- [ ] Rollback tested
- [ ] Grafana dashboards showing data

## Expected Results

### Drift Detection
- Alerts on PSI > 0.2 (medium) or > 0.25 (high)
- JS divergence > 0.1 triggers warning
- DDM fires on 3σ error rate increase
- ADWIN detects confidence distribution shifts

### Fine-Tuning
- Training completes in 5-15 minutes
- TPR degradation < 0.5%
- FP rate reduction > 20%
- Memory usage < 4GB GPU

### Model Versioning
- New version created each cycle
- Registry persists to disk
- Validation metrics logged
- Failed models not promoted

## API Endpoints (if exposed)

```python
# GET /online-learning/status
{
  "running": true,
  "last_training": "2025-10-24T10:00:00",
  "buffer_stats": {
    "recent_samples": 5234,
    "false_positives": 142
  },
  "active_version": "a3f2c8e9b1d4"
}

# POST /online-learning/trigger
# Manually trigger training cycle

# GET /online-learning/versions
[
  {
    "version_id": "a3f2c8e9b1d4",
    "timestamp": "2025-10-24T10:00:00",
    "status": "active",
    "metrics": {...}
  }
]

# POST /online-learning/rollback/{version_id}
# Rollback to specific version
```

## Performance Targets

| Metric | Target | Typical |
|--------|--------|---------|
| Drift check latency | < 1ms | 0.1-0.5ms |
| Training time (2K samples) | < 10 min | 5 min |
| Memory (training) | < 4GB | 2-3GB |
| FP reduction | > 20% | 25-40% |
| TPR degradation | < 0.5% | 0.1-0.3% |
| Validation pass rate | > 80% | 85-90% |

## Maintenance Tasks

### Daily
- Check drift alert counts
- Review buffer sizes
- Monitor training completions

### Weekly
- Review model versions
- Analyze FP trends
- Validate drift thresholds

### Monthly
- Refresh baseline distributions
- Audit model registry
- Review rollback history
- Optimize hyperparameters

## Support

For issues or questions:
1. Check logs in `logs/online_learning.log`
2. Review metrics in Grafana
3. Inspect registry at `backend/model/registry/registry.json`
4. Run tests: `pytest backend/tests/test_online_learning.py -v`
