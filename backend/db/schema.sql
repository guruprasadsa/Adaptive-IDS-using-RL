-- Schema initialization for Adaptive IDS PostgreSQL database
-- Generated on 2025-10-20

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(64) UNIQUE NOT NULL,
    flow_id VARCHAR(128) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Attack Classification
    class_idx INTEGER NOT NULL,
    class_name VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    
    -- Network Context
    src_ip VARCHAR(45) NOT NULL,
    dst_ip VARCHAR(45) NOT NULL,
    src_port INTEGER NOT NULL CHECK (src_port >= 0 AND src_port <= 65535),
    dst_port INTEGER NOT NULL CHECK (dst_port >= 0 AND dst_port <= 65535),
    protocol VARCHAR(16) NOT NULL,
    
    -- Model Metadata
    model_version VARCHAR(32) NOT NULL,
    feature_version VARCHAR(32) NOT NULL,
    
    -- Workflow Management
    status VARCHAR(32) NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'FALSE_POSITIVE')),
    assigned_to VARCHAR(128),
    notes TEXT,
    
    -- Raw Data
    raw_payload JSONB,
    
    -- Enrichment (optional fields for future use)
    src_geo VARCHAR(8),
    dst_geo VARCHAR(8),
    src_reputation DOUBLE PRECISION CHECK (src_reputation >= 0.0 AND src_reputation <= 1.0),
    dst_reputation DOUBLE PRECISION CHECK (dst_reputation >= 0.0 AND dst_reputation <= 1.0),
    tags TEXT[],
    
    -- Dispatch tracking
    destinations TEXT[],
    dispatch_status JSONB DEFAULT '{}'::jsonb,
    
    -- Legacy fields (for backward compatibility)
    priority VARCHAR(16),
    description TEXT,
    source VARCHAR(64),
    alert_type VARCHAR(64),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS alerts_flow_id_idx ON alerts (flow_id);
CREATE INDEX IF NOT EXISTS alerts_severity_idx ON alerts (severity);
CREATE INDEX IF NOT EXISTS alerts_status_idx ON alerts (status);
CREATE INDEX IF NOT EXISTS alerts_timestamp_idx ON alerts (timestamp DESC);
CREATE INDEX IF NOT EXISTS alerts_class_name_idx ON alerts (class_name);
CREATE INDEX IF NOT EXISTS alerts_src_ip_idx ON alerts (src_ip);
CREATE INDEX IF NOT EXISTS alerts_dst_ip_idx ON alerts (dst_ip);
CREATE INDEX IF NOT EXISTS alerts_created_at_idx ON alerts (created_at DESC);

-- Backward compatibility indexes
CREATE INDEX IF NOT EXISTS alerts_priority_idx ON alerts (priority);

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_alerts_updated_at ON alerts;
CREATE TRIGGER update_alerts_updated_at
    BEFORE UPDATE ON alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    assigned_to VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_updated_at TIMESTAMPTZ NOT NULL,
    summary TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_systems INTEGER NOT NULL DEFAULT 0,
    alerts_count INTEGER NOT NULL DEFAULT 0,
    related_alerts JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS incidents_status_idx ON incidents (status);
CREATE INDEX IF NOT EXISTS incidents_severity_idx ON incidents (severity);
CREATE INDEX IF NOT EXISTS incidents_updated_idx ON incidents (last_updated_at DESC);

-- Authentication tables
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'analyst',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS users_username_idx ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_idx ON users (email);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS refresh_tokens_user_id_idx ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS refresh_tokens_expires_at_idx ON refresh_tokens (expires_at);
