# Model Inference Service

FastAPI-based microservice for real-time intrusion detection inference with micro-batching and Kafka integration.

## Features

- **TorchScript Model Loading**: Loads pre-trained models with version validation
- **Micro-Batching**: Efficient batch processing (32-128 samples) for optimal throughput
- **Kafka Integration**: Consumes from `flows.features` topic, produces to `predictions` topic
- **Calibration**: Temperature scaling for confidence calibration
- **Prometheus Metrics**: Comprehensive monitoring and alerting
- **CPU/GPU Support**: Automatic device detection and optimization
- **Health Checks**: Readiness and liveness probes for Kubernetes

## Architecture

```
Kafka flows.features → Inference Worker (micro-batching) → Model Manager (TorchScript + calibration) → Kafka predictions
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BROKERS` | `localhost:9092` | Kafka broker addresses |
| `FEATURES_TOPIC` | `flows.features` | Input topic for flow features |
| `PRED_TOPIC` | `predictions` | Output topic for predictions |
| `CONSUMER_GROUP` | `model-inference-service` | Kafka consumer group ID |
| `MODEL_PATH` | `./model/checkpoints/final_model.pth` | Path to model checkpoint |
| `MODEL_VERSION` | `v1.0` | Model version identifier |
| `FEATURE_VERSION` | `v1.0` | Feature extraction version |
| `DEVICE` | `cpu` | Inference device (`cpu` or `cuda`) |
| `BATCH_SIZE` | `64` | Micro-batch size for inference |
| `MAX_BATCH_WAIT_MS` | `50` | Max wait time before processing partial batch |
| `CALIBRATION_TEMP` | `1.5` | Temperature scaling parameter |

### Docker Compose Example

```yaml
model-service:
  build:
    context: ./backend
    dockerfile: Dockerfile.model
  environment:
    - KAFKA_BROKERS=kafka:29092
    - FEATURES_TOPIC=flows.features
    - PRED_TOPIC=predictions
    - BATCH_SIZE=128
    - DEVICE=cpu
  ports:
    - "127.0.0.1:8000:8000"
```

## API Endpoints

### Health Check
```bash
GET /health
```

Returns service health status and configuration.

### Metrics
```bash
GET /metrics
```

Prometheus-compatible metrics endpoint. Exposes:
- `ids_inferences_total`: Total inference count
- `ids_inference_latency_seconds`: Latency histogram
- `ids_batch_size`: Batch size distribution
- `ids_messages_consumed_total`: Messages consumed
- `ids_messages_produced_total`: Predictions produced

### Model Info
```bash
GET /model/info
```

Returns model metadata and configuration.

### Direct Prediction (Testing)
```bash
POST /predict
```

Direct inference endpoint for testing (bypasses Kafka).

## Performance Targets

| Metric | Target |
|--------|--------|
| Throughput | > 5,000 samples/sec (CPU) |
| P95 Latency | < 100 ms per micro-batch |
| P99 Latency | < 200 ms per micro-batch |

## Testing

```bash
# Run all tests
pytest backend/model/service/test_inference.py -v

# Run performance tests
pytest backend/model/service/test_inference.py::TestPerformance -v -s
```

## Deployment

### Local Development
```bash
uvicorn model.service.app:app --reload --host 0.0.0.0 --port 8000
```

### Docker
```bash
docker compose up -d model-service
```

## Monitoring

### Prometheus Scraping
```yaml
scrape_configs:
  - job_name: 'model-inference'
    static_configs:
      - targets: ['model-service:8000']
    metrics_path: '/metrics'
```

### Key Metrics

**Throughput:**
```promql
rate(ids_inferences_total[5m])
```

**Latency (P95):**
```promql
histogram_quantile(0.95, rate(ids_inference_latency_seconds_bucket[5m]))
```

**Error Rate:**
```promql
rate(ids_inferences_total{status="error"}[5m]) / rate(ids_inferences_total[5m])
```

## Troubleshooting

### Model Not Loading
```bash
# Check model file
ls -lh backend/model/checkpoints/final_model.pth

# Check logs
docker compose logs model-service | grep -i error
```

### Low Throughput
```bash
# Increase batch size
docker compose restart model-service -e BATCH_SIZE=256

# Monitor metrics
curl http://localhost:8000/metrics | grep ids_inference_latency
```

### Kafka Connection Issues
```bash
# Test connectivity
docker exec -it adaptive_ids_kafka kafka-topics --list --bootstrap-server localhost:9092
```
