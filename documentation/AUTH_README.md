# JWT Authentication System for Adaptive IDS

## Overview

This document provides instructions for setting up and using the JWT-based authentication system for Adaptive IDS v2.0. The system includes user registration, login, logout, token refresh, and protected API endpoints.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Environment Setup](#environment-setup)
- [Database Schema](#database-schema)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Features

- ✅ User registration with email/username validation
- ✅ Secure password hashing using bcrypt (work factor 12+)
- ✅ JWT-based authentication with short-lived access tokens (15 min)
- ✅ Long-lived refresh tokens (7 days) with revocation support
- ✅ Protected API endpoints requiring authentication
- ✅ Token refresh mechanism for seamless user experience
- ✅ User logout with token revocation
- ✅ Role-based access (analyst, admin)
- ✅ Token hashing in database to prevent leaks
- ✅ Clock skew handling (30s leeway)

## Architecture

### Components

1. **Backend (`backend/api/`):**
   - `app.py` - Main Flask application
   - `auth.py` - Authentication module with JWT utilities and routes

2. **Database (`backend/db/schema.sql`):**
   - `users` table - User accounts
   - `refresh_tokens` table - Refresh token storage

3. **Scripts (`backend/scripts/`):**
   - `create_admin.py` - Create initial admin user

4. **Tests (`backend/tests/`):**
   - `test_auth.py` - Comprehensive authentication tests

5. **Frontend (`frontend/frontend/api.ts`):**
   - Token management and automatic refresh

### Authentication Flow

```
┌──────────┐           ┌──────────┐           ┌──────────┐
│  Client  │           │   API    │           │ Database │
└────┬─────┘           └────┬─────┘           └────┬─────┘
     │                      │                      │
     │  POST /auth/login    │                      │
     │─────────────────────>│                      │
     │                      │  Verify credentials  │
     │                      │─────────────────────>│
     │                      │                      │
     │  access_token +      │                      │
     │  refresh_token       │                      │
     │<─────────────────────│                      │
     │                      │                      │
     │  GET /api/alerts     │                      │
     │  (Bearer token)      │                      │
     │─────────────────────>│                      │
     │                      │  Verify JWT          │
     │                      │                      │
     │  Response            │                      │
     │<─────────────────────│                      │
     │                      │                      │
     │  POST /auth/refresh  │                      │
     │─────────────────────>│                      │
     │                      │  Verify refresh token│
     │                      │─────────────────────>│
     │  new access_token    │                      │
     │<─────────────────────│                      │
     │                      │                      │
```

## Environment Setup

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```env
# Flask configuration
SECRET_KEY=your-secret-key-change-this-in-production
JWT_SECRET=your-jwt-secret-change-this-in-production

# JWT token expiration times (in seconds)
ACCESS_TOKEN_TTL=900         # 15 minutes
REFRESH_TOKEN_TTL=604800     # 7 days

# PostgreSQL database configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=adaptive_ids
POSTGRES_USER=adaptive_ids
POSTGRES_PASSWORD=adaptive_ids_password

# Admin user creation (used by create_admin.py script)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@adaptive-ids.local
ADMIN_PASSWORD=change-this-password
```

**⚠️ IMPORTANT:** Change `SECRET_KEY`, `JWT_SECRET`, and `ADMIN_PASSWORD` in production!

## Database Schema

The authentication system adds two tables:

### `users` Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'analyst',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);
```

### `refresh_tokens` Table

```sql
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);
```

## Installation

### 1. Start PostgreSQL Database

```powershell
# Start PostgreSQL container
docker compose up -d postgres

# Verify it's running
docker ps
```

**Note:** If you need to reinitialize the database schema:
```powershell
docker compose down -v
docker compose up -d postgres
```

### 2. Install Python Dependencies

```powershell
# Activate virtual environment (if using one)
.\.venv\Scripts\activate

# Install dependencies
pip install -r backend\requirements.txt
```

### 3. Create Admin User

```powershell
# Using environment variables
python backend\scripts\create_admin.py

# Or prompt for credentials interactively
python backend\scripts\create_admin.py
```

Output:
```
============================================================
Adaptive IDS - Admin User Creation
============================================================

Enter admin user credentials:

Username: admin
Email: admin@adaptive-ids.local
Password: ********
Confirm password: ********

Creating admin user...

✓ Admin user created successfully!
  ID: 1
  Username: admin
  Email: admin@adaptive-ids.local
  Role: admin
  Created: 2025-10-20T12:34:56.789Z
```

## Running the Application

### Start Backend API

```powershell
# Navigate to backend API directory
cd backend\api

# Run Flask app
python app.py
```

The API will be available at `http://localhost:5000`.

### Verify Authentication

Check that auth routes are loaded:
```
INFO:root:Authentication module loaded successfully
 * Running on http://0.0.0.0:5000
```

## API Endpoints

### Public Endpoints

#### Health Check
```http
GET /api/health
```

Response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "timestamp": "2025-10-20T12:34:56.789Z"
}
```

#### Prediction (No auth required)
```http
POST /api/predict
```

### Authentication Endpoints

#### 1. Register New User

```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "analyst1",
  "email": "analyst1@company.com",
  "password": "SecurePass123"
}
```

**Response (201):**
```json
{
  "user": {
    "id": 2,
    "username": "analyst1",
    "email": "analyst1@company.com",
    "role": "analyst",
    "created_at": "2025-10-20T12:35:00.000Z"
  }
}
```

**Validation Rules:**
- Username: 3-64 characters, alphanumeric, hyphens, underscores
- Email: Valid email format
- Password: Minimum 8 characters, at least one letter

**Windows curl example:**
```powershell
curl -X POST http://localhost:5000/api/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"analyst1\",\"email\":\"analyst1@company.com\",\"password\":\"SecurePass123\"}"
```

#### 2. Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "email_or_username": "admin@adaptive-ids.local",
  "password": "your-admin-password"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@adaptive-ids.local",
    "role": "admin"
  }
}
```

**Windows curl example:**
```powershell
curl -X POST http://localhost:5000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email_or_username\":\"admin\",\"password\":\"your-admin-password\"}"
```

#### 3. Get Current User

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@adaptive-ids.local",
  "role": "admin",
  "created_at": "2025-10-20T12:00:00.000Z",
  "last_login": "2025-10-20T12:35:00.000Z"
}
```

**Windows curl example:**
```powershell
curl http://localhost:5000/api/auth/me ^
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### 4. Refresh Token

```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Windows curl example:**
```powershell
curl -X POST http://localhost:5000/api/auth/refresh ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\":\"YOUR_REFRESH_TOKEN\"}"
```

#### 5. Logout

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "ok": true
}
```

**Windows curl example:**
```powershell
curl -X POST http://localhost:5000/api/auth/logout ^
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\":\"YOUR_REFRESH_TOKEN\"}"
```

### Protected Endpoints

All protected endpoints require `Authorization: Bearer <access_token>` header.

**Errors (401 Unauthorized):**
```json
{
  "error": "unauthorized",
  "message": "Missing authorization header"
}
```

#### Alerts

```http
GET /api/alerts?page=1&per_page=10
Authorization: Bearer <access_token>

GET /api/alerts/{alert_id}
Authorization: Bearer <access_token>

PATCH /api/alerts/{alert_id}/status
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "status": "resolved"
}
```

#### Incidents

```http
GET /api/incidents?page=1&per_page=10
Authorization: Bearer <access_token>

GET /api/incidents/{incident_id}
Authorization: Bearer <access_token>

PATCH /api/incidents/{incident_id}/status
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "status": "resolved"
}
```

#### Dashboard

```http
GET /api/dashboard/stats
Authorization: Bearer <access_token>
```

**Windows curl example with auth:**
```powershell
curl http://localhost:5000/api/alerts ^
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Testing

### Run Tests

```powershell
# Ensure database is running
docker compose up -d postgres

# Run tests
cd backend
pytest tests/test_auth.py -v
```

### Test Coverage

The test suite covers:
- ✅ User registration (success, validation, duplicates)
- ✅ User login (email/username, invalid credentials)
- ✅ Get current user (with/without token)
- ✅ Token refresh (valid/invalid tokens)
- ✅ Logout (with/without refresh token)
- ✅ Protected endpoints (access control)
- ✅ Complete authentication flow

### Manual Testing Script

```powershell
# 1. Register a user
$register = @{
    username = "testuser"
    email = "testuser@test.com"
    password = "TestPass123"
} | ConvertTo-Json

$regResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/auth/register" `
  -Method POST -Body $register -ContentType "application/json"

# 2. Login
$login = @{
    email_or_username = "testuser"
    password = "TestPass123"
} | ConvertTo-Json

$loginResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/auth/login" `
  -Method POST -Body $login -ContentType "application/json"

$accessToken = $loginResponse.access_token
$refreshToken = $loginResponse.refresh_token

# 3. Access protected endpoint
$headers = @{
    Authorization = "Bearer $accessToken"
}

$alerts = Invoke-RestMethod -Uri "http://localhost:5000/api/alerts" `
  -Headers $headers

# 4. Get current user
$me = Invoke-RestMethod -Uri "http://localhost:5000/api/auth/me" `
  -Headers $headers

Write-Host "Current user: $($me.username)"

# 5. Refresh token
$refresh = @{
    refresh_token = $refreshToken
} | ConvertTo-Json

$refreshResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/auth/refresh" `
  -Method POST -Body $refresh -ContentType "application/json"

# 6. Logout
$logout = @{
    refresh_token = $refreshToken
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/auth/logout" `
  -Method POST -Headers $headers -Body $logout -ContentType "application/json"

Write-Host "✓ Authentication flow completed successfully"
```

## Security Considerations

### Password Security
- ✅ Bcrypt hashing with work factor 12+
- ✅ Passwords never stored in plaintext
- ✅ Minimum 8 characters with letter requirement

### Token Security
- ✅ Short-lived access tokens (15 minutes)
- ✅ Refresh tokens hashed before storage (SHA-256)
- ✅ HS256 algorithm for JWT signing
- ✅ JWT secrets from environment variables
- ✅ Clock skew tolerance (30 seconds)
- ✅ Token revocation on logout

### Database Security
- ✅ Unique constraints on username/email
- ✅ Foreign key constraints with CASCADE
- ✅ Indexed columns for performance
- ✅ Connection pooling via psycopg2

### CORS Configuration
- ⚠️ Currently allows all origins (`"*"`)
- 🔧 In production, update `CORS()` in `app.py`:
  ```python
  CORS(app, resources={
      r"/api/*": {
          "origins": ["https://your-frontend-domain.com"],
          "methods": ["GET", "POST", "PATCH", "DELETE"],
          "allow_headers": ["Content-Type", "Authorization"]
      }
  })
  ```

### Rate Limiting
- ⚠️ Not currently implemented
- 🔧 Consider adding Flask-Limiter:
  ```python
  from flask_limiter import Limiter
  limiter = Limiter(app, key_func=lambda: request.remote_addr)
  
  @app.route('/api/auth/login', methods=['POST'])
  @limiter.limit("5 per minute")
  def login():
      ...
  ```

## Troubleshooting

### Database Connection Issues

**Problem:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
```powershell
# Check if PostgreSQL is running
docker ps

# Check logs
docker logs adaptive_ids_postgres

# Restart container
docker compose restart postgres
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'jwt'`

**Solution:**
```powershell
# Reinstall dependencies
pip install -r backend\requirements.txt
```

### Token Errors

**Problem:** `401 Unauthorized` on protected endpoints

**Solutions:**
1. Check token is not expired (access tokens expire after 15 minutes)
2. Use refresh endpoint to get new access token
3. Verify `Authorization: Bearer <token>` header format
4. Check JWT_SECRET matches between token generation and verification

### Schema Issues

**Problem:** `relation "users" does not exist`

**Solution:**
```powershell
# Reinitialize database (WARNING: deletes all data)
docker compose down -v
docker compose up -d postgres

# Wait a few seconds for initialization
timeout /t 5

# Recreate admin user
python backend\scripts\create_admin.py
```

### Admin Creation Fails

**Problem:** `User already exists`

**Solution:**
```powershell
# Connect to database
docker exec -it adaptive_ids_postgres psql -U adaptive_ids -d adaptive_ids

# Check existing users
SELECT * FROM users;

# Delete specific user if needed
DELETE FROM users WHERE username = 'admin';

# Exit
\q
```

## Frontend Integration

The frontend `api.ts` automatically handles:
- ✅ Token storage in localStorage
- ✅ Automatic token refresh on 401 errors
- ✅ Authorization header injection
- ✅ Token cleanup on logout

### Usage Example

```typescript
import { apiService } from './api';

// Login
const loginResponse = await apiService.login('admin', 'password');
console.log('Logged in as:', loginResponse.user.username);

// Access protected endpoint (token added automatically)
const alerts = await apiService.getAlerts(1, 10);

// Check authentication status
if (apiService.isAuthenticated()) {
  const user = await apiService.getCurrentUser();
}

// Logout
await apiService.logout();
```

## Production Deployment Checklist

- [ ] Generate strong random values for `SECRET_KEY` and `JWT_SECRET`
- [ ] Use HTTPS for all API communication
- [ ] Configure specific CORS origins (no wildcards)
- [ ] Implement rate limiting on auth endpoints
- [ ] Set up database backups
- [ ] Enable database SSL connections
- [ ] Use environment-specific `.env` files
- [ ] Add monitoring for failed login attempts
- [ ] Implement password reset functionality
- [ ] Consider multi-factor authentication (MFA)
- [ ] Set up logging and audit trails
- [ ] Use secrets management service (e.g., Azure Key Vault, AWS Secrets Manager)

## Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [Flask-Bcrypt Documentation](https://flask-bcrypt.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

## Support

For issues or questions:
1. Check this documentation
2. Review test cases in `backend/tests/test_auth.py`
3. Check application logs
4. Verify environment variables in `.env`

---

**Last Updated:** October 20, 2025
