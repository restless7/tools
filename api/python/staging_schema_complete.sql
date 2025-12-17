-- ============================================
-- ICE Data Staging: Complete Schema
-- ============================================
-- Creates all staging tables in correct dependency order
-- Run this script to initialize the staging database from scratch

-- 1. Staging Ingestion Run table (no dependencies)
CREATE TABLE IF NOT EXISTS staging_ingestion_run (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMP DEFAULT NOW(),
    source_directory TEXT NOT NULL,
    total_students INTEGER DEFAULT 0,
    total_documents INTEGER DEFAULT 0,
    csv_files_processed INTEGER DEFAULT 0,
    records_enriched INTEGER DEFAULT 0,
    execution_time_seconds FLOAT,
    status TEXT DEFAULT 'COMPLETED',
    notes TEXT,
    -- Lead-related fields
    total_leads INTEGER DEFAULT 0,
    total_reference_files INTEGER DEFAULT 0,
    excel_files_processed INTEGER DEFAULT 0
);

-- 2. Staging Person table (no dependencies)
CREATE TABLE IF NOT EXISTS staging_person (
    id UUID PRIMARY KEY,
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    id_number TEXT,
    birth_date DATE,
    source TEXT,
    directory_path TEXT,
    csv_file TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_person_normalized_name 
ON staging_person(normalized_name);

CREATE INDEX IF NOT EXISTS idx_staging_person_email
ON staging_person(email);

CREATE INDEX IF NOT EXISTS idx_staging_person_id_number
ON staging_person(id_number);

-- 3. Staging Student table (depends on staging_person)
CREATE TABLE IF NOT EXISTS staging_student (
    id UUID PRIMARY KEY,
    person_id UUID NOT NULL REFERENCES staging_person(id),
    program TEXT,
    status TEXT DEFAULT 'PENDING_REVIEW',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_student_person
ON staging_student(person_id);

CREATE INDEX IF NOT EXISTS idx_staging_student_program
ON staging_student(program);

-- 4. Staging Document table (depends on staging_student)
CREATE TABLE IF NOT EXISTS staging_document (
    id SERIAL PRIMARY KEY,
    student_id UUID NOT NULL REFERENCES staging_student(id),
    original_file_name TEXT NOT NULL,
    normalized_file_name TEXT NOT NULL,
    original_file_path TEXT NOT NULL,
    staging_file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    document_type TEXT NOT NULL,
    checksum TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(checksum)
);

CREATE INDEX IF NOT EXISTS idx_staging_document_student
ON staging_document(student_id);

CREATE INDEX IF NOT EXISTS idx_staging_document_type
ON staging_document(document_type);

-- 5. Staging Lead table (depends on staging_ingestion_run, staging_student)
CREATE TABLE IF NOT EXISTS staging_lead (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic Information
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    cedula VARCHAR(50),
    birth_date DATE,
    
    -- Lead Source
    source_file VARCHAR(500),
    source_sheet VARCHAR(255),
    
    -- Lead Status
    status VARCHAR(50) DEFAULT 'NEW',
    interest_program VARCHAR(255),
    interest_level VARCHAR(50),
    
    -- Contact Information
    country VARCHAR(100),
    city VARCHAR(100),
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Tracking
    ingestion_run_id INTEGER REFERENCES staging_ingestion_run(id),
    converted_to_student_id UUID REFERENCES staging_student(id)
);

-- Unique constraints with conditional indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_lead_unique_email 
ON staging_lead(email) WHERE email IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_lead_unique_name_phone 
ON staging_lead(full_name, phone) WHERE phone IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_staging_lead_status ON staging_lead(status);
CREATE INDEX IF NOT EXISTS idx_staging_lead_email ON staging_lead(email);
CREATE INDEX IF NOT EXISTS idx_staging_lead_program ON staging_lead(interest_program);
CREATE INDEX IF NOT EXISTS idx_staging_lead_created ON staging_lead(created_at);
CREATE INDEX IF NOT EXISTS idx_staging_lead_run ON staging_lead(ingestion_run_id);
CREATE INDEX IF NOT EXISTS idx_staging_lead_cedula ON staging_lead(cedula);
CREATE INDEX IF NOT EXISTS idx_staging_lead_birth_date ON staging_lead(birth_date);

-- 6. Staging Reference Data table (depends on staging_ingestion_run)
CREATE TABLE IF NOT EXISTS staging_reference_data (
    id SERIAL PRIMARY KEY,
    
    -- Source Information
    source_file VARCHAR(500) NOT NULL,
    source_sheet VARCHAR(255),
    
    -- Classification
    data_type VARCHAR(100),
    category VARCHAR(100),
    
    -- Data Content (JSONB for flexibility)
    data_content JSONB NOT NULL,
    
    -- Metadata
    row_count INTEGER,
    column_count INTEGER,
    columns TEXT[],
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ingestion_run_id INTEGER REFERENCES staging_ingestion_run(id)
);

CREATE INDEX IF NOT EXISTS idx_staging_ref_type ON staging_reference_data(data_type);
CREATE INDEX IF NOT EXISTS idx_staging_ref_category ON staging_reference_data(category);
CREATE INDEX IF NOT EXISTS idx_staging_ref_source ON staging_reference_data(source_file);
CREATE INDEX IF NOT EXISTS idx_staging_ref_run ON staging_reference_data(ingestion_run_id);

-- 7. Staging Lead Failures table (depends on staging_ingestion_run)
CREATE TABLE IF NOT EXISTS staging_lead_failures (
    id SERIAL PRIMARY KEY,
    lead_data JSONB NOT NULL,
    error_message TEXT NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    ingestion_run_id INTEGER REFERENCES staging_ingestion_run(id),
    source_file VARCHAR(500),
    source_sheet VARCHAR(255),
    row_index INTEGER,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_staging_failures_run ON staging_lead_failures(ingestion_run_id);
CREATE INDEX IF NOT EXISTS idx_staging_failures_error_type ON staging_lead_failures(error_type);
CREATE INDEX IF NOT EXISTS idx_staging_failures_resolved ON staging_lead_failures(resolved);
CREATE INDEX IF NOT EXISTS idx_staging_failures_attempted ON staging_lead_failures(attempted_at DESC);

-- Update trigger for lead updated_at
CREATE OR REPLACE FUNCTION update_staging_lead_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_staging_lead_updated_at ON staging_lead;
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

-- Comments
COMMENT ON TABLE staging_ingestion_run IS 'Tracks all ingestion runs (students and leads)';
COMMENT ON TABLE staging_person IS 'Person records extracted from directory structure';
COMMENT ON TABLE staging_student IS 'Student enrollment records';
COMMENT ON TABLE staging_document IS 'Documents linked to students with normalized names';
COMMENT ON TABLE staging_lead IS 'Leads/prospects not yet enrolled in programs';
COMMENT ON TABLE staging_reference_data IS 'Reference data extracted from Excel files (price lists, configurations, etc.)';
COMMENT ON TABLE staging_lead_failures IS 'Failed lead insertion attempts with error details';
COMMENT ON VIEW staging_all_persons IS 'Combined view of all persons (students + leads)';
