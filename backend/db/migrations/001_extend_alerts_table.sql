-- Migration: Extend alerts table for alerting pipeline
-- Date: 2025-10-24
-- Description: Adds columns for flow_id, attack classification, network context, 
--              model metadata, enrichment, and dispatch tracking

-- Add new columns (only if they don't exist)
DO $$
BEGIN
    -- Flow and classification fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='flow_id') THEN
        ALTER TABLE alerts ADD COLUMN flow_id VARCHAR(128);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='class_idx') THEN
        ALTER TABLE alerts ADD COLUMN class_idx INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='class_name') THEN
        ALTER TABLE alerts ADD COLUMN class_name VARCHAR(64);
    END IF;
    
    -- Severity replaces/extends priority
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='severity') THEN
        ALTER TABLE alerts ADD COLUMN severity VARCHAR(16);
    END IF;
    
    -- Network context
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='src_ip') THEN
        ALTER TABLE alerts ADD COLUMN src_ip VARCHAR(45);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='dst_ip') THEN
        ALTER TABLE alerts ADD COLUMN dst_ip VARCHAR(45);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='src_port') THEN
        ALTER TABLE alerts ADD COLUMN src_port INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='dst_port') THEN
        ALTER TABLE alerts ADD COLUMN dst_port INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='protocol') THEN
        ALTER TABLE alerts ADD COLUMN protocol VARCHAR(16);
    END IF;
    
    -- Model metadata
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='model_version') THEN
        ALTER TABLE alerts ADD COLUMN model_version VARCHAR(32);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='feature_version') THEN
        ALTER TABLE alerts ADD COLUMN feature_version VARCHAR(32);
    END IF;
    
    -- Raw payload
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='raw_payload') THEN
        ALTER TABLE alerts ADD COLUMN raw_payload JSONB;
    END IF;
    
    -- Enrichment fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='src_geo') THEN
        ALTER TABLE alerts ADD COLUMN src_geo VARCHAR(8);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='dst_geo') THEN
        ALTER TABLE alerts ADD COLUMN dst_geo VARCHAR(8);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='src_reputation') THEN
        ALTER TABLE alerts ADD COLUMN src_reputation DOUBLE PRECISION;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='dst_reputation') THEN
        ALTER TABLE alerts ADD COLUMN dst_reputation DOUBLE PRECISION;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='tags') THEN
        ALTER TABLE alerts ADD COLUMN tags TEXT[];
    END IF;
    
    -- Dispatch tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='destinations') THEN
        ALTER TABLE alerts ADD COLUMN destinations TEXT[];
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='dispatch_status') THEN
        ALTER TABLE alerts ADD COLUMN dispatch_status JSONB DEFAULT '{}'::jsonb;
    END IF;
    
    -- Workflow fields (extend if needed)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='alerts' AND column_name='notes') THEN
        ALTER TABLE alerts ADD COLUMN notes TEXT;
    END IF;
END $$;

-- Update constraints
DO $$
BEGIN
    -- Add check constraints if they don't exist
    BEGIN
        ALTER TABLE alerts ADD CONSTRAINT alerts_confidence_check 
            CHECK (confidence >= 0.0 AND confidence <= 1.0);
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END;
    
    BEGIN
        ALTER TABLE alerts ADD CONSTRAINT alerts_severity_check 
            CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'));
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END;
    
    BEGIN
        ALTER TABLE alerts ADD CONSTRAINT alerts_status_check 
            CHECK (status IN ('NEW', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'FALSE_POSITIVE'));
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END;
    
    BEGIN
        ALTER TABLE alerts ADD CONSTRAINT alerts_src_port_check 
            CHECK (src_port >= 0 AND src_port <= 65535);
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END;
    
    BEGIN
        ALTER TABLE alerts ADD CONSTRAINT alerts_dst_port_check 
            CHECK (dst_port >= 0 AND dst_port <= 65535);
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END;
END $$;

-- Create additional indexes
CREATE INDEX IF NOT EXISTS alerts_flow_id_idx ON alerts (flow_id);
CREATE INDEX IF NOT EXISTS alerts_severity_idx ON alerts (severity);
CREATE INDEX IF NOT EXISTS alerts_class_name_idx ON alerts (class_name);
CREATE INDEX IF NOT EXISTS alerts_src_ip_idx ON alerts (src_ip);
CREATE INDEX IF NOT EXISTS alerts_dst_ip_idx ON alerts (dst_ip);
CREATE INDEX IF NOT EXISTS alerts_created_at_idx ON alerts (created_at DESC);

-- Create or replace the updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DROP TRIGGER IF EXISTS update_alerts_updated_at ON alerts;
CREATE TRIGGER update_alerts_updated_at
    BEFORE UPDATE ON alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Backfill severity from priority for existing records
UPDATE alerts 
SET severity = CASE 
    WHEN priority = 'critical' THEN 'CRITICAL'
    WHEN priority = 'high' THEN 'HIGH'
    WHEN priority = 'medium' THEN 'MEDIUM'
    WHEN priority = 'low' THEN 'LOW'
    ELSE 'INFO'
END
WHERE severity IS NULL AND priority IS NOT NULL;

COMMENT ON TABLE alerts IS 'Security alerts derived from ML predictions with enrichment and dispatch tracking';
COMMENT ON COLUMN alerts.flow_id IS 'Network flow identifier from prediction';
COMMENT ON COLUMN alerts.severity IS 'Alert severity level (INFO, LOW, MEDIUM, HIGH, CRITICAL)';
COMMENT ON COLUMN alerts.raw_payload IS 'Original prediction message as JSONB for audit trail';
COMMENT ON COLUMN alerts.dispatch_status IS 'JSON object tracking delivery status per integration';
