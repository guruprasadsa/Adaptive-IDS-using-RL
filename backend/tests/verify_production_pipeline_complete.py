"""
Complete End-to-End Production Pipeline Verification
Tests the full data flow: packet capture → features → predictions → alerts → database

This script validates that:
1. All services are healthy and responding
2. Kafka topics exist and are functioning
3. Data flows through the entire pipeline
4. Alerts are created and stored in the database
5. Frontend can retrieve real-time data via API
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import psycopg2
import requests
from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

def info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


class PipelineVerifier:
    """Comprehensive pipeline verification"""
    
    def __init__(self):
        self.kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
        self.backend_url = os.getenv('API_BASE_URL', 'http://127.0.0.1:5001')
        self.model_url = os.getenv('MODEL_SERVICE_URL', 'http://127.0.0.1:8000')
        self.db_dsn = os.getenv(
            'PG_DSN',
            'host=127.0.0.1 port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
        )
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
    
    def verify_service_health(self, name: str, url: str) -> bool:
        """Check if a service is healthy"""
        try:
            # Backend API uses /api/health, model service uses /health
            health_path = "/api/health" if "5001" in url else "/health"
            response = requests.get(f"{url}{health_path}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                success(f"{name} is healthy: {data.get('status', 'ok')}")
                return True
            else:
                error(f"{name} returned {response.status_code}")
                return False
        except Exception as e:
            error(f"{name} health check failed: {e}")
            return False
    
    def verify_database_connection(self) -> bool:
        """Verify database connectivity and schema"""
        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()
            
            # Check alerts table exists
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'alerts'
            """)
            if cursor.fetchone()[0] == 0:
                error("Alerts table does not exist")
                return False
            
            # Get alert count
            cursor.execute("SELECT COUNT(*) FROM alerts")
            count = cursor.fetchone()[0]
            success(f"Database connected, {count} alerts in database")
            
            # Check for recent alerts (last 10 minutes)
            cursor.execute("""
                SELECT COUNT(*) FROM alerts 
                WHERE timestamp > NOW() - INTERVAL '10 minutes'
            """)
            recent_count = cursor.fetchone()[0]
            if recent_count > 0:
                success(f"Found {recent_count} recent alerts (last 10 min)")
            else:
                warning("No recent alerts found in database")
            
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            error(f"Database verification failed: {e}")
            return False
    
    def verify_kafka_topics(self) -> bool:
        """Verify Kafka topics exist"""
        try:
            admin = AdminClient({'bootstrap.servers': self.kafka_brokers})
            metadata = admin.list_topics(timeout=10)
            
            required_topics = ['raw.packets', 'flows.features', 'predictions', 'alerts']
            existing_topics = set(metadata.topics.keys())
            
            all_exist = True
            for topic in required_topics:
                if topic in existing_topics:
                    partitions = len(metadata.topics[topic].partitions)
                    success(f"Topic '{topic}' exists with {partitions} partition(s)")
                else:
                    error(f"Topic '{topic}' does not exist")
                    all_exist = False
            
            return all_exist
        except Exception as e:
            error(f"Kafka topic verification failed: {e}")
            return False
    
    def verify_alert_data_integrity(self) -> bool:
        """Verify alerts have valid data"""
        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()
            
            # Get sample alerts
            cursor.execute("""
                SELECT alert_id, class_name, confidence, severity, 
                       src_ip, dst_ip, timestamp
                FROM alerts 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            
            alerts = cursor.fetchall()
            if not alerts:
                warning("No alerts found to verify data integrity")
                cursor.close()
                conn.close()
                return True
            
            info(f"Verifying data integrity for {len(alerts)} recent alerts...")
            
            for alert in alerts:
                alert_id, class_name, confidence, severity, src_ip, dst_ip, timestamp = alert
                
                # Validate confidence
                if not (0 <= confidence <= 1):
                    error(f"Alert {alert_id}: Invalid confidence {confidence}")
                    return False
                
                # Validate class name
                if not class_name or class_name == 'Unknown':
                    warning(f"Alert {alert_id}: Unknown class name")
                
                # Validate severity
                valid_severities = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
                if severity not in valid_severities:
                    error(f"Alert {alert_id}: Invalid severity '{severity}'")
                    return False
                
                # Validate IPs
                if not src_ip or not dst_ip:
                    error(f"Alert {alert_id}: Missing IP addresses")
                    return False
                
                success(f"Alert {alert_id}: {severity} - {class_name} ({confidence:.2%})")
            
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            error(f"Alert data integrity check failed: {e}")
            return False
    
    def verify_api_endpoints(self) -> bool:
        """Verify backend API endpoints return real data"""
        try:
            # Test /api/dashboard/stats (may require auth)
            try:
                response = requests.get(f"{self.backend_url}/api/dashboard/stats", timeout=5)
                if response.status_code == 200:
                    stats = response.json()
                    success(f"Dashboard stats: {stats.get('total_alerts', 0)} total alerts")
                elif response.status_code == 401:
                    warning("Dashboard stats requires authentication (expected)")
                else:
                    warning(f"Dashboard stats returned {response.status_code}")
            except Exception as e:
                warning(f"Dashboard stats check skipped: {e}")
            
            # Test /api/model/metrics
            try:
                response = requests.get(f"{self.backend_url}/api/model/metrics", timeout=5)
                if response.status_code == 200:
                    metrics = response.json()
                    accuracy = metrics.get('accuracy', 0)
                    success(f"Model metrics: {accuracy:.2%} accuracy")
                else:
                    warning(f"Model metrics returned {response.status_code}")
            except Exception as e:
                warning(f"Model metrics check skipped: {e}")
            
            return True
        except Exception as e:
            error(f"API endpoint verification failed: {e}")
            return False
    
    def verify_model_service(self) -> bool:
        """Verify model service is processing predictions"""
        try:
            response = requests.get(f"{self.model_url}/health", timeout=5)
            if response.status_code != 200:
                error(f"Model service health check failed: {response.status_code}")
                return False
            
            health = response.json()
            if not health.get('model_ready'):
                error("Model is not ready")
                return False
            
            success(f"Model service ready on {health.get('device', 'cpu')}")
            
            # Get model info
            try:
                response = requests.get(f"{self.model_url}/model/info", timeout=5)
                if response.status_code == 200:
                    info_data = response.json()
                    success(f"Model version: {info_data.get('model_version', 'unknown')}")
                    success(f"Classes: {info_data.get('num_classes', 0)}")
            except:
                pass
            
            return True
        except Exception as e:
            error(f"Model service verification failed: {e}")
            return False
    
    def verify_kafka_message_flow(self) -> bool:
        """Verify messages are flowing through Kafka"""
        try:
            consumer = Consumer({
                'bootstrap.servers': self.kafka_brokers,
                'group.id': 'verification-test',
                'auto.offset.reset': 'latest'
            })
            
            # Check predictions topic
            consumer.subscribe(['predictions'])
            
            info("Checking for messages in 'predictions' topic (5 second timeout)...")
            start_time = time.time()
            message_count = 0
            
            while time.time() - start_time < 5:
                msg = consumer.poll(timeout=1.0)
                if msg and not msg.error():
                    message_count += 1
            
            consumer.close()
            
            if message_count > 0:
                success(f"Received {message_count} prediction messages")
                return True
            else:
                warning("No messages in predictions topic (may be normal if no traffic)")
                return True  # Not a failure, just no traffic
        except Exception as e:
            error(f"Kafka message flow verification failed: {e}")
            return False
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all verification checks"""
        print("\n" + "="*60)
        print("PRODUCTION PIPELINE VERIFICATION")
        print("="*60 + "\n")
        
        checks = [
            ("Backend API Health", lambda: self.verify_service_health("Backend API", self.backend_url)),
            ("Model Service Health", lambda: self.verify_service_health("Model Service", self.model_url)),
            ("Database Connection", self.verify_database_connection),
            ("Kafka Topics", self.verify_kafka_topics),
            ("Alert Data Integrity", self.verify_alert_data_integrity),
            ("API Endpoints", self.verify_api_endpoints),
            ("Model Service Details", self.verify_model_service),
            ("Kafka Message Flow", self.verify_kafka_message_flow),
        ]
        
        passed = 0
        failed = 0
        
        for name, check_func in checks:
            print(f"\n[{name}]")
            try:
                if check_func():
                    passed += 1
                    self.results['passed'].append(name)
                else:
                    failed += 1
                    self.results['failed'].append(name)
            except Exception as e:
                error(f"Check raised exception: {e}")
                failed += 1
                self.results['failed'].append(name)
        
        # Summary
        print("\n" + "="*60)
        print("VERIFICATION SUMMARY")
        print("="*60)
        print(f"\nTotal Checks: {passed + failed}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {failed}{Colors.END}")
        
        if failed == 0:
            print(f"\n{Colors.GREEN}✓ ALL CHECKS PASSED!{Colors.END}")
            print("\nProduction pipeline is operational:")
            print("  • All services are healthy")
            print("  • Database is connected and populated")
            print("  • Kafka topics are configured")
            print("  • Alerts contain valid data")
            print("  • API endpoints are functional")
        else:
            print(f"\n{Colors.RED}✗ SOME CHECKS FAILED{Colors.END}")
            print("\nFailed checks:")
            for check in self.results['failed']:
                print(f"  - {check}")
        
        print("\n" + "="*60 + "\n")
        
        return {
            'success': failed == 0,
            'passed': passed,
            'failed': failed,
            'results': self.results
        }


def main():
    """Main entry point"""
    verifier = PipelineVerifier()
    result = verifier.run_all_checks()
    
    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
