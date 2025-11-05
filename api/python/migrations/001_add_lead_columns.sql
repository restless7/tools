-- Migration: Add missing columns to staging_lead table
-- Date: 2025-11-05
-- Issue: V3 ingestion failing to insert leads due to missing columns
--
-- The V3 enhanced pipeline captures additional person data from CSV files
-- (address, cedula, birth_date) but the original staging_lead table schema
-- was missing these columns.

ALTER TABLE staging_lead ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE staging_lead ADD COLUMN IF NOT EXISTS cedula VARCHAR(50);
ALTER TABLE staging_lead ADD COLUMN IF NOT EXISTS birth_date DATE;

-- Verify columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'staging_lead' 
  AND column_name IN ('address', 'cedula', 'birth_date');
