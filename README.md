# Adaptive IDS v2.0

**Advanced Intrusion Detection System with Hybrid Multi-Agent Reinforcement Learning**

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/pytorch-2.0+-red.svg)](https://pytorch.org/)
[![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8.2-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🎯 Overview

A production-ready Intrusion Detection System combining **A3C (Asynchronous Advantage Actor-Critic)** for intelligent specialist routing with **DQN (Deep Q-Network)** for binary attack classification. Achieves >99% attack detection rate with <1% false positives on CIC-IDS-2017/2018 datasets.

### Key Features

- 🧠 **Hybrid RL Architecture**: A3C router + 18 DQN specialists for multi-class attack detection
- 🎯 **High Performance**: >99% TPR, <1% FPR, F1 ≥0.95
- ⚡ **Real-Time**: <10ms inference latency per batch
- � **Well-Calibrated**: ECE <0.05 for reliable confidence estimates
- 🎓 **Curriculum Learning**: 4-phase difficulty progression
- ✅ **Production-Ready**: 63 unit tests (100% pass rate), comprehensive documentation
- 🔄 **Real-Time Processing**: Kafka streaming pipeline for live packet analysis

### Detected Attack Types (18 Classes)

| Category | Attack Types |
|----------|-------------|
| **DoS** | DoS Hulk, DoS GoldenEye, DoS Slowloris, DoS Slowhttptest |
| **DDoS** | DDoS HOIC, DDoS LOIC |
| **Web** | WebAttack Brute Force, WebAttack XSS, WebAttack SQL Injection |
| **Intrusion** | FTP-Patator, SSH-Patator, Infiltration, Botnet |
| **Reconnaissance** | PortScan |
| **Vulnerability** | Heartbleed |
| **Normal** | Benign traffic |

---

## 🏭 Production Setup (Live Data)

This section describes how to run the full live pipeline end-to-end using Docker on Windows and your local network interface.

Prerequisites
- Docker Desktop with WSL2 backend enabled
- Npcap and Wireshark/Tshark installed (for packet capture via pyshark)
- Python 3.12 on host (to run the packet capture and feature extractor if running outside containers)

Steps
- 1) Start core services
  - From the repo root:
    - Start infrastructure (Postgres, Kafka, Schema Registry, Backend API, Model Service, Alerting, Prometheus, Grafana, OTEL, Jaeger):
      - Use the VS Code Task "Docker: Start All Services" or run `docker compose up -d`.

- 2) Configure backend/.env
  - Set packet capture interface:
    - PCAP_IFACE=<your interface number or name> (e.g., 6 for Wi-Fi on Windows)
  - Ensure Kafka/DB endpoints use localhost:9092 and 127.0.0.1:55432 for host-run scripts
  - Optional: Configure alert integrations (EMAIL_*, SYSLOG_*)

- 3) Run the live data pipeline on host
  - In separate terminals:
    - Packet capture → Kafka:
      - `python backend/sensors/pcap_producer.py`
    - Feature extractor (raw.packets → flows.features):
      - `python backend/stream/feature_extractor.py`
    - Model inference and alerting services are already running in Docker (ports 8000 and 5001)

- 4) Verify topics and flow
  - Kafka has auto-create enabled. Required topics:
    - raw.packets, flows.features, predictions, alerts
  - Within 30–60 seconds of traffic on your interface:
    - Model service /health should report healthy at http://localhost:8000/health
    - Alerts should start populating the Postgres alerts table

- 5) Frontend
  - Set `frontend/.env.local`:
    - `VITE_API_BASE_URL=http://localhost:5001`
  - Start the dev server:
    - `npm install && npm run dev` in `frontend/`
  - Login, open Alerts and Dashboard pages; live updates stream via SSE from `/api/events`.

Troubleshooting
- If no packets are captured: confirm Tshark works and PCAP_IFACE is correct
- If features aren’t produced: check feature_extractor logs and Kafka connectivity
- If predictions/alerts are not flowing: check model-service logs, ensure model checkpoints exist at `backend/model/checkpoints/`
- Check `documentation/WINDOWS_RUNBOOK.md` and `documentation/TROUBLESHOOTING_MODEL_SERVICE.md` for more help

---

## 🚀 Quick Start - Get Running in 3 Steps!

### Prerequisites

Before you begin, ensure you have:
- **Docker Desktop** (24.0+) - [Download here](https://www.docker.com/products/docker-desktop)
- **Git** (2.0+) - [Download here](https://git-scm.com/downloads)
- **8GB RAM** minimum (16GB recommended)

> 📖 **Detailed Prerequisites**: See [SETUP_PREREQUISITES.md](./SETUP_PREREQUISITES.md) for complete installation guide

---

### Option 1: Automated Setup (Recommended)

**Windows:**
```cmd
git clone https://github.com/guruprasadsa/Adaptive-IDS-using-RL.git
cd Adaptive-IDS-using-RL
setup.bat
```

**Linux/macOS:**
```bash
git clone https://github.com/guruprasadsa/Adaptive-IDS-using-RL.git
cd Adaptive-IDS-using-RL
chmod +x setup.sh
./setup.sh
```

The script will:
- ✅ Verify all prerequisites
- ✅ Create environment files
- ✅ Install dependencies (optional)
- ✅ Start Docker services

---

### Option 2: Manual Setup (3 Steps)

#### 1️⃣ Clone the Repository
```bash
git clone https://github.com/guruprasadsa/Adaptive-IDS-using-RL.git
cd Adaptive-IDS-using-RL
```

#### 2️⃣ Configure Environment
```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env and set SECRET_KEY and JWT_SECRET

# Frontend
cp frontend/.env.example frontend/.env.local
```

**Generate secrets:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 3️⃣ Start Services
```bash
docker compose up -d
```

**That's it!** 🎉

---

### 🔍 Access the Dashboard

After 30-60 seconds, open your browser to:

**Dashboard**: http://localhost:8080

**Default Login:**
- Username: `admin`
- Password: `admin123`

### 📊 Other Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Backend API | http://localhost:5001 | N/A |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | N/A |
| Jaeger | http://localhost:16686 | N/A |

---

### 📚 Complete Documentation

- 👉 **[QUICK_START.md](./QUICK_START.md)** - Detailed setup guide (< 30 min)
- 👉 **[SETUP_PREREQUISITES.md](./SETUP_PREREQUISITES.md)** - Install all requirements
- 👉 **[documentation/](./documentation/)** - Complete documentation

---

### 🆘 Need Help?

**Common Issues:**
- Services won't start? → Run `docker compose logs` to check errors
- Frontend can't connect? → Verify backend is running: `curl http://localhost:5001/api/health`
- Port conflicts? → Change ports in `docker-compose.yml`

**More Help:**
- Check [QUICK_START.md](./QUICK_START.md) troubleshooting section
- See [documentation/TROUBLESHOOTING_MODEL_SERVICE.md](./documentation/TROUBLESHOOTING_MODEL_SERVICE.md)
- Open an issue on GitHub

---

## 📚 Documentation

All documentation is organized in the [`documentation/`](./documentation/) folder:

### Essential Guides

| Document | Description | When to Use |
|----------|-------------|-------------|
| 🔧 [**Installation Checklist**](./documentation/INSTALLATION_CHECKLIST.md) | Complete setup guide with verification steps | First-time setup |
| 🚀 [**Setup Guide**](./documentation/SETUP_GUIDE.md) | Quick start for development | Getting started |
| 📋 [**Quick Reference**](./documentation/QUICK_REFERENCE.md) | Developer cheat sheet | Daily development |
| 📖 [**API Integration**](./documentation/API_INTEGRATION.md) | Complete API reference and examples | Working with APIs |

### Machine Learning & Training

| Document | Description | When to Use |
|----------|-------------|-------------|
| 🧠 [**Phase 4 Complete**](./documentation/PHASE_4_COMPLETE.md) | Hybrid RL architecture and design decisions | Understanding ML pipeline |
| ⚡ [**Feature Extractor Guide**](./documentation/FEATURE_EXTRACTOR_QUICKSTART.md) | Network feature extraction | Working with streaming data |
| 🎯 [**Training Improvements**](./documentation/TRAINING_IMPROVEMENTS_SUMMARY.md) | Training optimizations and fixes | Model training |
| ⚖️ [**Imbalance Solution**](./documentation/IMBALANCE_SOLUTION.md) | Handling class imbalance | Addressing data issues |
| 📝 [**Training Guide**](./backend/scripts/README.md) | Training and evaluation procedures | Running experiments |
| ✅ [**Test Summary**](./backend/model/TEST_SUMMARY.md) | Test results and coverage analysis | Validating components |

### Additional Resources

| Document | Description |
|----------|-------------|
| 🔐 [**Authentication Setup**](./documentation/AUTH_SETUP_GUIDE.md) | JWT authentication configuration |
| 💻 [**Frontend-Backend Setup**](./documentation/FRONTEND_BACKEND_SETUP.md) | Full stack development guide |
| 🪟 [**Windows Runbook**](./documentation/WINDOWS_RUNBOOK.md) | Windows-specific setup instructions |
| 🐛 [**Troubleshooting**](./documentation/TROUBLESHOOTING_MODEL_SERVICE.md) | Common issues and solutions |

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

**Built with ❤️ for cybersecurity enthusiasts**

For detailed setup and usage, start with the [**Installation Checklist**](./documentation/INSTALLATION_CHECKLIST.md) 👈
