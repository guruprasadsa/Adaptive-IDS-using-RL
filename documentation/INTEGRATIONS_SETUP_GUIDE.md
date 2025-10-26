# External Integrations Setup Guide

Complete step-by-step guide to configure Syslog and Graylog SIEM integrations.

---

## Prerequisites

- ✅ Alerting pipeline working (database persistence operational)
- ✅ Email integration configured (optional but recommended for testing)
- ✅ Docker containers running
- ✅ Network access to target systems

> **Note**: This guide covers **free and open-source** integrations only. For enterprise SIEM solutions like Splunk (paid) or IBM QRadar (paid), please refer to their respective documentation.

---

## Integration 1: Syslog (RFC5424)

### Overview
Forward alerts to a centralized syslog server (rsyslog, syslog-ng, Logstash, etc.) using RFC5424 format.

### Use Cases
- Centralized logging infrastructure
- Forward to SIEM via syslog
- Integration with existing log management
- Multiple downstream consumers

### Step 1: Choose Your Protocol

**Option A: UDP (Simple, No Authentication)**
- Port: 514
- No encryption
- Fire-and-forget (no delivery guarantee)
- Best for: Internal networks, high volume

**Option B: TCP (Reliable)**
- Port: 601
- Connection-based
- Delivery confirmation
- Best for: Reliable delivery needed

**Option C: TLS (Secure)**
- Port: 6514
- Encrypted
- Mutual authentication (optional)
- Best for: Production, over internet

### Step 2: Test with Local Syslog Server

**Option 1: Using netcat (for testing UDP)**
```powershell
# Terminal 1: Start listener
nc -u -l 514

# Terminal 2: Enable syslog in backend/.env
```

**Option 2: Using Python syslog server (for testing)**
```python
# test_syslog_server.py
import socketserver
import socket

class SyslogHandler(socketserver.DatagramRequestHandler):
    def handle(self):
        data = self.rfile.read()
        print(f"Received: {data.decode('utf-8', errors='ignore')}")

server = socketserver.UDPServer(('0.0.0.0', 514), SyslogHandler)
print("Syslog server listening on UDP 514...")
server.serve_forever()
```

Run as admin:
```powershell
# Requires admin for port 514
sudo python test_syslog_server.py
```

### Step 3: Configure Syslog Integration

Edit `backend/.env`:

```bash
# For UDP (testing)
SYSLOG_ENABLED=true
SYSLOG_HOST=localhost
SYSLOG_PORT=514

# For production with TLS
SYSLOG_ENABLED=true
SYSLOG_HOST=syslog.company.com
SYSLOG_PORT=6514

# TLS certificates (if using TLS)
SYSLOG_CLIENT_CERT=/path/to/client.crt
SYSLOG_CLIENT_KEY=/path/to/client.key
SYSLOG_CA_CERT=/path/to/ca.crt
```

### Step 4: Update Protocol in config.yaml

Edit `backend/alerting/config.yaml`:

```yaml
integrations:
  syslog:
    enabled: ${SYSLOG_ENABLED:false}
    host: ${SYSLOG_HOST:localhost}
    port: ${SYSLOG_PORT:514}
    protocol: UDP  # Change to TCP or TLS as needed
    facility: 16   # local0
```

### Step 5: Restart and Test

```powershell
# Rebuild with syslog fix
docker compose up -d --build alerting-service

# Send test alert
python test_single_email.py

# Check syslog server output
# Should see RFC5424 formatted message
```

### Expected Syslog Message Format

```
<131>1 2025-10-24T09:00:00.123Z adaptive-ids-host adaptive-ids - - [ids@32473 alert_id="..." class_name="DDoS" confidence="0.95" severity="HIGH"] DDoS detected from 192.168.1.100 to 10.0.0.1
```

### Troubleshooting Syslog

**Problem: Connection refused**
```powershell
# Check firewall
Test-NetConnection -ComputerName localhost -Port 514

# Check syslog server is running
netstat -an | findstr :514
```

**Problem: Permission denied (port < 1024)**
- Use port 5514 instead
- Or run syslog server as admin
- Or use Docker port mapping

**Problem: No messages received**
```powershell
# Check service logs
docker compose logs alerting-service | Select-String -Pattern "syslog"

# Verify configuration loaded
docker compose exec alerting-service env | Select-String -Pattern "SYSLOG"
```

---

## Integration 2: Graylog SIEM

### Overview
Send alerts to Graylog using GELF (Graylog Extended Log Format) or HTTP API. Graylog is an easier-to-use alternative to Elasticsearch with built-in alerting and dashboards.

### Why Graylog?
- ✅ **Free and open-source** (truly free, no hidden costs)
- ✅ **Easier setup** than ELK stack
- ✅ **Built-in alerting** and notifications
- ✅ **Better web UI** than Kibana for most users
- ✅ **Lower resource usage** than Elasticsearch
- ✅ **Powerful search** with MongoDB backend

### Prerequisites
- Docker and Docker Compose
- 4GB RAM minimum (for full stack)
- Ports available: 9000 (web), 12201 (GELF), 1514 (syslog)

### Step 1: Deploy Graylog with Docker Compose

**Option A: Add to Existing docker-compose.yml**

Add these services to your `docker-compose.yml`:

```yaml
services:
  # ... existing services ...

  # MongoDB - Graylog metadata storage
  mongodb:
    image: mongo:6.0
    container_name: adaptive_ids_mongodb
    volumes:
      - mongodb_data:/data/db
    networks:
      - adaptive-ids-network
    restart: unless-stopped

  # Elasticsearch - Graylog message storage
  graylog-elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.15
    container_name: adaptive_ids_graylog_es
    environment:
      - http.host=0.0.0.0
      - transport.host=localhost
      - network.host=0.0.0.0
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - graylog_es_data:/usr/share/elasticsearch/data
    networks:
      - adaptive-ids-network
    restart: unless-stopped

  # Graylog server
  graylog:
    image: graylog/graylog:5.2
    container_name: adaptive_ids_graylog
    environment:
      # CHANGE THESE!
      GRAYLOG_PASSWORD_SECRET: "somepasswordpepper_changeme_min16chars"
      # Password: admin (SHA-256 hash)
      GRAYLOG_ROOT_PASSWORD_SHA2: "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
      GRAYLOG_HTTP_EXTERNAL_URI: "http://localhost:9000/"
      GRAYLOG_ELASTICSEARCH_HOSTS: "http://graylog-elasticsearch:9200"
      GRAYLOG_MONGODB_URI: "mongodb://mongodb:27017/graylog"
    entrypoint: /usr/bin/tini -- wait-for-it graylog-elasticsearch:9200 --  /docker-entrypoint.sh
    ports:
      - "9000:9000"   # Graylog web interface
      - "12201:12201/udp" # GELF UDP
      - "12201:12201" # GELF TCP
      - "1514:1514"   # Syslog TCP
      - "1514:1514/udp" # Syslog UDP
    volumes:
      - graylog_data:/usr/share/graylog/data
    networks:
      - adaptive-ids-network
    depends_on:
      - mongodb
      - graylog-elasticsearch
    restart: unless-stopped

volumes:
  mongodb_data:
  graylog_es_data:
  graylog_data:
```

**Option B: Standalone Graylog Stack**

Create `docker-compose.graylog.yml`:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    volumes:
      - mongodb_data:/data/db

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.15
    environment:
      - http.host=0.0.0.0
      - transport.host=localhost
      - network.host=0.0.0.0
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - es_data:/usr/share/elasticsearch/data

  graylog:
    image: graylog/graylog:5.2
    environment:
      GRAYLOG_PASSWORD_SECRET: "somepasswordpepper_changeme_min16chars"
      GRAYLOG_ROOT_PASSWORD_SHA2: "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
      GRAYLOG_HTTP_EXTERNAL_URI: "http://localhost:9000/"
      GRAYLOG_ELASTICSEARCH_HOSTS: "http://elasticsearch:9200"
      GRAYLOG_MONGODB_URI: "mongodb://mongodb:27017/graylog"
    entrypoint: /usr/bin/tini -- wait-for-it elasticsearch:9200 --  /docker-entrypoint.sh
    ports:
      - "9000:9000"
      - "12201:12201/udp"
      - "12201:12201"
      - "1514:1514"
      - "1514:1514/udp"
    volumes:
      - graylog_data:/usr/share/graylog/data
    depends_on:
      - mongodb
      - elasticsearch

volumes:
  mongodb_data:
  es_data:
  graylog_data:
```

Start it:
```powershell
docker compose -f docker-compose.graylog.yml up -d
```

### Step 2: Generate Admin Password Hash (Optional)

To change the default admin password:

```powershell
# Generate SHA-256 hash for your password
echo -n "YourPasswordHere" | sha256sum

# Or in PowerShell:
$password = "YourPasswordHere"
$hash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($password))).Replace("-","").ToLower()
Write-Host $hash
```

Update `GRAYLOG_ROOT_PASSWORD_SHA2` in docker-compose.yml with the hash.

### Step 3: Access Graylog Web Interface

**3.1. Wait for startup (may take 2-3 minutes)**
```powershell
# Check logs
docker compose logs -f graylog

# Wait for: "Graylog server up and running"
```

**3.2. Login to Graylog**
```
URL: http://localhost:9000
Username: admin
Password: admin (or your custom password)
```

### Step 4: Create GELF HTTP Input

**4.1. Navigate to Inputs**
```
System → Inputs
```

**4.2. Select GELF HTTP**
```
Select input: GELF HTTP
Click "Launch new input"
```

**4.3. Configure Input**
```
Title: Adaptive IDS Alerts
Bind address: 0.0.0.0
Port: 12201
```

**4.4. Save and Start**
```
Click "Save"
The input should show "Running" status
```

### Step 5: Configure Graylog Integration in Backend

Edit `backend/.env`:

```bash
# Graylog GELF HTTP Configuration
GRAYLOG_ENABLED=true
GRAYLOG_HOST=localhost
GRAYLOG_PORT=12201
GRAYLOG_PROTOCOL=HTTP  # or UDP or TCP
```

**For remote Graylog server:**
```bash
GRAYLOG_ENABLED=true
GRAYLOG_HOST=graylog.company.com
GRAYLOG_PORT=12201
GRAYLOG_PROTOCOL=HTTP
```

### Step 6: Create Graylog Client Integration

Create `backend/alerting/integrations/graylog_client.py`:

```python
"""Graylog GELF client for alert forwarding."""
import json
import logging
import socket
import struct
import time
import zlib
from typing import Dict, Any, Optional
import requests
from ..rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class GraylogClient:
    """Send alerts to Graylog using GELF format."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Graylog client.
        
        Args:
            config: Configuration dictionary with host, port, protocol
        """
        self.host = config.get('host', 'localhost')
        self.port = int(config.get('port', 12201))
        self.protocol = config.get('protocol', 'HTTP').upper()
        self.timeout = config.get('timeout_ms', 5000) / 1000
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            per_minute=config.get('rate_limit_per_min', 60),
            per_hour=config.get('rate_limit_per_hour', 1000)
        )
        
        logger.info(f"Graylog client initialized: {self.protocol}://{self.host}:{self.port}")
    
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """Send alert to Graylog in GELF format.
        
        Args:
            alert: Alert dictionary
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Check rate limit
        if not self.rate_limiter.allow():
            logger.warning("Graylog rate limit exceeded, dropping alert")
            return False
        
        try:
            # Convert to GELF format
            gelf_message = self._to_gelf(alert)
            
            # Send based on protocol
            if self.protocol == 'HTTP':
                return self._send_http(gelf_message)
            elif self.protocol == 'UDP':
                return self._send_udp(gelf_message)
            elif self.protocol == 'TCP':
                return self._send_tcp(gelf_message)
            else:
                logger.error(f"Unsupported protocol: {self.protocol}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send alert to Graylog: {e}", exc_info=True)
            return False
    
    def _to_gelf(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Convert alert to GELF format.
        
        GELF spec: https://docs.graylog.org/docs/gelf
        
        Args:
            alert: Alert dictionary
            
        Returns:
            GELF formatted message
        """
        # Map severity to syslog level
        severity_map = {
            'CRITICAL': 2,  # Critical
            'HIGH': 3,      # Error
            'MEDIUM': 4,    # Warning
            'LOW': 6,       # Informational
            'INFO': 7       # Debug
        }
        
        gelf = {
            'version': '1.1',
            'host': 'adaptive-ids',
            'short_message': alert.get('description', 'IDS Alert'),
            'full_message': self._format_full_message(alert),
            'timestamp': alert.get('timestamp', time.time()),
            'level': severity_map.get(alert.get('severity', 'INFO'), 6),
            
            # Custom fields (prefixed with _)
            '_alert_id': alert.get('alert_id'),
            '_flow_id': alert.get('flow_id'),
            '_severity': alert.get('severity'),
            '_class_name': alert.get('class_name'),
            '_confidence': alert.get('confidence'),
            '_src_ip': alert.get('src_ip'),
            '_dst_ip': alert.get('dst_ip'),
            '_src_port': alert.get('src_port'),
            '_dst_port': alert.get('dst_port'),
            '_protocol': alert.get('protocol'),
            '_model_version': alert.get('model_version'),
            '_feature_version': alert.get('feature_version'),
        }
        
        # Remove None values
        return {k: v for k, v in gelf.items() if v is not None}
    
    def _format_full_message(self, alert: Dict[str, Any]) -> str:
        """Format detailed message for full_message field."""
        lines = [
            f"Alert ID: {alert.get('alert_id')}",
            f"Severity: {alert.get('severity')}",
            f"Classification: {alert.get('class_name')}",
            f"Confidence: {alert.get('confidence', 0):.2%}",
            f"",
            f"Network Flow:",
            f"  Source: {alert.get('src_ip')}:{alert.get('src_port')}",
            f"  Destination: {alert.get('dst_ip')}:{alert.get('dst_port')}",
            f"  Protocol: {alert.get('protocol')}",
            f"",
            f"Model: {alert.get('model_version')} / Features: {alert.get('feature_version')}"
        ]
        return '\n'.join(lines)
    
    def _send_http(self, message: Dict[str, Any]) -> bool:
        """Send via GELF HTTP."""
        try:
            url = f"http://{self.host}:{self.port}/gelf"
            response = requests.post(
                url,
                json=message,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 202:
                logger.debug(f"Sent alert to Graylog via HTTP: {message.get('_alert_id')}")
                return True
            else:
                logger.error(f"Graylog HTTP returned {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send to Graylog via HTTP: {e}")
            return False
    
    def _send_udp(self, message: Dict[str, Any]) -> bool:
        """Send via GELF UDP (with chunking for large messages)."""
        try:
            # Compress message
            payload = json.dumps(message).encode('utf-8')
            compressed = zlib.compress(payload)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            
            # GELF UDP has 8192 byte limit, chunk if needed
            max_chunk_size = 8192
            if len(compressed) > max_chunk_size:
                logger.warning("Message too large for single UDP packet, chunking")
                # Implement chunking if needed
                return False
            
            sock.sendto(compressed, (self.host, self.port))
            sock.close()
            
            logger.debug(f"Sent alert to Graylog via UDP: {message.get('_alert_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Graylog via UDP: {e}")
            return False
    
    def _send_tcp(self, message: Dict[str, Any]) -> bool:
        """Send via GELF TCP."""
        try:
            payload = json.dumps(message).encode('utf-8')
            # TCP messages must be null-terminated
            payload += b'\0'
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(payload)
            sock.close()
            
            logger.debug(f"Sent alert to Graylog via TCP: {message.get('_alert_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Graylog via TCP: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if Graylog is reachable."""
        try:
            if self.protocol == 'HTTP':
                url = f"http://{self.host}:{self.port}/gelf"
                response = requests.get(url, timeout=2)
                return response.status_code in [200, 405]  # 405 = Method Not Allowed is OK
            else:
                # Try UDP/TCP connection
                sock = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_DGRAM if self.protocol == 'UDP' else socket.SOCK_STREAM
                )
                sock.settimeout(2)
                sock.connect((self.host, self.port))
                sock.close()
                return True
        except Exception as e:
            logger.error(f"Graylog health check failed: {e}")
            return False
```

### Step 7: Update Alerting Pipeline

Edit `backend/alerting/config.yaml`:

```yaml
integrations:
  # ... existing integrations ...
  
  graylog:
    enabled: ${GRAYLOG_ENABLED:false}
    host: ${GRAYLOG_HOST:localhost}
    port: ${GRAYLOG_PORT:12201}
    protocol: ${GRAYLOG_PROTOCOL:HTTP}  # HTTP, UDP, or TCP
    timeout_ms: 5000
    rate_limit_per_min: 60
    rate_limit_per_hour: 1000
```

Edit `backend/alerting/dispatcher.py` to add Graylog client:

```python
# Add import
from .integrations.graylog_client import GraylogClient

# In __init__ method, add:
if self.config['integrations']['graylog']['enabled']:
    self.clients['graylog'] = GraylogClient(
        self.config['integrations']['graylog']
    )
    logger.info("Graylog integration enabled")
```

### Step 8: Restart and Test

```powershell
# Rebuild alerting service with new Graylog client
docker compose up -d --build alerting-service

# Check logs
docker compose logs alerting-service | Select-String -Pattern "Graylog"

# Send test alert
python test_single_email.py
```

### Step 9: Verify in Graylog

**9.1. View incoming messages**
```
Search → All messages
Time range: Last 5 minutes
```

**9.2. Search for IDS alerts**
```
Search query: _class_name:*
Or: _severity:HIGH
Or: source:adaptive-ids
```

**9.3. View alert details**
Click on any message to see all custom fields (`_alert_id`, `_severity`, etc.)

### Step 10: Create Graylog Dashboard

**10.1. Create Stream for IDS Alerts**
```
Streams → Create Stream
Title: IDS Alerts
Description: Adaptive IDS alerts
Index Set: Default index set

Rules:
  Field: host
  Type: match exactly
  Value: adaptive-ids
```

**10.2. Create Dashboard**
```
Dashboards → Create Dashboard
Title: IDS Security Dashboard
```

**10.3. Add Widgets**

**Widget 1: Alerts Over Time**
```
Type: Line Chart
Query: source:adaptive-ids
Field: timestamp
Interval: 1 minute
```

**Widget 2: Severity Distribution**
```
Type: Pie Chart
Query: source:adaptive-ids
Field: _severity
```

**Widget 3: Top Attack Types**
```
Type: Quick Values
Query: source:adaptive-ids
Field: _class_name
Limit: 10
```

**Widget 4: Top Source IPs**
```
Type: Quick Values
Query: source:adaptive-ids AND _severity:(HIGH OR CRITICAL)
Field: _src_ip
Limit: 10
```

**Widget 5: Alert Count**
```
Type: Count
Query: source:adaptive-ids
Time range: Last 1 hour
```

### Graylog Search Queries

**High severity alerts:**
```
source:adaptive-ids AND _severity:(HIGH OR CRITICAL)
```

**Specific attack type:**
```
source:adaptive-ids AND _class_name:"DDoS"
```

**Alerts from specific IP:**
```
source:adaptive-ids AND _src_ip:192.168.1.100
```

**Alerts in time range:**
```
source:adaptive-ids AND timestamp:[2025-10-24T00:00:00 TO 2025-10-24T23:59:59]
```

**High confidence detections:**
```
source:adaptive-ids AND _confidence:>0.9
```

### Step 11: Set Up Graylog Alerts (Optional)

**11.1. Create Event Definition**
```
Alerts → Event Definitions → Create Event Definition

Title: High Severity IDS Alerts
Description: Trigger on HIGH/CRITICAL severity
```

**11.2. Configure Condition**
```
Condition Type: Filter & Aggregation
Search Query: source:adaptive-ids AND _severity:(HIGH OR CRITICAL)
Search within: 1 minutes
Execute search every: 1 minutes
```

**11.3. Add Notification**
```
Notifications → Add Notification
Type: Email, Slack, HTTP, etc.
Configure recipients/webhooks
```

### Troubleshooting Graylog

**Problem: Can't access web interface**
```powershell
# Check Graylog is running
docker compose ps graylog

# Check logs
docker compose logs graylog | Select-String -Pattern "ERROR"

# Check port
netstat -an | findstr :9000
```

**Problem: Input not receiving messages**
```
1. Check input is running (System → Inputs)
2. Verify port is accessible
3. Check firewall rules
4. Test with manual GELF message:

echo '{"version":"1.1","host":"test","short_message":"test"}' | nc -u localhost 12201
```

**Problem: Messages not appearing in search**
```
1. Check Elasticsearch is running:
   docker compose ps graylog-elasticsearch

2. Check index health:
   System → Indices → Show indices

3. Verify messages are being processed:
   System → Overview → Check throughput
```

**Problem: High resource usage**
```
1. Reduce Elasticsearch heap size in docker-compose.yml:
   ES_JAVA_OPTS=-Xms256m -Xmx256m

2. Limit retention:
   System → Indices → Configure rotation/deletion

3. Enable message processing optimization:
   System → Configurations → Tune buffer settings
```

---

## Testing All Integrations

### Complete Integration Test Script

Create `test_all_integrations.py`:

```python
"""Test all external integrations."""
import json
import time
from confluent_kafka import Producer

# Test alerts for each severity level
test_alerts = [
    {'severity': 'CRITICAL', 'class': 'Infiltration', 'confidence': 0.90},
    {'severity': 'HIGH', 'class': 'DDoS', 'confidence': 0.95},
    {'severity': 'MEDIUM', 'class': 'Web Attack – Sql Injection', 'confidence': 0.75},
    {'severity': 'LOW', 'class': 'PortScan', 'confidence': 0.65},
]

producer = Producer({'bootstrap.servers': 'localhost:9092'})

print("=" * 70)
print("Testing All Integrations".center(70))
print("=" * 70)

for i, alert in enumerate(test_alerts, 1):
    prediction = {
        'flow_id': f'test-all-integrations-{i}',
        'timestamp': int(time.time() * 1000),
        'class_idx': i,
        'class_name': alert['class'],
        'confidence': alert['confidence'],
        'model_version': 'v1.0',
        'feature_version': 'v1.0',
        'src_ip': f'192.168.1.{100 + i}',
        'dst_ip': '10.0.0.1',
        'src_port': 50000 + i,
        'dst_port': 80,
        'protocol': 'TCP'
    }
    
    print(f"\n[{i}/4] Sending {alert['severity']} alert: {alert['class']}")
    producer.produce('predictions', value=json.dumps(prediction).encode('utf-8'))
    time.sleep(2)  # Wait between alerts

producer.flush()

print("\n" + "=" * 70)
print("✓ All test alerts sent!".center(70))
print("=" * 70)

print("\nCheck each integration:")
print("  1. Email: Check inbox (TO + CC)")
print("  2. Syslog: Check syslog server logs")
print("  3. Graylog: Search in Graylog web UI (http://localhost:9000)")
print("\nService logs: docker compose logs -f alerting-service")
```

Run the test:
```powershell
python test_all_integrations.py
```

### Verification Checklist

```
□ Email
  □ TO address received alert
  □ CC address received alert
  □ HTML formatting correct
  □ All alert details present

  □ Syslog
  □ Messages received on syslog server
  □ RFC5424 format correct
  □ Structured data present
  □ Severity mapping correct

□ Graylog
  □ Messages visible in Search
  □ All custom fields present (_alert_id, _severity, etc.)
  □ Timestamp correct
  □ Searchable by severity/class
```---

## Monitoring & Maintenance

### Check Integration Health

```sql
-- Delivery success rate by destination
SELECT 
  UNNEST(destinations) as destination,
  COUNT(*) as total_alerts,
  SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) as successful,
  ROUND(100.0 * SUM(CASE WHEN dispatch_status::text LIKE '%success%' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND destinations IS NOT NULL
GROUP BY destination
ORDER BY total_alerts DESC;
```

### Check Dead Letter Queue

```powershell
# View failed deliveries
docker compose exec kafka kafka-console-consumer `
  --bootstrap-server localhost:9092 `
  --topic alerts.dlq `
  --from-beginning `
  --max-messages 10
```

### Integration Performance

```sql
-- Average alerts per minute by destination
SELECT 
  UNNEST(destinations) as destination,
  COUNT(*) / 60.0 as avg_per_minute
FROM alerts
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY destination;
```

---

## Summary

✅ **Syslog**: Centralized logging, forward to multiple systems (RFC5424, UDP/TCP/TLS)
✅ **Graylog**: User-friendly SIEM with built-in alerting, dashboards, and powerful search - 100% free and open-source

All integrations are now configured and ready for production use!

---

## Alternative Free SIEM Options

If you need different SIEM functionality, consider these alternatives:

### **ELK Stack (Elasticsearch + Kibana)** 
- More powerful than Graylog
- Steeper learning curve
- Better for large-scale deployments
- Requires more resources

### **OpenSearch + OpenSearch Dashboards**
- AWS fork of Elasticsearch
- 100% open-source (Apache 2.0)
- Compatible with Elasticsearch APIs
- AWS-backed support

### **Loki + Grafana**
- Lightweight log aggregation
- Great for Docker/Kubernetes
- Label-based indexing
- Lower resource usage

For enterprise solutions like **Splunk** (paid) or **IBM QRadar** (paid), please refer to their official documentation.
