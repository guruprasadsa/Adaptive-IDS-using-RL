# Observability Quick Reference
## Adaptive IDS Monitoring Cheat Sheet

---

## 🚀 Quick Start

```bash
# Start observability stack
docker compose up -d prometheus grafana otel-collector jaeger

# Access dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
open http://localhost:16686 # Jaeger
```

---

## 📊 Key Metrics Endpoints

| Service | Metrics URL | Port |
|---------|------------|------|
| Backend API | http://localhost:5001/metrics | 5001 |
| Model Service | http://localhost:8000/metrics | 8000 |
| Prometheus | http://localhost:9090 | 9090 |
| Grafana | http://localhost:3000 | 3000 |
| Jaeger UI | http://localhost:16686 | 16686 |
| OTEL Collector | http://localhost:8888/metrics | 8888 |

---

## 🔍 Essential PromQL Queries

### System Health
```promql
# Service health status
ids_service_health

# Total packets/sec
sum(rate(ids_packets_processed_total[1m]))

# Active flows
sum(ids_active_flows)
```

### Performance
```promql
# P95 inference latency (ms)
histogram_quantile(0.95, rate(ids_inference_latency_seconds_bucket[5m])) * 1000

# Kafka consumer lag
max(ids_kafka_consumer_lag) by (service, topic)

# DB query P99 latency
histogram_quantile(0.99, rate(ids_db_operation_seconds_bucket[5m]))
```

### Throughput
```promql
# Predictions per second
sum(rate(ids_predictions_total{status="success"}[5m]))

# Alerts per minute
sum(rate(ids_alerts_created_total[1m])) * 60

# Features extracted per second
rate(ids_features_extracted_total[5m])
```

### Error Rates
```promql
# Overall error rate
sum(rate(ids_errors_total[5m])) by (service)

# False positive rate (last hour)
sum(rate(ids_false_positives_total[1h])) / 
  (sum(rate(ids_false_positives_total[1h])) + sum(rate(ids_true_positives_total[1h])))

# Alert dispatch failures
sum by(destination) (rate(ids_alerts_dispatched_total{status="error"}[5m]))
```

---

## 🔎 Jaeger Trace Queries

### Find Traces by Flow
```
ids.flow_id="192.168.1.100:12345:10.0.0.50:80:TCP"
```

### Find Slow Operations
```
operation="model.inference" AND duration > 100ms
```

### Find Errors
```
error=true AND service="model-service"
```

### Alert Dispatch Traces
```
operation="alert.dispatch.syslog"
```

---

## 📈 Dashboard Overview

### System Overview Dashboard
- **Panels**: System health, throughput, active flows, alerts
- **Use**: High-level monitoring, incident detection
- **Refresh**: 10s

### ML Performance Dashboard
- **Panels**: Inference latency, predictions by class, drift scores
- **Use**: Model performance tuning, drift monitoring
- **Refresh**: 10s

### Alerting Dashboard
- **Panels**: Alert rates, dispatch status, integration latency
- **Use**: Alert pipeline monitoring, integration health
- **Refresh**: 10s

---

## 🔧 Common Operations

### Check Service Health
```bash
# Via Prometheus
curl -s http://localhost:9090/api/v1/query?query=ids_service_health | jq

# Via service endpoint
curl http://localhost:8000/health
```

### View Current Metrics
```bash
# Raw Prometheus metrics
curl http://localhost:8000/metrics

# Pretty print
curl -s http://localhost:8000/metrics | grep ids_
```

### Query Prometheus
```bash
# Instant query
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=sum(ids_active_flows)'

# Range query (last hour)
curl -G http://localhost:9090/api/v1/query_range \
  --data-urlencode 'query=rate(ids_predictions_total[5m])' \
  --data-urlencode 'start='$(date -u -d '1 hour ago' +%s) \
  --data-urlencode 'end='$(date -u +%s) \
  --data-urlencode 'step=60s'
```

### Trace a Specific Flow
```bash
# Search in Jaeger
curl "http://localhost:16686/api/traces?service=model-service&tags={\"ids.flow_id\":\"$FLOW_ID\"}"
```

---

## 🚨 Alert Thresholds

| Metric | Threshold | Severity |
|--------|-----------|----------|
| Kafka lag | > 10,000 msgs | Warning |
| Inference P95 | > 100ms | Warning |
| FP rate | > 1% | Critical |
| Service health | = 0 | Critical |
| Drift score | > 0.7 | Warning |
| Error rate | > 10/min | Warning |

---

## 🛠️ Troubleshooting Commands

### Metrics Not Updating
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Restart Prometheus
docker compose restart prometheus
```

### Traces Missing
```bash
# Check OTEL Collector health
curl http://localhost:13133/

# View OTEL Collector logs
docker compose logs --tail=100 otel-collector

# Verify service sends traces
docker compose exec model-service env | grep OTEL
```

### Dashboard Issues
```bash
# Check Grafana datasource
curl http://localhost:3000/api/datasources -u admin:admin

# View Grafana logs
docker compose logs --tail=50 grafana

# Re-provision dashboards
docker compose restart grafana
```

---

## 📝 Instrumentation Code Snippets

### Add Metrics to Python Service
```python
from observability.metrics import packets_processed, inference_latency

# Counter
packets_processed.labels(service='my-service', status='success').inc()

# Histogram
with inference_latency.labels(service='my-service', batch_size_bucket='32').time():
    # operation
    pass
```

### Add Tracing
```python
from observability.tracing import trace_flow_processing

with trace_flow_processing(flow_id=flow_id, operation='feature_extraction'):
    # processing logic
    pass
```

### Kafka Trace Propagation
```python
from observability.tracing import inject_trace_context

headers = {}
inject_trace_context(headers)
producer.produce(topic, value=msg, headers=headers)
```

---

## 🎯 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Packet processing | 10,000+/sec | Monitor |
| Inference latency P95 | < 100ms | Monitor |
| Kafka lag | < 1,000 msgs | Monitor |
| FP rate | < 1% | Monitor |
| Alert dispatch P95 | < 500ms | Monitor |
| DB query P99 | < 100ms | Monitor |

---

## 📚 Further Reading

- Full guide: `documentation/OBSERVABILITY_SETUP.md`
- Metrics reference: See full metric list in setup guide
- Dashboard JSON: `documentation/grafana-dashboards/`
- Config files: `config/prometheus.yml`, `config/otel-collector-config.yml`

---

**Quick Links**:
- [Grafana](http://localhost:3000)
- [Prometheus](http://localhost:9090)
- [Jaeger](http://localhost:16686)
- [OTEL Metrics](http://localhost:8888/metrics)
