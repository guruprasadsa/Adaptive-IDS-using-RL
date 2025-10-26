# Observability Setup Guide
## Adaptive IDS Monitoring & Tracing

This guide covers the comprehensive observability stack for the Adaptive IDS system, including Prometheus metrics, OpenTelemetry distributed tracing, and Grafana dashboards.

---

## Overview

The observability stack provides:
- **Metrics Collection**: Prometheus scrapes metrics from all services
- **Distributed Tracing**: OpenTelemetry traces flow through the entire pipeline
- **Visualization**: Grafana dashboards show real-time system performance
- **Trace Analysis**: Jaeger UI for exploring distributed traces
- **Correlation**: flow_id links traces across all services

### Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Service   │────▶│ Prometheus  │────▶│   Grafana   │
│  /metrics   │     │  (scrape)   │     │ (visualize) │
└─────────────┘     └─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Service   │────▶│    OTEL     │────▶│   Jaeger    │
│   (spans)   │     │  Collector  │     │   (traces)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## Quick Start

### 1. Start Observability Stack

The observability services are included in `docker-compose.yml`:

```bash
# Start all services including observability
docker compose up -d

# Start only observability services
docker compose up -d prometheus grafana otel-collector jaeger
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger UI**: http://localhost:16686
- **OTEL Collector Metrics**: http://localhost:8888/metrics

### 3. Import Dashboards

Dashboards are automatically provisioned from `documentation/grafana-dashboards/`:
- `adaptive-ids-overview.json` - System-wide overview
- `adaptive-ids-ml-performance.json` - ML model metrics
- `adaptive-ids-alerting.json` - Alerting & integrations

---

## Metrics Reference

### Packet Processing Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_packets_processed_total` | Counter | service, status | Total packets processed |
| `ids_flows_created_total` | Counter | service | Total flows created |
| `ids_flows_expired_total` | Counter | service, reason | Total flows expired |
| `ids_features_extracted_total` | Counter | service, feature_version | Features extracted |
| `ids_active_flows` | Gauge | service | Current active flows |

### ML Inference Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_predictions_total` | Counter | service, status, class_name | Total predictions made |
| `ids_inference_latency_seconds` | Histogram | service, batch_size_bucket | Inference latency distribution |
| `ids_batch_processing_seconds` | Histogram | service, stage | Batch processing time |
| `ids_model_ready` | Gauge | service, model_version | Model readiness (1=ready) |
| `ids_scaler_samples` | Gauge | service, feature_version | Scaler training samples |

### Alerting Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_alerts_created_total` | Counter | service, severity, class_name | Alerts created |
| `ids_alerts_dispatched_total` | Counter | service, destination, status | Alerts dispatched |
| `ids_alerts_suppressed_total` | Counter | service, reason | Alerts suppressed |
| `ids_external_integration_latency_seconds` | Histogram | service, integration, operation | Integration latency |

### Kafka Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_kafka_messages_consumed_total` | Counter | service, topic, status | Messages consumed |
| `ids_kafka_messages_produced_total` | Counter | service, topic, status | Messages produced |
| `ids_kafka_consumer_lag` | Gauge | service, topic, partition | Consumer lag in messages |
| `ids_kafka_produce_latency_seconds` | Histogram | service, topic | Production latency |
| `ids_kafka_consume_latency_seconds` | Histogram | service, topic | Consumption latency |

### Database Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_db_operation_seconds` | Histogram | service, operation, table | Database operation latency |
| `ids_db_operations_total` | Counter | service, operation, table, status | Total DB operations |
| `ids_db_pool_connections` | Gauge | service, state | Connection pool status |

### Drift Detection Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_drift_detected_total` | Counter | service, detector_type, severity | Drift events detected |
| `ids_drift_score` | Gauge | service, detector_type, feature | Current drift score |

### Error & Health Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_errors_total` | Counter | service, error_type, component | Total errors |
| `ids_service_health` | Gauge | service, component | Service health (1=healthy) |

### False Positive Tracking

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ids_false_positives_total` | Counter | service, class_name, severity | False positives marked |
| `ids_true_positives_total` | Counter | service, class_name, severity | True positives confirmed |

---

## Distributed Tracing

### Flow ID Correlation

All traces include the `ids.flow_id` attribute for end-to-end correlation:

1. **Packet Consumption** → `kafka.consume.raw.packets`
2. **Feature Extraction** → `flow.feature_extraction`
3. **Feature Production** → `kafka.produce.flows.features`
4. **Inference** → `model.inference`
5. **Prediction Production** → `kafka.produce.predictions`
6. **Alert Dispatch** → `alert.dispatch.{destination}`

### Trace Context Propagation

Trace context is injected into Kafka message headers:

```python
from observability import inject_trace_context

headers = {}
inject_trace_context(headers)
producer.produce(topic, value=message, headers=headers)
```

### Example Queries in Jaeger

Find all traces for a specific flow:
```
ids.flow_id="192.168.1.100:12345:10.0.0.50:80:TCP"
```

Find slow inference operations:
```
operation="model.inference" AND duration > 100ms
```

Find failed alert dispatches:
```
operation="alert.dispatch.*" AND error=true
```

---

## PromQL Query Examples

### Throughput Metrics

```promql
# Packets per second
rate(ids_packets_processed_total{status="success"}[1m])

# Features extracted per second
rate(ids_features_extracted_total[5m])

# Predictions per second by class
sum by(class_name) (rate(ids_predictions_total{status="success"}[5m]))
```

### Latency Metrics

```promql
# P95 inference latency
histogram_quantile(0.95, rate(ids_inference_latency_seconds_bucket[5m]))

# Average batch processing time
rate(ids_batch_processing_seconds_sum[5m]) / rate(ids_batch_processing_seconds_count[5m])

# P99 database query latency
histogram_quantile(0.99, rate(ids_db_operation_seconds_bucket[5m]))
```

### Error Rates

```promql
# Overall error rate
sum(rate(ids_errors_total[5m])) by (service)

# Kafka production errors
rate(ids_kafka_messages_produced_total{status="error"}[5m])

# Alert dispatch failures
sum by(destination) (rate(ids_alerts_dispatched_total{status="error"}[5m]))
```

### Lag & Queue Depth

```promql
# Kafka consumer lag
ids_kafka_consumer_lag

# Active flow count
sum(ids_active_flows)
```

### False Positive Rate

```promql
# FP rate over last hour
sum(rate(ids_false_positives_total[1h])) / 
  (sum(rate(ids_false_positives_total[1h])) + sum(rate(ids_true_positives_total[1h])))
```

---

## Alert Rules (Optional)

Create `config/prometheus/alerts.yml`:

```yaml
groups:
  - name: adaptive_ids_alerts
    interval: 1m
    rules:
      - alert: HighKafkaLag
        expr: ids_kafka_consumer_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High Kafka consumer lag"
          description: "{{ $labels.service }} lag is {{ $value }} messages"

      - alert: HighInferenceLatency
        expr: histogram_quantile(0.95, rate(ids_inference_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High inference latency"
          description: "P95 latency is {{ $value }}s"

      - alert: HighFalsePositiveRate
        expr: |
          sum(rate(ids_false_positives_total[1h])) / 
          (sum(rate(ids_false_positives_total[1h])) + sum(rate(ids_true_positives_total[1h]))) > 0.01
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "High false positive rate"
          description: "FP rate is {{ $value | humanizePercentage }}"

      - alert: ServiceUnhealthy
        expr: ids_service_health == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Service unhealthy"
          description: "{{ $labels.service }}/{{ $labels.component }} is unhealthy"

      - alert: DriftDetected
        expr: ids_drift_score > 0.7
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Data drift detected"
          description: "Drift score {{ $value }} on {{ $labels.feature }}"
```

---

## Integration with Services

### Backend API (Flask)

```python
from observability import init_metrics, init_tracing
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Initialize
init_metrics()
init_tracing("backend-api")

# Add /metrics endpoint
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
```

### Model Service (FastAPI)

Already integrated in `backend/model/service/app.py`:
- `/metrics` endpoint
- OTEL tracing via context managers

### Feature Extractor

Add metrics to main loop:

```python
from observability.metrics import (
    packets_processed,
    flows_created,
    active_flows_gauge
)

packets_processed.labels(service='feature-extractor', status='success').inc()
flows_created.labels(service='feature-extractor').inc()
active_flows_gauge.labels(service='feature-extractor').set(len(self.flows))
```

### Alerting Service

Add tracing to dispatch:

```python
from observability.tracing import trace_alert_dispatch

with trace_alert_dispatch(
    alert_id=alert['alert_id'],
    flow_id=alert['flow_id'],
    severity=alert['severity'],
    destination='syslog'
):
    syslog_client.send(alert)
```

---

## Troubleshooting

### Metrics Not Appearing

1. Check service is exposing `/metrics`:
   ```bash
   curl http://localhost:8000/metrics
   ```

2. Verify Prometheus scrape config:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

3. Check Prometheus logs:
   ```bash
   docker compose logs prometheus
   ```

### Traces Not Showing in Jaeger

1. Verify OTEL Collector is running:
   ```bash
   curl http://localhost:13133/
   ```

2. Check OTEL Collector logs:
   ```bash
   docker compose logs otel-collector
   ```

3. Verify service has OTEL_EXPORTER_OTLP_ENDPOINT set:
   ```bash
   docker compose exec model-service env | grep OTEL
   ```

### Grafana Dashboards Not Loading

1. Check dashboard files exist:
   ```bash
   ls documentation/grafana-dashboards/
   ```

2. Verify provisioning config:
   ```bash
   docker compose exec grafana cat /etc/grafana/provisioning/dashboards/dashboards.yml
   ```

3. Check Grafana logs:
   ```bash
   docker compose logs grafana | grep dashboard
   ```

---

## Performance Tuning

### Prometheus

- **Retention**: Adjust in `config/prometheus.yml` (`--storage.tsdb.retention.time`)
- **Scrape interval**: Balance freshness vs load
- **Cardinality**: Avoid high-cardinality labels (e.g., IP addresses)

### OTEL Collector

- **Batch size**: Increase for higher throughput
- **Memory limit**: Adjust based on trace volume
- **Sampling**: Add tail-based sampling for production

### Grafana

- **Query optimization**: Use recording rules for complex queries
- **Refresh rate**: Set appropriate dashboard refresh intervals
- **Panel count**: Limit panels per dashboard for performance

---

## Production Considerations

1. **Security**:
   - Enable authentication on Prometheus/Grafana
   - Use TLS for OTEL gRPC connections
   - Restrict metric endpoint access

2. **High Availability**:
   - Run Prometheus in HA mode with Thanos
   - Use remote storage (e.g., Cortex, Mimir)
   - Deploy OTEL Collector as sidecar

3. **Scalability**:
   - Shard Prometheus by service
   - Use federation for multi-cluster
   - Implement adaptive sampling in OTEL

4. **Cost Optimization**:
   - Apply metric relabeling to drop unused metrics
   - Configure appropriate retention periods
   - Use recording rules for expensive queries

---

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/)
- [Grafana Dashboards](https://grafana.com/docs/grafana/latest/dashboards/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)

---

**Last Updated**: 2025-10-24
