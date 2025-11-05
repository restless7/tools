# Local ICE Data Ingestion - Documentation

## Overview

The local ICE data ingestion pipeline allows you to ingest student, lead, and document data from the local filesystem, bypassing Google Drive dependencies. This is ideal for offline development, testing, and local data processing.

## Architecture

### Components

1. **Storage Adapter** (`storage_adapter.py`)
   - Abstract interface for document storage operations
   - `LocalStorageAdapter`: Handles local filesystem operations
   - Future: `MinIOStorageAdapter` for object storage

2. **Local Ingestion Loader** (`local_ingestion_loader.py`)
   - Scans local directories for data files
   - Parses Excel/CSV files
   - Extracts document metadata

3. **Database Manager** (`db_utils.py`)
   - Manages PostgreSQL operations
   - Handles idempotency checks
   - ETL logging and statistics

4. **Ingestion Pipeline** (`ingestion_local.py`)
   - Main orchestrator
   - Mode detection (local/remote/auto)
   - CLI interface

### Data Flow

```
Local Filesystem
    ↓
LocalIngestionLoader
    ↓
StorageAdapter (metadata extraction)
    ↓
DatabaseManager (PostgreSQL)
    ↓
ETL Logs & Statistics
```

## Directory Structure

```
/home/sebastiangarcia/ice-ingestion-data/
├── leads/
│   ├── leads_batch_2025_01.csv
│   └── leads_batch_2025_02.xlsx
├── students/
│   ├── students_batch_2025_01.csv
│   └── students_batch_2025_02.xlsx
└── documents/
    ├── STU001/
    │   ├── passport.pdf
    │   ├── transcript.pdf
    │   └── visa_form.pdf
    ├── STU002/
    │   ├── passport.pdf
    │   └── photo.jpg
    └── ...
```

## Setup

### 1. Environment Configuration

Create `.env` file in `api/python/`:

```bash
# Required
DATABASE_URL=postgresql://user:password@localhost:5432/ice_database
LOCAL_INGESTION_DIR=/home/sebastiangarcia/ice-ingestion-data

# Optional
INGESTION_MODE=auto  # or 'local' to force local mode
LOG_LEVEL=INFO
```

### 2. Create Data Directory

```bash
mkdir -p ~/ice-ingestion-data/{leads,students,documents}
```

### 3. Install Python Dependencies

The required dependencies should already be in your `requirements.txt`:

```
pandas>=2.0.0
openpyxl>=3.0.0
psycopg2-binary>=2.9.0
```

If not, install them:

```bash
cd api/python
source venv/bin/activate
pip install pandas openpyxl psycopg2-binary
```

### 4. Initialize Database Tables

The pipeline will automatically create required tables on first run:

- `student_documents`: Document metadata with idempotency
- `etl_logs`: Ingestion run history and statistics

Or manually initialize:

```bash
cd api/python
source venv/bin/activate
python db_utils.py
```

## Usage

### Command Line Interface

```bash
cd api/python
source venv/bin/activate

# Auto-detect mode (local if directory exists)
python ingestion_local.py

# Force local mode
python ingestion_local.py --mode local

# Override base directory
python ingestion_local.py --base-dir /path/to/data

# Set log level
python ingestion_local.py --log-level DEBUG

# Get help
python ingestion_local.py --help
```

### Expected Output

```
================================================================================
Starting ICE Data Ingestion - Mode: LOCAL
================================================================================
✔ Base directory exists: /home/sebastiangarcia/ice-ingestion-data
✔ Database connection successful
✔ Local environment validation successful
Loading student data...
✔ Loaded 32 student records from 2 files
Loading lead data...
✔ Loaded 78 lead records from 3 files
Scanning document files...
✔ Indexed 210 document files
✔ Saved metadata to PostgreSQL: 210 inserted, 0 skipped
================================================================================
Ingestion Complete - Summary
================================================================================
✔ Environment validated
✔ Found 32 student records
✔ Found 78 lead records
✔ Indexed 210 document files
✔ Saved metadata to PostgreSQL
⏱ Completed in 12.8 seconds
🎉 Ingestion successful!
```

## Data Format Requirements

### Student/Lead CSV/Excel Files

**Students:**
```csv
student_id,first_name,last_name,email,phone,country,program,status
STU001,John,Doe,john.doe@email.com,+1234567890,USA,Computer Science,Active
```

**Leads:**
```csv
lead_id,first_name,last_name,email,phone,country,interest,source,status
LEAD001,Ahmed,Hassan,ahmed.hassan@email.com,+1234567895,Egypt,MBA,Website,New
```

Supported formats: `.xlsx`, `.xls`, `.csv`

### Document Files

- Place in `documents/<student_id>/` subdirectories
- Any file type supported (PDF, JPG, PNG, DOCX, etc.)
- File names are used for document type inference:
  - `passport*` → passport
  - `transcript*` → transcript
  - `visa*` → visa_form
  - `photo*`, `picture*` → photo
  - `certificate*` → certificate
  - etc.

## Database Schema

### student_documents Table

```sql
CREATE TABLE student_documents (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(255) NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(255),
    checksum VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    storage_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, checksum)
);
```

### etl_logs Table

```sql
CREATE TABLE etl_logs (
    id SERIAL PRIMARY KEY,
    ingestion_mode VARCHAR(50) NOT NULL,
    source_path TEXT,
    student_records INT DEFAULT 0,
    lead_records INT DEFAULT 0,
    document_files INT DEFAULT 0,
    files_processed INT DEFAULT 0,
    execution_time FLOAT,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Idempotency

The pipeline is fully idempotent:

- Documents are identified by `(student_id, checksum)` tuple
- Re-running ingestion on the same data will skip duplicates
- Checksums are SHA256 hashes of file contents
- Safe to run multiple times without data duplication

Example:

```bash
# First run
python ingestion_local.py
# Output: 210 inserted, 0 skipped

# Second run (same data)
python ingestion_local.py
# Output: 0 inserted, 210 skipped
```

## Testing

### Quick Test with Sample Data

```bash
# Create test directory
mkdir -p ~/ice-ingestion-data-test/{leads,students,documents/STU001}

# Create sample files
echo "student_id,name" > ~/ice-ingestion-data-test/students/test.csv
echo "STU001,Test Student" >> ~/ice-ingestion-data-test/students/test.csv
echo "Sample document" > ~/ice-ingestion-data-test/documents/STU001/passport.pdf

# Run ingestion
python ingestion_local.py --base-dir ~/ice-ingestion-data-test
```

### Module Tests

```bash
# Test storage adapter
python storage_adapter.py

# Test database manager
python db_utils.py

# Test local loader
python local_ingestion_loader.py
```

## Integration with Existing System

### API Endpoint

The local ingestion can be integrated with the existing FastAPI endpoints:

```python
# In ice_ingestion.py
from ingestion_local import ICEIngestionPipeline

@router.post("/ingest/local")
async def run_local_ingestion_endpoint():
    pipeline = ICEIngestionPipeline(mode='local')
    result = pipeline.run_ingestion()
    
    if result['success']:
        return {"status": "success", "data": result}
    else:
        raise HTTPException(status_code=500, detail=result['error'])
```

### Frontend Integration

Update the frontend to call the local ingestion endpoint:

```typescript
// In lib/api.ts
export async function runLocalIngestion() {
  const response = await fetch(`${API_URL}/ice/ingest/local`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    throw new Error('Local ingestion failed');
  }
  
  return response.json();
}
```

## Troubleshooting

### Common Issues

**1. Database Connection Failed**
```
✗ Database connection failed
```
Solution: Check `DATABASE_URL` in `.env` file and ensure PostgreSQL is running.

**2. Base Directory Does Not Exist**
```
✗ Base directory does not exist: /path/to/data
```
Solution: Create directory or update `LOCAL_INGESTION_DIR` in `.env`.

**3. Permission Denied**
```
Error: Permission denied
```
Solution: Ensure user has read/write access to data directory.

**4. Module Import Errors**
```
ModuleNotFoundError: No module named 'pandas'
```
Solution: Install dependencies: `pip install pandas openpyxl psycopg2-binary`

### Logs

Check logs for detailed error information:

```bash
# Default log location
tail -f logs/ice_ingestion.log

# Or if /var/log is accessible
tail -f /var/log/ice_ingestion.log
```

### Debug Mode

Run with debug logging:

```bash
python ingestion_local.py --log-level DEBUG
```

## Future Enhancements

### MinIO Integration

The architecture is ready for MinIO object storage:

1. Implement `MinIOStorageAdapter` in `storage_adapter.py`
2. Add MinIO configuration to `.env`
3. Update `ingestion_local.py` to use MinIO adapter
4. Documents will be uploaded to MinIO and `storage_url` populated

### Validation Rules

Add data validation for student/lead records:

- Email format validation
- Phone number normalization
- Required field checks
- Data type validation

### Parallel Processing

For large datasets, implement parallel processing:

- Multi-threaded file parsing
- Batch database insertions
- Concurrent document metadata extraction

### Real-time Monitoring

Add monitoring capabilities:

- Progress bars for long-running ingestions
- WebSocket updates for frontend
- Prometheus metrics export

## API Reference

### ICEIngestionPipeline

```python
class ICEIngestionPipeline:
    def __init__(self, mode: str = 'auto')
    def validate_environment(self) -> bool
    def run_ingestion(self) -> Dict[str, Any]
```

### LocalIngestionLoader

```python
class LocalIngestionLoader:
    def __init__(self, base_dir: str)
    def validate_directory_structure(self) -> bool
    def load_student_data(self) -> List[Dict[str, Any]]
    def load_lead_data(self) -> List[Dict[str, Any]]
    def scan_document_files(self) -> List[DocumentMetadata]
    def load_all_data(self) -> Dict[str, Any]
```

### DatabaseManager

```python
class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None)
    def test_connection(self) -> bool
    def ensure_tables_exist(self)
    def check_document_exists(self, student_id: str, checksum: str) -> Optional[int]
    def insert_document_metadata(self, metadata: DocumentMetadata) -> Optional[int]
    def bulk_insert_document_metadata(self, metadata_list: List[DocumentMetadata]) -> Dict[str, Any]
    def log_etl_run(self, ...) -> int
```

### StorageAdapter

```python
class StorageAdapter(ABC):
    @abstractmethod
    def validate_file(self, file_path: str) -> bool
    @abstractmethod
    def get_metadata(self, file_path: str, student_id: Optional[str]) -> DocumentMetadata
    @abstractmethod
    def upload(self, file_path: str, destination: str) -> Dict[str, Any]
    @abstractmethod
    def get_public_url(self, file_path: str) -> Optional[str]
```

## Support

For issues or questions:

1. Check this documentation
2. Review log files
3. Test with sample data
4. Contact development team

## License

Part of the PlanMaestro Tools ecosystem.
