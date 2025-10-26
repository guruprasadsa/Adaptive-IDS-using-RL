# Data Schemas

## Overview
Versioned Avro schemas for Kafka topics ensuring consistent data contracts across services. All schemas support backward-compatible evolution and include version tracking.

## Schema Files

### 1. FlowFeatures (`flow_features.avsc`)
**Topic**: `flows.features`  
**Purpose**: Network flow-level traffic features for ML inference

**Key Fields**:
- `flow_id` (string): Unique 5-tuple identifier (src_ip:src_port:dst_ip:dst_port:protocol)
- `timestamp` (long): Flow start time in milliseconds since epoch
- `src_ip`, `dst_ip` (string): Source and destination IP addresses
- `src_port`, `dst_port` (int): Source and destination ports
- `protocol` (string): Transport protocol (TCP/UDP/ICMP)
- `features` (array<float>): 41+ normalized feature vector (order must match feature_version)
- `feature_names` (array<string>): Optional human-readable feature names
- `feature_version` (string): Hash/version of feature extraction algorithm (e.g., "v1.0-cic41")
- `schema_version` (int): Schema version for backward compatibility (default: 1)
- `metadata` (map<string>): Optional metadata for debugging/enrichment

**Feature Vector**:
The `features` array contains 41+ statistical metrics extracted from network flows:
- Basic: duration, packet/byte counts (fwd/bwd), protocol
- Time-based: inter-arrival time (IAT) statistics, flow active/idle times
- Content: flag counts (SYN/ACK/FIN/RST/PSH/URG), window sizes
- Statistical: min/max/mean/std for packet sizes, bits/packets per second

### 2. Prediction (`prediction.avsc`)
**Topic**: `predictions`  
**Purpose**: Model inference results from multi-agent DQN

**Key Fields**:
- `flow_id` (string): References FlowFeatures.flow_id
- `timestamp` (long): Prediction time in milliseconds since epoch
- `class_idx` (int): Numeric class index (0-15+) from model output
- `class_name` (string): Human-readable attack class (e.g., "DDoS", "PortScan", "Normal")
- `confidence` (float): Calibrated confidence score [0.0, 1.0] (softmax probability)
- `model_version` (string): Model version identifier (e.g., "v1.0", "run_1758022767")
- `feature_version` (string): Must match FlowFeatures.feature_version
- `agent_type` (string, optional): Specialist agent that made prediction (e.g., "ddos_specialist")
- `all_class_probs` (map<float>, optional): Full probability distribution over all classes
- `inference_latency_ms` (float, optional): Inference latency in milliseconds
- `schema_version` (int): Schema version (default: 1)

### 3. Alert (`alert.avsc`)
**Topic**: `alerts`  
**Purpose**: Enriched security alerts for persistence and external dispatch

**Key Fields**:
- `alert_id` (string): Unique UUID for the alert
- All fields from Prediction (flow_id, class_idx, class_name, confidence, timestamps, versions)
- 5-tuple: `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`
- `severity` (enum): INFO | LOW | MEDIUM | HIGH | CRITICAL
- `enrichment` (record, optional): External enrichment data
  - `src_geo`, `dst_geo`: IP geolocation (country codes)
  - `src_reputation`, `dst_reputation`: Threat intel scores [0.0, 1.0]
  - `tags`: Custom tags (e.g., "internal", "dmz", "whitelisted")
- `status` (enum): NEW | ACKNOWLEDGED | IN_PROGRESS | RESOLVED | FALSE_POSITIVE
- `assigned_to` (string, optional): User/team assigned to handle the alert
- `notes` (string, optional): Analyst notes or comments
- `destinations` (array<string>): Dispatch targets (e.g., ["email", "syslog", "splunk"])
- `schema_version` (int): Schema version (default: 1)

## Python Models (`models.py`)

Pydantic models mirror Avro schemas for runtime validation and easy serialization:

### FlowFeatures
```python
from schemas.models import FlowFeatures

flow = FlowFeatures(
    flow_id="192.168.1.100:54321:10.0.0.50:80:TCP",
    timestamp=1729468800000,
    src_ip="192.168.1.100",
    dst_ip="10.0.0.50",
    src_port=54321,
    dst_port=80,
    protocol="TCP",
    features=[0.123, ...],  # 41+ values
    feature_version="v1.0-cic41"
)

# Serialize to dict
data = flow.to_dict()

# Deserialize from dict
flow2 = FlowFeatures.from_dict(data)
```

### Prediction
```python
from schemas.models import Prediction

pred = Prediction(
    flow_id="192.168.1.100:54321:10.0.0.50:80:TCP",
    timestamp=1729468801500,
    class_idx=5,
    class_name="DDoS",
    confidence=0.957,
    model_version="v1.0",
    feature_version="v1.0-cic41"
)

# Check if attack
if pred.is_attack():
    print(f"Attack detected: {pred.class_name}")
```

### Alert
```python
from schemas.models import Alert, Severity, Enrichment, compute_severity

# Create from prediction
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

# Check severity
if alert.is_critical():
    print("CRITICAL alert!")
```

## Schema Registry Integration (`registry.py`)

Tools for Confluent Schema Registry:

### Register Schemas
```python
from schemas.registry import register_all_schemas

# Register all schemas to Schema Registry
results = register_all_schemas(registry_url="http://localhost:8081")
# Returns: {'flows.features-value': 1, 'predictions-value': 2, 'alerts-value': 3}
```

### Get Serializer/Deserializer
```python
from schemas.registry import SchemaRegistry
from schemas.models import FlowFeatures

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
```

### CLI Usage
```bash
# Register all schemas
python schemas/registry.py --url http://localhost:8081 --register

# List subjects
python schemas/registry.py --url http://localhost:8081 --list

# List versions for a subject
python schemas/registry.py --url http://localhost:8081 --subject flows.features-value --versions
```

## Validation Tool (`validate.py`)

CLI tool to validate JSON payloads:

```bash
# Validate a specific file
python schemas/validate.py --file data.json --schema flow_features

# Validate all examples
python schemas/validate.py --examples

# Skip Avro validation (if fastavro not installed)
python schemas/validate.py --file data.json --schema prediction --skip-avro

# List available schemas
python schemas/validate.py --list-schemas
```

**Output**:
```
Validating: examples/flow_features_example.json
Schema: flow_features
------------------------------------------------------------
✓ Avro schema validation passed: flow_features
✓ Pydantic validation passed: flow_features
  Model: FlowFeatures
  ✓ Round-trip serialization consistent

✓ All validations passed for flow_features
```

## Example Payloads

See `examples/` directory:
- `flow_features_example.json`: Sample flow with 41 features
- `prediction_example.json`: DDoS attack prediction with 95.7% confidence
- `alert_example.json`: Critical alert with enrichment data

## Schema Versioning Strategy

### Version Fields
All schemas include:
- `schema_version` (int): Avro schema version for backward compatibility
- `feature_version` (string): Feature extraction algorithm version
- `model_version` (string, in Prediction/Alert): Model training version

### Backward Compatibility
- **Add fields**: Use `default` values or `union` with `null`
- **Remove fields**: Mark as optional first, deprecate gradually
- **Rename fields**: Add new field with default, keep old field, migrate consumers
- **Change types**: Avoid; use new schema version and topic if necessary

### Version Negotiation
1. Producers include `feature_version` and `schema_version` in every message
2. Consumers check versions and handle accordingly
3. Model service validates `feature_version` matches training config
4. Schema Registry enforces compatibility rules (BACKWARD, FORWARD, FULL)

## Schema Evolution Example

Adding a new field (backward compatible):
```json
{
  "name": "packet_loss_rate",
  "type": ["null", "float"],
  "default": null,
  "doc": "Percentage of packet loss in flow"
}
```

Removing a field (requires deprecation):
1. Mark optional: `"type": ["null", "float"], "default": null`
2. Deploy consumers that ignore field
3. Deploy producers that stop sending field
4. Remove from schema in next major version

## Best Practices

1. **Always validate** payloads before producing to Kafka
2. **Use Pydantic models** for type safety and validation
3. **Include metadata** for debugging (sensor_id, timestamps)
4. **Version everything**: schemas, features, models
5. **Test compatibility** before deploying schema changes
6. **Document** all field meanings and units
7. **Use enums** for categorical fields (severity, status, protocol)
8. **Provide examples** for each schema

## Dependencies

Install required packages:
```bash
pip install confluent-kafka==2.3.0 fastavro==1.9.0 pydantic==2.5.0
```

## Troubleshooting

### Schema Registry Connection Failed
```bash
# Check if Schema Registry is running
curl http://localhost:8081/subjects

# Start with Docker Compose
docker compose up -d schema-registry
```

### Validation Errors
```python
# Get detailed validation error
try:
    flow = FlowFeatures.from_dict(data)
except ValidationError as e:
    print(e.json())
```

### Incompatible Schema
```bash
# Test compatibility before registering
python schemas/registry.py --test-compatibility --subject flows.features-value --file new_schema.avsc
```

## References

- [Avro Specification](https://avro.apache.org/docs/current/spec.html)
- [Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/index.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [CICFlowMeter Features](https://www.unb.ca/cic/datasets/ids-2017.html)
