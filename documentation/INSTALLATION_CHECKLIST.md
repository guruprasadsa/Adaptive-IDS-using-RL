# Installation and Verification Checklist

## 🎯 Complete This Checklist to Activate All Features

### Phase 1: Backend Setup

#### 1.1 Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

**Verify:**
```bash
pip list | grep -E "Flask-Compress|Flask-Limiter|gunicorn"
```

**Expected output:**
```
Flask-Compress    1.14
Flask-Limiter     3.5.0
gunicorn          21.2.0
```

- [ ] Flask-Compress installed
- [ ] Flask-Limiter installed
- [ ] All dependencies installed without errors

#### 1.2 Configure Backend Environment
```bash
cd backend
copy .env.example .env
```

**Edit `.env` file with:**
```env
SECRET_KEY=<generate-random-32-char-string>
JWT_SECRET=<generate-random-32-char-string>
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
POSTGRES_USER=adaptive_ids
POSTGRES_PASSWORD=adaptive_ids_password
```

- [ ] .env file created
- [ ] SECRET_KEY set (unique random string)
- [ ] JWT_SECRET set (unique random string)
- [ ] Database credentials configured
- [ ] CORS_ORIGINS includes frontend URL

#### 1.3 Test Backend
```bash
cd backend/api
python app.py
```

**In another terminal:**
```bash
curl http://localhost:5000/api/health
```

**Expected response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "connected",
  "timestamp": "2025-...",
  "version": "2.0.0"
}
```

- [ ] Backend starts without errors
- [ ] Health endpoint returns 200
- [ ] Database connection confirmed
- [ ] No import errors in console

---

### Phase 2: Frontend Setup

#### 2.1 Install Node Dependencies
```bash
cd frontend/frontend
npm install
```

**Verify key packages:**
```bash
npm list axios @tanstack/react-query
```

**Expected output:**
```
├── @tanstack/react-query@5.28.0
├── @tanstack/react-query-devtools@5.28.0
└── axios@1.6.7
```

- [ ] axios installed
- [ ] @tanstack/react-query installed
- [ ] @tanstack/react-query-devtools installed
- [ ] No installation errors

#### 2.2 Verify Environment Configuration

Check `frontend/frontend/.env.local`:
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
```

- [ ] .env.local exists
- [ ] VITE_API_BASE_URL points to backend
- [ ] Environment variables match backend URL

#### 2.3 Test Frontend Build
```bash
cd frontend/frontend
npm run type-check
```

- [ ] No TypeScript errors
- [ ] All types resolve correctly
- [ ] vite-env.d.ts recognized

---

### Phase 3: Integration Testing

#### 3.1 Start Both Services

**Terminal 1 (Backend):**
```bash
cd backend/api
python app.py
```

**Terminal 2 (Frontend):**
```bash
cd frontend/frontend
npm run dev
```

- [ ] Backend running on http://localhost:5000
- [ ] Frontend running on http://localhost:5173
- [ ] No CORS errors in browser console

#### 3.2 Test Basic Connectivity

Open browser to: `http://localhost:5173`

**Browser Console Test:**
```javascript
// Test health endpoint
fetch('http://localhost:5000/api/health')
  .then(r => r.json())
  .then(console.log);

// Should log: { status: "ok", model_loaded: true, ... }
```

- [ ] No CORS errors
- [ ] Health check returns data
- [ ] Response includes gzip compression header

#### 3.3 Test Authentication

1. **Navigate to login page**
2. **Enter credentials** (use test account from `create_admin.py`)
3. **Check browser console for API calls**

**Verify in Console:**
```javascript
// Check tokens are stored
localStorage.getItem('adaptive_ids_access_token');
localStorage.getItem('adaptive_ids_refresh_token');
```

- [ ] Login successful
- [ ] Access token stored in localStorage
- [ ] Refresh token stored in localStorage
- [ ] Authorization header in requests
- [ ] No 401 errors

#### 3.4 Test API Endpoints

**In authenticated session:**

1. **Dashboard Page**
   - [ ] Loads without errors
   - [ ] Shows statistics
   - [ ] Recent alerts displayed
   - [ ] Recent incidents displayed

2. **Alerts Page**
   - [ ] List loads with pagination
   - [ ] Filters work
   - [ ] Status update works
   - [ ] Cache headers present

3. **Incidents Page**
   - [ ] List loads with pagination
   - [ ] Filters work
   - [ ] Status update works

**Check Network Tab:**
- [ ] Response times < 500ms
- [ ] Content-Encoding: gzip header present
- [ ] X-Response-Time header present
- [ ] Authorization header in requests

#### 3.5 Test Real-time Features

**Browser Console:**
```javascript
// Test SSE connection
const token = localStorage.getItem('adaptive_ids_access_token');
const es = new EventSource(`http://localhost:5000/api/stream/alerts?token=${token}`);
es.onmessage = (e) => console.log('SSE:', e.data);
```

- [ ] Connection established
- [ ] Heartbeat messages every 30s
- [ ] No disconnection errors

#### 3.6 Test Performance Features

**Caching Test:**
```javascript
// Make same request twice
await fetch('http://localhost:5000/api/dashboard/stats', {
  headers: { 'Authorization': 'Bearer ' + localStorage.getItem('adaptive_ids_access_token') }
}).then(r => r.json());

// Second request should be faster (cached)
await fetch('http://localhost:5000/api/dashboard/stats', {
  headers: { 'Authorization': 'Bearer ' + localStorage.getItem('adaptive_ids_access_token') }
}).then(r => r.json());
```

- [ ] First request normal speed
- [ ] Second request faster (cached)
- [ ] Cache-Control headers present

**Rate Limiting Test:**
```javascript
// Rapid requests (should hit limit)
for (let i = 0; i < 15; i++) {
  fetch('http://localhost:5000/api/predict', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + localStorage.getItem('adaptive_ids_access_token')
    },
    body: JSON.stringify({ features: {} })
  }).then(r => console.log(i, r.status));
}
```

- [ ] First 10 requests succeed (200)
- [ ] Requests 11-15 fail with 429
- [ ] Rate limit error message displayed

---

### Phase 4: Component Integration (Optional)

#### 4.1 Add React Query Provider

**In your main app file:**
```typescript
import { QueryProvider } from './providers/QueryProvider';

function App() {
  return (
    <QueryProvider>
      {/* Your app components */}
    </QueryProvider>
  );
}
```

- [ ] QueryProvider imported
- [ ] App wrapped with QueryProvider
- [ ] React Query DevTools visible (dev mode)

#### 4.2 Add Connection Status Indicator

**In your header component:**
```typescript
import { createConnectionStatus } from './components/ConnectionStatus';

// On mount
const statusIndicator = createConnectionStatus('connection-status-container');
statusIndicator.mount();

// On unmount
statusIndicator.unmount();
```

**Add container to header HTML:**
```html
<div id="connection-status-container"></div>
```

- [ ] Connection status indicator visible
- [ ] Shows "Connected" when healthy
- [ ] Updates on connection changes
- [ ] Click shows detailed info

#### 4.3 Use Custom Hooks

**Example component:**
```typescript
import { useDashboardStats, useAlerts } from './hooks/useApi';

function DashboardPage() {
  const { data: stats, isLoading, error } = useDashboardStats();
  const { data: alerts } = useAlerts(1, 10);
  
  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return <div>{/* Render dashboard */}</div>;
}
```

- [ ] Hooks imported successfully
- [ ] Data loads automatically
- [ ] Loading states work
- [ ] Error states work
- [ ] Caching works (fast re-renders)

---

### Phase 5: Production Readiness

#### 5.1 Security Checklist

- [ ] SECRET_KEY is strong random string (production)
- [ ] JWT_SECRET is strong random string (production)
- [ ] CORS_ORIGINS limited to production domain
- [ ] HTTPS enabled (production)
- [ ] Rate limiting configured
- [ ] Security headers present in responses

#### 5.2 Performance Checklist

- [ ] Gzip compression enabled
- [ ] Response times < 500ms
- [ ] Database indexes created
- [ ] Caching strategy implemented
- [ ] Bundle size optimized

#### 5.3 Monitoring Checklist

- [ ] Backend logging configured
- [ ] Frontend error tracking setup
- [ ] Health check endpoint monitored
- [ ] Rate limit metrics tracked
- [ ] Response time metrics tracked

---

## 📊 Success Metrics

After completing this checklist, you should have:

### Response Times
- Health check: < 50ms
- Dashboard stats: < 200ms
- Alerts/Incidents: < 300ms
- Predictions: < 500ms

### Features Working
- ✅ Authentication flow
- ✅ Token refresh
- ✅ Real-time updates
- ✅ Connection status
- ✅ Error handling
- ✅ Caching
- ✅ Rate limiting
- ✅ Compression

### Zero Errors
- ✅ No CORS errors
- ✅ No 401 errors (with valid token)
- ✅ No TypeScript errors
- ✅ No console errors
- ✅ No import errors

---

## 🔧 Troubleshooting

### Issue: Import Errors in IDE

**Cause:** Packages not installed yet

**Fix:**
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend/frontend
npm install
```

### Issue: CORS Errors

**Fix:**
1. Check `.env` CORS_ORIGINS includes frontend URL
2. Restart backend server
3. Clear browser cache

### Issue: 401 Errors

**Fix:**
1. Check JWT_SECRET matches in .env
2. Verify token in localStorage
3. Try logging in again

### Issue: Real-time Connection Fails

**Fix:**
1. Verify backend running
2. Check token is valid
3. Test SSE endpoint directly

---

## 📚 Documentation References

- **Setup Guide:** `FRONTEND_BACKEND_SETUP.md`
- **API Docs:** `frontend/frontend/API_INTEGRATION.md`
- **Summary:** `IMPLEMENTATION_SUMMARY.md`

---

## ✅ Final Verification

Run this command to verify everything:

```bash
# Backend health
curl http://localhost:5000/api/health

# Frontend build
cd frontend/frontend && npm run type-check
```

**Expected:**
- Backend returns 200 with health data
- Frontend type-check passes with no errors

---

**Status:** Ready for development and testing! 🚀
