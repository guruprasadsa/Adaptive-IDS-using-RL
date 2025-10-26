# Stream Processing Module

Real-time flow feature extraction for the Adaptive IDS system.

## Overview

The stream processing module consumes raw packet metadata from Kafka, aggregates packets into bidirectional flows, computes 41 CICFlowMeter-compatible features, applies online normalization, and publishes normalized flow features for ML model inference.

## Architecture

```
Kafka: raw.packets
        ↓
    Flow Aggregator
    (5-tuple tracking)
        ↓
  Feature Computation
  (41 CIC features)
        ↓
 Online Normalization
 (StandardScaler)
        ↓
Kafka: flows.features
```

## Components

### 1. feature_extractor.py

Main stream processor that:
- Consumes `raw.packets` topic
- Aggregates packets into flows using 5-tuple (src_ip, dst_ip, src_port, dst_port, protocol)
- Tracks bidirectional flow statistics (forward/backward)
- Expires flows based on active timeout (60s) and idle timeout (15s)
- Computes 41 CICFlowMeter-compatible features
- Applies incremental StandardScaler normalization
- Publishes to `flows.features` topic

### 2. Flow Aggregation

**Flow Identification:**
- 5-tuple: source IP, destination IP, source port, destination port, protocol
- Bidirectional: packets in both directions belong to same flow
- Canonical ordering: lower IP:port first ensures consistent flow ID

**Timeouts:**
- **Active Timeout (60s)**: Maximum flow duration regardless of activity
- **Idle Timeout (15s)**: Maximum time between packets before flow expires

### 3. Feature Computation

41 features compatible with CIC-IDS-2017/2018 datasets:

**Basic (1-5):** Duration, forward/backward packet counts, forward/backward byte counts

**Packet Length Stats (6-13):** Min/max/mean/std for forward and backward packet lengths

**Rate Features (14-15):** Bytes per second, packets per second

**Inter-Arrival Time (16-23):** Mean/std/max/min IAT for forward and backward

**TCP Flags (24-35):** FIN, SYN, RST, PSH, ACK, URG counts (forward/backward)

**Additional Rates (36-39):** Forward/backward packet rate, forward/backward byte rate

**Ratios (40-41):** Forward packet ratio, forward byte ratio

### 4. Online Normalization

**OnlineStandardScaler:**
- Uses Welford's algorithm for incremental mean/variance calculation
- Updates with each new flow (partial_fit)
- Applies Z-score normalization: `(X - mean) / std`
- Persists scaler state to `backend/stream/state/scaler_{feature_version}.pkl`

## Setup

### Prerequisites

```bash
# Python packages (already in requirements.txt)
pip install confluent-kafka numpy

# Create Kafka topic
docker exec adaptive_ids_kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic flows.features \
  --partitions 3 \
  --replication-factor 1
```

### Configuration

Edit `backend/.env`:

```bash
KAFKA_BROKERS=localhost:9092
PACKETS_TOPIC=raw.packets
FEATURES_TOPIC=flows.features
FLOW_ACTIVE_TIMEOUT=60.0
FLOW_IDLE_TIMEOUT=15.0
FEATURE_VERSION=v1.0-cic41
STATE_DIR=stream/state
```

## Usage

```bash
# Start feature extractor
cd backend
python -m stream.feature_extractor

# Monitor output
docker exec -it adaptive_ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic flows.features \
  --from-beginning
```

## Testing

```bash
# Unit tests
pytest stream/test_feature_extractor.py -v

# CSV integration tests
python stream/test_csv_features.py
```

## Performance

**Target:** 10,000 messages/minute (167 msgs/sec)

**Measured:** 200-500 flows/sec per instance

**Scaling:** Run multiple instances with same consumer group for horizontal scaling

## Troubleshooting

See full troubleshooting guide in extended README documentation.
