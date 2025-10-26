# Schema Quick Reference

## Import Models
```python
from schemas.models import (
    FlowFeatures, Prediction, Alert,
    Severity, AlertStatus, Enrichment,
    compute_severity, timestamp_to_ms, ms_to_timestamp
)
```

## FlowFeatures

### Create
```python
flow = FlowFeatures(
    flow_id="192.168.1.100:54321:10.0.0.50:80:TCP",
    timestamp=timestamp_to_ms(datetime.now()),
    src_ip="192.168.1.100",
    dst_ip="10.0.0.50",
    src_port=54321,
    dst_port=80,
    protocol="TCP",
    features=[0.1, 0.2, ...],  # 41+ values
    feature_version="v1.0-cic41"
)
```

### Helper: Create Flow ID
```python
flow_id = FlowFeatures.create_flow_id(
    src_ip="192.168.1.100",
    src_port=54321,
    dst_ip="10.0.0.50",
    dst_port=80,
    protocol="TCP"
)
# Returns: "192.168.1.100:54321:10.0.0.50:80:TCP"
```

### Serialize
```python
# To dict
data = flow.to_dict()

# From dict
flow2 = FlowFeatures.from_dict(data)

# To JSON
import json
json_str = json.dumps(flow.to_dict())
```

## Prediction

### Create
```python
pred = Prediction(
    flow_id="192.168.1.100:54321:10.0.0.50:80:TCP",
    timestamp=timestamp_to_ms(datetime.now()),
    class_idx=5,
    class_name="DDoS",
    confidence=0.957,
    model_version="v1.0",
    feature_version="v1.0-cic41"
)
```

### Check Attack
```python
if pred.is_attack():
    print(f"Attack detected: {pred.class_name}")
else:
    print("Normal traffic")
```

### With Full Probabilities
```python
pred = Prediction(
    ...,
    all_class_probs={
        "Normal": 0.012,
        "DDoS": 0.957,
        "PortScan": 0.031
    },
    inference_latency_ms=23.5
)
```

## Alert

### Create from Prediction
```python
severity = compute_severity(pred.class_name, pred.confidence)

alert = Alert.from_prediction(
    prediction=pred,
    severity=severity,
    src_ip="192.168.1.100",
    dst_ip="10.0.0.50",
    src_port=54321,
    dst_port=80,
    protocol="TCP",
    destinations=["email", "syslog"]
)
```

### With Enrichment
```python
enrichment = Enrichment(
    src_geo="US",
    dst_geo="CN",
    src_reputation=0.85,
    dst_reputation=0.23,
    tags=["external", "suspicious"]
)

alert = Alert.from_prediction(
    ...,
    enrichment=enrichment
)
```

### Update Status
```python
alert.status = AlertStatus.ACKNOWLEDGED
alert.assigned_to = "security-team"
alert.notes = "Investigating traffic pattern"
```

### Check Severity
```python
if alert.is_critical():
    escalate_immediately(alert)

if alert.severity in [Severity.HIGH, Severity.CRITICAL]:
    send_email(alert)
```

### Check Status
```python
if alert.is_resolved():
    archive(alert)
else:
    display_active_alert(alert)
```

## Severity Computation

```python
# Automatic severity based on attack type and confidence
severity = compute_severity("DDoS", 0.95)      # CRITICAL
severity = compute_severity("DDoS", 0.75)      # HIGH
severity = compute_severity("DDoS", 0.60)      # MEDIUM
severity = compute_severity("PortScan", 0.85)  # MEDIUM
severity = compute_severity("PortScan", 0.70)  # LOW
severity = compute_severity("Normal", 0.99)    # INFO
```

## Timestamp Conversion

```python
from datetime import datetime

# Python datetime to milliseconds
now_ms = timestamp_to_ms(datetime.now())

# Milliseconds to Python datetime
dt = ms_to_timestamp(1729468800000)
```

## Enums

### Severity
```python
Severity.INFO
Severity.LOW
Severity.MEDIUM
Severity.HIGH
Severity.CRITICAL
```

### AlertStatus
```python
AlertStatus.NEW
AlertStatus.ACKNOWLEDGED
AlertStatus.IN_PROGRESS
AlertStatus.RESOLVED
AlertStatus.FALSE_POSITIVE
```

## Validation

### Validate Before Producing
```python
try:
    flow = FlowFeatures.from_dict(data)
    # Valid - safe to produce
except ValidationError as e:
    print(f"Invalid data: {e}")
```

### Field Constraints
- **Ports**: 0-65535
- **Confidence**: 0.0-1.0
- **Features**: minimum 41 elements
- **Protocol**: auto-normalized to uppercase

## Kafka Integration

### Produce
```python
from confluent_kafka import Producer
import json

producer = Producer({'bootstrap.servers': 'localhost:9092'})

flow = FlowFeatures(...)
producer.produce(
    'flows.features',
    key=flow.flow_id.encode('utf-8'),
    value=json.dumps(flow.to_dict()).encode('utf-8')
)
producer.flush()
```

### Consume
```python
from confluent_kafka import Consumer
import json

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-group',
    'auto.offset.reset': 'earliest'
})

consumer.subscribe(['flows.features'])

for msg in consumer:
    data = json.loads(msg.value())
    flow = FlowFeatures.from_dict(data)
    process(flow)
```

## CLI Tools

### Validate Examples
```bash
python -m schemas.validate --examples
```

### Validate Custom File
```bash
python -m schemas.validate --file data.json --schema flow_features
```

### List Schemas
```bash
python -m schemas.validate --list-schemas
```

### Register Schemas
```bash
python -m schemas.registry --url http://localhost:8081 --register
```

### List Registry Subjects
```bash
python -m schemas.registry --url http://localhost:8081 --list
```

## Common Patterns

### Stream Processor
```python
from confluent_kafka import Consumer, Producer
from schemas.models import FlowFeatures, Prediction

consumer = Consumer({...})
producer = Producer({...})

for msg in consumer:
    # Deserialize
    flow = FlowFeatures.from_dict(json.loads(msg.value()))
    
    # Process
    pred = model.predict(flow)
    
    # Serialize
    producer.produce('predictions', json.dumps(pred.to_dict()))
```

### Alert Pipeline
```python
from schemas.models import Prediction, Alert, compute_severity

def process_prediction(pred: Prediction) -> Alert:
    # Compute severity
    severity = compute_severity(pred.class_name, pred.confidence)
    
    # Create alert
    alert = Alert.from_prediction(
        prediction=pred,
        severity=severity,
        # ... flow metadata
    )
    
    # Persist
    db.save(alert)
    
    # Dispatch
    if alert.severity in [Severity.HIGH, Severity.CRITICAL]:
        send_email(alert)
    if alert.severity == Severity.CRITICAL:
        send_sms(alert)
    
    return alert
```

## Error Handling

```python
from pydantic import ValidationError

try:
    flow = FlowFeatures.from_dict(data)
except ValidationError as e:
    # Detailed validation errors
    for error in e.errors():
        print(f"Field: {error['loc']}")
        print(f"Error: {error['msg']}")
        print(f"Type: {error['type']}")
```

## Testing

```python
def test_round_trip():
    # Create
    flow = FlowFeatures(...)
    
    # Serialize
    data = flow.to_dict()
    
    # Deserialize
    flow2 = FlowFeatures.from_dict(data)
    
    # Assert equality
    assert flow.flow_id == flow2.flow_id
    assert flow.features == flow2.features
```

## Best Practices

1. **Always validate** before producing to Kafka
2. **Include metadata** for debugging (sensor_id, capture_interface)
3. **Use helper methods** (create_flow_id, compute_severity)
4. **Check versions** (feature_version, model_version, schema_version)
5. **Handle enums properly** (use .value for serialization)
6. **Add timestamps** for all events
7. **Log validation errors** with context

## Schema Registry with Avro

```python
from schemas.registry import SchemaRegistry

registry = SchemaRegistry("http://localhost:8081")

# Get serializer
serializer = registry.get_serializer(
    "flows.features-value",
    to_dict=lambda obj, ctx: obj.to_dict()
)

# Get deserializer
deserializer = registry.get_deserializer(
    "flows.features-value",
    from_dict=lambda data, ctx: FlowFeatures.from_dict(data)
)

# Use with Kafka
flow = FlowFeatures(...)
serialized_bytes = serializer(flow, None)
producer.produce('flows.features', value=serialized_bytes)
```
