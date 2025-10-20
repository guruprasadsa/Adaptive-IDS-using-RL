# Authentication Flow & Frontend Integration - Setup Guide

## Overview
This document provides comprehensive instructions for running the Adaptive IDS system with complete authentication flow and frontend-backend integration.

## Prerequisites
- **Python 3.8+** (for backend)
- **Node.js 16+** and **npm** (for frontend)
- **PostgreSQL 12+** (for database)
- **Git** (for version control)

## Quick Start

### 1. Database Setup

#### Start PostgreSQL
```cmd
# Using Docker (recommended)
docker-compose up -d postgres

# OR start your local PostgreSQL service
# Ensure PostgreSQL is running on port 55432 (or update .env)
```

#### Initialize Database
```cmd
cd backend
python scripts\migrate.py
```

#### Create Admin User
```cmd
python scripts\create_admin.py
```

Default admin credentials will be created:
- **Email**: `admin@adaptive-ids.local`
- **Username**: `admin`
- **Password**: `AdminPass123`

### 2. Backend Setup

#### Install Dependencies
```cmd
cd backend
pip install -r requirements.txt
```

#### Set Environment Variables
Create a `.env` file in the `backend` directory (or use the existing one):
```env
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
POSTGRES_USER=adaptive_ids
POSTGRES_PASSWORD=adaptive_ids_password

# Authentication
JWT_SECRET=your-secret-jwt-key-change-in-production
SECRET_KEY=your-secret-flask-key-change-in-production
ACCESS_TOKEN_TTL=900
REFRESH_TOKEN_TTL=604800

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_DEFAULT=100 per hour

# Compression
COMPRESS_ENABLED=True
```

#### Start Backend Server
```cmd
cd backend\api
python app.py
```

The backend will start on `http://localhost:5000`

### 3. Frontend Setup

#### Install Dependencies
```cmd
cd frontend\frontend
npm install
```

#### Configure Environment
Create a `.env` file (or use the existing one):
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_VERSION=v1
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
VITE_DEV_MODE=true
```

#### Start Development Server
```cmd
npm run dev
```

The frontend will start on `http://localhost:5173`

### 4. Access the Application

1. Open your browser and navigate to `http://localhost:5173`
2. You'll see the login page
3. Enter credentials:
   - **Email/Username**: `admin@adaptive-ids.local` or `admin`
   - **Password**: `AdminPass123`
4. Click **Sign In**

## Features Implemented

### ✅ Authentication Flow
- **Login Page** with email/username and password
- **JWT Token Management** (access token + refresh token)
- **Automatic Token Refresh** when access token expires
- **Secure Token Storage** in localStorage
- **Protected Routes** - redirects unauthenticated users to login
- **Logout Functionality** with token revocation

### ✅ Dashboard Integration
- **Real-time Dashboard Stats** from backend
- **Recent Alerts & Incidents** display
- **Model Metrics** integration
- **Traffic Visualization** with Chart.js

### ✅ RL Model Integration
- **Model Performance Metrics** display
- **Real-time Predictions** interface
- **Interactive Feature Input** form
- **Probability Visualization** with progress bars

### ✅ Real-time Updates
- **Server-Sent Events (SSE)** connection
- **Live Alert Notifications**
- **Connection Status Indicator**
- **Automatic Reconnection** on connection loss

### ✅ User Experience
- **Loading States** during authentication and data fetching
- **Error Handling** with user-friendly messages
- **User Profile Display** in header
- **Logout Button** with confirmation
- **Responsive Design** for all screen sizes

## API Endpoints

### Authentication Endpoints
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get tokens
- `POST /api/auth/logout` - Logout and revoke refresh token
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/refresh` - Refresh access token

### Dashboard Endpoints
- `GET /api/dashboard/stats` - Get dashboard statistics
- `GET /api/alerts` - Get alerts with pagination
- `GET /api/incidents` - Get incidents with pagination
- `GET /api/model/metrics` - Get model performance metrics

### RL Model Endpoints
- `POST /api/predict` - Get prediction from RL model
- `POST /api/model/retrain` - Trigger model retraining

### Real-time Endpoints
- `GET /api/stream/alerts` - SSE stream for real-time alerts

## Troubleshooting

### Database Connection Issues
```cmd
# Check if PostgreSQL is running
docker ps

# Check database logs
docker logs adaptive-ids-postgres

# Test connection manually
psql -h localhost -p 55432 -U adaptive_ids -d adaptive_ids
```

### Backend Issues
```cmd
# Check if backend is running
curl http://localhost:5000/api/health

# View backend logs
# Backend logs will appear in the terminal where you started the server
```

### Frontend Issues
```cmd
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Check if Vite dev server is running
curl http://localhost:5173
```

### Authentication Issues
- **Invalid credentials**: Ensure you're using the correct email/username and password
- **Token expired**: The app should automatically refresh the token; if not, try logging out and logging back in
- **CORS errors**: Ensure `CORS_ORIGINS` in backend `.env` includes your frontend URL

### Real-time Connection Issues
- **SSE not connecting**: Check browser console for errors
- **Connection keeps reconnecting**: Ensure backend is stable and tokens are valid
- **No real-time updates**: Check that the backend SSE endpoint is accessible

## Testing

### Test Authentication Flow
1. Go to login page
2. Enter invalid credentials - should show error
3. Enter valid credentials - should redirect to dashboard
4. Refresh page - should stay logged in
5. Click logout - should return to login page

### Test Dashboard
1. Login successfully
2. Verify dashboard stats are loaded
3. Check that recent alerts and incidents are displayed
4. Navigate to different pages (Alerts, Incidents, RL Model)

### Test RL Model
1. Navigate to "RL Model" page
2. View model performance metrics
3. Enter feature values in prediction form
4. Click "Generate Prediction"
5. Verify prediction results are displayed

### Test Real-time Updates
1. Login to the application
2. Check connection status indicator in header (should show "Connected")
3. Backend will send heartbeat events every 30 seconds
4. New alerts/incidents will appear automatically

## Production Deployment

### Security Considerations
1. **Change default secrets** in `.env` files
2. **Use HTTPS** for all connections
3. **Enable rate limiting** to prevent abuse
4. **Use secure token storage** (consider httpOnly cookies)
5. **Implement CSRF protection**
6. **Enable database connection pooling**
7. **Set up proper logging and monitoring**

### Environment Variables
Update the following for production:
```env
# Backend
JWT_SECRET=<strong-random-secret>
SECRET_KEY=<strong-random-secret>
CORS_ORIGINS=https://your-domain.com
RATE_LIMIT_ENABLED=True

# Frontend
VITE_API_BASE_URL=https://api.your-domain.com
VITE_DEV_MODE=false
VITE_ENABLE_API_LOGGING=false
```

### Build for Production
```cmd
# Frontend
cd frontend\frontend
npm run build

# Deploy the dist folder to your web server

# Backend
cd backend
# Set environment variables for production
# Use a production WSGI server like Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

## Architecture Overview

### Frontend Architecture
```
frontend/
├── pages/               # Page components
│   ├── LoginPage.ts    # Login interface
│   ├── Dashboard.ts    # Main dashboard
│   ├── AlertsPage.ts   # Alerts management
│   ├── IncidentsPage.ts # Incidents management
│   └── RLModelPage.ts  # RL model interface
├── services/           # Business logic
│   └── authService.ts  # Authentication service
├── utils/              # Utilities
│   ├── apiClient.ts    # HTTP client with interceptors
│   └── realtimeClient.ts # SSE client
├── components/         # Reusable components
│   ├── Header.ts       # App header with user info
│   └── ConnectionStatus.ts # Connection indicator
└── index.tsx           # Main app entry point
```

### Backend Architecture
```
backend/
├── api/
│   ├── app.py          # Main Flask application
│   ├── auth.py         # Authentication blueprint
│   └── middleware.py   # Request/response middleware
├── db/
│   └── schema.sql      # Database schema
├── model/              # RL model artifacts
└── scripts/
    ├── migrate.py      # Database migrations
    └── create_admin.py # Admin user creation
```

## Next Steps

1. **Add More Test Users**: Run `create_admin.py` with different credentials
2. **Customize Dashboard**: Modify `Dashboard.ts` to add more widgets
3. **Enhance RL Model**: Train with more data and update model checkpoints
4. **Add Notifications**: Implement toast notifications for real-time events
5. **Improve Error Handling**: Add retry mechanisms and better error messages
6. **Add Unit Tests**: Write tests for frontend and backend components

## Support

For issues or questions:
1. Check the logs in the terminal/console
2. Review the troubleshooting section above
3. Check browser developer tools for frontend errors
4. Verify all services are running correctly

## Additional Resources

- **Flask Documentation**: https://flask.palletsprojects.com/
- **Vite Documentation**: https://vitejs.dev/
- **JWT.io**: https://jwt.io/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/

---

**Version**: 2.0.0  
**Last Updated**: October 20, 2025
