# Schema Implementation Complete ✓

## Summary

Versioned Avro schemas, Pydantic models, and Schema Registry integration have been successfully implemented for the Adaptive IDS streaming pipeline.

## What Was Created

### 1. Avro Schema Files (`.avsc`)
- ✅ `flow_features.avsc` - Network flow features (41+ dimensions)
- ✅ `prediction.avsc` - Model inference predictions
- ✅ `alert.avsc` - Enriched security alerts

**Key Features**:
- Versioned with `schema_version` field (default: 1)
- Backward-compatible evolution support
- Comprehensive field documentation
- Logical types (timestamp-millis)
- Optional/nullable fields with defaults
- Enums for severity and status

### 2. Python Models (`models.py`)
- ✅ `FlowFeatures` - Pydantic model with validation
- ✅ `Prediction` - Inference results with confidence checks
- ✅ `Alert` - Alert with workflow management
- ✅ `Enrichment` - External enrichment data
- ✅ `Severity`, `AlertStatus` - Enums

**Features**:
- Field validation (port ranges, confidence [0-1], feature length)
- Helper methods (`is_attack()`, `is_critical()`, `is_resolved()`)
- Round-trip serialization (`to_dict()`, `from_dict()`)
- Factory methods (`Alert.from_prediction()`, `FlowFeatures.create_flow_id()`)
- Severity computation based on attack type and confidence

### 3. Example Payloads (`examples/`)
- ✅ `flow_features_example.json` - 41 features with metadata
- ✅ `prediction_example.json` - DDoS prediction with 95.7% confidence
- ✅ `alert_example.json` - Critical alert with enrichment

### 4. Validation Tool (`validate.py`)
CLI tool for validating JSON against schemas:
```bash
python -m schemas.validate --examples
python -m schemas.validate --file data.json --schema flow_features
```

**Validates**:
- Avro schema compliance (via fastavro)
- Pydantic model correctness
- Round-trip serialization consistency

### 5. Schema Registry Client (`registry.py`)
Integration with Confluent Schema Registry:
```bash
python -m schemas.registry --register
python -m schemas.registry --list
```

**Features**:
- Register all schemas
- Get serializers/deserializers
- List subjects and versions
- Test compatibility

### 6. Test Suite (`test_schemas.py`)
Comprehensive tests demonstrating:
- Model creation and validation
- Serialization/deserialization
- Severity computation
- Alert workflow

## Validation Results

### Example Payloads ✅
All three example files validated successfully:
```
✓ flow_features_example.json
  - Avro schema validation passed
  - Pydantic validation passed
  - Round-trip serialization consistent

✓ prediction_example.json
  - Avro schema validation passed
  - Pydantic validation passed
  - Round-trip serialization consistent

✓ alert_example.json
  - Avro schema validation passed
  - Pydantic validation passed
  - Round-trip serialization consistent
```

### Test Suite ✅
All model tests passed:
```
✓ FlowFeatures creation and validation
  - 41 features
  - Protocol normalization (tcp -> TCP)
  - Round-trip serialization

✓ Prediction creation
  - Attack detection (is_attack())
  - Confidence validation
  - Class probability distribution

✓ Alert creation from Prediction
  - Severity computation (DDoS @ 95.7% -> CRITICAL)
  - Enrichment with geo/reputation
  - Status workflow (NEW -> ACKNOWLEDGED)
  - Destinations routing

✓ Severity computation for 8 test cases
  - Normal @ 0.99 -> INFO
  - DDoS @ 0.95 -> CRITICAL
  - PortScan @ 0.85 -> MEDIUM
  - BruteForce @ 0.85 -> HIGH
```

## Schema Details

### FlowFeatures Schema
**Fields**: 12  
**Version**: 1  
**Size**: ~500 bytes (with 41 features)

Key fields:
- `flow_id`: 5-tuple identifier
- `features`: array<float>[41+]
- `feature_version`: "v1.0-cic41"
- `metadata`: optional map for debugging

### Prediction Schema
**Fields**: 11  
**Version**: 1  
**Size**: ~200-400 bytes

Key fields:
- `class_idx`, `class_name`: Attack classification
- `confidence`: [0.0, 1.0]
- `model_version`, `feature_version`: Compatibility tracking
- `all_class_probs`: Optional full distribution

### Alert Schema
**Fields**: 19  
**Version**: 1  
**Size**: ~400-800 bytes

Key fields:
- All Prediction fields + 5-tuple
- `severity`: INFO | LOW | MEDIUM | HIGH | CRITICAL
- `status`: NEW | ACKNOWLEDGED | IN_PROGRESS | RESOLVED | FALSE_POSITIVE
- `enrichment`: geo, reputation, tags
- `destinations`: ["email", "syslog", "splunk"]

## Usage Examples

### Creating Flow Features
```python
from schemas.models import FlowFeatures, timestamp_to_ms
from datetime import datetime

flow = FlowFeatures(
    flow_id=FlowFeatures.create_flow_id("192.168.1.100", 54321, "10.0.0.50", 80, "TCP"),
    timestamp=timestamp_to_ms(datetime.now()),
    src_ip="192.168.1.100",
    dst_ip="10.0.0.50",
    src_port=54321,
    dst_port=80,
    protocol="TCP",
    features=[...],  # 41+ values
    feature_version="v1.0-cic41"
)
```

### Creating Prediction
```python
from schemas.models import Prediction

pred = Prediction(
    flow_id=flow.flow_id,
    timestamp=timestamp_to_ms(datetime.now()),
    class_idx=5,
    class_name="DDoS",
    confidence=0.957,
    model_version="v1.0",
    feature_version="v1.0-cic41"
)

if pred.is_attack():
    print(f"Attack: {pred.class_name}")
```

### Creating Alert
```python
from schemas.models import Alert, compute_severity, Enrichment

severity = compute_severity(pred.class_name, pred.confidence)

alert = Alert.from_prediction(
    prediction=pred,
    severity=severity,
    src_ip="192.168.1.100",
    dst_ip="10.0.0.50",
    src_port=54321,
    dst_port=80,
    protocol="TCP",
    enrichment=Enrichment(
        src_geo="US",
        src_reputation=0.85,
        tags=["internal"]
    ),
    destinations=["email", "syslog"]
)

if alert.is_critical():
    # Escalate immediately
    pass
```

### Kafka Integration
```python
from confluent_kafka import Producer
from schemas.models import FlowFeatures

producer = Producer({'bootstrap.servers': 'localhost:9092'})

flow = FlowFeatures(...)
producer.produce(
    'flows.features',
    value=json.dumps(flow.to_dict()).encode('utf-8')
)
```

## Dependencies Added

Updated `requirements.txt`:
```
confluent-kafka==2.3.0
fastavro==1.9.0
pydantic==2.5.0
pydantic-settings==2.1.0
```

## File Structure

```
backend/schemas/
├── __init__.py
├── README.md (comprehensive documentation)
├── flow_features.avsc (Avro schema)
├── prediction.avsc (Avro schema)
├── alert.avsc (Avro schema)
├── models.py (Pydantic models + helpers)
├── validate.py (CLI validation tool)
├── registry.py (Schema Registry client)
├── test_schemas.py (Test suite)
└── examples/
    ├── flow_features_example.json
    ├── prediction_example.json
    └── alert_example.json
```

## Next Steps

### 1. Register Schemas
```bash
# Start Schema Registry (if not running)
docker compose up -d schema-registry

# Register all schemas
cd backend
python -m schemas.registry --url http://localhost:8081 --register
```

### 2. Use in Stream Processors
```python
from schemas.models import FlowFeatures, Prediction
from schemas.registry import SchemaRegistry

# Get serializer
registry = SchemaRegistry("http://localhost:8081")
serializer = registry.get_serializer(
    "flows.features-value",
    to_dict=lambda obj, ctx: obj.to_dict()
)

# Produce with schema
flow = FlowFeatures(...)
serialized = serializer(flow, None)
```

### 3. Implement Feature Extractor
Use `FlowFeatures` model in `backend/stream/feature_extractor.py`:
```python
from schemas.models import FlowFeatures

def extract_features(packets) -> FlowFeatures:
    # Aggregate and compute features
    features = [...]  # 41 values
    return FlowFeatures(
        flow_id=create_flow_id(...),
        features=features,
        feature_version="v1.0-cic41",
        ...
    )
```

### 4. Implement Model Service
Use `Prediction` model in `backend/model/service/app.py`:
```python
from schemas.models import Prediction

def predict(flow: FlowFeatures) -> Prediction:
    class_idx = model.predict(flow.features)
    return Prediction(
        flow_id=flow.flow_id,
        class_idx=class_idx,
        class_name=CLASS_NAMES[class_idx],
        confidence=probabilities[class_idx],
        model_version="v1.0",
        feature_version=flow.feature_version
    )
```

### 5. Implement Alert Processor
Use `Alert` model in `backend/alerting/alerter.py`:
```python
from schemas.models import Alert, compute_severity

def process_prediction(pred: Prediction) -> Alert:
    severity = compute_severity(pred.class_name, pred.confidence)
    
    alert = Alert.from_prediction(
        prediction=pred,
        severity=severity,
        # ... extract from flow metadata
        destinations=["email", "syslog"] if severity in [Severity.HIGH, Severity.CRITICAL] else []
    )
    
    # Persist to DB
    save_alert(alert)
    
    # Dispatch
    for dest in alert.destinations:
        dispatch(alert, dest)
    
    return alert
```

## Acceptance Criteria ✅

All criteria met:
- ✅ Avro schemas created for flows.features, predictions, alerts
- ✅ All schemas include `schema_version` field
- ✅ FlowFeatures has 5-tuple + 41+ features + feature_version
- ✅ Prediction has class, confidence, versions
- ✅ Alert extends Prediction with severity and enrichment
- ✅ Pydantic models mirror schemas in `models.py`
- ✅ Example JSON payloads validate against schemas
- ✅ Round-trip serialization works without data loss
- ✅ Validator utility (`validate.py`) functional
- ✅ Schema Registry client (`registry.py`) implemented

## Testing

Run validation:
```bash
cd backend
python -m schemas.validate --examples
```

Run test suite:
```bash
python -m schemas.test_schemas
```

List schemas:
```bash
python -m schemas.validate --list-schemas
```

## Documentation

Comprehensive documentation in `backend/schemas/README.md` covering:
- Schema specifications
- Python model usage
- Schema Registry integration
- Validation tools
- Versioning strategy
- Best practices
- Troubleshooting

---

**Status**: ✅ Complete and validated  
**Date**: October 20, 2025  
**Next Phase**: Implement stream processors using these schemas
