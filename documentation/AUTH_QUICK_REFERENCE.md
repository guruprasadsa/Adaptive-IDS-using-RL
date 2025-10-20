# Authentication Flow - Quick Reference Guide

## 🚀 Quick Start Commands

### Start All Services
```cmd
# Terminal 1 - Database
docker-compose up -d postgres

# Terminal 2 - Backend
cd backend\api
python app.py

# Terminal 3 - Frontend
cd frontend\frontend
npm run dev
```

### Access Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000
- **Database**: localhost:55432

### Default Credentials
- **Email**: admin@adaptive-ids.local
- **Username**: admin
- **Password**: AdminPass123

## 📋 Common Tasks

### Create New User
```cmd
cd backend
python scripts\create_admin.py
```

### Reset Database
```cmd
cd backend
python scripts\migrate.py --reset
```

### View Backend Logs
Backend logs appear in the terminal where you ran `python app.py`

### Build for Production
```cmd
# Frontend
cd frontend\frontend
npm run build

# Backend (use gunicorn)
cd backend
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

## 🔑 Authentication Flow Diagram

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │ 1. Enter credentials
       ▼
┌─────────────────┐
│  Login Page     │
└──────┬──────────┘
       │ 2. POST /api/auth/login
       ▼
┌─────────────────┐
│  Backend API    │◄──── Validate credentials
│  (auth.py)      │      Hash password
└──────┬──────────┘      Check database
       │ 3. Return tokens
       │ { access_token, refresh_token, user }
       ▼
┌─────────────────┐
│  Frontend       │◄──── Store tokens
│  (authService)  │      Update state
└──────┬──────────┘      Trigger re-render
       │ 4. Redirect to dashboard
       ▼
┌─────────────────┐
│  Dashboard      │◄──── Load data
│                 │      Connect realtime
└─────────────────┘      Show UI

       │ 5. On subsequent requests
       ▼
┌─────────────────┐
│  API Request    │◄──── Add Authorization header
│                 │      Bearer {access_token}
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Backend API    │◄──── Validate token
│  (middleware)   │      Check expiration
└──────┬──────────┘      Verify signature
       │
       ├──► Valid? Return data
       │
       └──► Expired? 401 Unauthorized
              │
              ▼
       ┌─────────────────┐
       │  Frontend       │◄──── Intercept 401
       │  (apiClient)    │      POST /api/auth/refresh
       └──────┬──────────┘      Get new access_token
              │                 Retry original request
              ▼
       Success! Continue
```

## 🎯 Key Endpoints

### Authentication
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | /api/auth/register | Register new user | No |
| POST | /api/auth/login | Login and get tokens | No |
| POST | /api/auth/logout | Logout and revoke token | Yes |
| GET | /api/auth/me | Get current user | Yes |
| POST | /api/auth/refresh | Refresh access token | No* |

*Requires valid refresh token in body

### Dashboard & Data
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | /api/health | Health check | No |
| GET | /api/dashboard/stats | Dashboard statistics | Yes |
| GET | /api/alerts | List alerts | Yes |
| GET | /api/incidents | List incidents | Yes |
| GET | /api/model/metrics | Model performance | No |
| POST | /api/predict | Get prediction | No** |

**Rate limited to 10/minute

### Real-time
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | /api/stream/alerts | SSE stream | Yes |

## 🔧 Environment Variables

### Backend (.env)
```env
# Required
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
POSTGRES_USER=adaptive_ids
POSTGRES_PASSWORD=adaptive_ids_password
JWT_SECRET=your-jwt-secret
SECRET_KEY=your-flask-secret

# Optional
ACCESS_TOKEN_TTL=900          # 15 minutes
REFRESH_TOKEN_TTL=604800      # 7 days
CORS_ORIGINS=http://localhost:5173
RATE_LIMIT_ENABLED=True
COMPRESS_ENABLED=True
```

### Frontend (.env)
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_VERSION=v1
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
VITE_DEV_MODE=true
```

## 🎨 Component Structure

### Frontend Pages
- **LoginPage** - Authentication interface
- **Dashboard** - Main overview page
- **AlertsPage** - Alerts management
- **IncidentsPage** - Incidents management
- **RLModelPage** - Model metrics & predictions

### Frontend Services
- **authService** - Handles authentication state
- **apiService** - API client with auth headers
- **realtimeClient** - SSE connection manager

### Backend Modules
- **app.py** - Main Flask application
- **auth.py** - Authentication blueprint
- **middleware.py** - Request/response middleware

## 🐛 Troubleshooting Quick Fixes

### Problem: Login fails with "Connection refused"
**Solution**: Ensure backend is running on port 5000
```cmd
curl http://localhost:5000/api/health
```

### Problem: CORS errors in browser console
**Solution**: Check CORS_ORIGINS in backend .env includes frontend URL

### Problem: "Unauthorized" on every request
**Solution**: 
1. Check if tokens are stored: Open DevTools → Application → Local Storage
2. Try logging out and logging in again
3. Check backend logs for JWT validation errors

### Problem: SSE connection keeps reconnecting
**Solution**: 
1. Ensure access token is valid
2. Check backend SSE endpoint is running
3. Verify no firewalls blocking EventSource

### Problem: Database connection error
**Solution**:
```cmd
# Check if PostgreSQL is running
docker ps | findstr postgres

# Restart database
docker-compose restart postgres
```

### Problem: "Module not found" errors in frontend
**Solution**:
```cmd
cd frontend\frontend
rm -rf node_modules package-lock.json
npm install
```

## 📱 Browser Support

### Tested Browsers
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Edge 90+
- ✅ Safari 14+

### Known Issues
- ⚠️ IE 11: Not supported (SSE not available)
- ⚠️ Safari < 14: Some CSS features may not work

## 🔐 Security Checklist

### Development
- [x] JWT tokens stored securely
- [x] HTTPS for production (pending)
- [x] CORS configured
- [x] Rate limiting enabled
- [x] Password hashing (bcrypt)
- [x] SQL injection prevention
- [x] XSS protection (input validation)

### Production (TODO)
- [ ] Change default secrets
- [ ] Enable HTTPS
- [ ] Use httpOnly cookies
- [ ] Add CSRF tokens
- [ ] Enable security headers
- [ ] Set up monitoring
- [ ] Configure firewall rules

## 📊 Performance Tips

### Frontend
- API responses cached (30s-5min)
- Pagination reduces data load
- Debounced search (300ms)
- Lazy component loading

### Backend
- Database indexes on key columns
- Connection pooling
- Response compression (gzip)
- Rate limiting prevents abuse

## 🧪 Testing Scenarios

### Happy Path
1. ✅ Login with valid credentials
2. ✅ View dashboard data
3. ✅ Navigate between pages
4. ✅ Get RL model prediction
5. ✅ Receive real-time updates
6. ✅ Logout successfully

### Error Scenarios
1. ✅ Invalid login credentials
2. ✅ Token expiration handling
3. ✅ Network error recovery
4. ✅ Backend unavailable fallback
5. ✅ Database connection loss
6. ✅ SSE reconnection

## 📞 Need Help?

1. **Check Documentation**: `documentation/AUTH_SETUP_GUIDE.md`
2. **View Logs**: Check terminal output for errors
3. **Browser Console**: Press F12 to see frontend errors
4. **Health Check**: Visit http://localhost:5000/api/health
5. **Database**: Use `psql` to inspect data

## 📦 Project Structure
```
adaptive-ids-v-2.0/
├── backend/
│   ├── api/
│   │   ├── app.py              # Main app
│   │   ├── auth.py             # Auth endpoints
│   │   └── middleware.py       # Middleware
│   ├── db/
│   │   └── schema.sql          # Database schema
│   └── scripts/
│       ├── migrate.py          # DB migrations
│       └── create_admin.py     # User creation
├── frontend/frontend/
│   ├── pages/
│   │   ├── LoginPage.ts        # ✨ NEW
│   │   ├── Dashboard.ts
│   │   ├── AlertsPage.ts
│   │   ├── IncidentsPage.ts
│   │   └── RLModelPage.ts      # ✨ NEW
│   ├── services/
│   │   └── authService.ts      # ✨ NEW
│   ├── utils/
│   │   ├── apiClient.ts        # Enhanced
│   │   └── realtimeClient.ts   # Enhanced
│   ├── components/
│   │   ├── Header.ts           # Updated
│   │   └── ConnectionStatus.ts
│   ├── index.tsx               # Updated
│   ├── index.css               # Updated
│   └── .env                    # ✨ NEW
└── documentation/
    ├── AUTH_SETUP_GUIDE.md              # ✨ NEW
    └── AUTH_IMPLEMENTATION_SUMMARY.md   # ✨ NEW
```

---

**Quick Reference Version**: 1.0  
**Last Updated**: October 20, 2025  
**For Full Details**: See AUTH_SETUP_GUIDE.md
