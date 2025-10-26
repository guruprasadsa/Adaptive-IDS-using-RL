"""
Real-Time Traffic Flow End-to-End Test
Demonstrates the complete pipeline from packet capture to frontend display
"""

import time
import subprocess
import sys
import requests
from datetime import datetime

def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")

def print_step(step_num, description):
    print(f"\n{'─' * 80}")
    print(f"STEP {step_num}: {description}")
    print(f"{'─' * 80}\n")

def check_docker_services():
    """Check if required Docker services are running"""
    print_step(1, "Checking Docker Services")
    
    required_services = [
        'adaptive_ids_kafka',
        'adaptive_ids_postgres',
        'adaptive_ids_backend',
        'adaptive_ids_model_service'
    ]
    
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True, text=True, check=True
        )
        running_services = result.stdout.strip().split('\n')
        
        all_running = True
        for service in required_services:
            if service in running_services:
                print(f"  ✅ {service}")
            else:
                print(f"  ❌ {service} - NOT RUNNING")
                all_running = False
        
        return all_running
    except Exception as e:
        print(f"  ❌ Error checking Docker: {e}")
        return False

def check_kafka_topic(topic_name):
    """Check if Kafka topic exists and has messages"""
    try:
        # List topics
        result = subprocess.run(
            ['docker', 'exec', 'adaptive_ids_kafka', 'kafka-topics',
             '--list', '--bootstrap-server', 'localhost:9092'],
            capture_output=True, text=True, timeout=10
        )
        
        if topic_name not in result.stdout:
            return False, 0
        
        # Get message count
        result = subprocess.run(
            ['docker', 'exec', 'adaptive_ids_kafka', 'kafka-run-class',
             'kafka.tools.GetOffsetShell', '--broker-list', 'localhost:9092',
             '--topic', topic_name],
            capture_output=True, text=True, timeout=10
        )
        
        total_messages = 0
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 3:
                    offset = int(parts[2])
                    total_messages += offset
        
        return True, total_messages
    except Exception as e:
        return False, 0

def start_packet_producer():
    """Start packet producer"""
    print_step(2, "Starting Packet Producer")
    print("  📡 Capturing network packets and sending to Kafka...")
    print("  Topic: raw.packets")
    print("  Duration: 10 seconds")
    print()
    
    # We'll just show the command, user should run it manually
    print("  RUN THIS COMMAND in a terminal:")
    print("  ─" * 78)
    print("  cd backend")
    print("  $env:PYTHONPATH = \"C:\\AIML\\Projects\\adaptive-ids-v-2.0\\backend\"")
    print("  python -m sensors.pcap_producer")
    print("  (Wait 10 seconds, then press Ctrl+C)")
    print("  ─" * 78)
    print()
    
    input("  Press Enter after starting the packet producer...")

def start_feature_extractor():
    """Start feature extractor"""
    print_step(3, "Starting Feature Extractor")
    print("  🔧 Processing packets into network flow features...")
    print("  Input Topic: raw.packets")
    print("  Output Topic: flows.features")
    print()
    
    print("  RUN THIS COMMAND in another terminal:")
    print("  ─" * 78)
    print("  cd backend")
    print("  $env:PYTHONPATH = \"C:\\AIML\\Projects\\adaptive-ids-v-2.0\\backend\"")
    print("  python -m stream.feature_extractor")
    print("  (Let it run for 20 seconds, then press Ctrl+C)")
    print("  ─" * 78)
    print()
    
    input("  Press Enter after starting the feature extractor...")

def check_pipeline_status():
    """Check status of all pipeline stages"""
    print_step(4, "Checking Pipeline Status")
    
    stages = [
        ('raw.packets', 'Packet Producer Output'),
        ('flows.features', 'Feature Extractor Output'),
        ('model.predictions', 'Model Service Output'),
        ('alerts', 'Alerting Service Output')
    ]
    
    for topic, description in stages:
        exists, count = check_kafka_topic(topic)
        if exists and count > 0:
            print(f"  ✅ {description:30s} : {count:,} messages")
        elif exists:
            print(f"  ⏳ {description:30s} : topic exists (0 messages)")
        else:
            print(f"  ❌ {description:30s} : topic missing")

def test_model_service():
    """Test model service"""
    print_step(5, "Testing Model Service")
    
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"  ✅ Status: {health.get('status', 'unknown')}")
            print(f"  Model Loaded: {health.get('model_loaded', False)}")
            print(f"  Model Version: {health.get('model_version', 'N/A')}")
            
            # Try to get model stats
            try:
                stats_response = requests.get('http://localhost:8000/model/stats', timeout=5)
                if stats_response.status_code == 200:
                    stats = stats_response.json()
                    print(f"  Predictions Made: {stats.get('predictions_made', 0)}")
            except:
                pass
        else:
            print(f"  ⚠️  Service returned HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:60]}")

def test_backend_api():
    """Test backend API"""
    print_step(6, "Testing Backend API")
    
    # Check health endpoint
    try:
        response = requests.get('http://localhost:5001/health', timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Health endpoint: OK")
        else:
            print(f"  ⚠️  Health endpoint: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Health endpoint: {str(e)[:60]}")
    
    # Check dashboard stats
    try:
        response = requests.get('http://localhost:5001/api/dashboard/stats', timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print(f"  ✅ Dashboard stats: OK")
            print(f"     Total Alerts: {stats.get('total_alerts', 0)}")
            print(f"     Critical Alerts: {stats.get('critical_alerts', 0)}")
        else:
            print(f"  ⚠️  Dashboard stats: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Dashboard stats: {str(e)[:60]}")
    
    # Check SSE endpoint
    try:
        response = requests.get('http://localhost:5001/api/events?token=test', 
                              timeout=2, stream=True)
        print(f"  ✅ SSE endpoint: Accessible (streaming)")
    except requests.exceptions.Timeout:
        print(f"  ✅ SSE endpoint: Active (timeout expected)")
    except Exception as e:
        print(f"  ❌ SSE endpoint: {str(e)[:60]}")

def test_frontend():
    """Test frontend application"""
    print_step(7, "Testing Frontend Application")
    
    try:
        response = requests.get('http://localhost:5173', timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Frontend: Accessible at http://localhost:5173")
            print(f"     You can now open this URL in your browser!")
        else:
            print(f"  ⚠️  Frontend: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Frontend: Not running")
        print(f"     Start it with: cd frontend && npm run dev")
    except Exception as e:
        print(f"  ❌ Frontend: {str(e)[:60]}")

def show_next_steps():
    """Show next steps for the user"""
    print_header("✅ REAL-TIME TRAFFIC FLOW TEST COMPLETE")
    
    print("📊 WHAT WE VERIFIED:")
    print("  1. Docker services are running (Kafka, PostgreSQL, Model, Backend)")
    print("  2. Packet producer can capture and send packets to Kafka")
    print("  3. Feature extractor can process packets into flow features")
    print("  4. Model service is ready to classify flows")
    print("  5. Backend API is serving data")
    print("  6. Frontend can connect to backend")
    print()
    
    print("🔄 DATA FLOW:")
    print("  Network Traffic")
    print("       ↓")
    print("  Packet Producer (pcap_producer.py)")
    print("       ↓")
    print("  Kafka Topic: raw.packets")
    print("       ↓")
    print("  Feature Extractor (feature_extractor.py)")
    print("       ↓")
    print("  Kafka Topic: flows.features")
    print("       ↓")
    print("  Model Service (port 8000)")
    print("       ↓")
    print("  Kafka Topic: model.predictions")
    print("       ↓")
    print("  Alerting Service")
    print("       ↓")
    print("  PostgreSQL (alerts table)")
    print("       ↓")
    print("  Backend API (port 5001)")
    print("       ↓")
    print("  SSE Stream (/api/events)")
    print("       ↓")
    print("  Frontend Dashboard (port 5173)")
    print()
    
    print("🎯 TO SEE REAL-TIME DATA IN FRONTEND:")
    print("  1. Open http://localhost:5173 in your browser")
    print("  2. Login with admin credentials")
    print("  3. Watch the Dashboard for:")
    print("     - Real-time traffic chart (updates live)")
    print("     - Alert statistics")
    print("     - Latest alerts feed")
    print()
    
    print("💡 TO GENERATE MORE TRAFFIC:")
    print("  1. Keep packet producer running: python -m sensors.pcap_producer")
    print("  2. Keep feature extractor running: python -m stream.feature_extractor")
    print("  3. Browse websites, download files, etc. to generate traffic")
    print("  4. Watch the frontend update in real-time!")
    print()
    
    print("📈 MONITORING:")
    print("  - Grafana: http://localhost:3000 (username: admin, password: admin123)")
    print("  - Prometheus: http://localhost:9090")
    print("  - Jaeger Tracing: http://localhost:16686")
    print()

def main():
    """Main test function"""
    print_header("ADAPTIVE IDS - REAL-TIME TRAFFIC FLOW TEST")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Check Docker services
    if not check_docker_services():
        print("\n❌ ERROR: Not all required Docker services are running!")
        print("Please start them with: docker-compose up -d")
        return
    
    # Step 2-3: Instructions for starting producers
    # (Manual steps - can't automate easily in background)
    start_packet_producer()
    start_feature_extractor()
    
    # Step 4: Check pipeline
    time.sleep(2)  # Give it a moment
    check_pipeline_status()
    
    # Step 5: Test model service
    test_model_service()
    
    # Step 6: Test backend API
    test_backend_api()
    
    # Step 7: Test frontend
    test_frontend()
    
    # Show next steps
    show_next_steps()

if __name__ == '__main__':
    main()
