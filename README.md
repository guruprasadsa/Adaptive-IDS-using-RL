# Adaptive IDS v2.0

**Advanced Intrusion Detection System with Reinforcement Learning and Real-time Monitoring**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8.2-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🚀 Quick Start

### New to the Project?

**Start here:** 👉 [**Installation Checklist**](./documentation/INSTALLATION_CHECKLIST.md)

This comprehensive guide will walk you through:
- Installing all dependencies
- Configuring backend and frontend
- Testing the connection
- Verifying all features work

---

## 📚 Documentation

All documentation is organized in the [`documentation/`](./documentation/) folder:

### Essential Guides

| Document | Description | When to Use |
|----------|-------------|-------------|
| 🔧 [**Installation Checklist**](./documentation/INSTALLATION_CHECKLIST.md) | Complete setup guide with verification steps | First-time setup |
| 🚀 [**Frontend-Backend Setup**](./documentation/FRONTEND_BACKEND_SETUP.md) | Quick start and testing procedures | Getting started |
| 📋 [**Quick Reference**](./documentation/QUICK_REFERENCE.md) | Developer cheat sheet | Daily development |
| 📖 [**API Integration**](./documentation/API_INTEGRATION.md) | Complete API reference and examples | Working with APIs |
| 🎯 [**Implementation Summary**](./documentation/IMPLEMENTATION_SUMMARY.md) | What was built and how it works | Understanding the system |

**See the [Documentation Index](./documentation/README.md) for complete details.**

---

## 🏗️ Architecture

```
adaptive-ids-v-2.0/
├── backend/                 # Flask API server
│   ├── api/
│   │   ├── app.py          # Main Flask application
│   │   ├── auth.py         # JWT authentication
│   │   └── middleware.py   # Request/response middleware
│   ├── model/              # ML models and checkpoints
│   ├── scripts/            # Utility scripts
│   └── requirements.txt    # Python dependencies
│
├── frontend/               # TypeScript/Vite frontend
│   └── frontend/
│       ├── components/     # UI components
│       ├── hooks/          # React Query hooks
│       ├── pages/          # Page components
│       ├── utils/          # API client, helpers
│       ├── api.ts          # API service layer
│       └── types.ts        # TypeScript definitions
│
├── data/                   # Training datasets (CICIDS2017/2018)
├── documentation/          # 📚 All documentation files
└── docker-compose.yml      # Docker configuration
```

---

## ✨ Key Features

### 🔐 Security
- JWT-based authentication with automatic token refresh
- Role-based access control (Admin, Analyst, Viewer)
- Rate limiting (100 requests/hour default)
- CORS configuration
- Security headers (XSS, CSRF protection)

### ⚡ Performance
- **Gzip compression** - Reduces response size by 70%+
- **Response caching** - 10s-5min depending on endpoint
- **React Query** - Automatic caching and deduplication
- **Database indexes** - Optimized queries
- **Response times** < 500ms for all endpoints

### 🔴 Real-time Updates
- **Server-Sent Events (SSE)** for live alert notifications
- Automatic reconnection with exponential backoff
- Connection status monitoring
- Heartbeat mechanism every 30 seconds

### 🤖 Machine Learning
- Reinforcement Learning (DQN/A3C) for threat detection
- Trained on CICIDS2017/2018 datasets
- Real-time prediction API
- Model performance metrics tracking
- Support for model retraining

### 📊 Monitoring Dashboard
- Real-time alerts and incidents
- Interactive charts and visualizations
- Filterable, sortable, paginated data tables
- Connection status indicator
- Model performance metrics

---

## 🛠️ Technology Stack

### Backend
- **Flask 3.0.0** - Web framework
- **PostgreSQL** - Database
- **PyTorch 2.1.0** - Machine learning
- **Flask-Compress** - Response compression
- **Flask-Limiter** - Rate limiting
- **PyJWT** - Authentication

### Frontend
- **TypeScript 5.8.2** - Type safety
- **Vite 6.2.0** - Build tool
- **React Query 5.28.0** - Data fetching
- **Axios 1.6.7** - HTTP client
- **Chart.js 4.5.0** - Visualizations

---

## 📦 Installation

### Prerequisites
- Python 3.8+
- Node.js 18+
- PostgreSQL 13+
- Git

### Backend Setup

```bash
# Clone repository
git clone <repository-url>
cd adaptive-ids-v-2.0

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your configuration

# Start backend
cd api
python app.py
```

Backend will run on `http://localhost:5000`

### Frontend Setup

```bash
# Install Node dependencies
cd frontend/frontend
npm install

# Start development server
npm run dev
```

Frontend will run on `http://localhost:5173`

### Detailed Instructions

For complete step-by-step instructions with verification:
👉 **[Installation Checklist](./documentation/INSTALLATION_CHECKLIST.md)**

---

## 🧪 Testing

### Test Backend Health
```bash
curl http://localhost:5000/api/health
```

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

### Test Frontend
1. Open browser to `http://localhost:5173`
2. Login with test credentials
3. Check browser console for API calls
4. Verify no CORS errors

### Comprehensive Testing
See [Frontend-Backend Setup Guide](./documentation/FRONTEND_BACKEND_SETUP.md) for complete testing procedures.

---

## 📖 API Documentation

### Authentication Endpoints
```
POST /api/auth/register    - Register new user
POST /api/auth/login       - Login and get tokens
POST /api/auth/logout      - Logout and revoke token
GET  /api/auth/me          - Get current user info
POST /api/auth/refresh     - Refresh access token
```

### Data Endpoints
```
GET  /api/dashboard/stats  - Dashboard statistics
GET  /api/alerts           - List alerts (paginated)
GET  /api/incidents        - List incidents (paginated)
GET  /api/model/metrics    - Model performance metrics
POST /api/predict          - Make prediction
```

### Real-time
```
GET  /api/stream/alerts    - SSE stream for live alerts
```

**Full API documentation:** [API Integration Guide](./documentation/API_INTEGRATION.md)

---

## 🎯 Usage Examples

### Frontend - React Query Hooks

```typescript
import { useDashboardStats, useAlerts, useUpdateAlertStatus } from './hooks/useApi';

function Dashboard() {
  // Fetch dashboard data (auto-cached for 30s)
  const { data, isLoading } = useDashboardStats();
  
  // Fetch alerts with pagination
  const { data: alerts } = useAlerts(page, perPage, filters);
  
  // Update alert status with optimistic updates
  const updateAlert = useUpdateAlertStatus({
    onSuccess: () => console.log('Alert updated!')
  });
  
  updateAlert.mutate({ id: '123', status: 'resolved' });
}
```

### Backend - Add New Endpoint

```python
from flask import jsonify, request
from auth import require_auth
from middleware import cache_control

@app.route("/api/custom-endpoint", methods=["GET"])
@require_auth
@cache_control(max_age=60, public=True)
@limiter.limit("20 per minute")
def custom_endpoint(user_id: int = None):
    # Your logic here
    return jsonify({"data": "response"})
```

---

## 🔧 Configuration

### Backend Environment (`.env`)
```env
SECRET_KEY=<random-string>
JWT_SECRET=<random-string>
CORS_ORIGINS=http://localhost:5173
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
COMPRESS_ENABLED=True
RATE_LIMIT_ENABLED=True
```

### Frontend Environment (`.env.local`)
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
VITE_ENABLE_REALTIME=true
VITE_ENABLE_CACHING=true
```

---

## 📊 Performance Metrics

| Endpoint | Target | Caching |
|----------|--------|---------|
| Health Check | < 50ms | 10s |
| Dashboard Stats | < 200ms | 30s |
| Alerts List | < 300ms | 10s |
| Incidents List | < 300ms | 10s |
| Predictions | < 500ms | None |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support

### Common Issues

**CORS Errors:**
- Check `CORS_ORIGINS` in backend `.env`
- Restart backend server
- See [troubleshooting guide](./documentation/INSTALLATION_CHECKLIST.md#issue-cors-errors)

**Authentication Issues:**
- Verify JWT_SECRET is set
- Check tokens in localStorage
- See [authentication guide](./documentation/API_INTEGRATION.md#authentication)

**Performance Issues:**
- Check database indexes
- Enable caching
- See [performance guide](./documentation/IMPLEMENTATION_SUMMARY.md#performance-enhancements)

### Getting Help

1. Check [Installation Checklist](./documentation/INSTALLATION_CHECKLIST.md)
2. Review [Frontend-Backend Setup](./documentation/FRONTEND_BACKEND_SETUP.md)
3. Read [Quick Reference](./documentation/QUICK_REFERENCE.md)
4. See [API Integration Guide](./documentation/API_INTEGRATION.md)

---

## 🎓 Learning Resources

- [Installation Checklist](./documentation/INSTALLATION_CHECKLIST.md) - Start here for setup
- [Quick Reference](./documentation/QUICK_REFERENCE.md) - Developer cheat sheet
- [API Integration](./documentation/API_INTEGRATION.md) - Complete API reference
- [Implementation Summary](./documentation/IMPLEMENTATION_SUMMARY.md) - Technical details

---

## 🏆 Project Status

✅ **Production Ready**

- ✅ Full authentication system with JWT
- ✅ Real-time alert notifications via SSE
- ✅ Comprehensive API with rate limiting
- ✅ Performance optimized (caching, compression)
- ✅ Type-safe frontend with TypeScript
- ✅ React Query for efficient data fetching
- ✅ Complete documentation
- ✅ Testing procedures included

---

## 🙏 Acknowledgments

- CICIDS2017/2018 datasets for training data
- Flask and PyTorch communities
- React Query and Axios maintainers

---

**Built with ❤️ for cybersecurity professionals**

For detailed setup and usage, start with the [**Installation Checklist**](./documentation/INSTALLATION_CHECKLIST.md) 👈
