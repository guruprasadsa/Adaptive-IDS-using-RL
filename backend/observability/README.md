# Observability Module
## Adaptive IDS Monitoring & Tracing

This module provides centralized Prometheus metrics and OpenTelemetry tracing for the Adaptive IDS system.

---

## Quick Usage

### Initialize in Your Service

```python
from observability import init_metrics, init_tracing

# Initialize metrics
init_metrics()

# Initialize tracing
init_tracing(service_name="my-service", service_version="2.0.0")
```

### Add Metrics

```python
from observability.metrics import (
    packets_processed,
    inference_latency,
    kafka_messages_consumed
)

# Increment counter
packets_processed.labels(service='my-service', status='success').inc()

# Record histogram
with inference_latency.labels(service='my-service', batch_size_bucket='32').time():
    # Your inference code
    model.predict(batch)

# Set gauge
kafka_messages_consumed.labels(service='my-service', topic='predictions', status='success').inc()
```

### Add Tracing

```python
from observability.tracing import (
    trace_kafka_consumption,
    trace_flow_processing,
    trace_inference
)

# Trace Kafka consumption
with trace_kafka_consumption(
    topic='flows.features',
    partition=0,
    offset=12345,
    flow_id='192.168.1.1:8080:10.0.0.1:443:TCP'
):
    # Process message
    process_message(msg)

# Trace flow processing
with trace_flow_processing(
    flow_id=flow.flow_id,
    operation='feature_extraction',
    src_ip=flow.src_ip,
    dst_ip=flow.dst_ip
):
    # Extract features
    features = extract_features(flow)

# Trace inference
with trace_inference(
    flow_id=flow_id,
    batch_size=32,
    model_version='v1.0'
):
    # Run inference
    predictions = model.predict(batch)
```

### Expose Metrics Endpoint (Flask)

```python
from flask import Flask, Response
from observability.metrics import export_metrics, get_content_type

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    return Response(export_metrics(), mimetype=get_content_type())
```

### Expose Metrics Endpoint (FastAPI)

```python
from fastapi import FastAPI, Response
from observability.metrics import export_metrics, get_content_type

app = FastAPI()

@app.get("/metrics")
async def metrics():
    return Response(content=export_metrics(), media_type=get_content_type())
```

---

## Available Metrics

### Packet Processing
- `ids_packets_processed_total` - Counter
- `ids_flows_created_total` - Counter
- `ids_flows_expired_total` - Counter
- `ids_features_extracted_total` - Counter
- `ids_active_flows` - Gauge

### ML Inference
- `ids_predictions_total` - Counter
- `ids_inference_latency_seconds` - Histogram
- `ids_batch_processing_seconds` - Histogram
- `ids_model_ready` - Gauge
- `ids_scaler_samples` - Gauge

### Alerting
- `ids_alerts_created_total` - Counter
- `ids_alerts_dispatched_total` - Counter
- `ids_alerts_suppressed_total` - Counter
- `ids_external_integration_latency_seconds` - Histogram

### Kafka
- `ids_kafka_messages_consumed_total` - Counter
- `ids_kafka_messages_produced_total` - Counter
- `ids_kafka_consumer_lag` - Gauge
- `ids_kafka_produce_latency_seconds` - Histogram
- `ids_kafka_consume_latency_seconds` - Histogram

### Database
- `ids_db_operation_seconds` - Histogram
- `ids_db_operations_total` - Counter
- `ids_db_pool_connections` - Gauge

### Drift Detection
- `ids_drift_detected_total` - Counter
- `ids_drift_score` - Gauge

### Errors & Health
- `ids_errors_total` - Counter
- `ids_service_health` - Gauge

### False Positives
- `ids_false_positives_total` - Counter
- `ids_true_positives_total` - Counter

See `metrics.py` for complete list and label definitions.

---

## Tracing Utilities

### Context Managers

- `trace_kafka_consumption()` - Trace message consumption
- `trace_kafka_production()` - Trace message production
- `trace_flow_processing()` - Trace flow operations
- `trace_inference()` - Trace model inference
- `trace_alert_dispatch()` - Trace alert dispatching

### Decorators

```python
from observability.tracing import trace_function

@trace_function("custom_operation")
def my_function():
    # Function automatically wrapped in span
    pass
```

### Context Propagation

```python
from observability.tracing import inject_trace_context, extract_trace_context

# Inject into Kafka headers
headers = {}
inject_trace_context(headers)
producer.produce(topic, value=msg, headers=headers)

# Extract from Kafka headers
context = extract_trace_context(headers)
```

---

## Configuration

### Environment Variables

```bash
# OpenTelemetry
export OTEL_EXPORTER_OTLP_ENDPOINT="localhost:4317"
export OTEL_CONSOLE_EXPORT="false"
export ENVIRONMENT="production"

# Service identification
export SERVICE_NAME="my-service"
export SERVICE_VERSION="2.0.0"
```

### Initialization Options

```python
# Metrics
init_metrics(registry=custom_registry)

# Tracing
init_tracing(
    service_name="my-service",
    service_version="2.0.0",
    otlp_endpoint="otel-collector:4317",
    enable_console=True  # For debugging
)
```

---

## Integration Examples

### Feature Extractor

```python
from observability.metrics import (
    packets_processed,
    flows_created,
    flows_expired,
    features_extracted,
    active_flows_gauge
)

# In packet processing loop
packets_processed.labels(service='feature-extractor', status='success').inc()

# When creating flow
flows_created.labels(service='feature-extractor').inc()

# When flow expires
flows_expired.labels(service='feature-extractor', reason='timeout').inc()

# When emitting features
features_extracted.labels(service='feature-extractor', feature_version='v1.0').inc()

# Periodically update active flows
active_flows_gauge.labels(service='feature-extractor').set(len(self.flows))
```

### Model Service

```python
from observability.metrics import predictions_made, inference_latency
from observability.tracing import trace_inference

# Wrap inference
with inference_latency.labels(service='model-service', batch_size_bucket='32').time():
    with trace_inference(flow_id=flow_id, batch_size=32, model_version='v1.0'):
        predictions = model.predict(batch)

# Record predictions
for pred in predictions:
    predictions_made.labels(
        service='model-service',
        status='success',
        class_name=pred['class_name']
    ).inc()
```

### Alerting Service

```python
from observability.metrics import alerts_created, alerts_dispatched
from observability.tracing import trace_alert_dispatch

# Create alert
alerts_created.labels(
    service='alerting',
    severity=alert['severity'],
    class_name=alert['class_name']
).inc()

# Dispatch alert
with trace_alert_dispatch(
    alert_id=alert['alert_id'],
    flow_id=alert['flow_id'],
    severity=alert['severity'],
    destination='syslog'
):
    syslog_client.send(alert)
    alerts_dispatched.labels(
        service='alerting',
        destination='syslog',
        status='success'
    ).inc()
```

---

## Testing

```python
# backend/tests/test_observability.py
python backend/tests/test_observability.py
```

This validates:
- Metrics endpoints are accessible
- Prometheus is scraping
- Grafana datasources are configured
- Jaeger is collecting traces
- OTEL Collector is running

---

## Documentation

- **Setup Guide**: `documentation/OBSERVABILITY_SETUP.md`
- **Quick Reference**: `documentation/OBSERVABILITY_QUICKREF.md`
- **Implementation Summary**: `documentation/OBSERVABILITY_IMPLEMENTATION_SUMMARY.md`

---

## Dashboards

Located in `documentation/grafana-dashboards/`:
- `adaptive-ids-overview.json` - System overview
- `adaptive-ids-ml-performance.json` - ML metrics
- `adaptive-ids-alerting.json` - Alerting metrics

Access at: http://localhost:3000 (admin/admin)

---

## Troubleshooting

### Metrics not appearing in Prometheus

```bash
# Check service metrics endpoint
curl http://localhost:8000/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify scrape config
docker compose exec prometheus cat /etc/prometheus/prometheus.yml
```

### Traces not in Jaeger

```bash
# Check OTEL Collector health
curl http://localhost:13133/

# Verify OTLP endpoint
echo $OTEL_EXPORTER_OTLP_ENDPOINT

# Check OTEL Collector logs
docker compose logs otel-collector
```

---

## Dependencies

- `prometheus-client>=0.19.0`
- `opentelemetry-api>=1.21.0`
- `opentelemetry-sdk>=1.21.0`
- `opentelemetry-exporter-otlp>=1.21.0`

---

**For complete documentation, see**: `documentation/OBSERVABILITY_SETUP.md`
