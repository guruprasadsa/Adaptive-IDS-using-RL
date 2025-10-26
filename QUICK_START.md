# 🚀 Quick Start Guide - Adaptive IDS v2.0

**Get the system running in less than 30 minutes!**

This guide will help you clone, configure, and run the Adaptive IDS system quickly. Follow the steps in order for the smoothest experience.

---

## ⏱️ Time Estimate

- **Beginner**: 25-30 minutes
- **Experienced**: 15-20 minutes
- **Just Docker**: 10 minutes (if prerequisites are already installed)

---

## 📋 Prerequisites

Before starting, ensure you have the following installed:

### Required Software

| Software | Minimum Version | Download Link |
|----------|----------------|---------------|
| **Docker Desktop** | 24.0+ | https://www.docker.com/products/docker-desktop |
| **Git** | 2.0+ | https://git-scm.com/downloads |
| **Python** | 3.12+ | https://www.python.org/downloads/ |
| **Node.js** | 18+ | https://nodejs.org/ |

### System Requirements

- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB free space
- **OS**: Windows 10/11, macOS, or Linux
- **Network**: Internet connection for initial setup

### Optional (For Live Packet Capture)

- **Npcap** (Windows): https://npcap.com/#download
- **Wireshark/Tshark**: https://www.wireshark.org/download.html

> 💡 **Note**: You can run the full system using simulated traffic without installing packet capture tools.

---

## 🎯 Quick Start (3 Steps)

### Step 1: Clone the Repository

```bash
git clone https://github.com/guruprasadsa/Adaptive-IDS-using-RL.git
cd Adaptive-IDS-using-RL
```

### Step 2: Configure Environment

#### Backend Configuration

```bash
# Copy the template
cp backend/.env.example backend/.env

# Edit backend/.env and update these REQUIRED fields:
# - SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
# - JWT_SECRET (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
```

**Windows Command:**
```cmd
copy backend\.env.example backend\.env
```

#### Frontend Configuration

```bash
# Copy the template
cp frontend/.env.example frontend/.env.local
```

**Windows Command:**
```cmd
copy frontend\.env.example frontend\.env.local
```

> ✅ **Default configurations work out of the box!** Just generate the SECRET_KEY and JWT_SECRET.

### Step 3: Start the System

```bash
# Start all services with Docker
docker compose up -d
```

**That's it!** The system is now running.

---

## 🔍 Verify Installation

### 1. Check All Services Are Running

```bash
docker compose ps
```

**Expected output**: All services should show "Up" status.

### 2. Test Backend API

Open your browser or use curl:

```bash
curl http://localhost:5001/api/health
```

**Expected response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "connected",
  "timestamp": "2025-10-26T...",
  "version": "2.0.0"
}
```

### 3. Access the Frontend

Open your browser to: **http://localhost:8080**

**Default Login Credentials:**
- **Username**: `admin`
- **Password**: `admin123`

### 4. View Real-time Dashboards

After logging in, you should see:
- ✅ Dashboard with real-time metrics
- ✅ Alerts page with incoming alerts
- ✅ Incidents page
- ✅ Model metrics

---

## 📊 Access Other Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend Dashboard** | http://localhost:8080 | admin / admin123 |
| **Backend API** | http://localhost:5001 | N/A |
| **Model Service** | http://localhost:8000 | N/A |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | N/A |
| **Jaeger Tracing** | http://localhost:16686 | N/A |
| **PostgreSQL** | localhost:55432 | adaptive_ids / adaptive_ids_password |
| **Kafka** | localhost:9092 | N/A |

---

## 🎓 Next Steps

### Create Additional Users

```bash
# Run the user creation script
python backend/scripts/create_users.py

# Or use Docker
docker exec adaptive_ids_backend python scripts/create_users.py
```

### View Logs

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f backend
docker compose logs -f model-service
docker compose logs -f alerting-service
```

### Stop the System

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart backend
```

---

## 🔧 Advanced Configuration

### Enable Email Alerts

Edit `backend/.env`:

```env
EMAIL_ENABLED=true
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Gmail App Password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=alerts@example.com
```

### Enable Live Packet Capture

1. Install Npcap/Wireshark
2. Find your network interface:
   ```bash
   tshark -D
   ```
3. Update `backend/.env`:
   ```env
   PCAP_IFACE=6  # Your interface number
   ```
4. Restart the packet-producer service:
   ```bash
   docker compose restart packet-producer
   ```

### Configure Model Settings

Edit `backend/.env`:

```env
BATCH_SIZE=256
CONFIDENCE_THRESHOLD=0.5
DEVICE=cuda  # or 'cpu' if no GPU
```

---

## 🐛 Troubleshooting

### Services Won't Start

**Problem**: Docker services fail to start

**Solution**:
```bash
# Check Docker is running
docker --version

# Check logs for errors
docker compose logs

# Try rebuilding
docker compose up -d --build
```

### Frontend Can't Connect to Backend

**Problem**: "Network Error" in frontend

**Solution**:
1. Check backend is running: `curl http://localhost:5001/api/health`
2. Verify `frontend/.env.local` has: `VITE_API_BASE_URL=http://localhost:5001`
3. Clear browser cache and reload

### Database Connection Error

**Problem**: Backend can't connect to PostgreSQL

**Solution**:
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Restart PostgreSQL
docker compose restart postgres

# Check logs
docker compose logs postgres
```

### Model Service Won't Start

**Problem**: Model service fails to load

**Solution**:
1. Check if model checkpoint exists:
   ```bash
   ls backend/model/checkpoints/final_model.pth
   ```
2. If missing, the system will use a default model (this is normal for first run)
3. Check logs:
   ```bash
   docker compose logs model-service
   ```

### Port Already in Use

**Problem**: "Port 5001 is already allocated"

**Solution**:
```bash
# Find process using the port (Windows)
netstat -ano | findstr :5001

# Kill the process or change the port in docker-compose.yml
```

---

## 📚 Additional Resources

- **Full Documentation**: See `documentation/` folder
- **API Reference**: `documentation/API_INTEGRATION.md`
- **Authentication Guide**: `documentation/AUTH_SETUP_GUIDE.md`
- **Frontend Guide**: `documentation/FRONTEND_README.md`
- **Troubleshooting**: `documentation/TROUBLESHOOTING_MODEL_SERVICE.md`

---

## 🆘 Getting Help

### Common Issues

1. **CORS Errors**: Check `CORS_ORIGINS` in `backend/.env`
2. **Authentication Failed**: Verify JWT_SECRET is set correctly
3. **No Traffic Data**: Wait 30-60 seconds for traffic simulation to start
4. **Slow Performance**: Increase Docker memory allocation to 4GB+

### Support Channels

- **Documentation**: Check the `documentation/` folder first
- **Issues**: Open an issue on GitHub
- **Email**: Contact the maintainers

---

## ✅ Success Checklist

Before you finish, verify:

- [ ] All Docker services are running (`docker compose ps`)
- [ ] Backend API responds to health check
- [ ] Frontend loads at http://localhost:8080
- [ ] You can log in with admin credentials
- [ ] Dashboard shows real-time metrics
- [ ] Alerts are being generated
- [ ] No errors in `docker compose logs`

---

## 🎉 You're All Set!

Your Adaptive IDS system is now running! 

**What's happening behind the scenes:**
1. 📡 **Traffic Simulator** is generating network packets
2. 🔍 **Feature Extractor** is processing flows
3. 🤖 **Model Service** is classifying traffic
4. 🚨 **Alerting Service** is monitoring for threats
5. 📊 **Dashboard** is displaying real-time metrics

**Next Recommended Steps:**
1. Explore the Dashboard and familiarize yourself with the UI
2. Review the documentation in `documentation/`
3. Try triggering some test alerts
4. Configure email notifications
5. Set up Grafana dashboards for deeper insights

---

**Built with ❤️ for cybersecurity professionals**

Need help? Check out our [comprehensive documentation](./documentation/README.md) or open an issue on GitHub.
