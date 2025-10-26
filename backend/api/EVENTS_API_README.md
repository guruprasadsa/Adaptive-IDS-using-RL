# Real-Time Events and Alerts API

## Overview

This document describes the real-time events streaming endpoint and enhanced alert query/management endpoints added to the Adaptive IDS backend API.

## Table of Contents

1. [SSE Events Streaming](#sse-events-streaming)
2. [Enhanced Alert Queries](#enhanced-alert-queries)
3. [Alert Management Actions](#alert-management-actions)
4. [Examples](#examples)
5. [Testing](#testing)

---

## SSE Events Streaming

### `GET /api/events`

Server-Sent Events (SSE) endpoint for real-time streaming of alerts and predictions from Kafka topics.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `token` | string | Yes | - | JWT authentication token (EventSource doesn't support headers) |
| `topic` | string | No | `alerts` | Kafka topic to stream from (`alerts` or `predictions`) |

#### Response

- **Content-Type**: `text/event-stream`
- **Status Codes**:
  - `200 OK`: Stream established successfully
  - `401 Unauthorized`: Invalid or missing token
  - `400 Bad Request`: Invalid topic specified

#### Event Types

The SSE stream emits the following event types:

1. **connected**: Sent immediately upon connection
   ```
   event: connected
   data: {"timestamp": "2025-10-24T10:00:00Z", "user_id": 1, "topic": "alerts"}
   ```

2. **alert**: Alert event from Kafka alerts topic
   ```
   event: alert
   data: {"alert_id": "...", "severity": "HIGH", "class_name": "DDoS", ...}
   ```

3. **prediction**: Prediction event from Kafka predictions topic
   ```
   event: prediction
   data: {"flow_id": "...", "class_name": "DDoS", "confidence": 0.95, ...}
   ```

4. **heartbeat**: Periodic keep-alive message (every 30 seconds)
   ```
   event: heartbeat
   data: {"timestamp": 1729764000000}
   ```

5. **error**: Error occurred in stream
   ```
   event: error
   data: {"error": "Connection lost", "timestamp": "..."}
   ```

#### Example Client (JavaScript)

```javascript
const token = localStorage.getItem('access_token');
const eventSource = new EventSource(
  `http://localhost:5000/api/events?token=${token}&topic=alerts`
);

eventSource.addEventListener('connected', (e) => {
  console.log('Connected:', JSON.parse(e.data));
});

eventSource.addEventListener('alert', (e) => {
  const alert = JSON.parse(e.data);
  console.log('New alert:', alert);
  // Update UI with new alert
});

eventSource.addEventListener('heartbeat', (e) => {
  console.log('Heartbeat received');
});

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  // Implement reconnection logic
};
```

---

## Enhanced Alert Queries

### `GET /api/alerts`

Query alerts with advanced filtering, pagination, and search capabilities.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-indexed) |
| `per_page` | integer | No | 10 | Results per page |
| `priority` | string | No | - | Filter by priority (`low`, `medium`, `high`, `critical`) |
| `status` | string | No | - | Filter by status (`new`, `investigating`, `resolved`, `false_positive`) |
| `severity` | string | No | - | Filter by severity (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `class_name` or `className` | string | No | - | Filter by attack class (e.g., `DDoS`, `PortScan`) |
| `min_confidence` or `minConfidence` | float | No | - | Minimum confidence score (0.0-1.0) |
| `max_confidence` or `maxConfidence` | float | No | - | Maximum confidence score (0.0-1.0) |
| `src_ip` or `srcIp` | string | No | - | Filter by source IP address |
| `dst_ip` or `dstIp` | string | No | - | Filter by destination IP address |
| `start_time` or `startTime` | string | No | - | Start of time range (ISO 8601 format) |
| `end_time` or `endTime` | string | No | - | End of time range (ISO 8601 format) |
| `search` | string | No | - | Full-text search in description, source, type, class name |

#### Response

```json
{
  "alerts": [
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
      "priority": "high",
      "description": "Potential DDoS attack detected",
      "source": "model-inference",
      "type": "attack",
      "assignedTo": null,
      "notes": null
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 10,
  "total_pages": 5
}
```

#### Status Codes

- `200 OK`: Success
- `401 Unauthorized`: Authentication required
- `503 Service Unavailable`: Database unavailable

#### Examples

**Filter by severity and confidence:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:5000/api/alerts?severity=CRITICAL&min_confidence=0.9"
```

**Filter by time range and IP:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:5000/api/alerts?startTime=2025-10-24T00:00:00Z&endTime=2025-10-24T23:59:59Z&srcIp=192.168.1.100"
```

**Combine multiple filters:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:5000/api/alerts?severity=HIGH&class_name=DDoS&status=new&page=1&per_page=20"
```

---

## Alert Management Actions

### `GET /api/alerts/{alert_id}`

Retrieve details of a specific alert.

#### Response

```json
{
  "id": "alert-uuid",
  "severity": "HIGH",
  "className": "DDoS",
  ...
}
```

#### Status Codes

- `200 OK`: Alert found
- `404 Not Found`: Alert not found
- `401 Unauthorized`: Authentication required

---

### `PATCH /api/alerts/{alert_id}/ack` or `POST /api/alerts/{alert_id}/ack`

Acknowledge an alert and optionally add analyst notes.

#### Request Body

```json
{
  "notes": "Investigating source IP reputation and traffic patterns"
}
```

#### Response

```json
{
  "success": true,
  "alert": {
    "id": "alert-uuid",
    "status": "investigating",
    "notes": "Investigating source IP reputation and traffic patterns",
    ...
  },
  "message": "Alert acknowledged successfully"
}
```

#### Status Codes

- `200 OK`: Alert acknowledged
- `404 Not Found`: Alert not found
- `401 Unauthorized`: Authentication required
- `503 Service Unavailable`: Database error

#### Audit Event

Generates an audit event logged and (in production) published to Kafka:

```json
{
  "event_type": "alert_acknowledged",
  "alert_id": "alert-uuid",
  "user_id": 1,
  "timestamp": "2025-10-24T10:00:00Z",
  "notes": "Investigating..."
}
```

---

### `PATCH /api/alerts/{alert_id}/false-positive` or `POST /api/alerts/{alert_id}/false-positive`

Mark an alert as a false positive for model feedback and retraining.

#### Request Body

```json
{
  "notes": "Legitimate traffic spike from load testing"
}
```

#### Response

```json
{
  "success": true,
  "alert": {
    "id": "alert-uuid",
    "status": "false_positive",
    "notes": "Legitimate traffic spike from load testing",
    ...
  },
  "message": "Alert marked as false positive"
}
```

#### Status Codes

- `200 OK`: Marked successfully
- `404 Not Found`: Alert not found
- `401 Unauthorized`: Authentication required
- `503 Service Unavailable`: Database error

#### Audit Event

Generates a feedback event for model retraining:

```json
{
  "event_type": "false_positive_marked",
  "alert_id": "alert-uuid",
  "user_id": 1,
  "timestamp": "2025-10-24T10:00:00Z",
  "notes": "Legitimate traffic spike from load testing",
  "class_name": "DDoS",
  "confidence": 0.85
}
```

This event can be consumed by the adaptive learning pipeline to improve model accuracy.

---

### `PATCH /api/alerts/{alert_id}/status`

Update alert status with custom notes (generic status update).

#### Request Body

```json
{
  "status": "resolved",
  "notes": "False alarm - internal testing"
}
```

#### Allowed Status Values

- `new`
- `investigating`
- `resolved`
- `false_positive`

#### Response

```json
{
  "id": "alert-uuid",
  "status": "resolved",
  "notes": "False alarm - internal testing",
  ...
}
```

#### Status Codes

- `200 OK`: Status updated
- `400 Bad Request`: Invalid status value
- `404 Not Found`: Alert not found
- `401 Unauthorized`: Authentication required
- `503 Service Unavailable`: Database error

---

## Examples

### Python Client

```python
import requests
import json
from requests.exceptions import HTTPError

API_BASE = "http://localhost:5000/api"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Query high-severity alerts
response = requests.get(
    f"{API_BASE}/alerts",
    headers=headers,
    params={
        "severity": "HIGH",
        "status": "new",
        "min_confidence": 0.8,
        "page": 1,
        "per_page": 20
    }
)
alerts = response.json()

print(f"Found {alerts['total']} high-severity alerts")

# Acknowledge first alert
if alerts['alerts']:
    alert_id = alerts['alerts'][0]['id']
    response = requests.patch(
        f"{API_BASE}/alerts/{alert_id}/ack",
        headers=headers,
        json={"notes": "Investigating DDoS from source IP"}
    )
    print(f"Acknowledged alert: {response.json()['message']}")

# Mark alert as false positive
response = requests.post(
    f"{API_BASE}/alerts/{alert_id}/false-positive",
    headers=headers,
    json={"notes": "Load test traffic"}
)
print(f"Marked false positive: {response.json()['message']}")
```

### SSE Client with Reconnection

```javascript
class AlertStream {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
    this.eventSource = null;
    this.reconnectInterval = 5000;
    this.maxReconnectAttempts = 10;
    this.reconnectAttempts = 0;
  }

  connect() {
    const url = `${this.apiUrl}/events?token=${this.token}&topic=alerts`;
    this.eventSource = new EventSource(url);

    this.eventSource.addEventListener('connected', (e) => {
      console.log('Connected to alert stream');
      this.reconnectAttempts = 0;
    });

    this.eventSource.addEventListener('alert', (e) => {
      const alert = JSON.parse(e.data);
      this.onAlert(alert);
    });

    this.eventSource.addEventListener('heartbeat', (e) => {
      console.log('Heartbeat received');
    });

    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      this.eventSource.close();
      this.reconnect();
    };
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting (attempt ${this.reconnectAttempts})...`);
      setTimeout(() => this.connect(), this.reconnectInterval);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }

  onAlert(alert) {
    // Override this method to handle alerts
    console.log('New alert:', alert);
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
}

// Usage
const stream = new AlertStream('http://localhost:5000/api', 'your-token');
stream.onAlert = (alert) => {
  // Update UI with new alert
  console.log(`${alert.severity} alert: ${alert.className}`);
};
stream.connect();
```

---

## Testing

### Running Unit Tests

```bash
cd backend
pytest tests/test_alerts_api.py -v
```

### Test Coverage

The test suite covers:

- ✅ Alert querying with all filter combinations
- ✅ Pagination and search
- ✅ Alert acknowledgment with notes
- ✅ False positive marking with audit events
- ✅ SSE connection and authentication
- ✅ SSE topic selection and validation
- ✅ SSE fallback mode (when Kafka unavailable)
- ✅ Error handling (database errors, invalid inputs)
- ✅ Kafka consumer lifecycle (start/stop)

### Manual Testing

**1. Test SSE Streaming:**

```bash
# Get token
TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r '.access_token')

# Subscribe to alerts stream
curl -N -H "Accept: text/event-stream" \
  "http://localhost:5000/api/events?token=$TOKEN&topic=alerts"
```

**2. Test Alert Queries:**

```bash
# Query with filters
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:5000/api/alerts?severity=HIGH&min_confidence=0.8"
```

**3. Test Acknowledgment:**

```bash
# Acknowledge alert
curl -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Investigating"}' \
  http://localhost:5000/api/alerts/ALERT_ID/ack
```

**4. Test False Positive:**

```bash
# Mark as false positive
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Load testing"}' \
  http://localhost:5000/api/alerts/ALERT_ID/false-positive
```

---

## Architecture Notes

### Kafka Consumer Management

- The SSE endpoint uses a shared Kafka consumer pool to avoid creating excessive consumers
- Each user gets a unique consumer group ID to ensure they receive all messages
- Consumers are automatically cleaned up on application shutdown via `atexit` handler
- Heartbeat messages keep connections alive and detect client disconnections

### Database Query Optimization

- Filtered queries use indexed columns (`severity`, `class_name`, `timestamp`, `src_ip`, `dst_ip`)
- Pagination prevents large result sets
- Full-text search uses PostgreSQL pattern matching (can be upgraded to full-text search indexes)

### Audit Events

- Alert actions (ack, false positive, status change) generate audit events
- Currently logged; in production, these are published to a Kafka `audit` topic
- False positive events can be consumed by the adaptive learning pipeline for model improvement

---

## Future Enhancements

1. **WebSocket Support**: Add WebSocket endpoint as alternative to SSE for bidirectional communication
2. **Alert Aggregation**: Group related alerts into incidents automatically
3. **Batch Operations**: Support bulk acknowledgment/resolution of alerts
4. **Alert Subscriptions**: Allow users to subscribe to specific alert types or severities
5. **Kafka Offset Management**: Allow clients to resume from last consumed position
6. **Rate Limiting**: Add per-user rate limits for SSE connections and API queries
7. **Metrics Export**: Expose Prometheus metrics for alert rates and query performance

---

## Troubleshooting

### SSE Connection Drops

- Check Kafka broker connectivity
- Verify JWT token hasn't expired
- Check server logs for consumer errors
- Ensure firewall allows long-lived connections

### Missing Alerts in Stream

- Verify `auto_offset_reset` is set to `latest` (default)
- Check Kafka consumer group lag
- Ensure alerts are being produced to the topic

### Slow Query Performance

- Add database indexes on frequently filtered columns
- Reduce `per_page` size
- Use more specific filters to reduce result set
- Check PostgreSQL query performance with `EXPLAIN ANALYZE`

---

## API Compatibility

This implementation follows RESTful conventions and is compatible with:

- Frontend frameworks: React, Vue, Angular
- API clients: `fetch`, `axios`, `requests`, `httpx`
- SSE libraries: EventSource API (browser), `eventsource` (Node.js), `sseclient` (Python)

All endpoints support both snake_case and camelCase query parameters for frontend convenience.
