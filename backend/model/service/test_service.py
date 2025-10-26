"""
Manual testing script for Model Inference Service

Usage:
    python backend/model/service/test_service.py
"""
import json
import time
import requests
import numpy as np
from typing import Dict, Any


SERVICE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    try:
        response = requests.get(f"{SERVICE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_model_info():
    """Test model info endpoint"""
    print("\n=== Testing Model Info Endpoint ===")
    try:
        response = requests.get(f"{SERVICE_URL}/model/info")
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Verify key fields
        assert 'model_version' in data
        assert 'num_classes' in data
        assert 'label_classes' in data
        print("✓ Model info validated")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_metrics():
    """Test Prometheus metrics endpoint"""
    print("\n=== Testing Metrics Endpoint ===")
    try:
        response = requests.get(f"{SERVICE_URL}/metrics")
        print(f"Status Code: {response.status_code}")
        
        # Check for key metrics
        content = response.text
        metrics = [
            'ids_inferences_total',
            'ids_inference_latency_seconds',
            'ids_messages_consumed_total',
            'ids_messages_produced_total',
            'ids_batch_size'
        ]
        
        found_metrics = []
        for metric in metrics:
            if metric in content:
                found_metrics.append(metric)
                print(f"✓ Found metric: {metric}")
            else:
                print(f"✗ Missing metric: {metric}")
        
        return len(found_metrics) >= 3
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_predict_single():
    """Test direct prediction endpoint with single sample"""
    print("\n=== Testing Direct Prediction (Single Sample) ===")
    try:
        # Create sample flow features
        flow_features = {
            "flow_id": "192.168.1.100:54321:192.168.1.1:80:TCP",
            "timestamp": int(time.time() * 1000),
            "src_ip": "192.168.1.100",
            "dst_ip": "192.168.1.1",
            "src_port": 54321,
            "dst_port": 80,
            "protocol": "TCP",
            "features": np.random.randn(41).tolist(),
            "feature_version": "v1.0",
            "schema_version": 1
        }
        
        print(f"Sending request with flow_id: {flow_features['flow_id']}")
        
        start_time = time.time()
        response = requests.post(
            f"{SERVICE_URL}/predict",
            json=flow_features,
            headers={"Content-Type": "application/json"}
        )
        latency = (time.time() - start_time) * 1000
        
        print(f"Status Code: {response.status_code}")
        print(f"Latency: {latency:.2f}ms")
        
        if response.status_code == 200:
            prediction = response.json()
            print(f"\nPrediction:")
            print(f"  Class: {prediction['class_name']} (index: {prediction['class_idx']})")
            print(f"  Confidence: {prediction['confidence']:.4f}")
            print(f"  Model Version: {prediction['model_version']}")
            print(f"  Inference Latency: {prediction.get('inference_latency_ms', 0):.2f}ms")
            
            if prediction.get('all_class_probs'):
                print(f"\n  Top 3 Classes:")
                sorted_probs = sorted(
                    prediction['all_class_probs'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                for class_name, prob in sorted_probs:
                    print(f"    - {class_name}: {prob:.4f}")
            
            return True
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_predict_batch():
    """Test batch prediction performance"""
    print("\n=== Testing Batch Prediction Performance ===")
    try:
        num_samples = 100
        samples = []
        
        print(f"Generating {num_samples} test samples...")
        for i in range(num_samples):
            flow_features = {
                "flow_id": f"192.168.1.{100 + i % 155}:{50000 + i}:192.168.1.1:80:TCP",
                "timestamp": int(time.time() * 1000),
                "src_ip": f"192.168.1.{100 + i % 155}",
                "dst_ip": "192.168.1.1",
                "src_port": 50000 + i,
                "dst_port": 80,
                "protocol": "TCP",
                "features": np.random.randn(41).tolist(),
                "feature_version": "v1.0",
                "schema_version": 1
            }
            samples.append(flow_features)
        
        print(f"Sending {num_samples} predictions...")
        start_time = time.time()
        
        results = []
        for sample in samples:
            response = requests.post(
                f"{SERVICE_URL}/predict",
                json=sample,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                results.append(response.json())
        
        total_time = time.time() - start_time
        throughput = len(results) / total_time
        avg_latency = (total_time / len(results)) * 1000
        
        print(f"\nPerformance Results:")
        print(f"  Total Samples: {num_samples}")
        print(f"  Successful: {len(results)}")
        print(f"  Total Time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.0f} samples/sec")
        print(f"  Avg Latency: {avg_latency:.2f}ms per sample")
        
        # Class distribution
        class_counts = {}
        for result in results:
            class_name = result['class_name']
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        print(f"\nClass Distribution:")
        for class_name, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {class_name}: {count} ({count/len(results)*100:.1f}%)")
        
        return len(results) == num_samples
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("Model Inference Service Test Suite")
    print("="*60)
    
    tests = [
        ("Health Check", test_health),
        ("Model Info", test_model_info),
        ("Metrics", test_metrics),
        ("Single Prediction", test_predict_single),
        ("Batch Performance", test_predict_batch),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\nTest '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
        
        time.sleep(0.5)  # Brief pause between tests
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
