# Testing the SSE Endpoint - Step by Step

## The Problem

You cannot use the `SECRET_KEY` or `JWT_SECRET` directly as a token. These are used to *sign* JWT tokens, not as tokens themselves. You need to:

1. Create a user account
2. Login to get a JWT access token
3. Use that token to access the SSE endpoint

---

## Quick Test (3 steps)

### Step 1: Make sure backend is running

```bash
# Start the backend
cd C:\AIML\Projects\adaptive-ids-v-2.0
python backend/api/app.py
```

In another terminal:

```bash
# Test health endpoint
curl http://localhost:5000/api/health
```

You should see:
```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "connected",
  ...
}
```

---

### Step 2: Get a JWT token

**Option A: Use the test script (recommended)**

```bash
cd C:\AIML\Projects\adaptive-ids-v-2.0
python test_sse_endpoint.py
```

This will:
- Create a test user
- Login and get a token
- Test the SSE endpoint automatically

**Option B: Manual login with curl**

First, create an admin user:

```bash
cd backend
python scripts/create_admin.py
```

When prompted, enter:
- Username: `admin`
- Email: `admin@adaptiveids.local`
- Password: `Admin123!`

Then login:

```bash
curl -X POST http://localhost:5000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email_or_username\":\"admin\",\"password\":\"Admin123!\"}"
```

You'll get a response like:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "...",
  "user": {...}
}
```

Copy the `access_token` value.

---

### Step 3: Test the SSE endpoint

**Windows CMD:**

```bash
set TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
curl -N "http://localhost:5000/api/events?token=%TOKEN%"
```

**PowerShell:**

```powershell
$TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
curl -N "http://localhost:5000/api/events?token=$TOKEN"
```

**Linux/Git Bash:**

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
curl -N "http://localhost:5000/api/events?token=$TOKEN"
```

You should see:
```
event: connected
data: {"timestamp": "2025-10-24T...", "user_id": 1, "topic": "alerts"}

event: heartbeat
data: {"timestamp": 1729764000000}

...
```

Press `Ctrl+C` to stop.

---

## Testing Other Endpoints

Once you have a token:

### Query alerts with filters

```bash
curl -H "Authorization: Bearer %TOKEN%" ^
  "http://localhost:5000/api/alerts?severity=HIGH&min_confidence=0.8"
```

### Get alert details

```bash
curl -H "Authorization: Bearer %TOKEN%" ^
  http://localhost:5000/api/alerts/ALERT_ID
```

### Acknowledge an alert

```bash
curl -X PATCH ^
  -H "Authorization: Bearer %TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"notes\":\"Investigating this alert\"}" ^
  http://localhost:5000/api/alerts/ALERT_ID/ack
```

### Mark as false positive

```bash
curl -X POST ^
  -H "Authorization: Bearer %TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"notes\":\"Load testing traffic\"}" ^
  http://localhost:5000/api/alerts/ALERT_ID/false-positive
```

---

## JavaScript Example (Browser/Node.js)

```javascript
// 1. Login
const loginResponse = await fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email_or_username: 'admin',
    password: 'Admin123!'
  })
});

const { access_token } = await loginResponse.json();

// 2. Subscribe to SSE stream
const eventSource = new EventSource(
  `http://localhost:5000/api/events?token=${access_token}`
);

eventSource.addEventListener('connected', (e) => {
  console.log('Connected:', JSON.parse(e.data));
});

eventSource.addEventListener('alert', (e) => {
  const alert = JSON.parse(e.data);
  console.log('New alert:', alert.severity, alert.className);
});

eventSource.addEventListener('heartbeat', (e) => {
  console.log('💓 Heartbeat');
});

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
};

// 3. Query alerts
const alertsResponse = await fetch(
  'http://localhost:5000/api/alerts?severity=HIGH&page=1&per_page=10',
  {
    headers: {
      'Authorization': `Bearer ${access_token}`
    }
  }
);

const alertsData = await alertsResponse.json();
console.log(`Found ${alertsData.total} high-severity alerts`);

// 4. Acknowledge alert
if (alertsData.alerts.length > 0) {
  const alertId = alertsData.alerts[0].id;
  
  await fetch(`http://localhost:5000/api/alerts/${alertId}/ack`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      notes: 'Investigating DDoS attack from 192.168.1.100'
    })
  });
}
```

---

## Python Example

```python
import requests

# 1. Login
response = requests.post(
    'http://localhost:5000/api/auth/login',
    json={'email_or_username': 'admin', 'password': 'Admin123!'}
)
token = response.json()['access_token']

headers = {'Authorization': f'Bearer {token}'}

# 2. Query alerts
response = requests.get(
    'http://localhost:5000/api/alerts',
    headers=headers,
    params={
        'severity': 'HIGH',
        'min_confidence': 0.8,
        'page': 1,
        'per_page': 20
    }
)
alerts = response.json()
print(f"Found {alerts['total']} alerts")

# 3. Acknowledge alert
if alerts['alerts']:
    alert_id = alerts['alerts'][0]['id']
    response = requests.patch(
        f'http://localhost:5000/api/alerts/{alert_id}/ack',
        headers=headers,
        json={'notes': 'Investigating...'}
    )
    print(response.json())

# 4. Stream events (SSE)
import sseclient  # pip install sseclient-py

response = requests.get(
    'http://localhost:5000/api/events',
    params={'token': token},
    headers={'Accept': 'text/event-stream'},
    stream=True
)

client = sseclient.SSEClient(response)
for event in client.events():
    print(f"Event: {event.event}")
    print(f"Data: {event.data}")
```

---

## Troubleshooting

### Error: "Unauthorized - Valid token required"

**Cause:** Invalid or missing JWT token

**Solution:** 
- Make sure you're using the `access_token` from the login response, not the SECRET_KEY
- Check that the token hasn't expired (tokens expire after 25 hours by default)
- Login again to get a fresh token

### Error: "Cannot connect to backend"

**Cause:** Backend not running

**Solution:**
```bash
cd backend
python api/app.py
```

### Error: Database connection failed

**Cause:** PostgreSQL not running or wrong credentials

**Solution:**
```bash
# Check if Docker is running
docker compose ps

# Start services
docker compose up -d

# Check .env has correct database settings
```

### No events received from SSE

**Cause:** No alerts being produced to Kafka

**Solution:**
- The SSE endpoint connects successfully but waits for events
- You'll see heartbeat messages every 30 seconds
- To generate test alerts, you need to:
  1. Run the packet producer
  2. Run the feature extractor
  3. Run the model inference service
  4. Run the alert processor

Or test with the fallback mode (no Kafka needed):
```bash
# The endpoint works even without Kafka, sending heartbeats only
```

---

## Next Steps

1. ✅ Use the test script: `python test_sse_endpoint.py`
2. ✅ Integrate the SSE endpoint in your frontend
3. ✅ See `backend/api/EVENTS_API_README.md` for full documentation
4. ✅ See `backend/api/EVENTS_API_QUICKREF.md` for quick reference
