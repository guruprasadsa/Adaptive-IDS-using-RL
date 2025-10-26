# Adaptive IDS - Quick Start Guide

## Prerequisites (Windows)

### Required Software
- Docker Desktop for Windows (with WSL2 backend)
- Python 3.10 or higher
- Node.js 18+ and npm (for frontend)
- Git

### Optional Tools
- VS Code with Python and Docker extensions
- Npcap (for packet capture on Windows)

## Initial Setup

### 1. Clone and Navigate
```bash
cd c:\AIML\Projects\adaptive-ids-v-2.0
```

### 2. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Configure Environment
Edit `backend/.env` and update values as needed (defaults should work for local dev).

### 4. Start Infrastructure Services
```bash
docker compose up -d
```

This starts:
- PostgreSQL (port 55432)
- Kafka KRaft (port 9092)
- Schema Registry (port 8081)
- Backend API (port 5001)
- Model Service (port 8000)

### 5. Verify Services
Check that all containers are healthy:
```bash
docker compose ps
```

Check service health endpoints:
```bash
curl http://localhost:5001/api/health
curl http://localhost:8000/health
```

### 6. Create Kafka Topics (if needed)
```bash
docker exec adaptive_ids_kafka kafka-topics --create --if-not-exists --bootstrap-server localhost:9092 --topic raw.packets --partitions 3 --replication-factor 1
docker exec adaptive_ids_kafka kafka-topics --create --if-not-exists --bootstrap-server localhost:9092 --topic flows.features --partitions 3 --replication-factor 1
docker exec adaptive_ids_kafka kafka-topics --create --if-not-exists --bootstrap-server localhost:9092 --topic predictions --partitions 3 --replication-factor 1
docker exec adaptive_ids_kafka kafka-topics --create --if-not-exists --bootstrap-server localhost:9092 --topic alerts --partitions 3 --replication-factor 1
```

List topics to verify:
```bash
docker exec adaptive_ids_kafka kafka-topics --list --bootstrap-server localhost:9092
```

### 7. Setup Frontend (Optional)
```bash
cd frontend/frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:5173

## VS Code Tasks

Use `Ctrl+Shift+P` → "Tasks: Run Task" to access:

- **Docker: Start All Services** - Start all Docker services
- **Docker: Stop All Services** - Stop all Docker services
- **Docker: View Logs** - Tail logs from all services
- **Backend: Install Dependencies** - Install Python packages
- **Frontend: Install Dependencies** - Install npm packages
- **Frontend: Run Dev Server** - Start Vite dev server

## Development Workflow

### Running Services Locally (Outside Docker)

1. **Backend API**:
```bash
cd backend
python -m flask run --host=0.0.0.0 --port=5001
```

2. **Model Service**:
```bash
cd backend
uvicorn model.service.app:app --reload --host 0.0.0.0 --port 8000
```

3. **Packet Sensor** (when implemented):
```bash
cd backend
python sensors/pcap_producer.py
```

4. **Feature Extractor** (when implemented):
```bash
cd backend
python stream/feature_extractor.py
```

### Using VS Code Debugger

Launch configurations available:
- **Python: Backend API** - Debug Flask API
- **Python: Model Service** - Debug model inference service
- **Python: Packet Sensor** - Debug packet capture
- **Python: Feature Extractor** - Debug stream processor
- **Full Stack (Python)** - Run both backend services together

## Architecture Overview

```
┌─────────────────┐
│   Packet        │
│   Sensors       │───► raw.packets (Kafka)
└─────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Feature       │
                  │   Extractor     │───► flows.features
                  └─────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Model         │
                  │   Service       │───► predictions
                  └─────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Alert         │
                  │   Processor     │───► PostgreSQL, Email, Syslog
                  └─────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Backend API   │◄──── React Frontend
                  │   (Flask)       │      (SSE/REST)
                  └─────────────────┘
```

## Environment Variables

Key variables in `backend/.env`:

### Kafka
- `KAFKA_BROKERS`: Kafka bootstrap servers
- `PACKETS_TOPIC`: Raw packet metadata
- `FEATURES_TOPIC`: Extracted flow features
- `PRED_TOPIC`: Model predictions
- `ALERTS_TOPIC`: Enriched alerts

### Database
- `PG_DSN`: PostgreSQL connection string
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

### Model
- `ADAPTIVE_IDS_MODEL_ROOT`: Model artifacts directory
- `DEVICE`: cuda or cpu (auto-detected)

### Alerting
- `SYSLOG_HOST`, `SYSLOG_PORT`: External syslog server (optional)
- `ALERT_EMAIL_TO`: Email recipients for high-severity alerts
- `SMTP_HOST`, `SMTP_PORT`: SMTP server config

## Troubleshooting

### Kafka Won't Start
- Ensure no other Kafka instance is using port 9092
- Check Docker Desktop has enough memory (4GB+ recommended)
- Clear volumes: `docker compose down -v` then `docker compose up -d`

### Backend API Fails
- Check PostgreSQL is running: `docker compose ps postgres`
- Verify connection: `docker compose logs postgres`
- Run migrations: `python backend/scripts/migrate.py`

### Model Service Fails
- Ensure model files exist in `backend/model/checkpoints/`
- Check logs: `docker compose logs model-service`
- Verify PyTorch installation: `python -c "import torch; print(torch.__version__)"`

### Port Conflicts
If ports are in use:
- Postgres: Change `55432` in docker-compose.yml
- Kafka: Change `9092` in docker-compose.yml
- Update corresponding `.env` values

## Next Steps

1. Implement packet capture producer (see `backend/sensors/README.md`)
2. Implement feature extraction (see `backend/stream/README.md`)
3. Train multi-agent DQN model (see `backend/scripts/trainrl.ipynb`)
4. Implement alert processor (see `backend/alerting/README.md`)
5. Add real-time UI updates (see `frontend/frontend/pages/AlertsPage.ts`)

## Useful Commands

### Docker
```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f kafka

# Restart a service
docker compose restart backend

# Rebuild and restart
docker compose up -d --build backend

# Clean everything
docker compose down -v
```

### Kafka CLI
```bash
# List topics
docker exec adaptive_ids_kafka kafka-topics --list --bootstrap-server localhost:9092

# Describe topic
docker exec adaptive_ids_kafka kafka-topics --describe --topic raw.packets --bootstrap-server localhost:9092

# Consume messages
docker exec adaptive_ids_kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw.packets --from-beginning

# Produce test message
docker exec -it adaptive_ids_kafka kafka-console-producer --bootstrap-server localhost:9092 --topic raw.packets
```

### Database
```bash
# Connect to PostgreSQL
docker exec -it adaptive_ids_postgres psql -U adaptive_ids -d adaptive_ids

# Run SQL file
docker exec -i adaptive_ids_postgres psql -U adaptive_ids -d adaptive_ids < backend/db/schema.sql
```

## Documentation

See `documentation/` folder for detailed guides:
- `WINDOWS_RUNBOOK.md` - Windows-specific setup
- `API_INTEGRATION.md` - API documentation
- `AUTH_SETUP_GUIDE.md` - Authentication setup
- `FRONTEND_BACKEND_SETUP.md` - Full stack setup

For implementation prompts, see `prompts.txt` at the project root.
