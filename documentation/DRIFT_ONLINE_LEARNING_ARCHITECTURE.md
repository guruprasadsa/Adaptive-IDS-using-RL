# Drift Detection and Online Learning Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Production Traffic                               │
│                   (Network Packets → Feature Extraction)                 │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────────────┐
         │         Inference Service (FastAPI)            │
         │  ┌──────────────────────────────────────────┐ │
         │  │  Model: Router + DQN Specialists         │ │
         │  │  Input: 78 features                      │ │
         │  │  Output: 15 classes + confidences        │ │
         │  └──────────────────────────────────────────┘ │
         └───────┬────────────────────────┬──────────────┘
                 │                        │
                 │                        │
    ┌────────────▼────────────┐  ┌────────▼────────────┐
    │  Drift Detection        │  │  Sample Buffer      │
    │  ┌──────────────────┐   │  │  ┌───────────────┐  │
    │  │ ADWIN           │   │  │  │ Recent: 10K  │  │
    │  │ - Confidence    │   │  │  │ samples      │  │
    │  │   shifts        │   │  │  └───────────────┘  │
    │  ├──────────────────┤   │  │  ┌───────────────┐  │
    │  │ DDM             │   │  │  │ FPs: 5K      │  │
    │  │ - Error rate    │   │  │  │ samples      │  │
    │  │   monitoring    │   │  │  └───────────────┘  │
    │  ├──────────────────┤   │  └──────────┬──────────┘
    │  │ PSI             │   │             │
    │  │ - Feature       │   │             │
    │  │   distribution  │   │             │
    │  ├──────────────────┤   │             │
    │  │ JS Divergence   │   │             │
    │  │ - Class dist    │   │             │
    │  └──────────────────┘   │             │
    └─────────┬───────────────┘             │
              │                             │
              │ Severity:                   │
              │ low/medium/                 │
              │ high/critical               │
              │                             │
              ▼                             ▼
    ┌─────────────────────┐    ┌────────────────────────┐
    │  Prometheus         │    │  Analyst Feedback      │
    │  Metrics            │    │  (False Positives)     │
    │  - Drift scores     │    │  - Confirmed FPs       │
    │  - Alert counts     │    │  - Corrected labels    │
    │  - Feature PSI      │    └──────────┬─────────────┘
    └─────────┬───────────┘               │
              │                           │
              ▼                           ▼
    ┌─────────────────────┐    ┌────────────────────────┐
    │  Grafana            │    │  FP Buffer Update      │
    │  Dashboards         │    │  (Priority samples     │
    │  - Drift trends     │    │   for fine-tuning)     │
    │  - Alert history    │    └──────────┬─────────────┘
    │  - Top features     │               │
    └─────────────────────┘               │
                                          │
              ┌───────────────────────────┘
              │
              │ Scheduled/
              │ Manual Trigger
              │
              ▼
    ┌─────────────────────────────────────────┐
    │  Online Learning Service                │
    │  ┌───────────────────────────────────┐  │
    │  │  1. Get Balanced Batch            │  │
    │  │     (70% recent + 30% FPs)        │  │
    │  └───────────────┬───────────────────┘  │
    │  ┌───────────────▼───────────────────┐  │
    │  │  2. Compute Fisher Matrix         │  │
    │  │     (on validation set)           │  │
    │  └───────────────┬───────────────────┘  │
    │  ┌───────────────▼───────────────────┐  │
    │  │  3. EWC Fine-Tuning               │  │
    │  │     L = L_CE + λ * L_EWC          │  │
    │  │     (3 epochs, lr=1e-4)           │  │
    │  └───────────────┬───────────────────┘  │
    │  ┌───────────────▼───────────────────┐  │
    │  │  4. Validation Gate               │  │
    │  │     ✓ TPR ≥ 98.5%                 │  │
    │  │     ✓ FPR ≤ 1%                    │  │
    │  └───────────────┬───────────────────┘  │
    │                  │                       │
    │         Pass ────┼──── Fail             │
    │         │        │        │              │
    │         ▼        │        ▼              │
    │  ┌──────────┐   │  ┌──────────┐         │
    │  │ Version  │   │  │ Rollback │         │
    │  │ & Save   │   │  │ (no      │         │
    │  └────┬─────┘   │  │  change) │         │
    │       │         │  └──────────┘         │
    │       ▼         │                       │
    │  ┌──────────┐   │                       │
    │  │ Promote  │   │                       │
    │  │ to Active│   │                       │
    │  └──────────┘   │                       │
    └──────┬───────────┴───────────────────────┘
           │
           ▼
    ┌─────────────────────────────┐
    │  Model Registry             │
    │  ┌─────────────────────────┐│
    │  │ version_1: retired      ││
    │  ├─────────────────────────┤│
    │  │ version_2: retired      ││
    │  ├─────────────────────────┤│
    │  │ version_3: active ←     ││
    │  ├─────────────────────────┤│
    │  │ version_4: shadow       ││
    │  └─────────────────────────┘│
    │  registry.json              │
    └─────────────┬───────────────┘
                  │
                  │ Load active
                  │ checkpoint
                  ▼
         ┌────────────────┐
         │  Restart       │
         │  Inference     │
         │  Service       │
         └────────────────┘
```

## Data Flow Details

### 1. Prediction Pipeline
```
Packet → Features → Model → [Class, Confidence, Distribution]
                              │      │            │
                              ├──────┼────────────┘
                              ▼      ▼            ▼
                        Prediction  Drift     Buffer
                        Response    Check     Update
```

### 2. Drift Detection Flow
```
Confidence      →  ADWIN  →  Drift Score
Error Status    →  DDM    →  Performance Drift
Features        →  PSI    →  Feature Drift (per feature)
Confidence Dist →  JS     →  Distribution Drift
                     │
                     ├─→ Aggregate Severity
                     │   (low/medium/high/critical)
                     │
                     └─→ Prometheus Metrics
                         └─→ Grafana Alerts
```

### 3. Fine-Tuning Workflow
```
Buffer (10K recent + 5K FPs)
    │
    ├─→ Sample 70% recent (1400 samples)
    ├─→ Sample 30% FPs (600 samples)
    │
    ├─→ Balanced Batch (2000 samples)
        │
        ├─→ Compute Fisher Matrix (val set)
        │   └─→ Store F_i for each parameter
        │
        ├─→ Fine-tune with EWC
        │   │
        │   ├─→ Epoch 1: L = L_CE + λ * Σ F_i(θ_i - θ*_i)²
        │   ├─→ Epoch 2: ...
        │   └─→ Epoch 3: ...
        │
        ├─→ Validate (val set)
        │   │
        │   ├─→ TPR ≥ 98.5%? ──┐
        │   └─→ FPR ≤ 1.0%?   ──┤
        │                       │
        │        Pass ──────────┼──── Fail
        │         │             │      │
        │         ▼             │      ▼
        │   Version & Save      │   Discard
        │         │             │      │
        │         ▼             │      └─→ Log failure
        │   Promote to Active   │
        │         │             │
        │         └─────────────┘
        │
        └─→ Model Registry
            └─→ registry.json updated
```

### 4. Model Version Lifecycle
```
Training → [New Model]
             │
             ├─→ Validation Pass?
             │       │
             │      Yes ──→ status: shadow
             │       │           │
             │       │      Shadow Eval (optional)
             │       │           │
             │       │           ├─→ Good ──→ Promote
             │       │           │              │
             │       │           │              ▼
             │       │           │         status: active
             │       │           │              │
             │       │           │         [Serve Traffic]
             │       │           │              │
             │       │           │         New version?
             │       │           │              │
             │       │           │              ▼
             │       │           │         status: retired
             │       │           │
             │       │           └─→ Bad ──→ status: failed
             │       │
             │      No ──→ status: failed
             │              │
             │              └─→ Rollback (no change)
             │
             └─→ All versions persist in registry
```

## Component Interactions

### Sample Buffer Thread Safety
```
Thread 1: Inference           Thread 2: Training
    │                             │
    ├─→ buffer.add_sample()       │
    │   └─→ [acquire lock]        │
    │       └─→ append to deque   │
    │           └─→ [release lock]│
    │                             │
    │                             ├─→ buffer.get_training_batch()
    │                             │   └─→ [acquire lock]
    │                             │       └─→ sample from deques
    │                             │           └─→ [release lock]
    │                             │
    └─→ buffer.add_sample()       │
        └─→ [wait for lock]  ─────┘
            └─→ [acquire lock]
                └─→ append
                    └─→ [release lock]
```

### EWC Regularization
```
Old Task (Validation Set)
    │
    ├─→ Forward Pass
    │   └─→ Compute Loss
    │       └─→ Backward
    │           └─→ Accumulate ∇²L
    │               └─→ Fisher Matrix F
    │                   └─→ Store old params θ*
    │
New Task (Training Batch)
    │
    ├─→ Forward Pass
    │   └─→ Cross-Entropy Loss: L_CE
    │       │
    │       ├─→ EWC Penalty: λ/2 * Σ F_i(θ_i - θ*_i)²
    │       │
    │       └─→ Total Loss: L_CE + L_EWC
    │           └─→ Backward
    │               └─→ Update params θ
    │                   (important params change less)
```

## Monitoring Dashboard Layout

```
┌────────────────────────────────────────────────────────────┐
│  IDS Drift Detection & Online Learning Dashboard          │
├────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ Drift Score      │  │ Alert Rate       │               │
│  │ (ADWIN)          │  │ (last 1h)        │               │
│  │ [Line Chart]     │  │ [Counter]        │               │
│  └──────────────────┘  └──────────────────┘               │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ Top 5 Drifting   │  │ Buffer Status    │               │
│  │ Features         │  │ Recent: 8523/10K │               │
│  │ [Bar Chart]      │  │ FPs:    142/5K   │               │
│  └──────────────────┘  └──────────────────┘               │
│  ┌────────────────────────────────────────┐               │
│  │ Model Versions                         │               │
│  │ v_abc123: active   | TPR: 99.1% | 1h  │               │
│  │ v_def456: retired  | TPR: 98.8% | 1d  │               │
│  │ v_ghi789: retired  | TPR: 98.5% | 2d  │               │
│  └────────────────────────────────────────┘               │
│  ┌────────────────────────────────────────┐               │
│  │ Training History (last 7 days)         │               │
│  │ [Timeline with success/fail markers]   │               │
│  └────────────────────────────────────────┘               │
└────────────────────────────────────────────────────────────┘
```

## Files and Directories

```
backend/
├── stream/
│   └── drift_detector.py          (600 lines)
│       ├── ADWINDetector
│       ├── DDMDetector
│       ├── PSIDetector
│       ├── JSDivergenceDetector
│       └── DriftDetectionSystem
│
├── model/
│   ├── service/
│   │   ├── online_learning.py     (750 lines)
│   │   │   ├── SampleBuffer
│   │   │   ├── EWCTrainer
│   │   │   ├── ModelRegistry
│   │   │   ├── ModelVersion
│   │   │   └── OnlineLearningService
│   │   │
│   │   └── app_with_online_learning.py (400 lines)
│   │       └── FastAPI integration example
│   │
│   ├── registry/
│   │   ├── registry.json          (version metadata)
│   │   └── {version_id}/
│   │       └── model.pth          (checkpoint)
│   │
│   ├── ONLINE_LEARNING_README.md          (400 lines)
│   ├── ONLINE_LEARNING_QUICKREF.md        (200 lines)
│   └── ONLINE_LEARNING_IMPLEMENTATION_SUMMARY.md
│
├── tests/
│   └── test_online_learning.py    (650 lines)
│       ├── TestDriftDetection
│       ├── TestSampleBuffer
│       ├── TestEWCTrainer
│       ├── TestModelRegistry
│       └── TestOnlineLearningIntegration
│
config/
└── online_learning.json           (100 lines)
    ├── drift_detection config
    ├── online_learning config
    ├── prometheus config
    └── logging config
```

## Key Metrics Summary

| Component | Metric | Value |
|-----------|--------|-------|
| **Drift Detection** | Latency | <1ms per sample |
| | Memory | ~50MB |
| | False Positive Rate | ~5% |
| **Sample Buffer** | Max Size | 10K recent + 5K FPs |
| | Thread Safety | Lock-based |
| | Access Time | O(1) |
| **Fine-Tuning** | Time (2K samples) | ~5 min |
| | GPU Memory | ~2-4GB |
| | TPR Degradation | <0.5% |
| | FP Reduction | 20-40% |
| **Model Registry** | Storage per Version | ~50-200MB |
| | Max Versions | 10 (configurable) |
| | Persistence | JSON + PyTorch |
