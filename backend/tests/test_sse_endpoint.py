"""
Test script for SSE endpoint.
This script will:
1. Create a test admin user (if needed)
2. Login to get a JWT token
3. Test the SSE /api/events endpoint
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / 'backend' / '.env')

API_BASE = os.getenv('API_BASE', 'http://localhost:5000/api')

# Test credentials
TEST_USER = {
    'username': 'testadmin',
    'email': 'testadmin@adaptiveids.local',
    'password': 'TestAdmin123!'
}


def create_test_user():
    """Create test admin user if it doesn't exist"""
    print("🔧 Setting up test user...")
    
    # We'll use the database directly
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    try:
        # Import bcrypt for password hashing
        from flask_bcrypt import Bcrypt
        from flask import Flask
        
        app = Flask(__name__)
        bcrypt = Bcrypt(app)
        password_hash = bcrypt.generate_password_hash(TEST_USER['password']).decode('utf-8')
        
        config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '55432')),
            'dbname': os.getenv('POSTGRES_DB', 'adaptive_ids'),
            'user': os.getenv('POSTGRES_USER', 'adaptive_ids'),
            'password': os.getenv('POSTGRES_PASSWORD', 'adaptive_ids_password'),
        }
        
        conn = psycopg2.connect(**config)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if user exists
            cur.execute(
                "SELECT id FROM users WHERE username = %s",
                (TEST_USER['username'],)
            )
            if cur.fetchone():
                print(f"  ✓ Test user '{TEST_USER['username']}' already exists")
                conn.close()
                return True
            
            # Create user
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, 'admin', true)
                RETURNING id
                """,
                (TEST_USER['username'], TEST_USER['email'], password_hash)
            )
            user_id = cur.fetchone()['id']
            conn.commit()
            print(f"  ✓ Created test user '{TEST_USER['username']}' (ID: {user_id})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ✗ Error creating test user: {e}")
        print(f"    You may need to create the users table first")
        return False


def login():
    """Login and get JWT token"""
    print("\n🔑 Logging in...")
    
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={
                'email_or_username': TEST_USER['username'],
                'password': TEST_USER['password']
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            print(f"  ✓ Login successful!")
            print(f"  Token: {token[:50]}..." if len(token) > 50 else f"  Token: {token}")
            return token
        else:
            print(f"  ✗ Login failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"  ✗ Error during login: {e}")
        return None


def test_sse_stream(token):
    """Test SSE endpoint"""
    print("\n📡 Testing SSE endpoint...")
    print(f"  URL: {API_BASE}/events?token=...")
    
    try:
        # Use requests with stream=True for SSE
        response = requests.get(
            f"{API_BASE}/events",
            params={'token': token},
            headers={'Accept': 'text/event-stream'},
            stream=True,
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"  ✗ Failed to connect: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
        
        print(f"  ✓ Connected successfully!")
        print(f"  Content-Type: {response.headers.get('Content-Type')}")
        print("\n📨 Receiving events (Ctrl+C to stop)...\n")
        
        # Read events
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"  {line}")
                if line.startswith('event:') or line.startswith('data:'):
                    event_count += 1
                    
                    # Stop after a few events for testing
                    if event_count >= 10:
                        print("\n  ✓ Received 10+ lines, stopping test...")
                        break
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n  ⏸  Stopped by user")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_alerts_query(token):
    """Test alert query endpoint"""
    print("\n📋 Testing alerts query endpoint...")
    
    try:
        response = requests.get(
            f"{API_BASE}/alerts",
            headers={'Authorization': f'Bearer {token}'},
            params={
                'page': 1,
                'per_page': 5,
                'severity': 'HIGH'
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Query successful!")
            print(f"    Total alerts: {data.get('total', 0)}")
            print(f"    Alerts on page: {len(data.get('alerts', []))}")
            return True
        else:
            print(f"  ✗ Query failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Main test function"""
    print("=" * 70)
    print("  Adaptive IDS - SSE Endpoint Test")
    print("=" * 70)
    
    # Check if backend is running
    print("\n🏥 Checking backend health...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"  ✓ Backend is running")
            print(f"    Status: {health.get('status')}")
            print(f"    Database: {health.get('database')}")
            print(f"    Model loaded: {health.get('model_loaded')}")
        else:
            print(f"  ✗ Backend returned: {response.status_code}")
            print("  ⚠ Make sure backend is running: python backend/api/app.py")
            sys.exit(1)
    except Exception as e:
        print(f"  ✗ Cannot connect to backend: {e}")
        print(f"  ⚠ Make sure backend is running at {API_BASE}")
        sys.exit(1)
    
    # Create test user
    if not create_test_user():
        print("\n⚠ Warning: Could not create test user, trying to login anyway...")
    
    # Login
    token = login()
    if not token:
        print("\n❌ Cannot proceed without valid token")
        print("\nAlternative: Create an admin user manually:")
        print("  python backend/scripts/create_admin.py")
        sys.exit(1)
    
    # Test alerts query
    test_alerts_query(token)
    
    # Test SSE stream
    test_sse_stream(token)
    
    print("\n" + "=" * 70)
    print("  Test complete!")
    print("=" * 70)
    print("\n💡 To use the SSE endpoint in your application:")
    print(f"   const token = '{token[:30]}...'")
    print(f"   const es = new EventSource('/api/events?token=' + token);")
    print(f"   es.addEventListener('alert', (e) => console.log(JSON.parse(e.data)));")
    print()


if __name__ == '__main__':
    main()
