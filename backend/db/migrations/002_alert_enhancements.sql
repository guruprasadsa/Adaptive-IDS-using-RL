-- Migration 002: Alert System Enhancements
-- Adds lifecycle tracking, comments, and incident correlation tables

-- ============================================================================
-- Alert History Table (Lifecycle Tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_history (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(64) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    from_status VARCHAR(32),
    to_status VARCHAR(32) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_alert_history_alert 
        FOREIGN KEY (alert_id) 
        REFERENCES alerts(alert_id) 
        ON DELETE CASCADE
);

-- Indexes for alert history
CREATE INDEX IF NOT EXISTS alert_history_alert_id_idx ON alert_history (alert_id);
CREATE INDEX IF NOT EXISTS alert_history_created_at_idx ON alert_history (created_at DESC);
CREATE INDEX IF NOT EXISTS alert_history_user_id_idx ON alert_history (user_id);

-- ============================================================================
-- Alert Comments Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_comments (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(64) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_alert_comments_alert 
        FOREIGN KEY (alert_id) 
        REFERENCES alerts(alert_id) 
        ON DELETE CASCADE
);

-- Indexes for alert comments
CREATE INDEX IF NOT EXISTS alert_comments_alert_id_idx ON alert_comments (alert_id);
CREATE INDEX IF NOT EXISTS alert_comments_created_at_idx ON alert_comments (created_at DESC);
CREATE INDEX IF NOT EXISTS alert_comments_user_id_idx ON alert_comments (user_id);

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_alert_comments_updated_at ON alert_comments;
CREATE TRIGGER update_alert_comments_updated_at
    BEFORE UPDATE ON alert_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Incident-Alert Many-to-Many Relationship
-- ============================================================================
CREATE TABLE IF NOT EXISTS incident_alerts (
    incident_id VARCHAR(64) NOT NULL,
    alert_id VARCHAR(64) NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    PRIMARY KEY (incident_id, alert_id),
    
    CONSTRAINT fk_incident_alerts_incident
        FOREIGN KEY (incident_id)
        REFERENCES incidents(incident_id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_incident_alerts_alert
        FOREIGN KEY (alert_id)
        REFERENCES alerts(alert_id)
        ON DELETE CASCADE
);

-- Indexes for incident_alerts
CREATE INDEX IF NOT EXISTS incident_alerts_incident_id_idx ON incident_alerts (incident_id);
CREATE INDEX IF NOT EXISTS incident_alerts_alert_id_idx ON incident_alerts (alert_id);
CREATE INDEX IF NOT EXISTS incident_alerts_added_at_idx ON incident_alerts (added_at DESC);

-- ============================================================================
-- Soft Delete Support for Alerts
-- ============================================================================
ALTER TABLE alerts 
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Index for soft deletes (query optimization for active alerts)
CREATE INDEX IF NOT EXISTS alerts_deleted_at_idx ON alerts (deleted_at) WHERE deleted_at IS NOT NULL;

-- ============================================================================
-- Alert Archival Table (for old alerts > 90 days)
-- ============================================================================
CREATE TABLE IF NOT EXISTS alerts_archive (
    LIKE alerts INCLUDING ALL
);

-- Add archival metadata
ALTER TABLE alerts_archive
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS archived_reason VARCHAR(128) DEFAULT 'age_based_archival';

-- Index for archive queries
CREATE INDEX IF NOT EXISTS alerts_archive_timestamp_idx ON alerts_archive (timestamp DESC);
CREATE INDEX IF NOT EXISTS alerts_archive_archived_at_idx ON alerts_archive (archived_at DESC);

-- ============================================================================
-- Incident Enhancements
-- ============================================================================
-- Add additional tracking fields to incidents
ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS correlation_key VARCHAR(256),
    ADD COLUMN IF NOT EXISTS incident_type VARCHAR(64) DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS first_seen TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ;

-- Index for correlation queries
CREATE INDEX IF NOT EXISTS incidents_correlation_key_idx ON incidents (correlation_key) WHERE correlation_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS incidents_type_idx ON incidents (incident_type);
CREATE INDEX IF NOT EXISTS incidents_first_seen_idx ON incidents (first_seen DESC);

-- ============================================================================
-- Functions for Alert Lifecycle Management
-- ============================================================================

-- Function to automatically create alert history entry on status change
CREATE OR REPLACE FUNCTION log_alert_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log if status actually changed
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO alert_history (alert_id, from_status, to_status, notes, user_id)
        VALUES (
            NEW.alert_id,
            OLD.status,
            NEW.status,
            NEW.notes,
            NEW.assigned_to::INTEGER  -- Assuming assigned_to stores user_id as string
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to log alert status changes
DROP TRIGGER IF EXISTS alert_status_change_trigger ON alerts;
CREATE TRIGGER alert_status_change_trigger
    AFTER UPDATE ON alerts
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_alert_status_change();

-- Function to update incident metadata when alerts are added/removed
CREATE OR REPLACE FUNCTION update_incident_metadata()
RETURNS TRIGGER AS $$
DECLARE
    incident_alert_count INTEGER;
    incident_first_alert TIMESTAMPTZ;
    incident_last_alert TIMESTAMPTZ;
BEGIN
    -- Get incident_id (works for both INSERT and DELETE)
    DECLARE v_incident_id VARCHAR(64);
    BEGIN
        IF TG_OP = 'DELETE' THEN
            v_incident_id := OLD.incident_id;
        ELSE
            v_incident_id := NEW.incident_id;
        END IF;
        
        -- Count alerts and get time range
        SELECT 
            COUNT(*),
            MIN(a.timestamp),
            MAX(a.timestamp)
        INTO 
            incident_alert_count,
            incident_first_alert,
            incident_last_alert
        FROM incident_alerts ia
        JOIN alerts a ON ia.alert_id = a.alert_id
        WHERE ia.incident_id = v_incident_id;
        
        -- Update incident
        UPDATE incidents
        SET 
            alerts_count = incident_alert_count,
            first_seen = incident_first_alert,
            last_seen = incident_last_alert,
            last_updated_at = NOW()
        WHERE incident_id = v_incident_id;
    END;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update incident metadata
DROP TRIGGER IF EXISTS incident_metadata_update_trigger ON incident_alerts;
CREATE TRIGGER incident_metadata_update_trigger
    AFTER INSERT OR DELETE ON incident_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_incident_metadata();

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- View for active (non-deleted) alerts
CREATE OR REPLACE VIEW active_alerts AS
SELECT * FROM alerts
WHERE deleted_at IS NULL;

-- View for alert details with user information
CREATE OR REPLACE VIEW alert_details_view AS
SELECT 
    a.*,
    u.username AS assigned_to_username,
    COUNT(ah.id) AS history_count,
    COUNT(ac.id) AS comment_count
FROM alerts a
LEFT JOIN users u ON a.assigned_to::INTEGER = u.id
LEFT JOIN alert_history ah ON a.alert_id = ah.alert_id
LEFT JOIN alert_comments ac ON a.alert_id = ac.alert_id
WHERE a.deleted_at IS NULL
GROUP BY a.id, u.username;

-- View for incident summary
CREATE OR REPLACE VIEW incident_summary AS
SELECT 
    i.*,
    u.username AS assigned_to_username,
    COUNT(DISTINCT ia.alert_id) AS alert_count,
    MIN(a.timestamp) AS earliest_alert,
    MAX(a.timestamp) AS latest_alert
FROM incidents i
LEFT JOIN users u ON i.assigned_to = u.username
LEFT JOIN incident_alerts ia ON i.incident_id = ia.incident_id
LEFT JOIN alerts a ON ia.alert_id = a.alert_id
GROUP BY i.id, u.username;

-- ============================================================================
-- Maintenance Functions
-- ============================================================================

-- Function to archive old alerts (>90 days)
CREATE OR REPLACE FUNCTION archive_old_alerts(days_threshold INTEGER DEFAULT 90)
RETURNS TABLE (archived_count INTEGER) AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Move alerts to archive table
    INSERT INTO alerts_archive
    SELECT * FROM alerts
    WHERE timestamp < NOW() - (days_threshold || ' days')::INTERVAL
    AND deleted_at IS NULL;
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    
    -- Mark as deleted in main table
    UPDATE alerts
    SET deleted_at = NOW(),
        deleted_by = NULL
    WHERE timestamp < NOW() - (days_threshold || ' days')::INTERVAL
    AND deleted_at IS NULL;
    
    RETURN QUERY SELECT archived_count;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old alert history (>180 days)
CREATE OR REPLACE FUNCTION cleanup_old_alert_history(days_threshold INTEGER DEFAULT 180)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM alert_history
    WHERE created_at < NOW() - (days_threshold || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Grant Permissions
-- ============================================================================
GRANT SELECT, INSERT, UPDATE ON alert_history TO adaptive_ids;
GRANT SELECT, INSERT, UPDATE, DELETE ON alert_comments TO adaptive_ids;
GRANT SELECT, INSERT, DELETE ON incident_alerts TO adaptive_ids;
GRANT SELECT ON active_alerts TO adaptive_ids;
GRANT SELECT ON alert_details_view TO adaptive_ids;
GRANT SELECT ON incident_summary TO adaptive_ids;

-- Grant sequence permissions
GRANT USAGE, SELECT ON SEQUENCE alert_history_id_seq TO adaptive_ids;
GRANT USAGE, SELECT ON SEQUENCE alert_comments_id_seq TO adaptive_ids;

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- To rollback this migration, run: 002_alert_enhancements_rollback.sql

