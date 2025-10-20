# 🚀 Quick Reference Card - Frontend-Backend Integration

## Essential Commands

### Start Services
```bash
# Backend
cd backend/api && python app.py

# Frontend  
cd frontend/frontend && npm run dev
```

### Install Dependencies
```bash
# Backend
cd backend && pip install -r requirements.txt

# Frontend
cd frontend/frontend && npm install
```

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `backend/.env` | Backend configuration |
| `frontend/frontend/.env.local` | Frontend configuration |
| `backend/api/app.py` | Main Flask application |
| `frontend/frontend/utils/apiClient.ts` | API client |
| `frontend/frontend/hooks/useApi.ts` | React Query hooks |
| `frontend/frontend/api.ts` | API service layer |

---

## 🌐 API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/health` | GET | No | Health check |
| `/api/auth/login` | POST | No | Login |
| `/api/auth/me` | GET | Yes | Current user |
| `/api/dashboard/stats` | GET | Yes | Dashboard data |
| `/api/alerts` | GET | Yes | List alerts |
| `/api/incidents` | GET | Yes | List incidents |
| `/api/predict` | POST | Yes | Make prediction |
| `/api/stream/alerts` | GET (SSE) | Yes | Real-time alerts |

---

## 🔧 Environment Variables

### Backend (`.env`)
```env
SECRET_KEY=<random-string>
JWT_SECRET=<random-string>
CORS_ORIGINS=http://localhost:5173
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
```

### Frontend (`.env.local`)
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
```

---

## 📦 React Query Hooks

```typescript
// Data fetching
const { data, isLoading } = useDashboardStats();
const { data } = useAlerts(page, perPage, filters);
const { data } = useIncidents(page, perPage, filters);
const { data } = useCurrentUser();

// Mutations
const login = useLogin();
const logout = useLogout();
const updateAlert = useUpdateAlertStatus();
const updateIncident = useUpdateIncidentStatus();
const predict = usePredict();
```

---

## 🔐 Authentication

```typescript
// Login
const login = useLogin({
  onSuccess: (data) => {
    // Tokens stored automatically
    console.log('Logged in:', data.user);
  }
});
login.mutate({ emailOrUsername: 'admin', password: 'pass' });

// Check auth status
const isAuth = tokenManager.isAuthenticated();

// Logout
const logout = useLogout();
logout.mutate();
```

---

## 🌊 Real-time Updates

```typescript
import { useRealtimeClient } from './utils/realtimeClient';

const realtime = useRealtimeClient();

// Connect
realtime.connect();

// Listen for events
realtime.onEvent((message) => {
  if (message.type === 'alert') {
    // Handle new alert
  }
});

// Connection status
realtime.onStatusChange((status) => {
  console.log('Status:', status); // connected/disconnected/reconnecting/error
});

// Disconnect
realtime.disconnect();
```

---

## 🎯 Common Patterns

### Fetch Data with Loading State
```typescript
const { data, isLoading, error } = useAlerts(1, 10);

if (isLoading) return <Spinner />;
if (error) return <Error message={error.message} />;
return <AlertsList alerts={data.alerts} />;
```

### Update Data with Optimistic UI
```typescript
const updateAlert = useUpdateAlertStatus({
  onSuccess: () => {
    // Cache automatically invalidated
    showToast('Alert updated!');
  }
});

// Trigger update
updateAlert.mutate({ id: '123', status: 'resolved' });
```

### Pagination
```typescript
const [page, setPage] = useState(1);
const { data } = useAlerts(page, 10);

// data.total_pages available
// Previous data shown while fetching new page
```

### Search with Debounce
```typescript
import { debounce } from './utils/apiClient';

const debouncedSearch = debounce((query) => {
  setFilters({ ...filters, search: query });
}, 300);

<input onChange={(e) => debouncedSearch(e.target.value)} />
```

---

## 🐛 Debugging

### Check Backend Logs
```python
# In app.py - already enabled
logging.info(f"Request: {request.method} {request.path}")
```

### Check Frontend Console
```typescript
// Enable in .env.local
VITE_ENABLE_API_LOGGING=true

// See:
// [API Request] GET /api/alerts
// [API Response] GET /api/alerts - 200 (156ms)
```

### Check Tokens
```javascript
// Browser console
localStorage.getItem('adaptive_ids_access_token')
localStorage.getItem('adaptive_ids_refresh_token')
```

### Check Network
```javascript
// Browser DevTools > Network tab
// Look for:
// - Authorization header
// - Response time (X-Response-Time)
// - Compression (Content-Encoding: gzip)
// - Status codes (200, 401, 429, etc.)
```

---

## ⚡ Performance Tips

### Frontend
- Use React Query hooks (automatic caching)
- Prefetch data before navigation
- Use pagination for large lists
- Debounce search inputs

### Backend
- Already has gzip compression ✅
- Already has rate limiting ✅
- Add database indexes (check schema.sql)
- Use Redis for sessions (production)

---

## 🔥 Quick Fixes

### CORS Error
```bash
# Backend .env
CORS_ORIGINS=http://localhost:5173
# Restart backend
```

### 401 Unauthorized
```javascript
// Re-login or check token
localStorage.clear();
// Login again
```

### Import Errors
```bash
# Install missing packages
pip install -r requirements.txt  # Backend
npm install                      # Frontend
```

### Slow Responses
```sql
-- Check indexes exist
\d alerts
\d incidents
-- Should see indexes on timestamp, status, priority
```

---

## 📈 Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| Health check | < 50ms | Check X-Response-Time |
| Dashboard | < 200ms | Check Network tab |
| Alerts list | < 300ms | Check Network tab |
| Predictions | < 500ms | Check Network tab |
| SSE latency | < 100ms | Check connection |

---

## 🧪 Test Endpoints

```bash
# Health
curl http://localhost:5000/api/health

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email_or_username":"admin","password":"pass"}'

# Authenticated request
curl http://localhost:5000/api/dashboard/stats \
  -H "Authorization: Bearer YOUR_TOKEN"

# SSE stream
curl http://localhost:5000/api/stream/alerts?token=YOUR_TOKEN
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `INSTALLATION_CHECKLIST.md` | Step-by-step setup |
| `FRONTEND_BACKEND_SETUP.md` | Quick start guide |
| `API_INTEGRATION.md` | Complete API docs |
| `IMPLEMENTATION_SUMMARY.md` | What was built |

---

## ✅ Health Check Indicators

### All Good ✅
- Backend: `status: "ok"`, `database: "connected"`
- Frontend: No console errors, requests succeed
- Connection: Status shows "Connected"
- Performance: Response times < targets

### Issues ⚠️
- 401 errors → Re-login
- CORS errors → Check CORS_ORIGINS
- Slow responses → Check database/indexes
- Connection errors → Check backend running

---

## 🎓 Best Practices

1. **Always use hooks** - Don't call apiService directly
2. **Handle loading states** - Show spinners/skeletons
3. **Handle errors gracefully** - Show user-friendly messages
4. **Use TypeScript** - Catch errors at compile time
5. **Monitor performance** - Use X-Response-Time header
6. **Test thoroughly** - Use checklist before deployment
7. **Keep tokens secure** - Never log tokens
8. **Use environment variables** - Never hardcode URLs

---

**Need help?** Check the full documentation in `FRONTEND_BACKEND_SETUP.md` and `API_INTEGRATION.md`
