-- ============================================================================
-- Alert Database Reset Script
-- ============================================================================
-- WARNING: This script will DELETE ALL alert and incident data
-- Use with caution - only for development/testing or fresh deployments
-- ============================================================================

DO $$
DECLARE
    alert_count INTEGER;
    incident_count INTEGER;
    history_count INTEGER;
    comment_count INTEGER;
BEGIN
    -- Get counts before deletion
    SELECT COUNT(*) INTO alert_count FROM alerts;
    SELECT COUNT(*) INTO incident_count FROM incidents;
    SELECT COUNT(*) INTO history_count FROM alert_history WHERE EXISTS (SELECT 1 FROM alert_history LIMIT 1);
    SELECT COUNT(*) INTO comment_count FROM alert_comments WHERE EXISTS (SELECT 1 FROM alert_comments LIMIT 1);
    
    RAISE NOTICE 'Starting alert database reset...';
    RAISE NOTICE 'Current counts: Alerts=%, Incidents=%, History=%, Comments=%',
        alert_count, incident_count, history_count, comment_count;
    
    -- Disable triggers temporarily to speed up deletion
    ALTER TABLE alerts DISABLE TRIGGER alert_status_change_trigger;
    ALTER TABLE incident_alerts DISABLE TRIGGER incident_metadata_update_trigger;
    
    -- Truncate tables (CASCADE will handle foreign key dependencies)
    -- Order matters: child tables first, parent tables last
    RAISE NOTICE 'Truncating alert_comments...';
    TRUNCATE TABLE alert_comments CASCADE;
    
    RAISE NOTICE 'Truncating alert_history...';
    TRUNCATE TABLE alert_history CASCADE;
    
    RAISE NOTICE 'Truncating incident_alerts...';
    TRUNCATE TABLE incident_alerts CASCADE;
    
    RAISE NOTICE 'Truncating incidents...';
    TRUNCATE TABLE incidents CASCADE;
    
    RAISE NOTICE 'Truncating alerts...';
    TRUNCATE TABLE alerts CASCADE;
    
    RAISE NOTICE 'Truncating alerts_archive...';
    TRUNCATE TABLE alerts_archive CASCADE;
    
    -- Reset sequences to start from 1
    RAISE NOTICE 'Resetting sequences...';
    ALTER SEQUENCE alerts_id_seq RESTART WITH 1;
    ALTER SEQUENCE incidents_id_seq RESTART WITH 1;
    ALTER SEQUENCE alert_history_id_seq RESTART WITH 1;
    ALTER SEQUENCE alert_comments_id_seq RESTART WITH 1;
    
    -- Re-enable triggers
    ALTER TABLE alerts ENABLE TRIGGER alert_status_change_trigger;
    ALTER TABLE incident_alerts ENABLE TRIGGER incident_metadata_update_trigger;
    
    RAISE NOTICE 'Alert database reset complete!';
    RAISE NOTICE 'All alert and incident data has been deleted.';
END $$;

-- Verify clean state
SELECT 
    (SELECT COUNT(*) FROM alerts) AS alerts_count,
    (SELECT COUNT(*) FROM incidents) AS incidents_count,
    (SELECT COUNT(*) FROM alert_history) AS history_count,
    (SELECT COUNT(*) FROM alert_comments) AS comments_count,
    (SELECT COUNT(*) FROM incident_alerts) AS incident_alerts_count,
    (SELECT COUNT(*) FROM alerts_archive) AS archived_count;

-- Show table sizes
SELECT 
    'alerts' AS table_name,
    pg_size_pretty(pg_total_relation_size('alerts')) AS total_size
UNION ALL
SELECT 
    'incidents',
    pg_size_pretty(pg_total_relation_size('incidents'))
UNION ALL
SELECT 
    'alert_history',
    pg_size_pretty(pg_total_relation_size('alert_history'))
UNION ALL
SELECT 
    'alert_comments',
    pg_size_pretty(pg_total_relation_size('alert_comments'))
UNION ALL
SELECT 
    'incident_alerts',
    pg_size_pretty(pg_total_relation_size('incident_alerts'));

-- ============================================================================
-- Optional: Clear Kafka Consumer Offsets
-- ============================================================================
-- Run this command externally to reset Kafka consumer group offsets:
-- 
-- docker exec -it adaptive_ids_kafka kafka-consumer-groups \
--   --bootstrap-server localhost:9092 \
--   --group alerting-service \
--   --reset-offsets --to-earliest --topic predictions --execute
-- ============================================================================

