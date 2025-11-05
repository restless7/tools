-- ============================================
-- ICE Data Staging: Leads & Reference Tables
-- ============================================

-- Leads Table
-- Stores prospects not yet enrolled in programs
CREATE TABLE IF NOT EXISTS staging_lead (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic Information
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    
    -- Lead Source
    source_file VARCHAR(500),  -- Original Excel/CSV file
    source_sheet VARCHAR(255),  -- Sheet name if from Excel
    
    -- Lead Status
    status VARCHAR(50) DEFAULT 'NEW',  -- NEW, CONTACTED, QUALIFIED, CONVERTED, LOST
    interest_program VARCHAR(255),  -- Program they're interested in
    interest_level VARCHAR(50),  -- HIGH, MEDIUM, LOW
    
    -- Contact Information
    country VARCHAR(100),
    city VARCHAR(100),
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Tracking
    ingestion_run_id INTEGER REFERENCES staging_ingestion_run(id),
    converted_to_student_id UUID REFERENCES staging_student(id)  -- Link if converted
);

-- Unique constraints with conditional indexes
CREATE UNIQUE INDEX idx_staging_lead_unique_email ON staging_lead(email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX idx_staging_lead_unique_name_phone ON staging_lead(full_name, phone) WHERE phone IS NOT NULL;

-- Reference Data Table
-- Stores metadata, lists, configurations from Excel files
CREATE TABLE IF NOT EXISTS staging_reference_data (
    id SERIAL PRIMARY KEY,
    
    -- Source Information
    source_file VARCHAR(500) NOT NULL,
    source_sheet VARCHAR(255),
    
    -- Classification
    data_type VARCHAR(100),  -- PRICE_LIST, COUNTRY_LIST, PROGRAM_INFO, etc.
    category VARCHAR(100),
    
    -- Data Content (JSONB for flexibility)
    data_content JSONB NOT NULL,
    
    -- Metadata
    row_count INTEGER,
    column_count INTEGER,
    columns TEXT[],  -- Array of column names
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ingestion_run_id INTEGER REFERENCES staging_ingestion_run(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_staging_lead_status ON staging_lead(status);
CREATE INDEX IF NOT EXISTS idx_staging_lead_email ON staging_lead(email);
CREATE INDEX IF NOT EXISTS idx_staging_lead_program ON staging_lead(interest_program);
CREATE INDEX IF NOT EXISTS idx_staging_lead_created ON staging_lead(created_at);
CREATE INDEX IF NOT EXISTS idx_staging_lead_run ON staging_lead(ingestion_run_id);

CREATE INDEX IF NOT EXISTS idx_staging_ref_type ON staging_reference_data(data_type);
CREATE INDEX IF NOT EXISTS idx_staging_ref_category ON staging_reference_data(category);
CREATE INDEX IF NOT EXISTS idx_staging_ref_source ON staging_reference_data(source_file);
CREATE INDEX IF NOT EXISTS idx_staging_ref_run ON staging_reference_data(ingestion_run_id);

-- Add extraction statistics to ingestion_run table
ALTER TABLE staging_ingestion_run ADD COLUMN IF NOT EXISTS total_leads INTEGER DEFAULT 0;
ALTER TABLE staging_ingestion_run ADD COLUMN IF NOT EXISTS total_reference_files INTEGER DEFAULT 0;
ALTER TABLE staging_ingestion_run ADD COLUMN IF NOT EXISTS excel_files_processed INTEGER DEFAULT 0;

-- Update trigger for lead updated_at
CREATE OR REPLACE FUNCTION update_staging_lead_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_staging_lead_updated_at
    BEFORE UPDATE ON staging_lead
    FOR EACH ROW
    EXECUTE FUNCTION update_staging_lead_updated_at();

-- View: All Person Data (Students + Leads combined)
CREATE OR REPLACE VIEW staging_all_persons AS
SELECT 
    'STUDENT' as person_type,
    s.id,
    p.full_name,
    p.email,
    p.phone,
    s.program,
    NULL as interest_program,
    'ENROLLED' as status,
    p.created_at
FROM staging_student s
JOIN staging_person p ON s.person_id = p.id

UNION ALL

SELECT 
    'LEAD' as person_type,
    l.id,
    l.full_name,
    l.email,
    l.phone,
    NULL as program,
    l.interest_program,
    l.status,
    l.created_at
FROM staging_lead l;

COMMENT ON TABLE staging_lead IS 'Leads/prospects not yet enrolled in programs';
COMMENT ON TABLE staging_reference_data IS 'Reference data extracted from Excel files (price lists, configurations, etc.)';
COMMENT ON VIEW staging_all_persons IS 'Combined view of all persons (students + leads)';
