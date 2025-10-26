# Integration Quick Reference Card

Quick setup commands and verification for each free and open-source integration.

---

## 1. Syslog

### Enable (UDP - Quick Test)
```bash
# backend/.env
SYSLOG_ENABLED=true
SYSLOG_HOST=localhost
SYSLOG_PORT=514
```

### Test Listener (PowerShell Admin)
```powershell
# Install nmap (includes ncat)
# Or use Python:
python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('', 514)); print('Listening...'); [print(s.recvfrom(4096)) for _ in range(10)]"
```

### Verify
```powershell
docker compose restart alerting-service
python test_single_email.py
# Check listener receives RFC5424 message
```

---

## 2. Graylog SIEM

### Enable
```bash
# backend/.env
GRAYLOG_ENABLED=true
GRAYLOG_HOST=localhost
GRAYLOG_PORT=12201
GRAYLOG_PROTOCOL=HTTP  # or UDP or TCP
```

### Deploy Graylog Stack
```powershell
# Add to docker-compose.yml (see full guide)
# Start services
docker compose up -d graylog mongodb graylog-elasticsearch

# Wait for startup (2-3 minutes)
docker compose logs -f graylog
```

### Access Web UI
```
URL: http://localhost:9000
Username: admin
Password: admin
```

### Create GELF HTTP Input
```
System → Inputs → GELF HTTP → Launch new input
Title: Adaptive IDS Alerts
Bind address: 0.0.0.0
Port: 12201
Save
```

### Test
```powershell
# Send test GELF message
$body = @{
    version = "1.1"
    host = "test"
    short_message = "test"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:12201/gelf" `
    -Method Post `
    -Body $body `
    -ContentType "application/json"
```

### Verify
```
Search → All messages
Query: source:adaptive-ids
Or: _severity:HIGH
Or: _class_name:*
```

---

## Test All Integrations

### Quick Test
```powershell
# Send 4 alerts (CRITICAL, HIGH, MEDIUM, LOW)
python test_all_integrations.py

# Watch logs
docker compose logs -f alerting-service
```

### Single Test Alert
```powershell
python test_single_email.py
```

---

## Troubleshooting Checklist

### No alerts sent?
```powershell
# Check service is running
docker compose ps

# Check logs for errors
docker compose logs alerting-service | Select-String -Pattern "ERROR"

# Verify environment variables loaded
docker compose exec alerting-service env | findstr /i "ENABLED"
```

### Integration not working?
```powershell
# Check specific integration logs
docker compose logs alerting-service | findstr /i "email"
docker compose logs alerting-service | findstr /i "syslog"
docker compose logs alerting-service | findstr /i "graylog"
```

### Need to reload config?
```powershell
# After changing .env file
docker compose restart alerting-service

# After code changes
docker compose up -d --build alerting-service
```

---

## Common Patterns

### Enable Multiple Integrations
```bash
# backend/.env
EMAIL_ENABLED=true
SYSLOG_ENABLED=true
GRAYLOG_ENABLED=true
# All three will receive alerts
```

### Severity Filtering
Edit `backend/alerting/config.yaml`:
```yaml
integrations:
  email:
    min_severity: HIGH  # Only HIGH and CRITICAL
  
  graylog:
    min_severity: MEDIUM  # MEDIUM, HIGH, CRITICAL
  
  syslog:
    min_severity: INFO  # All alerts
```

### Rate Limiting
```bash
# backend/.env
EMAIL_RATE_LIMIT_PER_MIN=5
EMAIL_RATE_LIMIT_PER_HOUR=100
EMAIL_RATE_LIMIT_PER_DAY=500
```

---

## Quick Verification Commands

### Email
```powershell
# Check email logs
docker compose logs alerting-service | Select-String -Pattern "Sent email"
```

### Syslog
```powershell
# Check syslog server
# Should see RFC5424 format messages
```

### Graylog
```
# Search in Graylog UI
source:adaptive-ids
```

---

## Status Dashboard Query

```sql
-- Check last hour's alerts by destination
SELECT 
  UNNEST(destinations) as destination,
  severity,
  COUNT(*) as count,
  MAX(created_at) as last_alert
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY destination, severity
ORDER BY destination, severity;
```

---

## Emergency Disable

```bash
# Disable all integrations quickly
EMAIL_ENABLED=false
SYSLOG_ENABLED=false
GRAYLOG_ENABLED=false
```

```powershell
docker compose restart alerting-service
```

---

## Documentation

- **Full Guide**: `INTEGRATIONS_SETUP_GUIDE.md`
- **Alerting Overview**: `documentation/ALERTING_COMPLETE.md`
- **Quick Start**: `backend/alerting/ALERTING_QUICK_START.md`
- **API Reference**: `documentation/API_INTEGRATION.md`
