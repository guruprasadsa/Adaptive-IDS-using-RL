"""
backend/tests/test_auth.py
Tests for JWT-based authentication system
"""

import json
import os
import sys
from pathlib import Path

import pytest

# Add api directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'api'))

from app import app
from auth import hash_password, hash_token


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_cursor():
    """Create database cursor for test setup/teardown"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '55432')),
        'dbname': os.getenv('POSTGRES_DB', 'adaptive_ids'),
        'user': os.getenv('POSTGRES_USER', 'adaptive_ids'),
        'password': os.getenv('POSTGRES_PASSWORD', 'adaptive_ids_password'),
    }
    
    conn = psycopg2.connect(**config)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def test_user(db_cursor):
    """Create a test user"""
    username = 'testuser'
    email = 'testuser@test.com'
    password = 'TestPassword123'
    password_hash = hash_password(password)
    
    # Clean up if exists
    db_cursor.execute("DELETE FROM users WHERE username = %s OR email = %s", (username, email))
    
    # Insert test user
    db_cursor.execute(
        """
        INSERT INTO users (username, email, password_hash, role)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (username, email, password_hash, 'analyst')
    )
    user_id = db_cursor.fetchone()['id']
    
    yield {
        'id': user_id,
        'username': username,
        'email': email,
        'password': password,
    }
    
    # Cleanup
    db_cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))


class TestAuthRegistration:
    """Test user registration"""
    
    def test_register_success(self, client, db_cursor):
        """Test successful user registration"""
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'SecurePass123',
        }
        
        response = client.post('/api/auth/register', json=data)
        assert response.status_code == 201
        
        result = json.loads(response.data)
        assert 'user' in result
        assert result['user']['username'] == 'newuser'
        assert result['user']['email'] == 'newuser@test.com'
        assert result['user']['role'] == 'analyst'
        
        # Cleanup
        db_cursor.execute("DELETE FROM users WHERE username = %s", ('newuser',))
    
    def test_register_duplicate_username(self, client, test_user):
        """Test registration with duplicate username"""
        data = {
            'username': test_user['username'],
            'email': 'different@test.com',
            'password': 'SecurePass123',
        }
        
        response = client.post('/api/auth/register', json=data)
        assert response.status_code == 409
        
        result = json.loads(response.data)
        assert 'error' in result
        assert result['error'] == 'conflict'
    
    def test_register_duplicate_email(self, client, test_user):
        """Test registration with duplicate email"""
        data = {
            'username': 'differentuser',
            'email': test_user['email'],
            'password': 'SecurePass123',
        }
        
        response = client.post('/api/auth/register', json=data)
        assert response.status_code == 409
    
    def test_register_invalid_email(self, client):
        """Test registration with invalid email"""
        data = {
            'username': 'newuser',
            'email': 'invalid-email',
            'password': 'SecurePass123',
        }
        
        response = client.post('/api/auth/register', json=data)
        assert response.status_code == 400
        
        result = json.loads(response.data)
        assert 'error' in result
        assert result['error'] == 'validation_error'
    
    def test_register_short_password(self, client):
        """Test registration with short password"""
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'short',
        }
        
        response = client.post('/api/auth/register', json=data)
        assert response.status_code == 400
    
    def test_register_missing_fields(self, client):
        """Test registration with missing fields"""
        data = {
            'username': 'newuser',
            # Missing email and password
        }
        
        response = client.post('/api/auth/register', json=data)
        assert response.status_code == 400


class TestAuthLogin:
    """Test user login"""
    
    def test_login_success_with_email(self, client, test_user):
        """Test successful login with email"""
        data = {
            'email_or_username': test_user['email'],
            'password': test_user['password'],
        }
        
        response = client.post('/api/auth/login', json=data)
        assert response.status_code == 200
        
        result = json.loads(response.data)
        assert 'access_token' in result
        assert 'refresh_token' in result
        assert 'user' in result
        assert result['user']['username'] == test_user['username']
        assert result['user']['email'] == test_user['email']
    
    def test_login_success_with_username(self, client, test_user):
        """Test successful login with username"""
        data = {
            'email_or_username': test_user['username'],
            'password': test_user['password'],
        }
        
        response = client.post('/api/auth/login', json=data)
        assert response.status_code == 200
        
        result = json.loads(response.data)
        assert 'access_token' in result
        assert 'refresh_token' in result
    
    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid password"""
        data = {
            'email_or_username': test_user['email'],
            'password': 'WrongPassword',
        }
        
        response = client.post('/api/auth/login', json=data)
        assert response.status_code == 401
        
        result = json.loads(response.data)
        assert 'error' in result
        assert result['error'] == 'unauthorized'
    
    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user"""
        data = {
            'email_or_username': 'nonexistent@test.com',
            'password': 'SomePassword123',
        }
        
        response = client.post('/api/auth/login', json=data)
        assert response.status_code == 401
    
    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        data = {
            'email_or_username': 'test@test.com',
            # Missing password
        }
        
        response = client.post('/api/auth/login', json=data)
        assert response.status_code == 400


class TestAuthMe:
    """Test get current user endpoint"""
    
    def test_me_success(self, client, test_user):
        """Test getting current user with valid token"""
        # Login first
        login_data = {
            'email_or_username': test_user['email'],
            'password': test_user['password'],
        }
        login_response = client.post('/api/auth/login', json=login_data)
        tokens = json.loads(login_response.data)
        access_token = tokens['access_token']
        
        # Get current user
        headers = {'Authorization': f'Bearer {access_token}'}
        response = client.get('/api/auth/me', headers=headers)
        assert response.status_code == 200
        
        result = json.loads(response.data)
        assert result['username'] == test_user['username']
        assert result['email'] == test_user['email']
        assert 'password_hash' not in result  # Should not expose password
    
    def test_me_missing_token(self, client):
        """Test getting current user without token"""
        response = client.get('/api/auth/me')
        assert response.status_code == 401
    
    def test_me_invalid_token(self, client):
        """Test getting current user with invalid token"""
        headers = {'Authorization': 'Bearer invalid-token'}
        response = client.get('/api/auth/me', headers=headers)
        assert response.status_code == 401


class TestAuthRefresh:
    """Test token refresh"""
    
    def test_refresh_success(self, client, test_user):
        """Test successful token refresh"""
        # Login first
        login_data = {
            'email_or_username': test_user['email'],
            'password': test_user['password'],
        }
        login_response = client.post('/api/auth/login', json=login_data)
        tokens = json.loads(login_response.data)
        refresh_token = tokens['refresh_token']
        
        # Refresh token
        refresh_data = {'refresh_token': refresh_token}
        response = client.post('/api/auth/refresh', json=refresh_data)
        assert response.status_code == 200
        
        result = json.loads(response.data)
        assert 'access_token' in result
    
    def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token"""
        refresh_data = {'refresh_token': 'invalid-token'}
        response = client.post('/api/auth/refresh', json=refresh_data)
        assert response.status_code == 401
    
    def test_refresh_missing_token(self, client):
        """Test refresh with missing token"""
        response = client.post('/api/auth/refresh', json={})
        assert response.status_code == 400


class TestAuthLogout:
    """Test logout"""
    
    def test_logout_success(self, client, test_user):
        """Test successful logout"""
        # Login first
        login_data = {
            'email_or_username': test_user['email'],
            'password': test_user['password'],
        }
        login_response = client.post('/api/auth/login', json=login_data)
        tokens = json.loads(login_response.data)
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']
        
        # Logout
        headers = {'Authorization': f'Bearer {access_token}'}
        logout_data = {'refresh_token': refresh_token}
        response = client.post('/api/auth/logout', headers=headers, json=logout_data)
        assert response.status_code == 200
        
        result = json.loads(response.data)
        assert result['ok'] is True
        
        # Try to refresh with revoked token (should fail)
        refresh_response = client.post('/api/auth/refresh', json={'refresh_token': refresh_token})
        assert refresh_response.status_code == 401
    
    def test_logout_without_refresh_token(self, client, test_user):
        """Test logout without providing refresh token"""
        # Login first
        login_data = {
            'email_or_username': test_user['email'],
            'password': test_user['password'],
        }
        login_response = client.post('/api/auth/login', json=login_data)
        tokens = json.loads(login_response.data)
        access_token = tokens['access_token']
        
        # Logout without refresh token
        headers = {'Authorization': f'Bearer {access_token}'}
        response = client.post('/api/auth/logout', headers=headers, json={})
        assert response.status_code == 200


class TestProtectedEndpoints:
    """Test protected API endpoints"""
    
    def test_alerts_requires_auth(self, client):
        """Test that alerts endpoint requires authentication"""
        response = client.get('/api/alerts')
        assert response.status_code == 401
    
    def test_alerts_with_auth(self, client, test_user):
        """Test that alerts endpoint works with valid token"""
        # Login first
        login_data = {
            'email_or_username': test_user['email'],
            'password': test_user['password'],
        }
        login_response = client.post('/api/auth/login', json=login_data)
        tokens = json.loads(login_response.data)
        access_token = tokens['access_token']
        
        # Access protected endpoint
        headers = {'Authorization': f'Bearer {access_token}'}
        response = client.get('/api/alerts', headers=headers)
        # Should succeed (200) or fail with database error (503), but not 401
        assert response.status_code in (200, 503)
    
    def test_incidents_requires_auth(self, client):
        """Test that incidents endpoint requires authentication"""
        response = client.get('/api/incidents')
        assert response.status_code == 401
    
    def test_dashboard_requires_auth(self, client):
        """Test that dashboard endpoint requires authentication"""
        response = client.get('/api/dashboard/stats')
        assert response.status_code == 401


class TestFullAuthFlow:
    """Test complete authentication flow"""
    
    def test_complete_flow(self, client, db_cursor):
        """Test register -> login -> me -> refresh -> logout flow"""
        # 1. Register
        register_data = {
            'username': 'flowtest',
            'email': 'flowtest@test.com',
            'password': 'FlowTest123',
        }
        register_response = client.post('/api/auth/register', json=register_data)
        assert register_response.status_code == 201
        
        # 2. Login
        login_data = {
            'email_or_username': 'flowtest@test.com',
            'password': 'FlowTest123',
        }
        login_response = client.post('/api/auth/login', json=login_data)
        assert login_response.status_code == 200
        tokens = json.loads(login_response.data)
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']
        
        # 3. Get current user
        headers = {'Authorization': f'Bearer {access_token}'}
        me_response = client.get('/api/auth/me', headers=headers)
        assert me_response.status_code == 200
        user_data = json.loads(me_response.data)
        assert user_data['username'] == 'flowtest'
        
        # 4. Refresh token
        refresh_response = client.post('/api/auth/refresh', json={'refresh_token': refresh_token})
        assert refresh_response.status_code == 200
        new_tokens = json.loads(refresh_response.data)
        new_access_token = new_tokens['access_token']
        
        # 5. Use new access token
        new_headers = {'Authorization': f'Bearer {new_access_token}'}
        me_response2 = client.get('/api/auth/me', headers=new_headers)
        assert me_response2.status_code == 200
        
        # 6. Logout
        logout_response = client.post('/api/auth/logout', headers=new_headers, json={'refresh_token': refresh_token})
        assert logout_response.status_code == 200
        
        # 7. Verify refresh token is revoked
        refresh_again = client.post('/api/auth/refresh', json={'refresh_token': refresh_token})
        assert refresh_again.status_code == 401
        
        # Cleanup
        db_cursor.execute("DELETE FROM users WHERE username = %s", ('flowtest',))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
