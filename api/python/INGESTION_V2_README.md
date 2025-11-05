# ICE Data Ingestion System V2 - Directory-First Approach

## Overview

The V2 ingestion system is designed to handle **real-world, non-normalized data** where:
- Student records may not exist in CSV files
- Documents are organized in directories named after students
- Data spans multiple years and programs without unified structure
- CSV files (if they exist) contain partial information

## Philosophy: Directory-First

**Primary Source: Student Directories**
- The file system structure defines who the students are
- Every directory containing documents represents a student
- Person and Student records are created from directory names

**Secondary Source: CSV Enrichment (Optional)**
- CSV files provide additional metadata (email, phone, birth date, etc.)
- CSV data enriches existing records via name matching
- System works perfectly fine with ZERO CSV files

## Key Features

### 1. Comprehensive Student Discovery
- Recursively scans all directories for student folders
- Creates Person and Student records with UUIDs for each discovered student
- No student is left behind, regardless of CSV presence

### 2. Intelligent Program Detection
Automatically infers program from directory path:
- `Au Pair` - from paths containing "au pair" or "aupair"
- `Work and Travel` - from "wat" or "work and travel"
- `H-2B` - from "h2b" or "h-2b"
- `Intern & Trainee` - from "intern" or "trainee"
- `Camp Counselor` - from "camp" or "counselor"
- `Canada` - from "canada" or "canadá"
- `Unknown` - default when no keywords match

### 3. Name Normalization & Matching
- Removes accents/diacritics (é → e, ñ → n)
- Converts to uppercase
- Removes special characters
- Normalizes whitespace
- Enables matching between directory names and CSV entries

### 4. Document Metadata Extraction
- Automatically matches documents to students by directory
- Computes SHA-256 checksums for file integrity
- Infers MIME types from file extensions
- Classifies document types (PASSPORT, VISA, DIPLOMA, PHOTO, etc.)

### 5. CSV Enrichment (Optional)
- Flexible column mapping supports various CSV formats
- Enriches records with: email, phone, address, ID number, birth date
- Handles Spanish and English column names
- Logs enrichment status in each record

## Usage

### Basic Usage (Auto-Discovery)
```python
from local_ingestion_loader_v2 import LocalIngestionLoaderV2

# Point to data directory
base_dir = "/path/to/data"
loader = LocalIngestionLoaderV2(base_dir)

# Run ingestion (auto-discovers everything)
results = loader.run_ingestion(program="Default Program")

print(f"Students: {len(results['student_records'])}")
print(f"Documents: {len(results['documents'])}")
```

### Specify CSV Files
```python
from pathlib import Path

csv_files = [
    Path("/path/to/au_pair.xlsx"),
    Path("/path/to/students_2024.csv")
]

results = loader.run_ingestion(
    csv_files=csv_files,
    program="Au Pair"
)
```

### Command Line
```bash
cd api/python
source venv/bin/activate
python local_ingestion_loader_v2.py
```

## Data Structure

### Input Directory Structure
```
data_ingestion/
├── Au Pair/
│   ├── AU PAIR.xlsx                          # Optional CSV enrichment
│   ├── AU PAIR 2024/
│   │   ├── VERA FLOREZ SYLVIA GIULIANNA/     # Student directory
│   │   │   ├── Passport Sylvia Vera.png
│   │   │   ├── Diploma Sylvia Vera.pdf
│   │   │   └── Resume Sylvia Vera.docx
│   │   └── ORTIZ VASQUEZ DANIELA/
│   │       └── Passport Daniela Ortiz.pdf
│   └── AU PAIR 2025/
│       └── ...
├── WAT/
│   ├── 2024/
│   │   └── STUDENT NAME/
│   │       └── documents...
│   └── 2025/
└── H2B/
    └── ...
```

### Output Record Structure

**Student Record (Directory Only)**
```python
{
    'person_id': 'uuid-generated',
    'student_id': 'uuid-generated',
    'full_name': 'VERA FLOREZ SYLVIA GIULIANNA',
    'normalized_name': 'VERA FLOREZ SYLVIA GIULIANNA',
    'email': None,
    'phone': None,
    'address': None,
    'id_number': None,
    'birth_date': None,
    'program': 'Au Pair',
    'source': 'directory',
    'directory_path': '/path/to/student/folder'
}
```

**Student Record (Enriched from CSV)**
```python
{
    'person_id': 'uuid-generated',
    'student_id': 'uuid-generated',
    'full_name': 'VERA FLOREZ SYLVIA GIULIANNA',
    'normalized_name': 'VERA FLOREZ SYLVIA GIULIANNA',
    'email': 'sylviavera1804@gmail.com',
    'phone': '3153234963',
    'address': 'Cra 22 #157-145 - Bucaramanga',
    'id_number': '1005161684',
    'birth_date': datetime.date(2002, 3, 4),
    'program': 'Au Pair',
    'source': 'directory+csv',
    'csv_file': 'AU PAIR.xlsx',
    'directory_path': '/path/to/student/folder'
}
```

**Document Metadata**
```python
{
    'student_id': 'uuid-matching-student',
    'file_name': 'Passport Sylvia Vera.png',
    'file_path': '/full/path/to/Passport Sylvia Vera.png',
    'file_size': 2437360,
    'mime_type': 'image/png',
    'document_type': 'PASSPORT',
    'checksum': 'sha256-hash-of-file'
}
```

## Ingestion Statistics

```
============================================================
Ingestion Complete!
Execution Time: 2.45s
Person Records Created: 160
Student Records Created: 160
Records Enriched from CSV: 10
Documents Indexed: 754
CSV Files Processed: 20
Errors: 0
============================================================
```

## CSV Column Mapping

The system supports flexible column names in CSV files:

| Field       | Supported Column Names                                    |
|-------------|----------------------------------------------------------|
| Full Name   | NOMBRE COMPLETO, Nombre Completo, Name, Full Name       |
| Email       | CORREO, Correo, Email, E-mail                            |
| Phone       | CELULAR, Celular, Teléfono, Telefono, Phone             |
| Address     | DIRECCION, Dirección, Direccion, Address                |
| ID Number   | CEDULA, Cédula, Cedula, ID                               |
| Birth Date  | FECHA DE NACIMIENTO, Fecha de Nacimiento, Birth Date    |
| Program     | PROGRAMA, Programa, Program                              |

## Document Type Classification

Automatic classification based on filename keywords:

| Document Type | Keywords                              |
|---------------|---------------------------------------|
| PASSPORT      | passport, pasaporte                   |
| VISA          | visa                                  |
| DIPLOMA       | diploma, certificate, certificado     |
| PHOTO         | photo, foto                           |
| OTHER         | resume, cv, antecedentes, (default)   |

## Real-World Results

### Test Run: Full Data Ingestion
**Base Directory**: `/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001`

**Results**:
- Total Students: **160**
- Total Documents: **754**
- CSV Files Found: **20**
- Records Enriched: **10**

**Program Breakdown**:
- Work and Travel: 95 students
- Unknown: 31 students
- Au Pair: 19 students
- Camp Counselor: 5 students
- Canada: 5 students
- H-2B: 4 students
- Intern & Trainee: 1 student

## Advantages Over V1

| Feature | V1 (CSV-First) | V2 (Directory-First) |
|---------|----------------|----------------------|
| Requires CSV | ✅ Yes | ❌ No |
| Creates records without CSV | ❌ No | ✅ Yes |
| Handles multi-year data | ⚠️ Partial | ✅ Full |
| Program detection | Manual | Automatic |
| Name normalization | Basic | Advanced (accents, special chars) |
| Document matching | By pre-existing ID | By directory name |
| Handles incomplete data | ❌ Fails | ✅ Continues |

## Next Steps: Database Integration

The V2 system generates structured data ready for database insertion:

### 1. Person Table
```sql
INSERT INTO "Person" (id, "fullName", email, phone)
VALUES (uuid, full_name, email, phone);
```

### 2. Student Table
```sql
INSERT INTO "Student" (id, "personId", "studentNumber", program, status)
VALUES (uuid, person_id, id_number, program, 'ACTIVE');
```

### 3. StudentDocument Table
```sql
INSERT INTO "StudentDocument" (
    id, "studentId", "documentType", "fileName", 
    "objectKey", bucket, "fileSize", "mimeType", 
    "storageProvider", status
)
VALUES (
    uuid(), student_id, document_type, file_name,
    object_key, 'apex-ice-docs', file_size, mime_type,
    'LOCAL', 'PENDING'
);
```

## Integration with db_utils.py

The next step is to integrate this loader with `db_utils.py` to:
1. Batch insert Person records
2. Batch insert Student records
3. Insert StudentDocument records
4. Log ETL run to etl_logs table
5. Handle idempotency via checksums

## Error Handling

The system gracefully handles:
- Missing CSV files (continues without enrichment)
- Invalid CSV formats (skips file, logs error)
- Missing columns (uses defaults/None)
- Invalid dates (logs warning, continues)
- Duplicate directory names (creates separate records)
- Empty directories (skips, no record created)

## Performance

**Tested on 160 students, 754 documents:**
- Execution Time: ~2.5 seconds
- Memory Usage: < 100MB
- CPU Usage: Single-threaded, minimal

**Scaling considerations:**
- Checksum computation is the bottleneck for large files
- Consider parallel processing for 1000+ students
- Database batch inserts for optimal performance

## Dependencies

```
pandas
openpyxl
unidecode
hashlib (stdlib)
pathlib (stdlib)
uuid (stdlib)
```

## Installation

```bash
cd api/python
source venv/bin/activate
pip install pandas openpyxl unidecode
```

## Summary

The V2 ingestion system solves the real-world problem of **non-normalized, scattered data**:
- ✅ Works with or without CSV files
- ✅ Creates comprehensive student records from directories
- ✅ Enriches with CSV data when available
- ✅ Handles multiple years and programs
- ✅ Automatic program detection
- ✅ Intelligent name matching
- ✅ Complete document indexing
- ✅ Ready for database integration

**Perfect for ICE's actual data structure!**
