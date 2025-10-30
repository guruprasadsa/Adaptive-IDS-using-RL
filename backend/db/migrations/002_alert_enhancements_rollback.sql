-- Rollback Migration 002: Alert System Enhancements

-- Drop views
DROP VIEW IF EXISTS incident_summary;
DROP VIEW IF EXISTS alert_details_view;
DROP VIEW IF EXISTS active_alerts;

-- Drop functions
DROP FUNCTION IF EXISTS cleanup_old_alert_history(INTEGER);
DROP FUNCTION IF EXISTS archive_old_alerts(INTEGER);
DROP FUNCTION IF EXISTS update_incident_metadata();
DROP FUNCTION IF EXISTS log_alert_status_change();

-- Drop triggers
DROP TRIGGER IF EXISTS incident_metadata_update_trigger ON incident_alerts;
DROP TRIGGER IF EXISTS alert_status_change_trigger ON alerts;
DROP TRIGGER IF EXISTS update_alert_comments_updated_at ON alert_comments;

-- Drop tables
DROP TABLE IF EXISTS alerts_archive CASCADE;
DROP TABLE IF NOT EXISTS incident_alerts CASCADE;
DROP TABLE IF EXISTS alert_comments CASCADE;
DROP TABLE IF EXISTS alert_history CASCADE;

-- Remove added columns from alerts
ALTER TABLE alerts 
    DROP COLUMN IF EXISTS deleted_at,
    DROP COLUMN IF EXISTS deleted_by;

-- Remove added columns from incidents
ALTER TABLE incidents
    DROP COLUMN IF EXISTS resolved_at,
    DROP COLUMN IF EXISTS resolved_by,
    DROP COLUMN IF EXISTS correlation_key,
    DROP COLUMN IF EXISTS incident_type,
    DROP COLUMN IF EXISTS first_seen,
    DROP COLUMN IF EXISTS last_seen;

-- Rollback complete

