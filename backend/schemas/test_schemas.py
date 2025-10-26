"""
Quick test demonstrating schema usage and serialization.
Run with: python -m schemas.test_schemas
"""
from datetime import datetime
from schemas.models import (
    FlowFeatures, Prediction, Alert,
    Severity, AlertStatus, Enrichment,
    compute_severity, timestamp_to_ms
)


def test_flow_features():
    """Test FlowFeatures creation and serialization"""
    print("\n=== Testing FlowFeatures ===")
    
    # Create flow features
    flow = FlowFeatures(
        flow_id=FlowFeatures.create_flow_id("192.168.1.100", 54321, "10.0.0.50", 80, "TCP"),
        timestamp=timestamp_to_ms(datetime.now()),
        src_ip="192.168.1.100",
        dst_ip="10.0.0.50",
        src_port=54321,
        dst_port=80,
        protocol="tcp",  # Will be normalized to TCP
        features=[0.5] * 41,  # 41 dummy features
        feature_version="v1.0-cic41",
        metadata={"sensor_id": "test-sensor"}
    )
    
    print(f"✓ Created FlowFeatures: {flow.flow_id}")
    print(f"  Features length: {len(flow.features)}")
    print(f"  Protocol (normalized): {flow.protocol}")
    
    # Serialize
    data = flow.to_dict()
    print(f"  Serialized to dict with {len(data)} keys")
    
    # Deserialize
    flow2 = FlowFeatures.from_dict(data)
    assert flow2.flow_id == flow.flow_id
    print(f"✓ Round-trip serialization successful")
    
    return flow


def test_prediction():
    """Test Prediction creation"""
    print("\n=== Testing Prediction ===")
    
    pred = Prediction(
        flow_id="192.168.1.100:54321:10.0.0.50:80:TCP",
        timestamp=timestamp_to_ms(datetime.now()),
        class_idx=5,
        class_name="DDoS",
        confidence=0.957,
        model_version="v1.0",
        feature_version="v1.0-cic41",
        agent_type="ddos_specialist",
        all_class_probs={
            "Normal": 0.012,
            "DDoS": 0.957,
            "PortScan": 0.031
        },
        inference_latency_ms=23.5
    )
    
    print(f"✓ Created Prediction: {pred.class_name}")
    print(f"  Confidence: {pred.confidence:.3f}")
    print(f"  Is attack: {pred.is_attack()}")
    
    # Serialize
    data = pred.to_dict()
    pred2 = Prediction.from_dict(data)
    assert pred2.class_idx == pred.class_idx
    print(f"✓ Round-trip serialization successful")
    
    return pred


def test_alert():
    """Test Alert creation from Prediction"""
    print("\n=== Testing Alert ===")
    
    # Create prediction first
    pred = Prediction(
        flow_id="192.168.1.100:54321:10.0.0.50:80:TCP",
        timestamp=timestamp_to_ms(datetime.now()),
        class_idx=5,
        class_name="DDoS",
        confidence=0.957,
        model_version="v1.0",
        feature_version="v1.0-cic41"
    )
    
    # Compute severity
    severity = compute_severity(pred.class_name, pred.confidence)
    print(f"  Computed severity: {severity.value}")
    
    # Create enrichment
    enrichment = Enrichment(
        src_geo="US",
        dst_geo="CN",
        src_reputation=0.85,
        dst_reputation=0.23,
        tags=["external", "suspicious"]
    )
    
    # Create alert from prediction
    alert = Alert.from_prediction(
        prediction=pred,
        severity=severity,
        src_ip="192.168.1.100",
        dst_ip="10.0.0.50",
        src_port=54321,
        dst_port=80,
        protocol="TCP",
        enrichment=enrichment,
        destinations=["email", "syslog"]
    )
    
    print(f"✓ Created Alert: {alert.alert_id}")
    print(f"  Class: {alert.class_name}")
    print(f"  Severity: {alert.severity.value}")
    print(f"  Status: {alert.status.value}")
    print(f"  Is critical: {alert.is_critical()}")
    print(f"  Is resolved: {alert.is_resolved()}")
    print(f"  Enrichment tags: {alert.enrichment.tags if alert.enrichment else None}")
    print(f"  Destinations: {alert.destinations}")
    
    # Update status
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.assigned_to = "security-team"
    alert.notes = "Under investigation"
    print(f"  Updated status: {alert.status.value}")
    
    # Serialize
    data = alert.to_dict()
    alert2 = Alert.from_dict(data)
    assert alert2.alert_id == alert.alert_id
    print(f"✓ Round-trip serialization successful")
    
    return alert


def test_severity_computation():
    """Test severity computation for different attack types"""
    print("\n=== Testing Severity Computation ===")
    
    test_cases = [
        ("Normal", 0.99, Severity.INFO),
        ("DDoS", 0.95, Severity.CRITICAL),
        ("DDoS", 0.75, Severity.HIGH),
        ("DDoS", 0.60, Severity.MEDIUM),
        ("PortScan", 0.85, Severity.MEDIUM),
        ("PortScan", 0.70, Severity.LOW),
        ("BruteForce", 0.85, Severity.HIGH),
        ("WebAttack", 0.65, Severity.MEDIUM),
    ]
    
    for attack_class, confidence, expected in test_cases:
        result = compute_severity(attack_class, confidence)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {attack_class:15s} @ {confidence:.2f} -> {result.value:8s} (expected: {expected.value})")


def main():
    print("\n" + "=" * 60)
    print("Schema Models Test Suite")
    print("=" * 60)
    
    try:
        # Test each model
        flow = test_flow_features()
        pred = test_prediction()
        alert = test_alert()
        test_severity_computation()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
        # Print summary
        print("\nCreated objects:")
        print(f"  FlowFeatures: {flow.flow_id}")
        print(f"  Prediction:   {pred.class_name} ({pred.confidence:.3f})")
        print(f"  Alert:        {alert.alert_id}")
        
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ Tests failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
