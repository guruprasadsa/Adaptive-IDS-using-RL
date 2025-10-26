-- Migration: Add audit logging and security tables
-- Version: 002
-- Description: Adds audit_logs table and extends security features

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(128) UNIQUE NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(256) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    service_name VARCHAR(128),
    status VARCHAR(32) NOT NULL CHECK (status IN ('success', 'failure', 'error')),
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    changes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for audit logs
CREATE INDEX IF NOT EXISTS audit_logs_timestamp_idx ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS audit_logs_user_id_idx ON audit_logs (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS audit_logs_resource_idx ON audit_logs (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS audit_logs_event_type_idx ON audit_logs (event_type);
CREATE INDEX IF NOT EXISTS audit_logs_action_idx ON audit_logs (action);
CREATE INDEX IF NOT EXISTS audit_logs_status_idx ON audit_logs (status);

-- Add permissions column to users table if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='users' AND column_name='permissions'
    ) THEN
        ALTER TABLE users ADD COLUMN permissions TEXT[] DEFAULT '{}';
    END IF;
END $$;

-- Add is_service_account column to users table if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='users' AND column_name='is_service_account'
    ) THEN
        ALTER TABLE users ADD COLUMN is_service_account BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- API keys table for service-to-service authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(128) UNIQUE NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    service_name VARCHAR(128) NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS api_keys_service_name_idx ON api_keys (service_name);
CREATE INDEX IF NOT EXISTS api_keys_is_active_idx ON api_keys (is_active);
CREATE INDEX IF NOT EXISTS api_keys_expires_at_idx ON api_keys (expires_at) WHERE expires_at IS NOT NULL;

-- Secrets metadata table (encrypted values stored separately)
CREATE TABLE IF NOT EXISTS secrets_metadata (
    id SERIAL PRIMARY KEY,
    secret_key VARCHAR(128) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    rotatable BOOLEAN NOT NULL DEFAULT TRUE,
    last_rotated_at TIMESTAMPTZ,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS secrets_metadata_expires_at_idx ON secrets_metadata (expires_at) WHERE expires_at IS NOT NULL;

-- Function to log alert changes to audit log
CREATE OR REPLACE FUNCTION log_alert_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert audit log for alert updates
    INSERT INTO audit_logs (
        event_id,
        timestamp,
        event_type,
        action,
        resource_type,
        resource_id,
        status,
        changes
    ) VALUES (
        'audit_' || extract(epoch from now())::bigint || '_' || substr(md5(random()::text), 1, 8),
        NOW(),
        'data_modification',
        TG_OP,
        'alert',
        NEW.alert_id,
        'success',
        jsonb_build_object(
            'old', row_to_json(OLD),
            'new', row_to_json(NEW)
        )
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for alert changes
DROP TRIGGER IF EXISTS alert_change_audit ON alerts;
CREATE TRIGGER alert_change_audit
    AFTER UPDATE ON alerts
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status OR 
          OLD.assigned_to IS DISTINCT FROM NEW.assigned_to)
    EXECUTE FUNCTION log_alert_change();

-- Grant permissions
GRANT SELECT ON audit_logs TO adaptive_ids;
GRANT INSERT ON audit_logs TO adaptive_ids;
GRANT SELECT, INSERT, UPDATE ON api_keys TO adaptive_ids;
GRANT SELECT, INSERT, UPDATE ON secrets_metadata TO adaptive_ids;
GRANT USAGE, SELECT ON SEQUENCE audit_logs_id_seq TO adaptive_ids;
GRANT USAGE, SELECT ON SEQUENCE api_keys_id_seq TO adaptive_ids;
GRANT USAGE, SELECT ON SEQUENCE secrets_metadata_id_seq TO adaptive_ids;

-- Insert initial admin user if not exists (password: admin123)
INSERT INTO users (username, email, password_hash, role, is_active)
VALUES (
    'admin',
    'admin@adaptive-ids.local',
    '$2b$12$LqGGXfQdZwUu3q3JZ3qV0eBk5vY5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z',  -- Replace with actual bcrypt hash
    'admin',
    TRUE
)
ON CONFLICT (username) DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE audit_logs IS 'Comprehensive audit trail for security and compliance';
COMMENT ON TABLE api_keys IS 'API keys for service-to-service authentication';
COMMENT ON TABLE secrets_metadata IS 'Metadata for encrypted secrets management';
