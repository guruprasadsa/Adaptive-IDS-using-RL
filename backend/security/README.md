# Security Implementation for Adaptive IDS

This document provides a comprehensive guide to the security features implemented in Adaptive IDS for production readiness.

## Overview

The security implementation includes:

1. **Service-to-Service Authentication**: API keys and mTLS for internal service communication
2. **Secrets Management**: Encrypted secrets storage with rotation support
3. **Role-Based Access Control (RBAC)**: Fine-grained permissions for users
4. **Audit Logging**: Comprehensive audit trail for compliance and security monitoring
5. **TLS/SSL**: Encrypted communication for external integrations

## Architecture

```
┌─────────────┐
│  Frontend   │
│  (Browser)  │
└──────┬──────┘
       │ JWT Auth
       ▼
┌─────────────────┐
│   Backend API   │◄────── mTLS ──────┐
│   (Flask)       │                    │
└────────┬────────┘                    │
         │ API Key                     │
         ▼                             │
┌──────────────────┐         ┌────────────────┐
│  Model Service   │◄────────│Alerting Service│
│  (FastAPI)       │ mTLS    │                │
└──────────────────┘         └────────────────┘
         │
         ▼
    Audit Logs
```

## Components

### 1. API Key Management

API keys provide service-to-service authentication for internal microservices.

**Features:**
- Key generation with scopes and TTL
- Secure hashing (SHA-256)
- Automatic expiration
- Key rotation with grace period
- Usage metrics

**Usage:**

```python
from security.api_keys import get_api_key_manager, require_api_key

# Generate an API key
manager = get_api_key_manager()
raw_key, api_key = manager.generate_key(
    service_name='model-service',
    scopes=['predictions.write', 'health.read'],
    ttl_days=90
)

# Protect an endpoint
@app.route('/api/internal/predict')
@require_api_key(required_scope='predictions.write')
def predict(api_key):
    # api_key object available in kwargs
    return jsonify({'status': 'ok'})
```

**Key Rotation:**

```python
# Rotate a key with 7-day grace period
new_raw_key, new_api_key = manager.rotate_key(
    old_key_id='api_key_123',
    grace_period_days=7
)
```

### 2. Mutual TLS (mTLS)

mTLS provides certificate-based authentication and encrypted communication between services.

**Certificate Structure:**
- **CA Certificate**: Root certificate authority
- **Server Certificates**: For backend API and model service
- **Client Certificates**: For services making requests

**Generating Certificates:**

On Linux/WSL:
```bash
cd backend/security
chmod +x generate_certs.sh
./generate_certs.sh
```

On Windows (PowerShell):
```powershell
# Use OpenSSL for Windows or WSL
wsl bash backend/security/generate_certs.sh
```

**Using mTLS:**

```python
from security.mtls import init_mtls_manager, verify_client_cert

# Initialize mTLS
init_mtls_manager(
    ca_cert_path='certs/ca-cert.pem',
    server_cert_path='certs/backend-server-cert.pem',
    server_key_path='certs/backend-server-key.pem'
)

# Protect an endpoint
@app.route('/api/internal/sensitive')
@verify_client_cert
def sensitive_endpoint():
    return jsonify({'data': 'secure'})
```

### 3. Secrets Management

Centralized, encrypted secrets storage with rotation support.

**Features:**
- AES-256 encryption using Fernet
- Master key derivation from password or random generation
- TTL-based expiration
- Rotation tracking
- Audit trail

**Usage:**

```python
from security.secrets import init_secrets_manager, get_secret

# Initialize secrets manager
init_secrets_manager(
    secrets_file='backend/security/secrets.enc',
    master_key_file='backend/security/master.key',
    master_password=os.getenv('SECRETS_MASTER_PASSWORD')
)

# Set a secret
manager = get_secrets_manager()
manager.set_secret(
    key='database_password',
    value='super-secret-password',
    ttl_days=90,
    description='PostgreSQL database password'
)

# Get a secret
db_password = get_secret('database_password')

# Rotate a secret
manager.rotate_secret('database_password', 'new-super-secret-password')
```

**Secret Rotation Schedule:**

| Secret | Rotation Period | Auto-Rotate |
|--------|----------------|-------------|
| API Keys | 90 days | Yes |
| Database Passwords | 180 days | Manual |
| JWT Secret | 365 days | Manual |
| TLS Certificates | 365 days | Manual |

### 4. Role-Based Access Control (RBAC)

Fine-grained permission system for user authorization.

**Roles:**
- **Admin**: Full system access
- **Analyst**: Alert and incident management
- **Viewer**: Read-only access
- **Auditor**: Audit log access

**Permissions:**

```python
class Permission(Enum):
    VIEW_ALERTS = 'view_alerts'
    UPDATE_ALERTS = 'update_alerts'
    ACK_ALERTS = 'ack_alerts'
    MARK_FALSE_POSITIVE = 'mark_false_positive'
    VIEW_INCIDENTS = 'view_incidents'
    CREATE_INCIDENTS = 'create_incidents'
    DEPLOY_MODELS = 'deploy_models'
    VIEW_AUDIT_LOGS = 'view_audit_logs'
    # ... more permissions
```

**Usage:**

```python
from security.rbac import require_role, require_permission, Permission
from api.auth import require_auth

# Require specific role
@app.route('/api/admin/users')
@require_auth
@require_role('admin')
def list_users(user_id: int, user_role: str):
    # Only admins can access
    return jsonify({'users': []})

# Require specific permission
@app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
@require_auth
@require_permission(Permission.ACK_ALERTS)
def ack_alert(user_id: int, alert_id: str):
    # Users with ACK_ALERTS permission can access
    return jsonify({'ok': True})
```

### 5. Audit Logging

Comprehensive audit trail for security and compliance.

**Event Types:**
- `authentication`: Login, logout, token refresh
- `data_access`: View, search operations
- `data_modification`: Create, update, delete operations
- `configuration`: System configuration changes
- `system_operation`: Administrative operations

**Usage:**

```python
from security.audit import init_audit_logger, audit_log, audit_context

# Initialize audit logger
init_audit_logger(
    pg_dsn=os.getenv('PG_DSN'),
    log_file_path='logs/audit.log'
)

# Decorator for automatic audit logging
@app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
@require_auth
@audit_log(
    action='acknowledge',
    resource_type='alert',
    event_type='data_modification',
    include_changes=True
)
def ack_alert(user_id: int, alert_id: str):
    # Automatically logged
    return jsonify({'ok': True})

# Context manager for programmatic logging
with audit_context('rotate', 'api_key', key_id, user_id=user_id):
    new_key = rotate_api_key(key_id)
```

**Audit Log Query:**

```sql
-- Recent alert modifications by user
SELECT 
    timestamp,
    action,
    resource_id,
    status,
    changes
FROM audit_logs
WHERE 
    user_id = 123 
    AND resource_type = 'alert'
    AND event_type = 'data_modification'
ORDER BY timestamp DESC
LIMIT 100;
```

## Configuration

### Environment Variables

Add to `backend/.env`:

```bash
# Security Configuration
SECRETS_MASTER_PASSWORD=your-secure-master-password-here

# mTLS Certificates
MTLS_CA_CERT=/app/security/certs/ca-cert.pem
MTLS_SERVER_CERT=/app/security/certs/backend-server-cert.pem
MTLS_SERVER_KEY=/app/security/certs/backend-server-key.pem

# Audit Logging
AUDIT_LOG_FILE=/var/log/adaptive-ids/audit.log
AUDIT_LOG_LEVEL=INFO

# API Key Settings
API_KEY_DEFAULT_TTL_DAYS=90
API_KEY_ROTATION_GRACE_DAYS=7
```

### Docker Compose

Update `docker-compose.yml` to mount certificates:

```yaml
backend:
  volumes:
    - ./backend:/app
    - ./backend/security/certs:/app/security/certs:ro
  environment:
    - MTLS_ENABLED=true
    - MTLS_CA_CERT=/app/security/certs/ca-cert.pem
```

## Setup Instructions

### 1. Generate Certificates

```bash
# On Linux/WSL
cd backend/security
./generate_certs.sh

# On Windows, use WSL or OpenSSL for Windows
```

### 2. Initialize Secrets Manager

```bash
# Set master password
export SECRETS_MASTER_PASSWORD="your-secure-password"

# Run initialization script
python -c "
from security.secrets import init_secrets_manager, get_secrets_manager
init_secrets_manager(
    secrets_file='backend/security/secrets.enc',
    master_key_file='backend/security/master.key'
)
manager = get_secrets_manager()
manager.set_secret('jwt_secret', 'your-jwt-secret', ttl_days=365)
manager.set_secret('database_password', 'db-password', ttl_days=180)
print('Secrets initialized')
"
```

### 3. Apply Database Migration

```bash
# Apply migration for audit logs and security tables
psql -h localhost -p 55432 -U adaptive_ids -d adaptive_ids \
  -f backend/db/migrations/002_security_features.sql
```

### 4. Generate API Keys

```python
from security.api_keys import get_api_key_manager

manager = get_api_key_manager()

# Model service key
model_key, _ = manager.generate_key(
    service_name='model-service',
    scopes=['predictions.write', 'health.read'],
    ttl_days=90
)
print(f"Model Service API Key: {model_key}")

# Alerting service key
alert_key, _ = manager.generate_key(
    service_name='alerting-service',
    scopes=['alerts.write', 'health.read'],
    ttl_days=90
)
print(f"Alerting Service API Key: {alert_key}")
```

### 5. Update Service Configurations

Add API keys to service environment variables:

```bash
# Model service
MODEL_SERVICE_API_KEY=aids_xxxxxxxxxxxxx

# Alerting service
ALERTING_SERVICE_API_KEY=aids_yyyyyyyyyyyyy
```

## Security Best Practices

### 1. API Keys
- ✅ Rotate every 90 days
- ✅ Use scopes to limit access
- ✅ Never commit keys to version control
- ✅ Monitor usage in audit logs
- ✅ Revoke compromised keys immediately

### 2. Certificates
- ✅ Renew before expiration (30 days)
- ✅ Use strong key sizes (4096-bit RSA)
- ✅ Protect private keys (chmod 600)
- ✅ Keep CA key offline when not in use
- ✅ Implement certificate pinning for critical services

### 3. Secrets
- ✅ Encrypt at rest using Fernet (AES-256)
- ✅ Use strong master password (16+ characters)
- ✅ Rotate secrets on schedule
- ✅ Back up master key securely
- ✅ Never log secret values

### 4. Audit Logs
- ✅ Review regularly for anomalies
- ✅ Retain for compliance period (90+ days)
- ✅ Alert on suspicious patterns
- ✅ Export to SIEM for analysis
- ✅ Protect integrity (append-only)

### 5. RBAC
- ✅ Follow principle of least privilege
- ✅ Review permissions quarterly
- ✅ Disable inactive accounts
- ✅ Require MFA for admin accounts
- ✅ Log all permission changes

## Testing

### Test mTLS

```python
import requests
from security.mtls import get_mtls_manager

manager = get_mtls_manager()
context = manager.create_ssl_context()

response = requests.get(
    'https://backend:5001/api/internal/health',
    cert=('certs/client-cert.pem', 'certs/client-key.pem'),
    verify='certs/ca-cert.pem'
)

assert response.status_code == 200
```

### Test API Keys

```python
import requests

response = requests.get(
    'http://localhost:5001/api/internal/health',
    headers={'X-API-Key': 'aids_xxxxxxxxxxxxx'}
)

assert response.status_code == 200
```

### Test RBAC

```python
# Login as analyst
response = requests.post(
    'http://localhost:5001/api/auth/login',
    json={'email_or_username': 'analyst', 'password': 'password'}
)
token = response.json()['access_token']

# Try admin endpoint (should fail)
response = requests.get(
    'http://localhost:5001/api/admin/users',
    headers={'Authorization': f'Bearer {token}'}
)
assert response.status_code == 403
```

### Test Audit Logging

```python
# Perform audited action
response = requests.post(
    'http://localhost:5001/api/alerts/alert_123/ack',
    headers={'Authorization': f'Bearer {token}'}
)

# Check audit log
import psycopg2
conn = psycopg2.connect(os.getenv('PG_DSN'))
cur = conn.cursor()
cur.execute("""
    SELECT * FROM audit_logs 
    WHERE resource_id = 'alert_123' 
    ORDER BY timestamp DESC 
    LIMIT 1
""")
audit_entry = cur.fetchone()
assert audit_entry is not None
```

## Troubleshooting

### Certificate Errors

```
Error: certificate verify failed
```

**Solution:**
- Verify certificate paths are correct
- Check certificate expiration: `openssl x509 -in cert.pem -noout -dates`
- Ensure CA certificate is in trust store

### API Key Invalid

```
Error: Invalid or expired API key
```

**Solution:**
- Check key hasn't expired
- Verify key hasn't been revoked
- Ensure key has required scope

### Permission Denied

```
Error: Insufficient permissions
```

**Solution:**
- Check user role in database
- Verify RBAC configuration
- Review audit logs for permission checks

## Compliance

This security implementation supports compliance with:

- **GDPR**: Audit logging, data access controls
- **HIPAA**: Encryption at rest and in transit, audit trails
- **SOC 2**: Access controls, monitoring, audit logs
- **PCI DSS**: Encryption, key management, access control

## References

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [RFC 5246 - TLS 1.2](https://tools.ietf.org/html/rfc5246)
- [RFC 5424 - Syslog Protocol](https://tools.ietf.org/html/rfc5424)
