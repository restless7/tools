-- Migration: Add staging_lead_failures table
-- Purpose: Track failed lead insertions with error details for debugging and manual review
-- Created: 2025-11-05

CREATE TABLE IF NOT EXISTS staging_lead_failures (
    id SERIAL PRIMARY KEY,
    
    -- Lead data that failed to insert (stored as JSONB for flexibility)
    lead_data JSONB NOT NULL,
    
    -- Error information
    error_message TEXT NOT NULL,
    error_type VARCHAR(100),  -- e.g., 'DATE_PARSE_ERROR', 'VALIDATION_ERROR', 'DATABASE_ERROR'
    
    -- Context
    ingestion_run_id INTEGER REFERENCES staging_ingestion_run(id) ON DELETE CASCADE,
    source_file TEXT,
    source_sheet TEXT,
    row_index INTEGER,
    
    -- Timestamps
    attempted_at TIMESTAMP DEFAULT NOW(),
    
    -- Resolution tracking
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

-- Indexes for efficient querying
CREATE INDEX idx_lead_failures_run_id ON staging_lead_failures(ingestion_run_id);
CREATE INDEX idx_lead_failures_error_type ON staging_lead_failures(error_type);
CREATE INDEX idx_lead_failures_resolved ON staging_lead_failures(resolved);
CREATE INDEX idx_lead_failures_attempted_at ON staging_lead_failures(attempted_at DESC);

-- Add comment
COMMENT ON TABLE staging_lead_failures IS 'Tracks failed lead insertions during V3 ingestion for debugging and manual review';
