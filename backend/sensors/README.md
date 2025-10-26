# Sensors Module

This module handles packet capture and initial data ingestion into the streaming pipeline.

## Overview

The sensors module is responsible for:
- Capturing network packets from interfaces
- Converting packets to structured events
- Producing events to Kafka topics

For **development**, we use pyshark/Npcap for Windows-compatible packet capture.
For **production**, use Zeek or Suricata for robust, scalable packet processing.

## Components

### `pcap_producer.py`
Windows-compatible packet capture producer using pyshark with Npcap backend.

**Features:**
- Live packet capture from network interfaces
- Minimal metadata extraction (5-tuple + timestamp + length)
- Kafka producer with LZ4 compression and idempotence
- Graceful shutdown handling (Ctrl+C)
- BPF filtering support
- Delivery callbacks and statistics

**Output Schema (JSON to `raw.packets`):**
```json
{
  "ts": 1729468800.123456,
  "src_ip": "192.168.1.100",
  "dst_ip": "10.0.0.50",
  "src_port": 54321,
  "dst_port": 80,
  "proto": "TCP",
  "raw_len": 1500
}
```

## Windows Setup

### Prerequisites

1. **Install Npcap** (required for packet capture on Windows):
   - Download from: https://npcap.com/#download
   - During installation, check these options:
     - ✅ "Install Npcap in WinPcap API-compatible Mode"
     - ✅ "Support raw 802.11 traffic"
   - Restart after installation

2. **Install Wireshark** (includes tshark, required by pyshark):
   - Download from: https://www.wireshark.org/download.html
   - Install with default options
   - Add to PATH: `C:\Program Files\Wireshark`

3. **Verify tshark is accessible:**
   ```cmd
   tshark --version
   ```
   Should output: `TShark (Wireshark) 4.x.x`

### Python Dependencies

Install pyshark and confluent-kafka:
```cmd
pip install pyshark confluent-kafka[avro]
```

Or install all backend dependencies:
```cmd
pip install -r backend/requirements.txt
```

### List Available Interfaces

To see available network interfaces:
```cmd
tshark -D
```

Example output:
```
1. \Device\NPF_{GUID} (Wi-Fi)
2. \Device\NPF_{GUID} (Ethernet)
3. \Device\NPF_{GUID} (Loopback)
```

Use the interface name or number with `PCAP_IFACE` environment variable.

## Configuration

Environment variables (add to `backend/.env`):

```bash
# Kafka Configuration
KAFKA_BROKERS=localhost:9092
PACKETS_TOPIC=raw.packets

# Packet Capture Configuration
PCAP_IFACE=Wi-Fi                    # Interface name (or number like "1")
PCAP_FILTER=tcp or udp              # Optional BPF filter
```

### BPF Filter Examples

Capture only specific traffic:
```bash
# HTTP/HTTPS traffic
PCAP_FILTER="tcp port 80 or tcp port 443"

# All TCP traffic
PCAP_FILTER="tcp"

# Specific host
PCAP_FILTER="host 192.168.1.100"

# Exclude local traffic
PCAP_FILTER="not net 127.0.0.0/8"

# SSH and DNS
PCAP_FILTER="tcp port 22 or udp port 53"
```

## Usage

### Basic Usage

1. **Start Kafka** (if not already running):
   ```cmd
   docker compose up -d kafka
   ```

2. **Set environment variables** (or use `.env` file):
   ```cmd
   set KAFKA_BROKERS=localhost:9092
   set PACKETS_TOPIC=raw.packets
   set PCAP_IFACE=Wi-Fi
   ```

3. **Run the producer**:
   ```cmd
   cd backend
   python -m sensors.pcap_producer
   ```

### With BPF Filter

Capture only HTTP/HTTPS traffic:
```cmd
set PCAP_FILTER=tcp port 80 or tcp port 443
python -m sensors.pcap_producer
```

### Monitor Kafka Topic

In another terminal, consume messages to verify:
```cmd
docker exec -it adaptive_ids_kafka kafka-console-consumer ^
  --bootstrap-server localhost:9092 ^
  --topic raw.packets ^
  --from-beginning ^
  --property print.key=true
```

Expected output:
```
192.168.1.100:54321:10.0.0.50:80:TCP	{"ts": 1729468800.123, "src_ip": "192.168.1.100", ...}
```

## Graceful Shutdown

Press **Ctrl+C** to gracefully shutdown the producer.

Output:
```
2025-01-15 10:30:45 - INFO - Keyboard interrupt received
2025-01-15 10:30:45 - INFO - Shutting down producer...
2025-01-15 10:30:46 - INFO - ============================================================
2025-01-15 10:30:46 - INFO - Final Statistics:
2025-01-15 10:30:46 - INFO -   Packets Captured: 5000
2025-01-15 10:30:46 - INFO -   Packets Produced: 4998
2025-01-15 10:30:46 - INFO -   Packets Failed:   2
2025-01-15 10:30:46 - INFO - ============================================================
```

## Troubleshooting

### Issue: "tshark not found"

**Solution:**
- Ensure Wireshark is installed
- Add to PATH: `C:\Program Files\Wireshark`
- Restart terminal/VS Code

### Issue: "No module named 'pyshark'"

**Solution:**
```cmd
pip install pyshark
```

### Issue: "Npcap not found" or "No interfaces found"

**Solution:**
- Install Npcap from https://npcap.com/
- Check "WinPcap API-compatible Mode" during installation
- Restart Windows

### Issue: "Permission denied" on interface

**Solution:**
- Run terminal as Administrator
- Or use a non-admin accessible interface (e.g., loopback)

### Issue: No packets captured

**Possible causes:**
1. Wrong interface selected → Use `tshark -D` to list interfaces
2. BPF filter too restrictive → Remove `PCAP_FILTER` or use `PCAP_FILTER=tcp`
3. No network traffic → Generate traffic (ping, browse web)
4. Firewall blocking → Temporarily disable Windows Firewall

### Issue: Kafka connection failed

**Solution:**
- Verify Kafka is running: `docker compose ps`
- Check `KAFKA_BROKERS` is correct (default: `localhost:9092`)
- Test connection: `docker exec adaptive_ids_kafka kafka-topics --list --bootstrap-server localhost:9092`

## Performance

### Statistics

The producer logs statistics every 1000 packets:
```
INFO - Captured 1000 packets
INFO - Produced 1000 packets (captured: 1000, failed: 0)
```

### Typical Throughput

- **Low traffic**: 10-100 packets/sec
- **Medium traffic**: 100-1,000 packets/sec
- **High traffic**: 1,000-10,000 packets/sec

The producer can handle 10k+ packets/sec on modern hardware.

### Optimization Tips

1. **Use BPF filters** to reduce unnecessary packets
2. **Increase Kafka batch size** if producing millions of packets
3. **Use multiple producers** across interfaces for higher throughput
4. **Consider Zeek/Suricata** for production deployments

## Linux/WSL2 Alternative

For Linux or WSL2 environments:

### Install libpcap

```bash
# Ubuntu/Debian
sudo apt-get install libpcap-dev

# CentOS/RHEL
sudo yum install libpcap-devel
```

### Run with sudo (if needed)

```bash
sudo -E python -m sensors.pcap_producer
```

The `-E` flag preserves environment variables.

## Production Deployment

**⚠️ This producer is for development only.**

For production, use:
- **Zeek** (recommended): Full-featured network security monitor
- **Suricata**: IDS/IPS with high-performance packet processing
- **Packetbeat**: Lightweight shipper for network data

These tools provide:
- Higher performance (10 Gbps+)
- Protocol parsing (HTTP, DNS, TLS, etc.)
- Anomaly detection
- Flow reassembly
- Mature logging and integration

## Development Notes

### Adding Custom Fields

To extract additional packet metadata, modify `_extract_packet_metadata()`:

```python
def _extract_packet_metadata(self, packet) -> Optional[Dict]:
    metadata = {...}
    
    # Add TTL
    if hasattr(packet, 'ip'):
        metadata['ttl'] = int(packet.ip.ttl)
    
    # Add TCP flags
    if hasattr(packet, 'tcp'):
        metadata['tcp_flags'] = packet.tcp.flags
    
    return metadata
```

### Testing with Pcap Files

For testing with pcap files, use `pyshark.FileCapture`:

```python
capture = pyshark.FileCapture('sample.pcap')
for packet in capture:
    metadata = self._extract_packet_metadata(packet)
    self._produce_packet(metadata)
```

## Next Steps

After sensor implementation:
1. **Implement feature extractor** (`backend/stream/feature_extractor.py`) to consume `raw.packets` and produce `flows.features`
2. **Test end-to-end flow**: sensor → Kafka → feature extractor → model inference
3. **Add monitoring** (Prometheus metrics for packet rate, Kafka lag)
4. **Production planning** (Zeek/Suricata deployment strategy)
