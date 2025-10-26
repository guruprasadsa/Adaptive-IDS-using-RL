# 🚀 Real-Time Traffic Processing - Quick Start

**Last Updated**: 2025-10-25  
**Status**: Production Ready ✅

---

## ⚡ Quick Start (3 Commands)

### Step 1: Start Docker Services
```bash
docker-compose up -d
```
Wait 30 seconds for all services to initialize.

### Step 2: Start Packet Capture (Terminal 1)
```powershell
cd backend
$env:PYTHONPATH = "C:\AIML\Projects\adaptive-ids-v-2.0\backend"
python -m sensors.pcap_producer
```
**Leave running** - captures network packets continuously

### Step 3: Start Feature Extraction (Terminal 2)
```powershell
cd backend
$env:PYTHONPATH = "C:\AIML\Projects\adaptive-ids-v-2.0\backend"
python -m stream.feature_extractor
```
**Leave running** - processes packets into features

### Step 4: Open Dashboard
```
http://localhost:5173
```
Login: `admin` / (your password from create-test-user.py)

---

## 🎯 What You'll See

### In Packet Producer Terminal:
```
Captured 100 packets, sent 98 to Kafka...
Captured 200 packets, sent 196 to Kafka...
Captured 300 packets, sent 294 to Kafka...
```

### In Feature Extractor Terminal:
```
Loaded StandardScaler with 97,547 samples
Subscribed to topic: raw.packets
Processing packet...
Active flows: 15, Completed flows: 5
Scaler updated, total samples: 97,552
```

### In Frontend Dashboard:
- **Traffic Chart**: Live updates every few seconds
- **Alert Feed**: New alerts appear in real-time
- **Statistics**: Alert counts update live
- **Latest Alerts**: Stream of DDoS, PortScan, etc.

---

## 🔍 Verify Everything Works

Run the test script:
```bash
python test_realtime_flow.py
```

Expected output:
```
✅ Docker Services Running (11/11)
✅ Kafka Topics Active
   - raw.packets: 2,011 messages
   - flows.features: 2,011 messages
   - alerts: 4 messages
✅ Model Service Ready (model loaded)
✅ Backend API Accessible
✅ SSE Endpoint Streaming
✅ Frontend Available
```

---

## 📊 Quick Status Checks

### Check Alerts in Database
```bash
docker exec adaptive_ids_postgres psql -U adaptive_ids -d adaptive_ids \
  -c "SELECT id, class_name, severity, confidence FROM alerts ORDER BY created_at DESC LIMIT 5;"
```

### Check Kafka Messages
```bash
# Total messages in raw.packets
docker exec adaptive_ids_kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 --topic raw.packets | awk -F: '{sum += $3} END {print sum}'
```

### Check Model Health
```bash
curl http://localhost:8000/health
```

### Check Backend SSE
```bash
curl -N "http://localhost:5001/api/events?token=test"
```
(Will stream events - press Ctrl+C to stop)

---

## 🛑 Stop Services

### Stop Producers (Ctrl+C in terminals)
1. Terminal 1 (Packet Producer): `Ctrl+C`
2. Terminal 2 (Feature Extractor): `Ctrl+C`

### Stop Docker
```bash
docker-compose down
```

Or to keep data:
```bash
docker-compose stop
```

---

## 🔧 Troubleshooting

### No Packets Captured?
```bash
# List network interfaces
tshark -D

# Update interface in pcap_producer.py
CAPTURE_INTERFACE = 6  # Change to your interface number
```

### Features Not Processing?
```bash
# Check raw.packets has messages
docker exec adaptive_ids_kafka kafka-topics --list --bootstrap-server localhost:9092

# Check feature extractor logs
# Look for "Loaded StandardScaler" message
```

### No Alerts Generated?
```bash
# Check model is loaded
curl http://localhost:8000/model/info

# Check alerting service logs
docker logs adaptive_ids_alerting

# Verify predictions in Kafka
docker exec adaptive_ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic model.predictions \
  --from-beginning --max-messages 5
```

### Frontend Not Updating?
```bash
# Check SSE connection in browser DevTools Console
# Should see: "SSE connection opened"

# Check backend logs
docker logs adaptive_ids_backend -f

# Verify token is valid
# Login again to get fresh token
```

---

## 📈 Generate Traffic for Testing

### Option 1: Normal Browsing
Just browse the internet normally - the packet producer will capture:
- Web traffic (HTTP/HTTPS)
- DNS queries
- SSH connections
- Any network activity

### Option 2: Generate Test Traffic
```bash
# Generate HTTP traffic
curl http://example.com

# Generate multiple requests
for i in {1..10}; do curl http://example.com; done

# Generate DNS traffic
nslookup google.com
```

### Option 3: Use Training Data
```bash
# Replay PCAP files (if you have them)
tcpreplay -i YourInterface file.pcap
```

---

## 🎯 What Gets Classified

The model classifies traffic into 10 categories:

1. **Benign** (normal traffic) - not alerted
2. **Botnet** - HIGH severity alert
3. **DDoS** - HIGH severity alert
4. **FTP-Patator** (brute force) - MEDIUM severity
5. **Infiltration** - CRITICAL severity
6. **PortScan** - MEDIUM severity
7. **SSH-Patator** (brute force) - MEDIUM severity
8. **Web Attack - Brute Force** - HIGH severity
9. **Web Attack - SQL Injection** - CRITICAL severity
10. **Web Attack - XSS** - HIGH severity

Only malicious traffic (2-10) generates alerts.

---

## 📊 Expected Performance

| Metric | Value |
|--------|-------|
| Packet Capture Rate | 100-150 packets/sec |
| Feature Extraction Rate | ~100 flows/sec |
| Model Inference Latency | <100ms |
| End-to-End Latency | <1 second |
| Alert Generation | Real-time |
| Frontend Update Frequency | Every 2-5 seconds |

---

## 🔐 Security Notes

- **Packet capture requires Administrator privileges** on Windows
- SSE endpoint uses JWT authentication (token in query param)
- Database credentials in `docker-compose.yml`
- Model weights in `backend/model/checkpoints/`

---

## 📚 Full Documentation

For complete details, see:
- [REALTIME_TRAFFIC_COMPLETE.md](./REALTIME_TRAFFIC_COMPLETE.md) - Full documentation
- [OBSERVABILITY_QUICKREF.md](./OBSERVABILITY_QUICKREF.md) - Monitoring
- [FRONTEND_EXECUTIVE_SUMMARY.md](./FRONTEND_EXECUTIVE_SUMMARY.md) - Frontend guide

---

## ✅ Quick Checklist

Before starting:
- [ ] Docker Desktop running
- [ ] Npcap installed (for packet capture)
- [ ] Network interface identified
- [ ] Backend dependencies installed (`pip install -r requirements.txt`)
- [ ] Frontend dependencies installed (`cd frontend && npm install`)

Runtime:
- [ ] Docker services: `docker ps` shows 11 containers
- [ ] Packet producer running in Terminal 1
- [ ] Feature extractor running in Terminal 2
- [ ] Frontend accessible at http://localhost:5173
- [ ] SSE connected (check browser console)
- [ ] Alerts appearing in dashboard

---

**Need Help?** Check logs:
```bash
docker logs adaptive_ids_backend -f       # Backend API
docker logs adaptive_ids_model_service -f # Model Service
docker logs adaptive_ids_alerting -f      # Alerting Service
docker logs adaptive_ids_kafka -f         # Kafka
```

---

**Status**: ✅ **PRODUCTION READY**  
**Version**: v2.0  
**Last Test**: 2025-10-25 (73 alerts generated successfully)
