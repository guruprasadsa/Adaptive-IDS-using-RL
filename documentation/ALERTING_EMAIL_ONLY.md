# Email-Only Alerting Configuration

**Status**: ✅ **Active** - Only email alerting is enabled

---

## Current Configuration

### ✅ **Enabled Integrations**
- **Email Notifications** (Gmail)
  - Primary: guruprasadsa8@gmail.com
  - CC: jeevanthecrplayerno1@gmail.com
  - Server: smtp.gmail.com:587 (TLS)
  - Min Severity: HIGH (only HIGH and CRITICAL alerts)

### ❌ **Disabled Integrations**
- ~~Syslog~~ - Commented out in config.yaml
- ~~Splunk HEC~~ - Removed from .env
- ~~QRadar~~ - Removed from .env
- ~~Elastic SIEM~~ - Removed from .env
- ~~Graylog~~ - Not configured

---

## Verification

### Service Status
```bash
docker compose logs alerting-service --tail 5
```

**Expected Output:**
```
Email integration enabled
Alert dispatcher initialized with 1 integrations
Alerting service started
```

✅ Shows **1 integration** (was 5 when all were enabled)

### Test Alert
```bash
python test_single_email.py
```

**Expected Result:**
- ✅ Email sent to guruprasadsa8@gmail.com
- ✅ Email CC'd to jeevanthecrplayerno1@gmail.com
- ✅ Alert saved to database
- ❌ No syslog messages
- ❌ No SIEM integration attempts

---

## Configuration Files

### 1. `.env` File
```bash
# Email - ENABLED
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=true
SMTP_USER=adaptiveids@gmail.com
SMTP_PASSWORD=afsn jgpq zuyl bpvn
EMAIL_FROM=adaptiveids@gmail.com
EMAIL_TO=guruprasadsa8@gmail.com
EMAIL_CC=jeevanthecrplayerno1@gmail.com

# All other integrations disabled
# (Syslog, Splunk, QRadar, Elastic, Graylog removed)
```

### 2. `config.yaml`
```yaml
integrations:
  # Email notifications - ENABLED (only active integration)
  email:
    enabled: ${EMAIL_ENABLED:false}
    smtp_host: ${SMTP_HOST:localhost}
    smtp_port: ${SMTP_PORT:587}
    # ... rest of email config

  # All other integrations commented out
  # syslog: disabled
  # splunk: disabled
  # qradar: disabled
  # elastic: disabled
  # graylog: disabled
```

---

## Alert Flow

```
Prediction (Kafka)
    ↓
Severity Classification
    ↓
Confidence Check (>70% for HIGH)
    ↓
Alert Created in Database
    ↓
Email Notification ONLY
    ↓
✉️ Sent to Gmail
```

**No external SIEM integrations** - alerts only go to:
1. PostgreSQL database
2. Email (Gmail)

---

## Rate Limiting

Email sending is rate-limited to prevent flooding:

```yaml
rate_limit:
  max_per_hour: 100
  max_per_day: 500
```

**Current Settings:**
- 5 emails per minute
- 100 emails per hour
- 500 emails per day

---

## Email Content

### Subject Line
```
[HIGH] IDS Alert: DDoS detected from 192.168.1.100
```

### Email Body (HTML)
- Alert ID and severity
- Attack classification
- Confidence score
- Source/Destination IPs and ports
- Protocol
- Timestamp
- Model/Feature versions

---

## Troubleshooting

### No email received?
```bash
# Check service logs
docker compose logs alerting-service | Select-String -Pattern "email"

# Check alert was created
docker compose logs alerting-service | Select-String -Pattern "Alert created"

# Verify email settings
docker compose exec alerting-service env | Select-String -Pattern "EMAIL"
```

### Email rate limiting?
```bash
# Check for rate limit warnings
docker compose logs alerting-service | Select-String -Pattern "rate limit"
```

### Want to re-enable other integrations?
See the comprehensive integration guides:
- `INTEGRATIONS_SETUP_GUIDE.md` - Full setup for Syslog and Graylog
- `INTEGRATION_QUICK_REFERENCE.md` - Quick commands

---

## Benefits of Email-Only Configuration

✅ **Simplicity** - No complex SIEM setup needed
✅ **Reliability** - Email is universally available
✅ **No Infrastructure** - No additional servers required
✅ **Easy Testing** - Just check your inbox
✅ **Zero Cost** - Free Gmail account
✅ **Proven Delivery** - SMTP is battle-tested

---

## Performance Impact

**Before** (All integrations enabled):
- 5 integration clients initialized
- Multiple network connections maintained
- Higher resource usage

**After** (Email only):
- 1 integration client (email)
- Single SMTP connection
- Lower resource usage
- Faster startup

---

## Next Steps

### Option 1: Keep Email Only ✅ **Recommended for Testing**
- Current setup is perfect for development/testing
- Low complexity, easy to debug
- All alerts still logged to database

### Option 2: Add Graylog Later
When you need centralized logging/dashboards:
1. Follow `INTEGRATIONS_SETUP_GUIDE.md`
2. Deploy Graylog with Docker Compose
3. Enable in `.env`: `GRAYLOG_ENABLED=true`
4. Restart service

### Option 3: Add Custom Integration
The system supports webhooks for custom destinations:
```yaml
webhook:
  enabled: true
  url: https://your-service.com/alerts
  method: POST
```

---

## Summary

🎯 **Current State:**
- ✅ Email alerting: **ACTIVE**
- ✅ Database persistence: **ACTIVE**
- ❌ Syslog: **DISABLED**
- ❌ SIEM integrations: **DISABLED**

**Result:** Simplified, reliable alerting via email only.

All HIGH and CRITICAL alerts will be sent to:
- 📧 guruprasadsa8@gmail.com (TO)
- 📧 jeevanthecrplayerno1@gmail.com (CC)
- 💾 PostgreSQL database (for all severities)

---

**Last Updated:** October 24, 2025
**Configuration:** Email-only alerting with Gmail
**Status:** Production Ready ✅
