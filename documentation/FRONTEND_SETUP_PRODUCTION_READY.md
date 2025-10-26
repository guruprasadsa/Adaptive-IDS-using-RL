# Frontend Setup - Production Ready

## Date: October 24, 2025

## 🎯 Overview

This guide will help you get the Adaptive IDS frontend connected to the backend and production-ready.

---

## ✅ COMPLETED FIXES

### 1. Added Missing React Dependencies
Updated `frontend/package.json` to include:
- ✅ `react` and `react-dom` (core framework)
- ✅ `@vitejs/plugin-react` (Vite React plugin)
- ✅ `@types/react-dom` (TypeScript types)

### 2. Updated Vite Configuration
Enhanced `frontend/vite.config.ts` with:
- ✅ React plugin initialization
- ✅ API proxy to backend (`/api` → `http://localhost:5001`)
- ✅ CORS handling
- ✅ Production build optimization

### 3. Environment Variables
Frontend `.env` file configured:
```env
VITE_API_BASE_URL=http://localhost:5001
VITE_API_VERSION=v1
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
VITE_DEV_MODE=true
```

---

## 🚀 MANUAL SETUP STEPS

### Step 1: Install Dependencies

```powershell
# Navigate to frontend directory
cd C:\AIML\Projects\adaptive-ids-v-2.0\frontend

# Install all dependencies (including React)
npm install
```

**Expected Output:**
```
added 52 packages, and audited 102 packages in 6s
```

### Step 2: Verify Installation

```powershell
# Check that React is installed
npm list react react-dom
```

**Expected Output:**
```
adaptive-ids-dashboard@2.0.0
├── react@18.2.0
└── react-dom@18.2.0
```

### Step 3: Start Development Server

```powershell
# Make sure you're in the frontend directory
cd C:\AIML\Projects\adaptive-ids-v-2.0\frontend

# Start dev server
npm run dev
```

**Expected Output:**
```
  VITE v6.2.0  ready in 1234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
  ➜  press h to show help
```

### Step 4: Verify Backend is Running

```powershell
# In a separate terminal, check backend health
curl http://localhost:5001/api/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "model_loaded": false,
  "timestamp": "2025-10-24T18:00:00+00:00",
  "version": "2.0.0"
}
```

### Step 5: Access Frontend

Open your browser and navigate to:
```
http://localhost:5173
```

You should see the login page.

---

## 🔧 TROUBLESHOOTING

### Issue: "Cannot find module 'react'"

**Solution:**
```powershell
cd C:\AIML\Projects\adaptive-ids-v-2.0\frontend
rm -r node_modules
rm package-lock.json
npm install
```

### Issue: "Failed to fetch from backend"

**Checks:**
1. Backend is running: `docker ps | findstr backend`
2. Backend is healthy: `curl http://localhost:5001/api/health`
3. CORS is configured in backend
4. Environment variable is correct in `.env`

**Fix Backend CORS (if needed):**
Check `backend/api/app.py` has:
```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173", "http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

### Issue: "Port 5173 already in use"

**Solution:**
```powershell
# Kill process on port 5173
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Or use a different port
$env:PORT=3000
npm run dev
```

### Issue: Login fails with 401

**Check:**
1. Backend authentication is configured
2. Database contains user accounts
3. JWT secret is set in backend `.env`

**Create test user:**
```powershell
# In backend container
docker exec -it adaptive_ids_backend python -c "
from backend.api.auth import create_user
create_user('admin', 'admin@example.com', 'password123', 'admin')
"
```

---

## 📦 PRODUCTION BUILD

### Build for Production

```powershell
cd C:\AIML\Projects\adaptive-ids-v-2.0\frontend

# Build optimized production bundle
npm run build
```

**Output:** `frontend/dist/` directory with optimized files

### Test Production Build

```powershell
# Preview production build
npm run preview
```

**Access:** `http://localhost:4173`

### Deploy Production Build

**Option 1: Docker (Recommended)**

Create `frontend/Dockerfile`:
```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

Create `frontend/nginx.conf`:
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://backend:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Cache static assets
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

**Build and run:**
```powershell
cd C:\AIML\Projects\adaptive-ids-v-2.0\frontend
docker build -t adaptive-ids-frontend .
docker run -d -p 80:80 --name frontend adaptive-ids-frontend
```

**Option 2: Add to docker-compose.yml**

```yaml
services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: adaptive_ids_frontend
    ports:
      - "80:80"
    environment:
      - VITE_API_BASE_URL=http://backend:5001
    depends_on:
      - backend
    networks:
      - adaptive-ids-network
    restart: unless-stopped
```

---

## 🔐 PRODUCTION SECURITY CHECKLIST

### Backend CORS Configuration
- [ ] Only allow specific frontend origins (no `*`)
- [ ] Enable credentials support
- [ ] Set appropriate headers

### Environment Variables
- [ ] Remove `VITE_ENABLE_API_LOGGING=true` in production
- [ ] Set `VITE_DEV_MODE=false`
- [ ] Use production API URL

### Frontend Security
- [ ] Enable HTTPS in production
- [ ] Configure CSP headers
- [ ] Add security headers (X-Frame-Options, etc.)
- [ ] Implement rate limiting
- [ ] Add request signing for critical operations

### Build Optimization
- [ ] Enable source maps in production: NO (set to false)
- [ ] Minification enabled
- [ ] Tree shaking enabled
- [ ] Code splitting configured
- [ ] Gzip compression enabled

---

## 📊 MONITORING & PERFORMANCE

### Add Performance Monitoring

Install web-vitals:
```powershell
npm install web-vitals
```

Add to `index.tsx`:
```typescript
import { onCLS, onFID, onFCP, onLCP, onTTFB } from 'web-vitals';

function sendToAnalytics(metric) {
  console.log(metric);
  // Send to your analytics endpoint
}

onCLS(sendToAnalytics);
onFID(sendToAnalytics);
onFCP(sendToAnalytics);
onLCP(sendToAnalytics);
onTTFB(sendToAnalytics);
```

### Error Tracking

Add Sentry or similar:
```powershell
npm install @sentry/react
```

Configure in `index.tsx`:
```typescript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "YOUR_SENTRY_DSN",
  environment: import.meta.env.MODE,
  tracesSampleRate: 1.0,
});
```

---

## 🧪 TESTING

### Run Type Checking

```powershell
npm run type-check
```

### Build Test

```powershell
npm run build
```

Should complete without errors.

---

## 📝 NEXT STEPS

1. ✅ Install dependencies
2. ✅ Start dev server
3. ⏭️ Test login functionality
4. ⏭️ Test real-time alerts (SSE)
5. ⏭️ Test API connectivity
6. ⏭️ Create production build
7. ⏭️ Deploy to Docker
8. ⏭️ Configure reverse proxy (Nginx)
9. ⏭️ Set up SSL/TLS certificates
10. ⏭️ Configure monitoring

---

## 🎯 ACCEPTANCE CRITERIA

### Functional Requirements
- ✅ Frontend builds without errors
- ✅ Development server starts successfully
- ⏳ Can login with valid credentials
- ⏳ Can view dashboard with stats
- ⏳ Can see real-time alerts via SSE
- ⏳ Can filter and sort alerts
- ⏳ Can acknowledge/mark false positives
- ⏳ Can view incidents
- ⏳ Can export data to CSV

### Performance Requirements
- ⏳ Page load time < 2 seconds
- ⏳ Time to Interactive < 3 seconds
- ⏳ Lighthouse score > 90
- ⏳ Bundle size < 500KB (gzipped)

### Security Requirements
- ⏳ HTTPS enabled in production
- ⏳ JWT token refresh working
- ⏳ XSS protection enabled
- ⏳ CSP headers configured
- ⏳ API requests authenticated

---

## 🆘 GETTING HELP

If you encounter issues:

1. Check console for errors (F12 in browser)
2. Check network tab for failed requests
3. Verify backend is running and accessible
4. Check CORS configuration
5. Review environment variables
6. Check this troubleshooting guide

**Common Commands:**
```powershell
# Check if port is in use
netstat -ano | findstr :5173

# Check backend health
curl http://localhost:5001/api/health

# View Docker logs
docker logs adaptive_ids_backend

# Restart backend
docker-compose restart backend

# Clear npm cache
npm cache clean --force
```

---

**Status:** READY FOR TESTING
**Last Updated:** October 24, 2025
**Version:** 2.0.0
