# Frontend-Backend Connection Setup Guide

## Quick Start

This guide will help you set up and test the enhanced frontend-backend connection for the Adaptive IDS application.

## Prerequisites

- **Python 3.8+** installed
- **Node.js 18+** and npm installed
- **PostgreSQL** running (see main README)
- **Redis** (optional, for production rate limiting)

## Backend Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

New dependencies added:
- `Flask-Compress` - Response compression
- `Flask-Limiter` - Rate limiting
- `gunicorn` - Production server (optional)
- `redis` - Redis client for rate limiting (optional)

### 2. Configure Environment

Copy the example environment file:

```bash
copy .env.example .env
```

Update `.env` with your settings:

```env
# Required
SECRET_KEY=your-secret-key-here
JWT_SECRET=your-jwt-secret-here

# Database (update if different)
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
POSTGRES_USER=adaptive_ids
POSTGRES_PASSWORD=adaptive_ids_password

# CORS (add your frontend URL)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### 3. Run Backend

**Development:**

```bash
cd backend/api
python app.py
```

The backend will run on `http://localhost:5000`

**Production (with Gunicorn):**

```bash
cd backend/api
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 4. Verify Backend Health

Open browser to: `http://localhost:5000/api/health`

Expected response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "connected",
  "timestamp": "2025-10-20T...",
  "version": "2.0.0"
}
```

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend/frontend
npm install
```

New dependencies added:
- `axios` - HTTP client
- `@tanstack/react-query` - Data fetching and caching

### 2. Configure Environment

The `.env.local` file has been updated with:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:5000
VITE_API_VERSION=v1
VITE_API_TIMEOUT=30000

# WebSocket Configuration
VITE_WS_URL=http://localhost:5000

# Feature Flags
VITE_ENABLE_REALTIME=true
VITE_ENABLE_CACHING=true

# Development
VITE_ENABLE_API_LOGGING=true
```

**For production**, create `.env.production`:

```env
VITE_API_BASE_URL=https://your-api-domain.com
VITE_ENABLE_API_LOGGING=false
```

### 3. Run Frontend

```bash
cd frontend/frontend
npm run dev
```

The frontend will run on `http://localhost:5173`

## Testing the Connection

### 1. Test Basic Connectivity

Open browser console (F12) and run:

```javascript
// Check health
fetch('http://localhost:5000/api/health')
  .then(r => r.json())
  .then(console.log);
```

### 2. Test CORS

The frontend should be able to make requests without CORS errors. If you see CORS errors:

1. Check backend `.env` - ensure `CORS_ORIGINS` includes your frontend URL
2. Restart the backend server
3. Clear browser cache

### 3. Test Authentication

1. Open the frontend: `http://localhost:5173`
2. Navigate to login page
3. Use test credentials (created with `backend/scripts/create_admin.py`)
4. Check browser console for API calls
5. Verify JWT token in localStorage:

```javascript
// In browser console
localStorage.getItem('adaptive_ids_access_token')
```

### 4. Test Real-time Updates

Open browser console:

```javascript
// Check connection status
const es = new EventSource('http://localhost:5000/api/stream/alerts?token=YOUR_TOKEN');
es.onmessage = (e) => console.log('SSE:', e.data);
```

You should see heartbeat messages every 30 seconds.

### 5. Test API Calls

In the frontend application:

1. **Dashboard** - Should load statistics without errors
2. **Alerts Page** - Should display paginated alerts
3. **Incidents Page** - Should display paginated incidents
4. **Update Status** - Click to update an alert/incident status

Check browser Network tab (F12) for:
- ✓ Status 200 responses
- ✓ Authorization headers present
- ✓ Gzip compression (in Response Headers: `Content-Encoding: gzip`)
- ✓ Response times < 500ms

## Performance Verification

### 1. Check Response Compression

In Network tab, check response headers:

```
Content-Encoding: gzip
X-Response-Time: 45.23ms
```

### 2. Verify Caching

Make the same request twice. Second request should:
- Be faster (cache hit)
- Show "[Cache Hit]" in console (if logging enabled)

### 3. Test Rate Limiting

Make rapid requests to `/api/predict`:

```javascript
// Should hit rate limit after 10 requests in 1 minute
for (let i = 0; i < 15; i++) {
  fetch('http://localhost:5000/api/predict', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer YOUR_TOKEN'
    },
    body: JSON.stringify({ features: {} })
  }).then(r => console.log(i, r.status));
}
```

After 10 requests, you should see `429 Too Many Requests`.

## Monitoring

### Backend Logs

Watch backend logs for:

```
INFO:root:Request: GET /api/health from 127.0.0.1
INFO:root:Response: GET /api/health Status: 200 Duration: 12.34ms
```

### Frontend Console

With `VITE_ENABLE_API_LOGGING=true`, you'll see:

```
[API Request] GET /api/alerts {page: 1, per_page: 10}
[API Response] GET /api/alerts - 200 (156ms) {...}
```

## Common Issues

### Issue: CORS Errors

**Solution:**
1. Check `CORS_ORIGINS` in backend `.env`
2. Ensure no trailing slashes in URLs
3. Restart backend server

### Issue: 401 Unauthorized

**Solution:**
1. Check if token exists: `localStorage.getItem('adaptive_ids_access_token')`
2. Try logging in again
3. Check JWT_SECRET matches between backend instances

### Issue: Real-time Connection Fails

**Solution:**
1. Verify backend is running
2. Check browser console for errors
3. Test SSE endpoint directly in browser
4. Ensure firewall allows connections

### Issue: Slow API Responses

**Solution:**
1. Check database connection
2. Add indexes to database (see `schema.sql`)
3. Enable caching with Redis for rate limiting
4. Monitor with `X-Response-Time` header

## Database Indexes

Ensure these indexes exist for optimal performance:

```sql
-- Already in schema.sql
CREATE INDEX IF NOT EXISTS alerts_timestamp_idx ON alerts (timestamp DESC);
CREATE INDEX IF NOT EXISTS incidents_updated_idx ON incidents (last_updated_at DESC);
CREATE INDEX IF NOT EXISTS alerts_priority_idx ON alerts (priority);
CREATE INDEX IF NOT EXISTS alerts_status_idx ON alerts (status);
```

Verify indexes:

```sql
\d alerts
\d incidents
```

## Production Deployment

### Backend

1. **Use Gunicorn:**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 app:app
   ```

2. **Set up Redis for rate limiting:**
   ```env
   RATE_LIMIT_STORAGE_URL=redis://localhost:6379
   ```

3. **Enable production settings:**
   ```env
   FLASK_ENV=production
   FLASK_DEBUG=False
   ```

### Frontend

1. **Build for production:**
   ```bash
   npm run build
   ```

2. **Serve with nginx/apache** or deploy to Vercel/Netlify

3. **Update environment:**
   - Create `.env.production` with production API URL
   - Disable debug logging

## Performance Benchmarks

Expected performance metrics:

| Endpoint | Response Time | Cached |
|----------|--------------|--------|
| `/api/health` | < 50ms | 10s TTL |
| `/api/dashboard/stats` | < 200ms | 30s TTL |
| `/api/alerts` | < 300ms | 10s TTL |
| `/api/incidents` | < 300ms | 10s TTL |
| `/api/predict` | < 500ms | No cache |

## Next Steps

1. ✅ Install dependencies (backend & frontend)
2. ✅ Configure environment variables
3. ✅ Start backend server
4. ✅ Start frontend development server
5. ✅ Test basic connectivity
6. ✅ Test authentication flow
7. ✅ Verify real-time updates
8. ✅ Monitor performance
9. 📝 Read [API_INTEGRATION.md](./API_INTEGRATION.md) for detailed API docs
10. 🚀 Start building features!

## Getting Help

- Check browser console for errors
- Check backend logs for request/response details
- Review [API_INTEGRATION.md](./API_INTEGRATION.md) for API documentation
- Verify environment configuration matches between frontend and backend

---

**Note:** The connection status indicator will automatically show in the header once the `ConnectionStatus` component is integrated into your header component.
