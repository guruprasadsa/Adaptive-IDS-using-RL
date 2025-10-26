# Alerting Module

## Overview

The alerting pipeline consumes ML predictions from Kafka, classifies severity, persists alerts to PostgreSQL, and dispatches to external integrations with comprehensive error handling.

**Key Features:**
- 🎯 **Severity Classification**: Maps attack classes to severity levels (INFO → CRITICAL)
- 🔍 **Alert Filtering**: Deduplication, confidence thresholds, rate limiting
- 💾 **Persistent Storage**: Alerts stored in PostgreSQL with full audit trail
- 🚨 **Multi-Channel Dispatch**: Syslog (TLS), SIEM (Splunk/QRadar/Elastic), Email
- 🔄 **Retry & DLQ**: Failed deliveries sent to dead-letter queue for analysis

## Quick Start

### 1. Start Services

```bash
# Start all services (including alerting)
docker compose up -d

# Check alerting service
docker compose logs -f alerting-service
```

### 2. Configure Integrations

Edit `config.yaml` or set environment variables:

```bash
# Enable syslog
export SYSLOG_ENABLED=true
export SYSLOG_HOST=syslog.example.com

# Enable email
export EMAIL_ENABLED=true
export SMTP_HOST=smtp.gmail.com
export SMTP_USER=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
export EMAIL_TO=security@example.com
```

### 3. Verify Operation

```bash
# Check recent alerts
docker compose exec postgres psql -U adaptive_ids -d adaptive_ids \
  -c "SELECT alert_id, severity, class_name, src_ip, created_at FROM alerts ORDER BY created_at DESC LIMIT 10;"

# Run integration test
cd backend
python alerting/test_integration.py
```

## Components

```
backend/alerting/
├── alerter.py              # Main service (Kafka consumer, dispatcher)
├── config.yaml             # Configuration (severity mappings, integrations)
├── dlq.py                  # Dead Letter Queue producer
├── integrations/
│   ├── syslog_client.py    # RFC5424 syslog (TLS)
│   ├── siem_client.py      # Splunk/QRadar/Elastic clients
│   └── email_client.py     # Email with rate limiting
├── test_alerter.py         # Unit tests
├── test_integration.py     # Integration test script
├── INTEGRATION.md          # Full documentation
└── README.md              # This file
```

## Alert Flow

```
Predictions (Kafka)
       ↓
   Classify Severity
       ↓
   Apply Filters (dedup, confidence, rate limit)
       ↓
   ┌─────────────────┐
   │ Persist to DB   │
   └─────────────────┘
       ↓
   Dispatch to Integrations
   ├─→ Syslog (TLS)
   ├─→ Splunk HEC
   ├─→ QRadar API
   ├─→ Elastic SIEM
   └─→ Email (SMTP)
       ↓
   (on failure) → DLQ (alerts.dlq)
```

## Severity Levels

| Severity | Description | Examples | Default Threshold |
|----------|-------------|----------|-------------------|
| **CRITICAL** | System compromise, data exfiltration | Infiltration, Heartbleed | 75% confidence |
| **HIGH** | Distributed attacks, severe impact | DDoS, Botnet | 70% confidence |
| **MEDIUM** | Confirmed attacks, moderate impact | Web attacks, DoS | 60% confidence |
| **LOW** | Reconnaissance, minor violations | PortScan, Nmap | 50% confidence |
| **INFO** | Normal traffic, low-confidence detections | BENIGN, Normal | 0% (suppressed) |

## Configuration

### Severity Mapping (config.yaml)

```yaml
severity_mapping:
  Infiltration: CRITICAL
  DDoS: HIGH
  DoS Hulk: MEDIUM
  PortScan: LOW
  Normal: INFO
  _default: MEDIUM
```

### Environment Variables

**Required:**
- `KAFKA_BROKERS`: Kafka servers (default: `localhost:9092`)
- `PRED_TOPIC`: Predictions topic (default: `predictions`)
- `PG_DSN`: PostgreSQL connection string

**Optional (Integrations):**
- `SYSLOG_ENABLED`, `SYSLOG_HOST`, `SYSLOG_PORT`
- `EMAIL_ENABLED`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`
- `SPLUNK_ENABLED`, `SPLUNK_HEC_URL`, `SPLUNK_HEC_TOKEN`
- `QRADAR_ENABLED`, `QRADAR_URL`, `QRADAR_API_KEY`
- `ELASTIC_ENABLED`, `ELASTIC_URL`, `ELASTIC_API_KEY`

See `INTEGRATION.md` for complete configuration reference.

## Integrations

### PostgreSQL (Always Enabled)
Alerts persisted to `alerts` table with:
- Alert metadata (ID, flow ID, timestamps)
- Classification (class, confidence, severity)
- Network context (src/dst IP/port, protocol)
- Model versions, workflow status, dispatch tracking

### Syslog (RFC5424 over TLS)
Send structured alerts to syslog server:
- TLS encryption with client certificates
- Connection pooling and automatic retry
- RFC5424 compliant formatting
- Configurable facility and severity mapping

### Splunk (HTTP Event Collector)
Index alerts in Splunk:
- Bulk ingestion via HEC API
- Custom sourcetype (`ids:alert`)
- Structured JSON events

### QRadar (REST API)
Create offenses in IBM QRadar:
- Automatic offense creation
- Severity/credibility mapping
- Source/destination tracking

### Elastic SIEM (Elasticsearch)
Index alerts for Elastic SIEM:
- ECS (Elastic Common Schema) compatible
- Bulk API for performance
- Integration with Kibana

### Email (SMTP)
Send notifications for high-severity alerts:
- HTML and plain text formats
- Rate limiting (per-minute/hour/day)
- Customizable subject templates
- TLS/SSL support

## Dead Letter Queue (DLQ)

Failed deliveries written to `alerts.dlq` Kafka topic:
- **Retry Policy**: 3 attempts with exponential backoff
- **Metadata**: Error details, retry count, original message
- **Analysis**: Consume DLQ to identify integration issues

```bash
# Check DLQ for failures
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic alerts.dlq \
  --from-beginning
```

## Testing

### Unit Tests
```bash
cd backend
pytest alerting/test_alerter.py -v
```

### Integration Test
```bash
# Send test predictions and verify alerts
python alerting/test_integration.py
```

### Manual Testing
```bash
# Query recent alerts
docker compose exec postgres psql -U adaptive_ids -d adaptive_ids \
  -c "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 5;"
```

## Monitoring

### Service Health
```bash
# Check service status
docker compose ps alerting-service

# View logs
docker compose logs -f alerting-service
```

### Database Queries
```sql
-- Alerts by severity (last hour)
SELECT severity, COUNT(*) 
FROM alerts 
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY severity;

-- Delivery success rate
SELECT 
  destinations[1] as destination,
  COUNT(*) as total,
  SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) as success
FROM alerts 
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY destination;
```

## Troubleshooting

### No alerts created
- Check alerting service: `docker compose logs alerting-service`
- Verify predictions: `kafka-console-consumer --topic predictions`
- Review severity mappings in `config.yaml`

### Integration failures
- Check DLQ: `kafka-console-consumer --topic alerts.dlq`
- Verify credentials and connectivity
- Review service logs for error details

### High DLQ volume
- Identify failing destination in DLQ messages
- Check destination availability/credentials
- Increase retry attempts if transient errors

## Documentation

- **Full Guide**: See `INTEGRATION.md` for complete setup instructions
- **Config Reference**: All options documented in `config.yaml`
- **API Docs**: Integration-specific setup for Splunk, QRadar, Elastic

## Support

For issues or questions:
1. Check logs: `docker compose logs alerting-service`
2. Review `INTEGRATION.md` troubleshooting section
3. Check DLQ for failed deliveries
4. Open issue on GitHub repository
