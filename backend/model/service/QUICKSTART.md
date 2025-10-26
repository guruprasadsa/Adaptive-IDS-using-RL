# Model Inference Service - Quick Start Guide

This guide will help you quickly get the model inference service up and running.

## Prerequisites

- Docker and Docker Compose installed
- Model checkpoint file exists at `backend/model/checkpoints/final_model.pth`
- Label classes and config files in `backend/model/output/run_*/`

## Quick Start (Docker Compose)

### 1. Start All Services

```bash
# Start Kafka, Postgres, and Model Service
docker compose up -d

# View logs
docker compose logs -f model-service
```

### 2. Verify Service is Running

```bash
# Check health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "model-inference",
#   "model_ready": true,
#   "worker_running": true
# }
```

### 3. Check Model Info

```bash
curl http://localhost:8000/model/info | python -m json.tool

# You should see:
# - model_version
# - feature_version  
# - num_classes (15)
# - label_classes array
```

### 4. Test Direct Prediction

```bash
# Test with sample data
python backend/model/service/test_service.py
```

## Development Setup (Without Docker)

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Windows (cmd)
set KAFKA_BROKERS=localhost:9092
set FEATURES_TOPIC=flows.features
set PRED_TOPIC=predictions
set MODEL_PATH=./model/checkpoints/final_model.pth
set DEVICE=cpu
set BATCH_SIZE=64

# Windows (PowerShell)
$env:KAFKA_BROKERS="localhost:9092"
$env:FEATURES_TOPIC="flows.features"
$env:PRED_TOPIC="predictions"
$env:MODEL_PATH="./model/checkpoints/final_model.pth"
$env:DEVICE="cpu"
$env:BATCH_SIZE="64"

# Linux/Mac
export KAFKA_BROKERS=localhost:9092
export FEATURES_TOPIC=flows.features
export PRED_TOPIC=predictions
export MODEL_PATH=./model/checkpoints/final_model.pth
export DEVICE=cpu
export BATCH_SIZE=64
```

### 3. Start Kafka (Required)

```bash
# Using Docker
docker compose up -d kafka

# Wait for Kafka to be ready
docker compose logs kafka | grep "started"
```

### 4. Run Service

```bash
# From backend directory
cd backend
python -m uvicorn model.service.app:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test the Service

```bash
# In another terminal
python backend/model/service/test_service.py
```

## Testing Kafka Integration

### 1. Start Feature Producer (Optional)

If you have the feature extractor running:

```bash
# Start feature extractor
python backend/stream/feature_extractor.py
```

### 2. Monitor Predictions Topic

```bash
# View predictions being produced
docker exec -it adaptive_ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic predictions \
  --from-beginning \
  --property print.key=true \
  --property print.timestamp=true
```

### 3. Produce Test Features

```bash
# Produce sample features to test end-to-end
python backend/stream/test_feature_extractor.py
```

## Performance Validation

### Run Performance Tests

```bash
# Run unit tests including performance tests
pytest backend/model/service/test_inference.py::TestPerformance -v -s

# Expected results:
# - P95 latency < 100ms (batch of 64)
# - Throughput > 5,000 samples/sec on CPU
```

### Monitor Metrics

```bash
# View Prometheus metrics
curl http://localhost:8000/metrics

# Key metrics to check:
# - ids_inferences_total
# - ids_inference_latency_seconds
# - ids_batch_size
```

## Troubleshooting

### Service Won't Start

```bash
# Check if model file exists
dir backend\model\checkpoints\final_model.pth  # Windows
ls -lh backend/model/checkpoints/final_model.pth  # Linux/Mac

# Check Docker logs
docker compose logs model-service

# Common issues:
# - Model file missing: Run training script first
# - Kafka not ready: Wait for kafka service to be healthy
# - Port conflict: Check if port 8000 is already in use
```

### Model Not Loading

```bash
# Verify model files
dir backend\model\output\run_*\*.json  # Windows
ls -lh backend/model/output/run_*/*.json  # Linux/Mac

# Files needed:
# - label_classes.json
# - config.json

# Check logs for specific error
docker compose logs model-service | findstr /i "error"  # Windows
docker compose logs model-service | grep -i error  # Linux/Mac
```

### Kafka Connection Issues

```bash
# Test Kafka connectivity
docker exec -it adaptive_ids_kafka kafka-broker-api-versions \
  --bootstrap-server localhost:9092

# List topics
docker exec -it adaptive_ids_kafka kafka-topics \
  --list \
  --bootstrap-server localhost:9092

# Check if topics exist
# - flows.features (input)
# - predictions (output)
```

### Low Performance

```bash
# Check CPU usage
docker stats adaptive_ids_model_service

# Increase batch size for better throughput
docker compose down
# Edit docker-compose.yml: BATCH_SIZE=128
docker compose up -d model-service

# Check metrics for actual throughput
curl http://localhost:8000/metrics | findstr ids_inferences_total
```

## Next Steps

1. **Integration Testing**: Connect feature extractor → inference service → alerting
2. **Load Testing**: Use Apache Kafka load generators for stress testing
3. **Production Deployment**: 
   - Add TLS for Kafka
   - Set up Prometheus scraping
   - Configure resource limits
   - Enable horizontal scaling

## Quick Reference

| Action | Command |
|--------|---------|
| Start service | `docker compose up -d model-service` |
| View logs | `docker compose logs -f model-service` |
| Stop service | `docker compose stop model-service` |
| Restart | `docker compose restart model-service` |
| Check health | `curl http://localhost:8000/health` |
| View metrics | `curl http://localhost:8000/metrics` |
| Run tests | `pytest backend/model/service/test_inference.py -v` |

## Support

For issues or questions:
1. Check logs: `docker compose logs model-service`
2. Review README: `backend/model/service/README.md`
3. Run diagnostic: `python backend/model/service/test_service.py`
