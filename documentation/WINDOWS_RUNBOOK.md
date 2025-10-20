# Windows Quick Start Guide - Adaptive IDS Authentication

## Prerequisites
- Docker Desktop installed and running
- Python 3.9+ installed
- Git Bash or PowerShell

## Step-by-Step Setup

### 1. Start PostgreSQL Database

```powershell
# Navigate to project root
cd c:\AIML\Projects\adaptive-ids-v-2.0

# Start PostgreSQL (detached mode)
docker compose up -d postgres

# Verify it's running
docker ps

# You should see: adaptive_ids_postgres ... Up
```

### 2. Set Up Python Environment

```powershell
# Create virtual environment (if not exists)
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\activate

# Install dependencies
pip install -r backend\requirements.txt
```

### 3. Configure Environment Variables

```powershell
# Copy example env file
copy .env.example .env

# Edit .env file with your preferred text editor
notepad .env

# Update these values:
# SECRET_KEY=<generate-random-string>
# JWT_SECRET=<generate-random-string>
# ADMIN_PASSWORD=<your-secure-password>
```

**Generate secure secrets (PowerShell):**
```powershell
# Generate random secret keys
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
```

### 4. Create Admin User

```powershell
# Using environment variables from .env
python backend\scripts\create_admin.py

# Or provide credentials interactively
python backend\scripts\create_admin.py
```

Expected output:
```
============================================================
Adaptive IDS - Admin User Creation
============================================================

✓ Admin user created successfully!
  ID: 1
  Username: admin
  Email: admin@adaptive-ids.local
  Role: admin
```

### 5. Start Backend API

```powershell
# Navigate to API directory
cd backend\api

# Run Flask app
python app.py
```

Expected output:
```
INFO:root:Authentication module loaded successfully
 * Running on http://0.0.0.0:5000
```

**Keep this terminal open!**

### 6. Test Authentication (New Terminal)

Open a new PowerShell window:

```powershell
# Test health endpoint
curl http://localhost:5000/api/health

# Test login (replace password with your admin password)
curl -X POST http://localhost:5000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email_or_username\":\"admin\",\"password\":\"your-admin-password\"}"
```

Expected response:
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@adaptive-ids.local",
    "role": "admin"
  }
}
```

### 7. Test Protected Endpoint

```powershell
# Save your access token
$token = "YOUR_ACCESS_TOKEN_FROM_LOGIN"

# Test protected endpoint
curl http://localhost:5000/api/alerts ^
  -H "Authorization: Bearer $token"
```

## PowerShell Complete Test Script

Save this as `test-auth.ps1`:

```powershell
# Test complete authentication flow

$baseUrl = "http://localhost:5000"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Adaptive IDS - Authentication Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Health Check
Write-Host "1. Testing health endpoint..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/api/health"
    Write-Host "   ✓ Health check passed: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Health check failed: $_" -ForegroundColor Red
    exit 1
}

# 2. Register new user
Write-Host "`n2. Registering new user..." -ForegroundColor Yellow
$register = @{
    username = "testuser_$(Get-Random -Maximum 9999)"
    email = "testuser_$(Get-Random -Maximum 9999)@test.com"
    password = "TestPass123"
} | ConvertTo-Json

try {
    $regResponse = Invoke-RestMethod -Uri "$baseUrl/api/auth/register" `
      -Method POST -Body $register -ContentType "application/json"
    Write-Host "   ✓ User registered: $($regResponse.user.username)" -ForegroundColor Green
    $username = $regResponse.user.username
    $email = $regResponse.user.email
} catch {
    Write-Host "   ✗ Registration failed: $_" -ForegroundColor Red
    exit 1
}

# 3. Login
Write-Host "`n3. Logging in..." -ForegroundColor Yellow
$login = @{
    email_or_username = $username
    password = "TestPass123"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "$baseUrl/api/auth/login" `
      -Method POST -Body $login -ContentType "application/json"
    Write-Host "   ✓ Login successful" -ForegroundColor Green
    $accessToken = $loginResponse.access_token
    $refreshToken = $loginResponse.refresh_token
} catch {
    Write-Host "   ✗ Login failed: $_" -ForegroundColor Red
    exit 1
}

# 4. Get current user
Write-Host "`n4. Getting current user info..." -ForegroundColor Yellow
$headers = @{
    Authorization = "Bearer $accessToken"
}

try {
    $me = Invoke-RestMethod -Uri "$baseUrl/api/auth/me" -Headers $headers
    Write-Host "   ✓ Current user: $($me.username) ($($me.role))" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Get current user failed: $_" -ForegroundColor Red
    exit 1
}

# 5. Access protected endpoint
Write-Host "`n5. Accessing protected endpoint (alerts)..." -ForegroundColor Yellow
try {
    $alerts = Invoke-RestMethod -Uri "$baseUrl/api/alerts?page=1&per_page=5" `
      -Headers $headers
    Write-Host "   ✓ Alerts retrieved: $($alerts.total) total" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Alerts access failed: $_" -ForegroundColor Red
}

# 6. Refresh token
Write-Host "`n6. Refreshing access token..." -ForegroundColor Yellow
$refresh = @{
    refresh_token = $refreshToken
} | ConvertTo-Json

try {
    $refreshResponse = Invoke-RestMethod -Uri "$baseUrl/api/auth/refresh" `
      -Method POST -Body $refresh -ContentType "application/json"
    Write-Host "   ✓ Token refreshed successfully" -ForegroundColor Green
    $newAccessToken = $refreshResponse.access_token
} catch {
    Write-Host "   ✗ Token refresh failed: $_" -ForegroundColor Red
}

# 7. Logout
Write-Host "`n7. Logging out..." -ForegroundColor Yellow
$logout = @{
    refresh_token = $refreshToken
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$baseUrl/api/auth/logout" `
      -Method POST -Headers $headers -Body $logout -ContentType "application/json"
    Write-Host "   ✓ Logout successful" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Logout failed: $_" -ForegroundColor Red
}

# 8. Verify token is revoked
Write-Host "`n8. Verifying token revocation..." -ForegroundColor Yellow
try {
    Invoke-RestMethod -Uri "$baseUrl/api/auth/refresh" `
      -Method POST -Body $refresh -ContentType "application/json"
    Write-Host "   ✗ Token should be revoked but still works!" -ForegroundColor Red
} catch {
    Write-Host "   ✓ Token correctly revoked" -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "✓ All tests completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
```

Run the test:
```powershell
.\test-auth.ps1
```

## Common Commands

### Database Management

```powershell
# Stop database
docker compose stop postgres

# Start database
docker compose start postgres

# View logs
docker logs adaptive_ids_postgres

# Connect to database
docker exec -it adaptive_ids_postgres psql -U adaptive_ids -d adaptive_ids

# Reinitialize database (⚠️ DELETES ALL DATA)
docker compose down -v
docker compose up -d postgres
```

### Check Running Processes

```powershell
# Check Docker containers
docker ps

# Check Python processes
Get-Process python

# Check what's using port 5000
netstat -ano | findstr :5000
```

### Cleanup

```powershell
# Stop Flask app (Ctrl+C in terminal)

# Stop PostgreSQL
docker compose down

# Remove virtual environment (optional)
Remove-Item -Recurse -Force .venv
```

## Troubleshooting

### Port 5000 Already in Use

```powershell
# Find process using port 5000
netstat -ano | findstr :5000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### PostgreSQL Connection Failed

```powershell
# Check if container is running
docker ps -a | findstr postgres

# Check container logs
docker logs adaptive_ids_postgres

# Restart container
docker compose restart postgres
```

### Import Errors

```powershell
# Ensure virtual environment is activated
.\.venv\Scripts\activate

# Reinstall dependencies
pip install --upgrade -r backend\requirements.txt
```

### Token Expired Errors

Access tokens expire after 15 minutes. Use the refresh endpoint:

```powershell
curl -X POST http://localhost:5000/api/auth/refresh ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\":\"YOUR_REFRESH_TOKEN\"}"
```

## Next Steps

1. ✅ Test authentication with curl or PowerShell
2. ✅ Run test suite: `pytest backend\tests\test_auth.py -v`
3. ✅ Start frontend development server
4. ✅ Integrate login UI with frontend
5. ✅ Configure production environment variables
6. ✅ Set up HTTPS for production
7. ✅ Implement rate limiting
8. ✅ Add password reset functionality

## Quick Reference

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/health` | GET | No | Health check |
| `/api/auth/register` | POST | No | Register new user |
| `/api/auth/login` | POST | No | Login and get tokens |
| `/api/auth/me` | GET | Yes | Get current user |
| `/api/auth/refresh` | POST | No | Refresh access token |
| `/api/auth/logout` | POST | Yes | Logout and revoke token |
| `/api/alerts` | GET | Yes | List alerts |
| `/api/incidents` | GET | Yes | List incidents |
| `/api/dashboard/stats` | GET | Yes | Dashboard statistics |

## Support

See `AUTH_README.md` for comprehensive documentation.
