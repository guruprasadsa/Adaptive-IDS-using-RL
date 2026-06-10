# Adaptive Intrusion Detection System using Reinforcement Learning

An intelligent intrusion detection system combining **Asynchronous Advantage Actor-Critic (A3C)** for attack classification routing with **Deep Q-Networks (DQN)** specialist agents for multi-class threat detection.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/pytorch-2.0+-red.svg)](https://pytorch.org/)
[![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8+-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

This project implements a production-ready intrusion detection system using hybrid reinforcement learning techniques. The system classifies network traffic across 18 attack categories with high accuracy and minimal false positive rates, designed for real-time packet analysis and threat alerting.

### Key Characteristics

- **Hybrid RL Architecture**: A3C meta-router with 18 specialized DQN agents
- **Classification Performance**: >99% true positive rate, <1% false positive rate, F1-score ≥0.95
- **Inference Speed**: <10ms latency per batch
- **Calibration**: Expected calibration error <0.05
- **Curriculum Learning**: 4-phase difficulty progression during training
- **Test Coverage**: 63 unit tests with 100% pass rate
- **Real-Time Processing**: Kafka-based streaming pipeline for live packet analysis

### Supported Attack Types

| Category | Attack Types |
|----------|-------------|
| **DoS** | Hulk, GoldenEye, Slowloris, Slowhttptest |
| **DDoS** | HOIC, LOIC |
| **Web** | Brute Force, XSS, SQL Injection |
| **Intrusion** | FTP-Patator, SSH-Patator, Infiltration, Botnet |
| **Reconnaissance** | PortScan |
| **Vulnerability** | Heartbleed |
| **Normal** | Benign traffic |

---

## Quick Start

### Prerequisites

- Docker Desktop (24.0+) — [Download](https://www.docker.com/products/docker-desktop)
- Git (2.0+) — [Download](https://git-scm.com/downloads)
- 8GB RAM minimum (16GB recommended)

### Setup Options

#### Automated Setup (Recommended)

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

#### Manual Setup

**1. Clone and configure:**
```bash
git clone https://github.com/guruprasadsa/Adaptive-IDS-using-RL.git
cd Adaptive-IDS-using-RL

# Backend environment
cp backend/.env.example backend/.env

# Frontend environment
cp frontend/.env.example frontend/.env.local
```

**2. Generate secrets:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**3. Start services:**
```bash
docker compose up -d
```

### Access the System

After 30-60 seconds:

| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | http://localhost:8080 | admin / admin123 |
| Backend API | http://localhost:5001 | N/A |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | N/A |

---

## Production Deployment

### Live Data Pipeline

For real-time network monitoring, follow these steps:

**1. Start core services:**
```bash
docker compose up -d
```

**2. Configure `backend/.env`:**
```env
PCAP_IFACE=<interface_number>  # e.g., 6 for Wi-Fi on Windows
```

**3. Run data pipeline (host terminals):**
```bash
# Terminal 1: Packet capture
python backend/sensors/pcap_producer.py

# Terminal 2: Feature extraction
python backend/stream/feature_extractor.py

# Model service and alerting run in Docker (ports 8000, 5001)
```

**4. Verify pipeline:**
- Check health: `curl http://localhost:8000/health`
- Alerts should populate within 30-60 seconds of traffic
- Monitor via dashboard or Grafana

**Troubleshooting:**
- No packets captured → Verify Tshark and `PCAP_IFACE` setting
- Features not produced → Check `feature_extractor` logs and Kafka connectivity
- No predictions → Verify model checkpoints at `backend/model/checkpoints/`
- See `documentation/TROUBLESHOOTING_MODEL_SERVICE.md` for detailed diagnostics

---

## Architecture

```
Adaptive-IDS-using-RL/
├── backend/
│   ├── api/                    # Flask REST API
│   │   ├── app.py              # Application entry point
│   │   ├── auth.py             # JWT authentication
│   │   └── middleware.py       # Request/response handlers
│   ├── sensors/                # Data collection
│   │   └── pcap_producer.py    # Network packet capture
│   ├── stream/                 # Real-time processing
│   │   └── feature_extractor.py # Network feature extraction
│   ├── model/                  # ML models and checkpoints
│   ├── scripts/                # Utility and training scripts
│   └── requirements.txt        # Python dependencies
│
├── frontend/                   # TypeScript/React UI
│   ├── components/             # Reusable UI components
│   ├── hooks/                  # React Query integration
│   ├── pages/                  # Page-level components
│   ├── utils/                  # Helpers and API client
│   └── types.ts                # TypeScript definitions
│
├── data/                       # Training datasets (CICIDS2017/2018)
├── documentation/              # Complete reference documentation
└── docker-compose.yml          # Service orchestration
```

---

## Features

### Security
- JWT-based authentication with automatic token refresh
- Role-based access control (Admin, Analyst, Viewer)
- Rate limiting (100 requests/hour default)
- CORS and security headers (XSS, CSRF protection)

### Performance
- Gzip compression (70%+ size reduction)
- Response caching (10s–5min depending on endpoint)
- React Query automatic deduplication
- Optimized database indexes
- Sub-500ms response times

### Real-Time Monitoring
- Server-Sent Events (SSE) for live alert streaming
- Automatic connection recovery with exponential backoff
- Heartbeat mechanism (30s intervals)
- Connection status indicators

### Machine Learning
- Hybrid reinforcement learning (DQN/A3C)
- Trained on CICIDS2017/2018 datasets
- Real-time inference API
- Performance metric tracking
- Retraining capabilities

---

## Technology Stack

### Backend
- Python 3.12
- Flask 3.0
- PostgreSQL 13+
- PyTorch 2.1
- Kafka (streaming)

### Frontend
- TypeScript 5.8
- React 18+
- Vite 6.2
- React Query 5.28
- Axios 1.6

---

## API Reference

### Authentication
```
POST   /api/auth/register      Register new user
POST   /api/auth/login         Login (returns tokens)
POST   /api/auth/logout        Logout
GET    /api/auth/me            Current user info
POST   /api/auth/refresh       Refresh access token
```

### Data Access
```
GET    /api/dashboard/stats    Dashboard statistics
GET    /api/alerts             Alerts (paginated)
GET    /api/incidents          Incidents (paginated)
GET    /api/model/metrics      Model performance metrics
POST   /api/predict            Make prediction
GET    /api/stream/alerts      Live alert stream (SSE)
```

See [API_INTEGRATION.md](./documentation/API_INTEGRATION.md) for complete endpoint documentation.

---

## Configuration

### Backend (`.env`)
```env
SECRET_KEY=<random-string>
JWT_SECRET=<random-string>
CORS_ORIGINS=http://localhost:5173
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
```

### Frontend (`.env.local`)
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_TIMEOUT=30000
VITE_ENABLE_REALTIME=true
```

---

## Testing

### Backend Health Check
```bash
curl http://localhost:5000/api/health
```

### Run Test Suite
```bash
cd backend
python -m pytest tests/ -v
```

### Frontend Testing
1. Navigate to http://localhost:5173
2. Login with credentials: `admin` / `admin123`
3. Verify API calls in browser console
4. Check for CORS errors

---

## Documentation

Complete documentation is available in the [`documentation/`](./documentation/) directory:

- **[Installation Checklist](./documentation/INSTALLATION_CHECKLIST.md)** — Complete setup guide with verification
- **[Setup Guide](./documentation/SETUP_GUIDE.md)** — Quick start for development
- **[API Integration](./documentation/API_INTEGRATION.md)** — Complete API reference
- **[Phase 4 Complete](./documentation/PHASE_4_COMPLETE.md)** — Hybrid RL architecture and design
- **[Troubleshooting](./documentation/TROUBLESHOOTING_MODEL_SERVICE.md)** — Common issues and solutions

See [documentation/README.md](./documentation/README.md) for the complete index.

---

## Training & Model Development

The system uses a 4-phase curriculum learning approach:

1. **Phase 1**: Training on benign and simple DoS attacks
2. **Phase 2**: Introduction of intermediate attacks
3. **Phase 3**: Advanced attack variants and combinations
4. **Phase 4**: Full mixed attack dataset with hard examples

For training procedures and performance analysis:
- See [Training Improvements Summary](./documentation/TRAINING_IMPROVEMENTS_SUMMARY.md)
- Check [Test Summary](./backend/model/TEST_SUMMARY.md)

---

## Contributing

Contributions are welcome. Please follow standard practices:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/description`)
3. Make changes with descriptive commits
4. Push to your branch
5. Open a pull request with clear description

---

## Performance Metrics

| Component | Target | Actual |
|-----------|--------|--------|
| Inference latency | <10ms | <8ms |
| True positive rate | >99% | >99.5% |
| False positive rate | <1% | <0.8% |
| F1-score | ≥0.95 | ≥0.96 |
| Expected calibration error | <0.05 | <0.04 |

---

## Troubleshooting

### Services Won't Start
```bash
docker compose logs
docker compose down && docker compose up -d
```

### CORS Errors
- Verify `CORS_ORIGINS` in `backend/.env`
- Restart backend service
- Check browser console for details

### Database Connection Issues
- Verify PostgreSQL container is running: `docker ps | grep postgres`
- Check connection string in `.env`
- Review `docker compose logs postgres`

### Model Inference Failures
- Verify model checkpoints exist at `backend/model/checkpoints/`
- Check model service health: `curl http://localhost:8000/health`
- Review model service logs for errors

See [documentation/TROUBLESHOOTING_MODEL_SERVICE.md](./documentation/TROUBLESHOOTING_MODEL_SERVICE.md) for additional diagnostics.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Support

For issues or questions:
1. Check [Installation Checklist](./documentation/INSTALLATION_CHECKLIST.md)
2. Review [API Integration Guide](./documentation/API_INTEGRATION.md)
3. See [Troubleshooting Guide](./documentation/TROUBLESHOOTING_MODEL_SERVICE.md)
4. Open an issue on GitHub with error logs and configuration details

---

**Version**: 2.1  
**Last Updated**: January 2026  
**Status**: Production Ready
