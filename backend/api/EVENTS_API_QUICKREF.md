# Real-Time Events API - Quick Reference

## Endpoints Summary

### 🔴 Real-Time Streaming

```
GET /api/events?token={JWT}&topic={alerts|predictions}
```
Server-Sent Events stream for real-time alerts/predictions

---

### 🔍 Alert Queries

```
GET /api/alerts?page=1&per_page=10
  &severity={INFO|LOW|MEDIUM|HIGH|CRITICAL}
  &class_name={DDoS|PortScan|...}
  &status={new|investigating|resolved|false_positive}
  &min_confidence=0.8&max_confidence=1.0
  &srcIp=192.168.1.100&dstIp=10.0.0.1
  &startTime=2025-10-24T00:00:00Z&endTime=2025-10-24T23:59:59Z
  &search=DDoS
```
Query alerts with advanced filtering

```
GET /api/alerts/{alert_id}
```
Get alert details

---

### ✅ Alert Actions

```
PATCH /api/alerts/{alert_id}/ack
POST  /api/alerts/{alert_id}/ack
Body: {"notes": "Investigating..."}
```
Acknowledge alert

```
PATCH /api/alerts/{alert_id}/false-positive
POST  /api/alerts/{alert_id}/false-positive
Body: {"notes": "Load testing traffic"}
```
Mark alert as false positive (triggers model feedback)

```
PATCH /api/alerts/{alert_id}/status
Body: {"status": "resolved", "notes": "..."}
```
Update alert status

---

## Quick Examples

### JavaScript SSE Client

```javascript
const token = localStorage.getItem('access_token');
const es = new EventSource(`/api/events?token=${token}`);

es.addEventListener('alert', (e) => {
  const alert = JSON.parse(e.data);
  console.log('Alert:', alert.severity, alert.className);
});

es.addEventListener('heartbeat', () => console.log('💓'));
```

### Python Query & Action

```python
import requests

headers = {"Authorization": f"Bearer {token}"}

# Query critical alerts
r = requests.get("/api/alerts", headers=headers, params={
    "severity": "CRITICAL",
    "status": "new",
    "min_confidence": 0.9
})
alerts = r.json()['alerts']

# Acknowledge first alert
if alerts:
    requests.patch(
        f"/api/alerts/{alerts[0]['id']}/ack",
        headers=headers,
        json={"notes": "Investigating DDoS"}
    )
```

### curl Examples

```bash
TOKEN="your-jwt-token"

# Stream events
curl -N "http://localhost:5000/api/events?token=$TOKEN"

# Query alerts
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:5000/api/alerts?severity=HIGH&min_confidence=0.8"

# Acknowledge
curl -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Investigating"}' \
  http://localhost:5000/api/alerts/ALERT_ID/ack

# Mark false positive
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Benign"}' \
  http://localhost:5000/api/alerts/ALERT_ID/false-positive
```

---

## Filter Cheat Sheet

| Filter | Type | Example | Description |
|--------|------|---------|-------------|
| `severity` | string | `HIGH` | Alert severity level |
| `class_name` | string | `DDoS` | Attack class |
| `status` | string | `new` | Workflow status |
| `min_confidence` | float | `0.8` | Min confidence score |
| `max_confidence` | float | `1.0` | Max confidence score |
| `srcIp` | string | `192.168.1.100` | Source IP |
| `dstIp` | string | `10.0.0.1` | Destination IP |
| `startTime` | ISO 8601 | `2025-10-24T00:00:00Z` | Start time |
| `endTime` | ISO 8601 | `2025-10-24T23:59:59Z` | End time |
| `search` | string | `DDoS` | Full-text search |
| `page` | int | `1` | Page number |
| `per_page` | int | `20` | Results per page |

---

## Status Values

**Alert Status:**
- `new` - Newly detected
- `investigating` - Being analyzed
- `resolved` - Confirmed and mitigated
- `false_positive` - Benign traffic

**Severity Levels:**
- `INFO` - Informational
- `LOW` - Low impact
- `MEDIUM` - Moderate impact
- `HIGH` - High impact
- `CRITICAL` - Critical threat

---

## SSE Event Types

| Event | Description |
|-------|-------------|
| `connected` | Connection established |
| `alert` | New alert from Kafka |
| `prediction` | New prediction from model |
| `heartbeat` | Keep-alive message (30s) |
| `error` | Stream error occurred |

---

## Response Formats

### Alert Object

```json
{
  "id": "alert-uuid",
  "severity": "HIGH",
  "className": "DDoS",
  "classIdx": 5,
  "confidence": 0.95,
  "timestamp": "2025-10-24T10:00:00Z",
  "srcIp": "192.168.1.100",
  "dstIp": "10.0.0.1",
  "srcPort": 54321,
  "dstPort": 80,
  "protocol": "TCP",
  "status": "new",
  "modelVersion": "v2.0",
  "featureVersion": "v1.0-cic41",
  "assignedTo": null,
  "notes": null
}
```

### Paginated Response

```json
{
  "alerts": [...],
  "total": 42,
  "page": 1,
  "per_page": 10,
  "total_pages": 5
}
```

### Action Response

```json
{
  "success": true,
  "alert": {...},
  "message": "Alert acknowledged successfully"
}
```

---

## Testing

```bash
# Run tests
cd backend
pytest tests/test_alerts_api.py -v

# Run with coverage
pytest tests/test_alerts_api.py --cov=api --cov-report=html
```

---

## Common Issues

**SSE disconnects:**
- Check token expiration
- Verify Kafka is running
- Check network/firewall

**No alerts in stream:**
- Verify alerts are being produced to Kafka topic
- Check consumer group lag
- Ensure topic name is correct

**Slow queries:**
- Add database indexes
- Reduce page size
- Use more specific filters

---

For full documentation, see [EVENTS_API_README.md](./EVENTS_API_README.md)
