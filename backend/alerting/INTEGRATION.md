# Alerting Pipeline Integration Guide

## Overview

The Adaptive IDS alerting pipeline consumes predictions from the model service, classifies severity, persists alerts to PostgreSQL, and dispatches to external integrations (syslog, SIEM, email) with comprehensive error handling via a Dead Letter Queue (DLQ).

## Architecture

```
┌─────────────────┐
│ Model Service   │
│ (Predictions)   │
└────────┬────────┘
         │ Kafka: predictions
         ▼
┌─────────────────┐
│ Alerting Service│
│                 │
│ • Severity Map  │
│ • Alert Filter  │
│ • Deduplication │
└────┬───┬───┬────┘
     │   │   │
     │   │   └──────────────┐
     │   │                  │
     ▼   ▼                  ▼
┌──────┐ ┌──────────┐  ┌─────────┐
│ DB   │ │ Syslog   │  │ SIEM    │
│ (PG) │ │ (TLS)    │  │ (REST)  │
└──────┘ └──────────┘  └─────────┘
     │        │              │
     │        │         ┌────┴────┐
     │        │         │         │
     ▼        ▼         ▼         ▼
┌────────────────────────────────────┐
│   Email        Splunk      Elastic │
│  (SMTP)        (HEC)      (Search) │
└────────────────────────────────────┘
              │
         (on failure)
              ▼
    ┌──────────────────┐
    │ Dead Letter Queue│
    │  (alerts.dlq)    │
    └──────────────────┘
```

## Quick Start

### 1. Database Migration

Apply the database migration to extend the `alerts` table:

```bash
# Connect to PostgreSQL
psql -h localhost -p 55432 -U adaptive_ids -d adaptive_ids

# Run migration
\i backend/db/migrations/001_extend_alerts_table.sql

# Or drop and recreate from schema
\i backend/db/schema.sql
```

### 2. Configure Integrations

Edit `backend/alerting/config.yaml` to customize:
- Severity mappings (attack class → severity level)
- Confidence thresholds
- Rate limits
- Integration settings

Or use environment variables (see Configuration section).

### 3. Start Alerting Service

#### Using Docker Compose:
```bash
docker compose up -d alerting-service
```

#### Standalone (local development):
```bash
cd backend
pip install -r requirements.txt

# Set environment variables
export KAFKA_BROKERS=localhost:9092
export PG_DSN="host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password"

# Run service
python -m alerting.alerter
```

### 4. Verify Operation

Check service logs:
```bash
docker compose logs -f alerting-service
```

Query alerts from database:
```sql
SELECT alert_id, severity, class_name, src_ip, dst_ip, confidence, created_at
FROM alerts
ORDER BY created_at DESC
LIMIT 10;
```

---

## Configuration

### Severity Mapping

Maps attack class names to severity levels in `config.yaml`:

```yaml
severity_mapping:
  # Critical threats
  Infiltration: CRITICAL
  Heartbleed: CRITICAL
  
  # High severity
  DDoS: HIGH
  Botnet: HIGH
  
  # Medium severity
  DoS Hulk: MEDIUM
  Web Attack – Sql Injection: MEDIUM
  
  # Low severity
  PortScan: LOW
  Nmap: LOW
  
  # Benign traffic
  BENIGN: INFO
  Normal: INFO
  
  # Default for unknown classes
  _default: MEDIUM
```

### Confidence Thresholds

Minimum confidence required per severity level:

```yaml
confidence_thresholds:
  INFO: 0.0      # Always alert (if enabled)
  LOW: 0.5       # 50% confidence
  MEDIUM: 0.6    # 60% confidence
  HIGH: 0.7      # 70% confidence
  CRITICAL: 0.75 # 75% confidence
```

### Alert Filtering

```yaml
alert_filtering:
  suppress_info: true          # Suppress INFO-level alerts
  suppress_classes:            # Suppress specific classes
    - BENIGN
    - Normal
  min_confidence: 0.5          # Global minimum confidence
  deduplication_window: 300    # 5 minutes (seconds)
  deduplication_keys:          # Keys for deduplication
    - src_ip
    - dst_ip
    - class_name
```

### Rate Limiting

```yaml
rate_limiting:
  global:
    enabled: true
    max_alerts_per_minute: 100
  
  per_severity:
    HIGH: 50
    CRITICAL: 100  # Never rate-limit critical
  
  per_destination:
    email:
      max_per_minute: 5
      max_per_hour: 20
      max_per_day: 100
```

---

## Integration Setup

### PostgreSQL Database

**Always enabled** - alerts persisted to `alerts` table.

**Schema:**
- Alert metadata (ID, flow ID, timestamp)
- Classification (class index/name, confidence, severity)
- Network context (src/dst IP/port, protocol)
- Model versions (model, feature)
- Workflow (status, assigned_to, notes)
- Enrichment (geolocation, reputation, tags)
- Dispatch tracking (destinations, status)

**Batch Configuration:**
```yaml
integrations:
  database:
    enabled: true
    batch_size: 10          # Bulk insert batch size
    batch_timeout_ms: 500   # Flush timeout
```

---

### Syslog (RFC5424 over TLS)

Send alerts to syslog server using RFC5424 format over TLS.

**Configuration:**
```yaml
integrations:
  syslog:
    enabled: ${SYSLOG_ENABLED:false}
    host: ${SYSLOG_HOST:syslog.example.com}
    port: ${SYSLOG_PORT:6514}
    protocol: TLS          # TLS, TCP, or UDP
    facility: 16           # local0 (16)
    
    tls:
      enabled: true
      cert_file: ${SYSLOG_CLIENT_CERT:}
      key_file: ${SYSLOG_CLIENT_KEY:}
      ca_file: ${SYSLOG_CA_CERT:}
      verify_cert: true
    
    connection:
      pool_size: 5
      max_retries: 3
      retry_delay_ms: 1000
      timeout_ms: 5000
      keepalive: true
    
    min_severity: MEDIUM   # Only send MEDIUM+ alerts
```

**Environment Variables:**
```bash
export SYSLOG_ENABLED=true
export SYSLOG_HOST=syslog.example.com
export SYSLOG_PORT=6514
export SYSLOG_CLIENT_CERT=/path/to/client.crt
export SYSLOG_CLIENT_KEY=/path/to/client.key
export SYSLOG_CA_CERT=/path/to/ca.crt
```

**Message Format (RFC5424):**
```
<priority>version timestamp hostname app-name procid msgid [structured-data] message

Example:
<131>1 2025-10-24T12:00:00.123Z ids-host adaptive-ids - - [ids@32473 alert_id="..." class_name="DDoS" confidence="0.95"] [HIGH] DDoS detected: 192.168.1.100:12345 -> 10.0.0.1:80 (confidence: 95.00%)
```

**Testing:**
```bash
# Test with netcat (no TLS)
nc -l 6514

# Test with openssl (TLS)
openssl s_server -accept 6514 -cert server.crt -key server.key -CAfile ca.crt
```

---

### Splunk (HTTP Event Collector)

Send alerts to Splunk via HEC (HTTP Event Collector).

**Configuration:**
```yaml
integrations:
  splunk:
    enabled: ${SPLUNK_ENABLED:false}
    url: ${SPLUNK_HEC_URL:https://splunk.example.com:8088/services/collector}
    token: ${SPLUNK_HEC_TOKEN:}
    index: ${SPLUNK_INDEX:ids_alerts}
    source: adaptive_ids
    sourcetype: ids:alert
    verify_ssl: true
    batch_size: 10
    min_severity: LOW
```

**Setup in Splunk:**
1. Go to **Settings > Data Inputs > HTTP Event Collector**
2. Click **New Token**
3. Set **Name**: `adaptive-ids`
4. Set **Source Type**: `ids:alert` (or create custom)
5. Select **Index**: Create or use existing (e.g., `ids_alerts`)
6. Copy **Token Value**
7. Enable HEC: **Settings > Data Inputs > HTTP Event Collector > Global Settings > All Tokens > Enabled**

**Environment Variables:**
```bash
export SPLUNK_ENABLED=true
export SPLUNK_HEC_URL=https://splunk.example.com:8088/services/collector
export SPLUNK_HEC_TOKEN=your-hec-token-here
export SPLUNK_INDEX=ids_alerts
```

**Query Alerts in Splunk:**
```spl
index=ids_alerts sourcetype=ids:alert
| table _time severity class_name src_ip dst_ip confidence
| sort -_time
```

---

### IBM QRadar

Create offenses in QRadar from high-severity alerts.

**Configuration:**
```yaml
integrations:
  qradar:
    enabled: ${QRADAR_ENABLED:false}
    url: ${QRADAR_URL:https://qradar.example.com/api/siem/offenses}
    api_key: ${QRADAR_API_KEY:}
    verify_ssl: true
    min_severity: MEDIUM
```

**Setup in QRadar:**
1. Go to **Admin > Authorized Services**
2. Create new **Authentication Token**
3. Set **User Role**: SecurityAdmin or similar
4. Copy token

**Environment Variables:**
```bash
export QRADAR_ENABLED=true
export QRADAR_URL=https://qradar.example.com/api/siem/offenses
export QRADAR_API_KEY=your-api-key-here
```

**Note:** QRadar API v14.0 is used. Adjust version if needed.

---

### Elastic SIEM (Elasticsearch)

Index alerts into Elasticsearch for analysis in Elastic SIEM/Kibana.

**Configuration:**
```yaml
integrations:
  elastic:
    enabled: ${ELASTIC_ENABLED:false}
    url: ${ELASTIC_URL:https://elastic.example.com:9200}
    api_key: ${ELASTIC_API_KEY:}
    index: ${ELASTIC_INDEX:ids-alerts}
    verify_ssl: true
    batch_size: 20
    min_severity: LOW
```

**Setup in Elasticsearch:**
1. Create API key:
```bash
curl -X POST "https://elastic.example.com:9200/_security/api_key" \
  -H "Content-Type: application/json" \
  -u elastic:password \
  -d '{"name":"adaptive-ids","role_descriptors":{"ids-writer":{"cluster":[],"index":[{"names":["ids-alerts*"],"privileges":["create_index","write","index"]}]}}}'
```

2. Create index template (optional):
```json
PUT _index_template/ids-alerts
{
  "index_patterns": ["ids-alerts*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1
    },
    "mappings": {
      "properties": {
        "@timestamp": {"type": "date"},
        "event.severity": {"type": "integer"},
        "source.ip": {"type": "ip"},
        "destination.ip": {"type": "ip"}
      }
    }
  }
}
```

**Environment Variables:**
```bash
export ELASTIC_ENABLED=true
export ELASTIC_URL=https://elastic.example.com:9200
export ELASTIC_API_KEY=your-api-key-here
export ELASTIC_INDEX=ids-alerts
```

**Query in Kibana:**
```
GET ids-alerts/_search
{
  "query": {
    "range": {
      "@timestamp": {"gte": "now-1h"}
    }
  },
  "sort": [{"@timestamp": "desc"}]
}
```

---

### Email Notifications

Send email alerts for high-severity threats with rate limiting.

**Configuration:**
```yaml
integrations:
  email:
    enabled: ${EMAIL_ENABLED:false}
    smtp_host: ${SMTP_HOST:smtp.gmail.com}
    smtp_port: ${SMTP_PORT:587}
    smtp_tls: ${SMTP_TLS:true}
    smtp_user: ${SMTP_USER:}
    smtp_password: ${SMTP_PASSWORD:}
    
    from_address: ${EMAIL_FROM:ids-alerts@example.com}
    to_addresses: ${EMAIL_TO:security-team@example.com}
    cc_addresses: ${EMAIL_CC:}
    
    subject_template: "[{severity}] IDS Alert: {class_name} detected from {src_ip}"
    min_severity: HIGH     # Only email HIGH+ alerts
    
    rate_limit:
      max_per_hour: 10
      max_per_day: 50
```

**Environment Variables:**
```bash
export EMAIL_ENABLED=true
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_TLS=true
export SMTP_USER=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
export EMAIL_FROM=ids-alerts@example.com
export EMAIL_TO=security@example.com,soc@example.com
```

**Gmail Setup:**
1. Enable 2FA on Google Account
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use app password for `SMTP_PASSWORD`

**Email Format:**
- **Plain text** and **HTML** multipart
- **Subject**: Configurable template with alert fields
- **Body**: Alert details, network context, model info
- **Link**: Dashboard URL (customize in template)

---

## Dead Letter Queue (DLQ)

Failed alert deliveries are written to `alerts.dlq` Kafka topic for retry and analysis.

**Configuration:**
```yaml
dlq:
  enabled: true
  topic: alerts.dlq
  
  retry:
    max_attempts: 3
    initial_delay_ms: 1000
    max_delay_ms: 60000
    backoff_multiplier: 2.0
  
  include_original_message: true
  include_error_details: true
  include_retry_count: true
```

**DLQ Message Format:**
```json
{
  "timestamp": "2025-10-24T12:00:00.123Z",
  "destination": "syslog",
  "error": {
    "type": "ConnectionError",
    "message": "Failed to connect to syslog server"
  },
  "retry_count": 3,
  "original_message": { ... },
  "metadata": {}
}
```

**Consume DLQ for Analysis:**
```bash
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic alerts.dlq \
  --from-beginning \
  --property print.key=true \
  --property print.value=true
```

**Replay Failed Alerts:**
```python
# Read from DLQ and retry manually
from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'dlq-replay',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(['alerts.dlq'])

# Process and retry...
```

---

## Testing

### 1. Unit Tests

Run alerting service unit tests:

```bash
cd backend
pytest alerting/test_alerter.py -v
```

### 2. Integration Tests

Test end-to-end flow:

```bash
# Start services
docker compose up -d

# Send test prediction
python backend/alerting/test_integration.py
```

### 3. Manual Testing

**Send test prediction to Kafka:**
```python
from confluent_kafka import Producer
import json

producer = Producer({'bootstrap.servers': 'localhost:9092'})

test_prediction = {
    'flow_id': 'test-flow-12345',
    'timestamp': 1729776000000,
    'class_idx': 5,
    'class_name': 'DDoS',
    'confidence': 0.95,
    'model_version': 'v1.0',
    'feature_version': 'v1.0',
    'src_ip': '192.168.1.100',
    'dst_ip': '10.0.0.1',
    'src_port': 12345,
    'dst_port': 80,
    'protocol': 'TCP'
}

producer.produce(
    'predictions',
    value=json.dumps(test_prediction).encode('utf-8')
)
producer.flush()
```

**Verify alert in database:**
```sql
SELECT * FROM alerts WHERE flow_id = 'test-flow-12345';
```

**Check integration delivery:**
- **Syslog**: Check syslog server logs
- **Splunk**: Search in Splunk UI
- **Email**: Check inbox

---

## Monitoring & Metrics

### Service Health

Check service status:
```bash
docker compose ps alerting-service
docker compose logs alerting-service
```

### Database Metrics

Query alert statistics:
```sql
-- Alerts by severity
SELECT severity, COUNT(*) as count
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY severity
ORDER BY count DESC;

-- Alerts by class
SELECT class_name, COUNT(*) as count
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY class_name
ORDER BY count DESC;

-- Delivery success rate
SELECT 
  destinations[1] as destination,
  COUNT(*) as total,
  SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) as success,
  ROUND(100.0 * SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND destinations IS NOT NULL
GROUP BY destination;
```

### DLQ Monitoring

Check DLQ topic size:
```bash
kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic alerts.dlq
```

---

## Troubleshooting

### Issue: Alerts not being created

**Check:**
1. Alerting service running: `docker compose ps alerting-service`
2. Predictions being produced: Check model service logs
3. Severity mapping: Review `config.yaml` severity mappings
4. Confidence thresholds: Check if predictions meet minimum confidence

**Debug:**
```bash
# Check Kafka consumer lag
kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group alerting-service \
  --describe

# Check service logs
docker compose logs alerting-service | grep -i error
```

### Issue: Syslog delivery failing

**Check:**
1. Network connectivity: `telnet syslog-host 6514`
2. TLS certificates: Verify cert paths and validity
3. Syslog server accepting connections

**Debug:**
```bash
# Test TLS connection
openssl s_client -connect syslog-host:6514

# Check alerting service logs
docker compose logs alerting-service | grep -i syslog
```

### Issue: Email not sending

**Check:**
1. SMTP credentials: Verify username/password
2. Rate limits: Check if rate limit exceeded
3. SMTP server connectivity

**Debug:**
```python
# Test SMTP connection manually
import smtplib

server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('user@gmail.com', 'app-password')
server.quit()
```

### Issue: High DLQ volume

**Check:**
1. Review DLQ messages: Identify failing destination
2. Check destination availability
3. Review error patterns

**Fix:**
1. Address root cause (network, credentials, etc.)
2. Increase retry attempts if transient errors
3. Replay DLQ messages after fix

---

## Performance Tuning

### High Alert Volume

Increase batch sizes and worker threads:

```yaml
performance:
  consumer:
    batch_size: 200        # Increase from 100
    batch_timeout_ms: 50
  
  database:
    connection_pool_size: 20  # Increase from 10
    batch_size: 50            # Increase from 10
  
  worker_threads: 8          # Increase from 4
```

### Reduce Latency

Decrease batch timeouts:

```yaml
integrations:
  database:
    batch_timeout_ms: 100  # Decrease from 500
  
  splunk:
    batch_timeout_ms: 500  # Decrease from 1000
```

### Memory Optimization

Limit deduplication window:

```yaml
alert_filtering:
  deduplication_window: 60  # 1 minute instead of 5
```

---

## Security Considerations

1. **TLS Certificates**: Use valid certificates for syslog TLS
2. **API Keys**: Rotate SIEM API keys regularly
3. **SMTP Credentials**: Use app passwords, not account passwords
4. **Database Access**: Limit alerting service DB permissions (INSERT only)
5. **Rate Limiting**: Prevent alert flooding (DoS)
6. **PII Handling**: Consider anonymizing IP addresses if required

---

## Maintenance

### Rotate Logs

Configure log rotation in `docker-compose.yml`:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Clean Old Alerts

Archive or delete old alerts:

```sql
-- Archive alerts older than 90 days
DELETE FROM alerts WHERE created_at < NOW() - INTERVAL '90 days';
```

### Update Configuration

1. Edit `backend/alerting/config.yaml`
2. Restart service: `docker compose restart alerting-service`

---

## References

- [RFC5424 Syslog Protocol](https://tools.ietf.org/html/rfc5424)
- [Splunk HEC Documentation](https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector)
- [QRadar API Reference](https://www.ibm.com/docs/en/qradar-common)
- [Elastic Common Schema (ECS)](https://www.elastic.co/guide/en/ecs/current/index.html)

---

## Support

For issues or questions:
1. Check logs: `docker compose logs alerting-service`
2. Review configuration: `backend/alerting/config.yaml`
3. Check DLQ: `kafka-console-consumer --topic alerts.dlq`
4. Open issue on GitHub repository
