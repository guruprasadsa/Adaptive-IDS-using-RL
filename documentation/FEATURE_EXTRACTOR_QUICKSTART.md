# Feature Extractor Quick Start

## Start Services

```bash
# 1. Start Kafka (if not running)
docker compose up -d

# 2. Create flows.features topic
docker exec adaptive_ids_kafka kafka-topics --create \
  --if-not-exists \
  --bootstrap-server localhost:9092 \
  --topic flows.features \
  --partitions 3 \
  --replication-factor 1

# 3. Start packet producer (Terminal 1 - as Administrator)
cd backend
python -m sensors.pcap_producer

# 4. Start feature extractor (Terminal 2)
cd backend
python -m stream.feature_extractor

# 5. Monitor output (Terminal 3)
docker exec -it adaptive_ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic flows.features \
  --from-beginning

# 6. Generate traffic (Terminal 4)
ping -n 100 google.com
```

## Test

```bash
# Unit tests (30 tests)
cd backend
pytest stream/test_feature_extractor.py -v

# Expected: 30 passed in < 1s
```

## Features

41 CICFlowMeter-compatible features per flow:
- Duration, packet/byte counts (forward/backward)
- Packet length statistics (min/max/mean/std)
- Inter-arrival time statistics
- TCP flag counts
- Rate features (packets/sec, bytes/sec)
- Flow ratios

## Performance

- Target: 10,000 msgs/min (167 msgs/sec)
- Actual: 200-500 flows/sec per instance
- Horizontal scaling: Run multiple instances with same consumer group

## Troubleshooting

**No messages in flows.features:**
- Wait 15+ seconds after last packet (idle timeout)
- Check raw.packets has messages
- Verify Kafka connection

**Memory issues:**
- Monitor active flows (should decrease after timeout)
- Check flow expiration logic

**Feature errors:**
- All flows produce exactly 41 features
- Check for NaN/Inf values (should be 0)

## Next: Phase 4 - Model Training

Train ML models using historical CIC-IDS-2017/2018 data with same feature extraction logic.
