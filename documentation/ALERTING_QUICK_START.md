# Alerting Pipeline - Quick Start Guide

## Current Status ✅

Your alerting pipeline is **fully operational** with:
- ✅ Database persistence (PostgreSQL)
- ✅ Severity classification (INFO, LOW, MEDIUM, HIGH, CRITICAL)
- ✅ Alert filtering and deduplication
- ✅ Dead Letter Queue for failures
- ⚠️ External integrations (disabled by default)

---

## Quick Setup Options

### Option 1: Interactive Setup (Recommended)

Run the interactive configuration script:

```powershell
python setup_alerting_integrations.py
```

This will guide you through configuring:
- Email notifications
- Syslog forwarding
- Splunk HEC
- Elastic SIEM

---

### Option 2: Manual Configuration

#### Step 1: Copy Environment Template

```powershell
copy .env.alerting.example .env.alerting
```

#### Step 2: Edit `.env.alerting`

Enable and configure your desired integrations:

**For Email (Gmail):**
```bash
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=true
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=ids-alerts@company.com
EMAIL_TO=security@company.com
```

**For Splunk:**
```bash
SPLUNK_ENABLED=true
SPLUNK_HEC_URL=https://your-splunk.com:8088/services/collector
SPLUNK_HEC_TOKEN=your-token-here
SPLUNK_INDEX=ids_alerts
```

#### Step 3: Update Docker Compose

Add to `alerting-service` in `docker-compose.yml`:

```yaml
alerting-service:
  # ... existing config ...
  env_file:
    - .env.alerting
```

#### Step 4: Restart Service

```powershell
docker compose restart alerting-service
```

---

## Common Integration Scenarios

### Scenario 1: Email-Only Alerts (Small Team)

**Use Case:** Small team, want email for critical threats

```bash
# .env.alerting
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=security@company.com
SMTP_PASSWORD=your-app-password
EMAIL_TO=team@company.com

SYSLOG_ENABLED=false
SPLUNK_ENABLED=false
ELASTIC_ENABLED=false
QRADAR_ENABLED=false
```

**Gmail App Password:**
1. Enable 2FA: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Select "Mail" and "Windows Computer"
4. Copy generated password

---

### Scenario 2: Splunk Integration (Enterprise)

**Use Case:** Already using Splunk for SIEM

```bash
# .env.alerting
EMAIL_ENABLED=true  # For critical alerts
EMAIL_TO=soc@company.com

SPLUNK_ENABLED=true
SPLUNK_HEC_URL=https://splunk.company.com:8088/services/collector
SPLUNK_HEC_TOKEN=12345678-1234-1234-1234-123456789012
SPLUNK_INDEX=ids_alerts
SPLUNK_VERIFY_SSL=true
```

**Splunk Setup:**
```
1. Settings → Data Inputs → HTTP Event Collector
2. Click "New Token"
3. Name: adaptive-ids
4. Source Type: ids:alert (or _json)
5. Select Index: ids_alerts
6. Copy Token
7. Global Settings → Enable HEC
```

**Splunk Queries:**
```spl
# Recent high-severity alerts
index=ids_alerts severity IN (HIGH, CRITICAL)
| table _time severity class_name src_ip dst_ip confidence
| sort -_time

# Alerts by attack type
index=ids_alerts 
| stats count by class_name
| sort -count

# Top source IPs
index=ids_alerts severity!=INFO
| stats count by src_ip
| sort -count limit=10
```

---

### Scenario 3: Elastic Stack (ELK)

**Use Case:** Using Elastic Security/SIEM

```bash
# .env.alerting
ELASTIC_ENABLED=true
ELASTIC_URL=https://elasticsearch.company.com:9200
ELASTIC_API_KEY=your-api-key-id:your-api-key-secret
ELASTIC_INDEX=ids-alerts
ELASTIC_VERIFY_SSL=true
```

**Elastic Setup:**

1. **Create API Key** (Kibana Dev Tools):
```json
POST /_security/api_key
{
  "name": "adaptive-ids",
  "role_descriptors": {
    "ids-writer": {
      "cluster": [],
      "index": [
        {
          "names": ["ids-alerts*"],
          "privileges": ["create_index", "write", "index"]
        }
      ]
    }
  }
}
```

2. **Query Alerts** (Kibana Dev Tools):
```json
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

### Scenario 4: Multi-Tier Alerting

**Use Case:** Different severity levels to different channels

```bash
# .env.alerting

# Email for CRITICAL only (executive team)
EMAIL_ENABLED=true
EMAIL_TO=executives@company.com
# min_severity: CRITICAL (configured in config.yaml)

# Splunk for all alerts (SOC analysis)
SPLUNK_ENABLED=true
SPLUNK_HEC_URL=https://splunk.company.com:8088/services/collector
SPLUNK_HEC_TOKEN=your-token
# min_severity: LOW (configured in config.yaml)

# Syslog for HIGH+ (forwarding to other systems)
SYSLOG_ENABLED=true
SYSLOG_HOST=siem.company.com
SYSLOG_PORT=6514
# min_severity: HIGH (configured in config.yaml)
```

**Adjust severity thresholds** in `backend/alerting/config.yaml`:
```yaml
integrations:
  email:
    min_severity: CRITICAL  # Only critical alerts
  splunk:
    min_severity: LOW       # All alerts
  syslog:
    min_severity: HIGH      # High and critical
```

---

## Testing Your Configuration

### 1. Test Single Integration

```powershell
# Enable ONE integration in .env.alerting
# Restart service
docker compose restart alerting-service

# Send test alerts
python backend\alerting\test_integration.py

# Check logs
docker compose logs -f alerting-service
```

### 2. Verify Each Integration

**Email:**
- Check your inbox for test alerts
- Look for subject: `[HIGH] IDS Alert: DDoS detected from 192.168.1.x`

**Splunk:**
- Search: `index=ids_alerts | head 10`
- Should see JSON events with alert details

**Elastic:**
- Query: `GET ids-alerts/_search`
- Should see documents with ECS-formatted alerts

**Syslog:**
- Check syslog server logs
- Look for RFC5424 formatted messages

### 3. Check for Errors

```powershell
# Service logs
docker compose logs alerting-service | Select-String -Pattern "ERROR"

# Dead Letter Queue (failed deliveries)
docker compose exec kafka kafka-console-consumer `
  --bootstrap-server localhost:9092 `
  --topic alerts.dlq `
  --from-beginning `
  --max-messages 10
```

---

## Troubleshooting

### Email Not Sending

**Problem:** `SMTPAuthenticationError` or connection refused

**Solutions:**
```powershell
# Test SMTP connection manually
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('user@gmail.com', 'app-password')
server.quit()
print('✓ SMTP connection successful')
"
```

- Gmail: Use App Password, not regular password
- Check 2FA is enabled
- Verify SMTP_HOST and SMTP_PORT
- Check firewall allows outbound port 587

---

### Splunk HEC Not Receiving

**Problem:** `Connection refused` or `401 Unauthorized`

**Solutions:**
1. Verify HEC is enabled: Settings → HTTP Event Collector → Global Settings
2. Check token is valid
3. Test HEC manually:
```powershell
curl -k https://splunk:8088/services/collector `
  -H "Authorization: Splunk YOUR-TOKEN" `
  -d '{"event":"test"}'
```
4. Check firewall allows port 8088
5. Verify SSL certificate if `SPLUNK_VERIFY_SSL=true`

---

### Elastic Not Indexing

**Problem:** `403 Forbidden` or `401 Unauthorized`

**Solutions:**
1. Verify API key format: `id:secret`
2. Check API key permissions include `write` and `create_index`
3. Test API key:
```bash
curl -H "Authorization: ApiKey YOUR_API_KEY" \
  https://elastic:9200/_security/_authenticate
```
4. Verify index pattern matches: `ids-alerts*`

---

### Syslog Not Forwarding

**Problem:** `Connection timeout` or `TLS handshake failed`

**Solutions:**
1. Test connection: `telnet syslog-host 6514`
2. For TLS: Verify certificate paths are correct
3. Try UDP instead of TLS:
```yaml
# In config.yaml
integrations:
  syslog:
    protocol: UDP  # Instead of TLS
    port: 514
```
4. Check firewall rules

---

## Performance Tuning

### High Alert Volume

If processing >1000 alerts/minute:

1. **Increase batch sizes** (`backend/alerting/config.yaml`):
```yaml
integrations:
  database:
    batch_size: 50  # Increase from 10
  splunk:
    batch_size: 50  # Increase from 10
  elastic:
    batch_size: 100 # Increase from 20
```

2. **Reduce retention**:
```sql
-- Archive/delete old alerts
DELETE FROM alerts WHERE created_at < NOW() - INTERVAL '30 days';
```

3. **Add database indexes** (already done):
```sql
-- Check indexes
\d alerts
```

---

## Monitoring Queries

### Recent Alerts by Severity
```sql
SELECT severity, COUNT(*) as count
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY severity
ORDER BY 
  CASE severity
    WHEN 'CRITICAL' THEN 1
    WHEN 'HIGH' THEN 2
    WHEN 'MEDIUM' THEN 3
    WHEN 'LOW' THEN 4
    WHEN 'INFO' THEN 5
  END;
```

### Top Attack Types
```sql
SELECT class_name, COUNT(*) as count, AVG(confidence) as avg_confidence
FROM alerts
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND severity IN ('HIGH', 'CRITICAL')
GROUP BY class_name
ORDER BY count DESC
LIMIT 10;
```

### Top Source IPs
```sql
SELECT src_ip, COUNT(*) as alert_count, 
       ARRAY_AGG(DISTINCT class_name) as attack_types
FROM alerts
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY src_ip
ORDER BY alert_count DESC
LIMIT 10;
```

### Delivery Success Rate
```sql
SELECT 
  UNNEST(destinations) as destination,
  COUNT(*) as total,
  SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) as successful,
  ROUND(100.0 * SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND destinations IS NOT NULL
GROUP BY destination;
```

---

## Support & Documentation

- **Full Integration Guide:** `backend/alerting/INTEGRATION.md`
- **Configuration Reference:** `backend/alerting/config.yaml`
- **Service Logs:** `docker compose logs -f alerting-service`
- **Test Script:** `python backend/alerting/test_integration.py`

---

## Next Steps

1. ✅ Choose your integration scenario above
2. ✅ Configure `.env.alerting` file
3. ✅ Update `docker-compose.yml` with `env_file`
4. ✅ Restart service and test
5. ✅ Monitor logs and verify delivery
6. ✅ Set up dashboards in Splunk/Elastic/Kibana
7. ✅ Configure alert retention policies
8. ✅ Document your integration for your team

**Your alerting pipeline is ready for production!** 🚀
