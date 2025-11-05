# ICE Data Ingestion Pipeline V3 - Enhanced with Excel/CSV Extraction

## Overview

The V3 ingestion pipeline is a comprehensive data extraction and normalization system that captures **all** available data from the ICE source directory, including:

- **Students**: Enrolled participants with documents
- **Leads**: Prospects and interested persons not yet enrolled
- **Reference Data**: Price lists, employer databases, configurations, etc.

## Architecture

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOURCE DATA DIRECTORY                        │
│  - Excel/CSV files (mixed programs, leads, reference data)     │
│  - Folder structure (organized by student names)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: EXCEL/CSV DATA EXTRACTION                              │
│ ─────────────────────────────────────────────────────────────  │
│ • ExcelDataExtractor: Converts all XLSX/XLS/CSV files         │
│ • DataClassifier: Categorizes as STUDENT/LEAD/REFERENCE       │
│ • PersonDataProcessor: Extracts person records                │
│                                                                 │
│ Output:                                                         │
│  - Classified CSV files in /extracted_csvs/                   │
│  - Structured person data (students + leads)                  │
│  - Reference data metadata                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: DIRECTORY STRUCTURE SCAN                               │
│ ─────────────────────────────────────────────────────────────  │
│ • LocalIngestionLoaderV2: Scans folders for documents         │
│ • Creates Person/Student records from folder names            │
│ • Indexes all documents with metadata                         │
│                                                                 │
│ Output:                                                         │
│  - Student records (UUID-based)                               │
│  - Document index with file paths                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: DATA MERGING & ENRICHMENT                             │
│ ─────────────────────────────────────────────────────────────  │
│ • Match students by normalized name                            │
│ • Enrich directory students with CSV email/phone              │
│ • Add additional fields (cedula, birth_date, address)         │
│                                                                 │
│ Output:                                                         │
│  - Enriched student records                                   │
│  - Separate leads collection                                  │
│  - Reference data collection                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: STAGING DATABASE INSERTION                            │
│ ─────────────────────────────────────────────────────────────  │
│ Tables:                                                         │
│  • staging_person       - Person records                       │
│  • staging_student      - Student records (linked to persons) │
│  • staging_document     - Document metadata                   │
│  • staging_lead         - Lead/prospect records               │
│  • staging_reference_data - Reference files metadata          │
│  • staging_ingestion_run  - ETL run logs                      │
│                                                                 │
│ Conflict Handling:                                             │
│  - Leads: ON CONFLICT update phone/address                    │
│  - Students: Checksum-based deduplication                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: REPORTING & VALIDATION                                │
│ ─────────────────────────────────────────────────────────────  │
│ • Comprehensive statistics                                     │
│ • Program distribution analysis                                │
│ • Enrichment metrics                                           │
│ • Execution time tracking                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Excel/CSV Data Extraction

**Module**: `data_extractor.py`

- Recursively finds all Excel/CSV files
- Converts multi-sheet Excel files to separate CSVs
- Handles date formatting issues and encoding problems
- Skips empty sheets automatically

**Classification Logic**:

- **STUDENT**: Files with keywords (student, estudiante, participant, enrolled, inscrito, visa, passport, program)
- **LEAD**: Files with keywords (lead, prospecto, inquiry, interested, pending, contact)
- **REFERENCE**: All other files (price lists, configurations, employer databases)

### 2. Person Data Processing

**Module**: `csv_data_processor.py`

**Column Mappings** (Multilingual):
```python
'full_name': ['NOMBRE COMPLETO', 'Nombre Completo', 'Name', 'Full Name']
'email': ['CORREO', 'Email', 'E-mail', 'Correo electrónico']
'phone': ['CELULAR', 'Teléfono', 'Phone', 'Móvil']
'address': ['DIRECCION', 'Dirección', 'Address']
'cedula': ['CEDULA', 'Cédula', 'ID', 'Document ID']
'birth_date': ['FECHA DE NACIMIENTO', 'Birth Date']
```

**Status Detection** (from sheet names):
- `ENROLLED`: inscrito, inscrita, registered, enrolled, active
- `INTERESTED`: interesada, interesado, interested, lead, prospecto
- `CANCELLED`: cancelad, cancelled, lost
- `SCHEDULED`: agendad, scheduled

### 3. Data Enrichment

**Matching Strategy**:
- Normalized name-based matching (accent removal, uppercase)
- Enriches directory students with CSV email/phone
- Preserves all additional CSV fields (cedula, birth_date, address)

**Deduplication**:
- Persons: By (normalized_name, email) tuple
- Leads: By email (with conflict resolution)
- Documents: By checksum

### 4. Database Schema

#### staging_lead
```sql
CREATE TABLE staging_lead (
    id UUID PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    cedula VARCHAR(50),
    birth_date DATE,
    country VARCHAR(100),
    city VARCHAR(100),
    source_file VARCHAR(500),
    source_sheet VARCHAR(255),
    status VARCHAR(50) DEFAULT 'NEW',
    interest_program VARCHAR(255),
    interest_level VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    ingestion_run_id INTEGER,
    converted_to_student_id UUID
);
```

#### staging_reference_data
```sql
CREATE TABLE staging_reference_data (
    id SERIAL PRIMARY KEY,
    source_file VARCHAR(500) NOT NULL,
    source_sheet VARCHAR(255),
    data_type VARCHAR(100),  -- PRICE_LIST, EMPLOYER_LIST, etc.
    category VARCHAR(100),
    data_content JSONB NOT NULL,
    row_count INTEGER,
    column_count INTEGER,
    columns TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    ingestion_run_id INTEGER
);
```

#### staging_all_persons (View)
```sql
-- Combined view of students + leads
CREATE VIEW staging_all_persons AS
SELECT 'STUDENT' as person_type, s.id, p.full_name, p.email, 
       s.program, 'ENROLLED' as status
FROM staging_student s
JOIN staging_person p ON s.person_id = p.id
UNION ALL
SELECT 'LEAD' as person_type, l.id, l.full_name, l.email,
       l.interest_program as program, l.status
FROM staging_lead l;
```

## Usage

### Command Line Execution

```bash
# Navigate to Python API directory
cd /home/sebastiangarcia/planmaestro-ecosystem/packages/tools/api/python

# Run V3 ingestion pipeline
python3 ingestion_to_staging_v3.py
```

### Programmatic Usage

```python
from ingestion_to_staging_v3 import EnhancedStagingIngestionManager

manager = EnhancedStagingIngestionManager(
    source_dir="/path/to/source/data",
    staging_dir="/path/to/staging",
    db_url="postgresql://user:pass@localhost:5432/database"
)

manager.run_full_ingestion()
```

### Environment Variables

```bash
# .env file
SOURCE_DIR="/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001"
STAGING_DIR="/home/sebastiangarcia/ice-data-staging"
DATABASE_URL="postgresql://postgres:password@localhost:5432/leads_project"
```

## Output Structure

### Staging Directory
```
/home/sebastiangarcia/ice-data-staging/
├── documents/
│   ├── {student-uuid}/
│   │   ├── STUDENT_INFO.json
│   │   ├── {uuid}_PASSPORT_00.pdf
│   │   ├── {uuid}_DIPLOMA_01.pdf
│   │   └── ...
├── extracted_csvs/
│   ├── AU_PAIR_INSCRITAS.csv
│   ├── Camp_2025_CAMP_2025.csv
│   ├── H2B_Employers_from_Colorado_Sheet_1.csv
│   └── ...
├── metadata/
│   └── ingestion_results_*.json
└── reports/
    ├── ingestion_v3.log
    └── ingestion_v3_report_*.txt
```

### Final Report Example
```
================================================================================
ICE DATA INGESTION - ENHANCED V3 FINAL REPORT
================================================================================
Run ID: 1
Execution Time: 45.23 seconds
Timestamp: 2025-11-05T10:30:00

EXCEL/CSV EXTRACTION
================================================================================
Excel Files Processed:      21
CSV Sheets Extracted:       58
Students from CSV:          0
Leads Found:               655
Reference Files:           17

DIRECTORY SCAN
================================================================================
Students from Directories: 160
Documents Found:           754

DATA ENRICHMENT
================================================================================
Total Unique Students:     160
CSV-Enriched Students:     35

FINAL DATABASE RECORDS
================================================================================
Students Inserted:         160
Documents Inserted:        754
Leads Inserted:            655
Reference Files Stored:    17

PROGRAM DISTRIBUTION
================================================================================
Work and Travel                95
Unknown                        31
Au Pair                        19
Camp Counselor                  5
Canada                          5
H-2B                            4
Intern & Trainee                1
================================================================================
```

## Statistics & Metrics

### Real Data Results (Sample Run)

- **Excel Files**: 21 files processed
- **CSV Sheets**: 58 sheets extracted
- **Students**: 160 records (from directories)
- **Leads**: 655 prospects (from CSV files)
- **Reference Files**: 17 files (employer lists, prices, etc.)
- **Documents**: 754 indexed and normalized
- **Execution Time**: ~45 seconds

### Enrichment Rate

- 35 out of 160 students (21.9%) enriched with CSV data
- Email/phone added where missing
- Additional fields captured: cedula, birth_date, address

## Data Quality

### Name Normalization
```python
Input:  "García López, María José"
Output: "GARCIA LOPEZ MARIA JOSE"

Input:  "João-Carlos de Souza"
Output: "JOAO-CARLOS DE SOUZA"
```

### Document Type Classification

Enhanced with 14 types:
- PASSPORT
- VISA
- DIPLOMA
- TRANSCRIPT
- PHOTO
- FINANCIAL
- MEDICAL
- ID_CARD
- LETTER
- RESUME
- CONTRACT
- BACKGROUND_CHECK
- EMERGENCY_CONTACT
- QUOTATION
- OTHER (fallback)

## Error Handling

### Graceful Degradation

- **Empty sheets**: Skipped automatically
- **Missing columns**: Falls back to available data
- **Invalid data**: Logged as warnings, continues processing
- **Date formatting issues**: Captured in logs, treated as errors
- **Database conflicts**: ON CONFLICT clauses for upserts

### Logging

All operations logged to:
- Console (INFO level)
- File: `/home/sebastiangarcia/ice-data-staging/reports/ingestion_v3.log`

## Performance

### Optimization Techniques

1. **Batch Processing**: CSV files processed in batches
2. **Deduplication Cache**: In-memory cache for person records
3. **Connection Pooling**: Single database connection reused
4. **Lazy Loading**: Documents copied only when needed
5. **Parallel Processing**: Multiple CSV sheets processed concurrently

### Bottlenecks

- Excel file conversion (I/O bound)
- Database insertions (can be batched further)
- Large file copying (disk speed dependent)

## Future Enhancements

1. **Async Processing**: Use asyncio for parallel Excel conversion
2. **Batch Insertions**: Use execute_batch for leads/reference data
3. **Document OCR**: Extract text from PDFs for better classification
4. **Fuzzy Matching**: Improve name matching with Levenshtein distance
5. **API Integration**: Expose pipeline as REST endpoint
6. **Progress Tracking**: Real-time progress updates via WebSocket
7. **Incremental Updates**: Process only changed files

## API Integration

### FastAPI Endpoint (Planned)

```python
@app.post("/ingestion/v3/trigger")
async def trigger_v3_ingestion(
    source_dir: str,
    background_tasks: BackgroundTasks
):
    """Trigger V3 ingestion pipeline in background."""
    background_tasks.add_task(
        run_v3_ingestion_pipeline,
        source_dir=source_dir
    )
    return {"status": "started", "message": "V3 ingestion running"}
```

### Dashboard Integration

The V3 pipeline is designed to work with the existing Next.js dashboard at:
- URL: `http://localhost:3005/ice-database`
- Features: Ingestion trigger, statistics display, lead management

## Troubleshooting

### Common Issues

**Problem**: `ModuleNotFoundError: No module named 'local_ingestion_loader_v2'`  
**Solution**: Run from `api/python` directory or use `sys.path` manipulation

**Problem**: Database connection errors  
**Solution**: Check DATABASE_URL in .env file, verify PostgreSQL is running

**Problem**: Excel files not converting  
**Solution**: Check openpyxl installation, verify file permissions

**Problem**: Leads not classified correctly  
**Solution**: Review sheet name keywords in DataClassifier

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Testing

### Unit Tests (To Do)
```bash
pytest api/python/test_data_extractor.py
pytest api/python/test_csv_processor.py
pytest api/python/test_ingestion_v3.py
```

### Integration Test
```bash
# Dry run without database insertion
python3 api/python/ingestion_to_staging_v3.py --dry-run
```

## Contributors

- PlanMaestro Development Team
- ICE Data Engineering Team

## License

Internal use only - PlanMaestro Ecosystem

## References

- [V2 Ingestion Documentation](./LOCAL_INGESTION_README.md)
- [Database Schema](./api/python/staging_schema_leads.sql)
- [WARP Development Guide](./WARP.md)
