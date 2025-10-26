# Security Quick Reference

Quick reference guide for security features in Adaptive IDS.

## Setup

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Run security setup
cd backend
python security/setup.py

# 3. Generate TLS certificates (optional)
cd security
./generate_certs.sh

# 4. Apply database migration
psql -h localhost -p 55432 -U adaptive_ids -d adaptive_ids \
  -f db/migrations/002_security_features.sql
```

## API Key Management

```python
from security.api_keys import get_api_key_manager, require_api_key

# Generate API key
manager = get_api_key_manager()
raw_key, api_key = manager.generate_key(
    service_name='my-service',
    scopes=['resource.read', 'resource.write'],
    ttl_days=90
)

# Protect endpoint
@app.route('/api/internal/endpoint')
@require_api_key(required_scope='resource.write')
def protected_endpoint(api_key):
    return jsonify({'status': 'ok'})

# Rotate key
new_key, new_api_key = manager.rotate_key(
    old_key_id='api_key_123',
    grace_period_days=7
)
```

## Secrets Management

```python
from security.secrets import get_secret, get_secrets_manager

# Get secret (auto-fallback to env var)
db_password = get_secret('database_password')
jwt_secret = get_secret('jwt_secret')

# Set secret
manager = get_secrets_manager()
manager.set_secret(
    key='api_token',
    value='secret-value',
    ttl_days=90,
    description='Third-party API token'
)

# Rotate secret
manager.rotate_secret('api_token', 'new-secret-value')
```

## RBAC (Role-Based Access Control)

```python
from security.rbac import require_role, require_permission, Permission
from api.auth import require_auth

# Require specific role
@app.route('/api/admin/users')
@require_auth
@require_role('admin')
def admin_only(user_id: int, user_role: str):
    return jsonify({'users': []})

# Require specific permission
@app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
@require_auth
@require_permission(Permission.ACK_ALERTS)
def ack_alert(user_id: int, alert_id: str):
    return jsonify({'ok': True})
```

### Roles and Permissions

| Role | Permissions |
|------|-------------|
| **Admin** | Full system access (all permissions) |
| **Analyst** | Alert/incident management, model viewing |
| **Viewer** | Read-only access to alerts, incidents, models |
| **Auditor** | Audit log access, read-only system access |

### Available Permissions

```python
Permission.VIEW_ALERTS
Permission.UPDATE_ALERTS
Permission.DELETE_ALERTS
Permission.ACK_ALERTS
Permission.MARK_FALSE_POSITIVE
Permission.VIEW_INCIDENTS
Permission.CREATE_INCIDENTS
Permission.UPDATE_INCIDENTS
Permission.DELETE_INCIDENTS
Permission.VIEW_MODELS
Permission.DEPLOY_MODELS
Permission.TRAIN_MODELS
Permission.VIEW_USERS
Permission.CREATE_USERS
Permission.UPDATE_USERS
Permission.DELETE_USERS
Permission.VIEW_CONFIG
Permission.UPDATE_CONFIG
Permission.VIEW_AUDIT_LOGS
Permission.MANAGE_INTEGRATIONS
```

## Audit Logging

```python
from security.audit import audit_log, audit_context, AuditEvent, get_audit_logger

# Decorator (automatic logging)
@app.route('/api/alerts/<alert_id>/resolve', methods=['POST'])
@require_auth
@audit_log(
    action='resolve',
    resource_type='alert',
    event_type='data_modification',
    include_changes=True
)
def resolve_alert(user_id: int, alert_id: str):
    # Automatically logged with request details
    return jsonify({'ok': True})

# Context manager
with audit_context('deploy', 'model', model_id, user_id=user_id):
    deploy_model(model_id)

# Manual logging
logger = get_audit_logger()
event = AuditEvent(
    event_type='configuration',
    action='update_setting',
    resource_type='config',
    resource_id='alert_thresholds',
    user_id=user_id,
    status='success',
    changes={'min_confidence': 0.8}
)
logger.log(event)
```

### Query Audit Logs

```sql
-- Recent user actions
SELECT timestamp, action, resource_type, resource_id, status
FROM audit_logs
WHERE user_id = 123
ORDER BY timestamp DESC
LIMIT 50;

-- Failed authentication attempts
SELECT timestamp, ip_address, details
FROM audit_logs
WHERE event_type = 'authentication' AND status = 'failure'
ORDER BY timestamp DESC;

-- Alert modifications
SELECT timestamp, user_id, resource_id, changes
FROM audit_logs
WHERE resource_type = 'alert' AND action IN ('acknowledge', 'mark_false_positive')
ORDER BY timestamp DESC;
```

## mTLS (Mutual TLS)

```python
from security.mtls import init_mtls_manager, verify_client_cert, get_mtls_manager

# Initialize
init_mtls_manager(
    ca_cert_path='certs/ca-cert.pem',
    server_cert_path='certs/server-cert.pem',
    server_key_path='certs/server-key.pem'
)

# Protect endpoint
@app.route('/api/internal/secure')
@verify_client_cert
def secure_endpoint():
    return jsonify({'data': 'secure'})

# Create SSL context for client
manager = get_mtls_manager()
ssl_context = manager.create_ssl_context(purpose=ssl.Purpose.CLIENT_AUTH)

import requests
response = requests.get(
    'https://backend:5001/api/internal/secure',
    cert=('client-cert.pem', 'client-key.pem'),
    verify='ca-cert.pem'
)
```

## Environment Variables

```bash
# backend/.env

# Secrets
SECRETS_MASTER_PASSWORD=your-secure-password
SECRETS_FILE=backend/security/secrets.enc
MASTER_KEY_FILE=backend/security/master.key

# mTLS (optional)
MTLS_ENABLED=false
MTLS_CA_CERT=backend/security/certs/ca-cert.pem
MTLS_SERVER_CERT=backend/security/certs/backend-server-cert.pem
MTLS_SERVER_KEY=backend/security/certs/backend-server-key.pem

# Audit Logging
AUDIT_LOG_FILE=logs/audit.log

# API Keys (from setup script)
MODEL_SERVICE_API_KEY=aids_xxxxx
ALERTING_SERVICE_API_KEY=aids_yyyyy
```

## Common Tasks

### Create Admin User

```python
from api.auth import hash_password
import psycopg2

conn = psycopg2.connect(os.getenv('PG_DSN'))
cur = conn.cursor()

cur.execute("""
    INSERT INTO users (username, email, password_hash, role, is_active)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id
""", ('admin', 'admin@example.com', hash_password('admin123'), 'admin', True))

user_id = cur.fetchone()[0]
conn.commit()
print(f"Admin user created: ID={user_id}")
```

### Rotate API Key

```python
manager = get_api_key_manager()
new_key, new_api_key = manager.rotate_key(
    old_key_id='api_key_123',
    grace_period_days=7  # Old key valid for 7 more days
)
print(f"New API key: {new_key}")
```

### Check Permissions

```python
from security.rbac import get_rbac_manager, Permission

manager = get_rbac_manager()
has_perm = manager.has_permission('analyst', Permission.ACK_ALERTS)
print(f"Analyst can acknowledge alerts: {has_perm}")
```

### Export Audit Logs

```sql
-- Export to CSV
COPY (
    SELECT 
        timestamp,
        event_type,
        action,
        resource_type,
        resource_id,
        user_id,
        status,
        ip_address
    FROM audit_logs
    WHERE timestamp >= NOW() - INTERVAL '30 days'
    ORDER BY timestamp DESC
) TO '/tmp/audit_logs.csv' WITH CSV HEADER;
```

## Troubleshooting

### API Key Not Working

```python
# Check if key exists and is valid
manager = get_api_key_manager()
keys = manager.list_keys(service_name='my-service')
for key in keys:
    print(f"Key ID: {key.key_id}, Valid: {key.is_valid()}, Expires: {key.expires_at}")
```

### Secrets Not Loading

```python
# Check secrets manager status
manager = get_secrets_manager()
if manager:
    secrets = manager.list_secrets()
    print(f"Loaded {len(secrets)} secrets")
    for key, meta in secrets.items():
        print(f"  {key}: expired={meta['is_expired']}")
else:
    print("Secrets manager not initialized!")
```

### Permission Denied

```python
# Check user role and permissions
import psycopg2
conn = psycopg2.connect(os.getenv('PG_DSN'))
cur = conn.cursor()
cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
role = cur.fetchone()[0]

manager = get_rbac_manager()
permissions = manager.get_role_permissions(role)
print(f"Role: {role}")
print(f"Permissions: {[p.value for p in permissions]}")
```

## Testing

```bash
# Test API key authentication
curl -H "X-API-Key: aids_xxxxx" http://localhost:5001/api/internal/health

# Test JWT authentication
TOKEN=$(curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email_or_username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5001/api/alerts

# Test mTLS
curl --cert client-cert.pem --key client-key.pem \
  --cacert ca-cert.pem \
  https://localhost:5001/api/internal/secure
```

## Security Checklist

- [ ] Master password set and stored securely
- [ ] Database migration applied
- [ ] API keys generated for all services
- [ ] TLS certificates generated (if using mTLS)
- [ ] Secrets encrypted and backed up
- [ ] Audit logging enabled
- [ ] Admin user created
- [ ] Environment variables updated
- [ ] Services restarted with new config
- [ ] Security features tested

## References

- Full documentation: `backend/security/README.md`
- Implementation summary: `documentation/SECURITY_IMPLEMENTATION_SUMMARY.md`
- Database migration: `backend/db/migrations/002_security_features.sql`
