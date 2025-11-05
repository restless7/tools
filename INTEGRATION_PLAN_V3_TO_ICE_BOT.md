# V3 Enhanced Pipeline → ICE-Visa-Rescheduler-Bot Integration Plan

**Created**: November 5, 2025  
**Status**: 🔄 Ready for Implementation  
**Objective**: Integrate V3 Enhanced Staging Data into Production ICE-Visa-Rescheduler-Bot Database

---

## 🎯 Overview

This plan details the integration of the **V3 Enhanced ICE Data Ingestion Pipeline** (currently in `tools` package) with the **production ICE-Visa-Rescheduler-Bot** database. The goal is to create a unified, accumulative system where new data enriches existing records without creating duplicates.

### Current State

**V3 Staging System** (`tools` package):
- Database: `leads_project` (PostgreSQL)
- Tables: `staging_student`, `staging_lead`, `staging_document`, `staging_reference_data`, `staging_lead_failures`
- Data: 484+ leads, 17 reference files, comprehensive CSV extraction
- Features: Sanitization, normalization, failure tracking, pagination

**ICE-Visa-Rescheduler-Bot** (production):
- Database: ICE bot database (PostgreSQL)
- Schema: Prisma with `Person`, `Student`, `Lead`, `StudentDocument` models
- Storage: MinIO-ready document system
- Features: Role-based access, document management, appointment scheduling

### Integration Goals

1. **Unified Database**: Merge staging data into production ICE bot database
2. **Accumulative System**: New ingestion adds data without duplicates
3. **Source of Truth**: Implement idempotency checks across all entities
4. **Schema Expansion**: Add missing fields from staging to production
5. **Document Migration**: Migrate documents from staging to MinIO
6. **Data Enrichment**: Enhance existing persons/students with CSV data

---

## 📋 Phase 1: Schema Analysis & Expansion

### 1.1 Missing Fields in Production Schema

#### Staging vs Production Comparison

| Staging Field | Production Model | Action Required |
|---------------|------------------|------------------|
| **Person Fields** |
| `address` | `Person` | ✅ Add to Person |
| `cedula` | `Person` | ✅ Add to Person |
| `birth_date` | `Person` | ✅ Add to Person |
| `country` | `Person` | ❌ Already exists (indirectly) |
| **Lead Fields** |
| `interest_program` | `Lead` | ✅ Add as `programType` |
| `address` | `Lead.person` | Via Person |
| `cedula` | `Lead.person` | Via Person |
| `birth_date` | `Lead.person` | Via Person |
| **Student Fields** |
| `source` | `Student` | ✅ Add as `dataSource` |
| `original_name` | `Student` | ✅ Add for data lineage |
| `csv_enriched` | `Student` | ✅ Add as boolean flag |
| **Document Fields** |
| `original_file_path` | `StudentDocument` | ✅ Add for migration tracking |
| `checksum` | `StudentDocument` | ✅ Add for deduplication |
| `normalized_file_name` | `StudentDocument` | Maps to `fileName` |
| `staging_file_path` | `StudentDocument` | Maps to `objectKey` |

### 1.2 Required Prisma Schema Changes

**File**: `/packages/ICE-Visa-Rescheduler-Bot/prisma/schema.prisma`

```prisma
// Enhanced Person model with staging fields
model Person {
  id                 String              @id @default(uuid()) @db.Uuid
  fullName           String              @map("full_name")
  email              String              @unique
  phone              String?
  age                Int?
  city               String?
  
  // ✅ NEW FIELDS FROM STAGING
  address            String?              // From staging_lead/staging_student
  cedula             String?             @unique // Colombian ID (unique identifier)
  birthDate          DateTime?           @map("birth_date") // Date of birth
  country            String?             // Country of residence
  dataSource         String?             @map("data_source") // "CSV", "MANUAL", "API"
  originalName       String?             @map("original_name") // Pre-normalization name
  csvEnriched        Boolean             @default(false) @map("csv_enriched") // Enriched via CSV
  
  agencyId           String?             @map("agency_id") @db.Uuid
  createdAt          DateTime            @default(now()) @map("created_at")
  updatedAt          DateTime            @updatedAt @map("updated_at")
  
  // ... (rest of relations)
  
  @@index([cedula])
  @@index([birthDate])
  @@index([dataSource])
  @@map("persons")
}

// Enhanced Student model
model Student {
  id               String            @id @default(uuid()) @db.Uuid
  personId         String            @unique @map("person_id") @db.Uuid
  studentNumber    String?           @unique @map("student_number")
  program          String?
  startDate        DateTime?         @map("start_date")
  endDate          DateTime?         @map("end_date")
  status           String            @default("ACTIVE")
  
  // ✅ NEW FIELDS FROM STAGING
  dataSource       String?            @map("data_source") // "directory+csv", "csv_only", "directory_only"
  csvEnriched      Boolean            @default(false) @map("csv_enriched")
  
  currentSemester  String?           @map("current_semester")
  gpa              Float?
  creditsTotal     Int?              @map("credits_total")
  creditsCompleted Int?              @map("credits_completed")
  createdAt        DateTime          @default(now()) @map("created_at")
  updatedAt        DateTime          @updatedAt @map("updated_at")
  
  // ... (rest of relations)
  
  @@index([dataSource])
  @@map("students")
}

// Enhanced Lead model
model Lead {
  id              String    @id @default(uuid()) @db.Uuid
  leadDate        DateTime? @map("lead_date")
  leadStatus      String?   @map("lead_status")
  followupStatus  Json?     @map("followup_status")
  notes           String?
  
  // ✅ NEW FIELDS FROM STAGING
  programType     String?   @map("program_type") // Interest program (Au Pair, Camp, etc.)
  
  sourceSheet     String?   @map("source_sheet")
  sourceRow       Int?      @map("source_row")
  sourceFile      String?   @map("source_file")
  personId        String    @map("person_id") @db.Uuid
  serviceId       String?   @map("service_id") @db.Uuid
  eventId         String?   @map("event_id") @db.Uuid
  assignedAgentId String?   @map("assigned_agent_id") @db.Uuid
  createdAt       DateTime  @default(now()) @map("created_at")
  updatedAt       DateTime  @updatedAt @map("updated_at")
  
  // ... (rest of relations)
  
  @@index([programType])
  @@map("leads")
}

// Enhanced StudentDocument model
model StudentDocument {
  id               String            @id @default(uuid()) @db.Uuid
  studentId        String            @map("student_id") @db.Uuid
  documentType     String            @map("document_type")
  fileName         String            @map("file_name")
  objectKey        String            @map("object_key")
  bucket           String            @default("apex-ice-docs")
  fileSize         Int               @map("file_size")
  mimeType         String            @map("mime_type")
  
  // ✅ NEW FIELDS FROM STAGING
  checksum         String?           // SHA256 for deduplication
  originalFilePath String?           @map("original_file_path") // Source file path
  
  storageProvider  StorageProvider   @default(MINIO)
  status           String            @default("PENDING")
  uploadedAt       DateTime          @default(now()) @map("uploaded_at")
  uploadedBy       String?           @map("uploaded_by") @db.Uuid
  approvedAt       DateTime?         @map("approved_at")
  approvedBy       String?           @map("approved_by") @db.Uuid
  comments         String?
  version          Int               @default(1)
  createdAt        DateTime          @default(now()) @map("created_at")
  updatedAt        DateTime          @updatedAt @map("updated_at")
  
  student          Student           @relation(fields: [studentId], references: [id], onDelete: Cascade)
  
  @@unique([studentId, checksum]) // Prevent duplicate documents
  @@index([checksum])
  @@map("student_documents")
}
```

### 1.3 Migration Script

**File**: `/packages/ICE-Visa-Rescheduler-Bot/prisma/migrations/20251105_add_staging_fields/migration.sql`

```sql
-- Migration: Add V3 Staging Fields to Production Schema
-- Created: 2025-11-05
-- Purpose: Integrate V3 Enhanced Pipeline data

-- Person enhancements
ALTER TABLE persons ADD COLUMN address TEXT;
ALTER TABLE persons ADD COLUMN cedula VARCHAR(50) UNIQUE;
ALTER TABLE persons ADD COLUMN birth_date DATE;
ALTER TABLE persons ADD COLUMN country VARCHAR(100);
ALTER TABLE persons ADD COLUMN data_source VARCHAR(50);
ALTER TABLE persons ADD COLUMN original_name TEXT;
ALTER TABLE persons ADD COLUMN csv_enriched BOOLEAN DEFAULT FALSE;

-- Indexes for Person
CREATE INDEX idx_persons_cedula ON persons(cedula);
CREATE INDEX idx_persons_birth_date ON persons(birth_date);
CREATE INDEX idx_persons_data_source ON persons(data_source);

-- Student enhancements
ALTER TABLE students ADD COLUMN data_source VARCHAR(50);
ALTER TABLE students ADD COLUMN csv_enriched BOOLEAN DEFAULT FALSE;

-- Index for Student
CREATE INDEX idx_students_data_source ON students(data_source);

-- Lead enhancements
ALTER TABLE leads ADD COLUMN program_type VARCHAR(100);

-- Index for Lead
CREATE INDEX idx_leads_program_type ON leads(program_type);

-- StudentDocument enhancements
ALTER TABLE student_documents ADD COLUMN checksum VARCHAR(64);
ALTER TABLE student_documents ADD COLUMN original_file_path TEXT;

-- Unique constraint and index for StudentDocument
CREATE UNIQUE INDEX idx_student_documents_unique_checksum 
  ON student_documents(student_id, checksum) 
  WHERE checksum IS NOT NULL;
  
CREATE INDEX idx_student_documents_checksum ON student_documents(checksum);

-- Comment for documentation
COMMENT ON COLUMN persons.cedula IS 'Colombian national ID number';
COMMENT ON COLUMN persons.csv_enriched IS 'Indicates if person data was enriched from CSV files';
COMMENT ON COLUMN students.data_source IS 'Source of student data: directory+csv, csv_only, directory_only';
COMMENT ON COLUMN leads.program_type IS 'Type of program lead is interested in (Au Pair, Camp, etc.)';
COMMENT ON COLUMN student_documents.checksum IS 'SHA256 checksum for document deduplication';
```

---

## 📋 Phase 2: Source of Truth & Idempotency System

### 2.1 Deduplication Strategy

#### Person Deduplication Priority

```python
# Priority 1: Cedula (most unique - Colombian ID)
if cedula:
    person = find_person_by_cedula(cedula)
    
# Priority 2: Email
elif email:
    person = find_person_by_email(email)
    
# Priority 3: Full Name + Birth Date
elif full_name and birth_date:
    person = find_person_by_name_and_birthdate(full_name, birth_date)
    
# Priority 4: Full Name + Phone
elif full_name and phone:
    person = find_person_by_name_and_phone(full_name, phone)
    
# Otherwise: Create new person
else:
    person = create_person(data)
```

#### Student Deduplication Priority

```python
# Priority 1: Student Number
if student_number:
    student = find_student_by_number(student_number)
    
# Priority 2: Person ID
elif person_id:
    student = find_student_by_person_id(person_id)
    
# Otherwise: Create new student
else:
    student = create_student(person_id, data)
```

#### Lead Deduplication Priority

```python
# Priority 1: Person ID + Service ID + Event ID
if person_id and service_id and event_id:
    lead = find_lead_by_combination(person_id, service_id, event_id)
    
# Priority 2: Person ID + Program Type
elif person_id and program_type:
    lead = find_lead_by_person_and_program(person_id, program_type)
    
# Priority 3: Person ID only (update existing lead)
elif person_id:
    lead = find_latest_lead_by_person(person_id)
    
# Otherwise: Create new lead
else:
    lead = create_lead(person_id, data)
```

#### Document Deduplication Priority

```python
# Priority 1: Student ID + Checksum
if student_id and checksum:
    document = find_document_by_checksum(student_id, checksum)
    if document:
        return document  # Skip upload (duplicate)
        
# Priority 2: Student ID + Object Key
elif student_id and object_key:
    document = find_document_by_object_key(student_id, object_key)
    if document:
        return document  # Skip upload (duplicate)
        
# Otherwise: Create new document
else:
    document = create_document(student_id, data)
```

### 2.2 Accumulative Data Strategy

#### Field Update Rules

```python
def merge_person_data(existing: Person, new_data: dict) -> Person:
    """
    Merge new CSV data into existing Person without overwriting.
    Rule: Only update NULL fields or append to arrays.
    """
    # Update NULL fields only
    if not existing.address and new_data.get('address'):
        existing.address = new_data['address']
        
    if not existing.cedula and new_data.get('cedula'):
        existing.cedula = new_data['cedula']
        
    if not existing.birthDate and new_data.get('birth_date'):
        existing.birthDate = new_data['birth_date']
        
    if not existing.country and new_data.get('country'):
        existing.country = new_data['country']
    
    # Mark as CSV enriched
    if new_data.get('from_csv'):
        existing.csvEnriched = True
        existing.dataSource = 'CSV' if not existing.dataSource else f"{existing.dataSource},CSV"
    
    # Always update updatedAt
    existing.updatedAt = datetime.now()
    
    return existing
```

#### Conflict Resolution Rules

| Field | Existing Value | New Value | Resolution |
|-------|----------------|-----------|------------|
| `email` | `old@email.com` | `new@email.com` | **Keep existing** (email is unique ID) |
| `phone` | `+57 123` | `+57 456` | **Keep existing** OR append to notes |
| `address` | NULL | `"Bogotá"` | **Update** |
| `cedula` | NULL | `"12345678"` | **Update** |
| `birthDate` | `1990-01-01` | `1990-02-02` | **Keep existing** (unlikely to change) |
| `fullName` | `"JOHN DOE"` | `"John Doe"` | **Keep existing** (normalized) |

---

## 📋 Phase 3: Integration Pipeline Implementation

### 3.1 New Integration Module

**File**: `/packages/tools/api/python/integration_to_ice_bot.py`

```python
#!/usr/bin/env python3
"""
V3 Staging to ICE-Visa-Rescheduler-Bot Integration
Transfers staging data to production database with deduplication
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class StagingToProduction:
    """
    Migrates data from staging_* tables to production ICE bot tables.
    Implements source-of-truth deduplication and accumulative updates.
    """
    
    def __init__(self, staging_db_url: str, production_db_url: str):
        self.staging_conn = psycopg2.connect(staging_db_url, cursor_factory=RealDictCursor)
        self.prod_conn = psycopg2.connect(production_db_url, cursor_factory=RealDictCursor)
        
        self.stats = {
            'persons_created': 0,
            'persons_updated': 0,
            'students_created': 0,
            'students_updated': 0,
            'leads_created': 0,
            'leads_updated': 0,
            'documents_created': 0,
            'documents_skipped': 0,
        }
    
    def find_or_create_person(self, staging_student: dict) -> Tuple[str, bool]:
        """
        Find existing person or create new one using deduplication priority.
        Returns: (person_id, created_new)
        """
        with self.prod_conn.cursor() as cur:
            # Priority 1: Cedula
            if staging_student.get('cedula'):
                cur.execute(
                    "SELECT id FROM persons WHERE cedula = %s",
                    (staging_student['cedula'],)
                )
                result = cur.fetchone()
                if result:
                    return (result['id'], False)
            
            # Priority 2: Email
            if staging_student.get('email'):
                cur.execute(
                    "SELECT id FROM persons WHERE email = %s",
                    (staging_student['email'],)
                )
                result = cur.fetchone()
                if result:
                    # Update existing person with new data
                    self._update_person(result['id'], staging_student)
                    return (result['id'], False)
            
            # Priority 3: Name + Birth Date
            if staging_student.get('birth_date'):
                cur.execute(
                    "SELECT id FROM persons WHERE full_name = %s AND birth_date = %s",
                    (staging_student['full_name'], staging_student['birth_date'])
                )
                result = cur.fetchone()
                if result:
                    self._update_person(result['id'], staging_student)
                    return (result['id'], False)
            
            # Priority 4: Name + Phone
            if staging_student.get('phone'):
                cur.execute(
                    "SELECT id FROM persons WHERE full_name = %s AND phone = %s",
                    (staging_student['full_name'], staging_student['phone'])
                )
                result = cur.fetchone()
                if result:
                    self._update_person(result['id'], staging_student)
                    return (result['id'], False)
            
            # Create new person
            person_id = self._create_person(staging_student)
            return (person_id, True)
    
    def _create_person(self, data: dict) -> str:
        """Create new person record."""
        with self.prod_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO persons (
                    full_name, email, phone, address, cedula, birth_date,
                    city, country, data_source, original_name, csv_enriched
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data['full_name'],
                data.get('email'),
                data.get('phone'),
                data.get('address'),
                data.get('cedula'),
                data.get('birth_date'),
                data.get('city'),
                data.get('country'),
                'CSV',
                data.get('original_name'),
                True
            ))
            person_id = cur.fetchone()['id']
            self.prod_conn.commit()
            self.stats['persons_created'] += 1
            return person_id
    
    def _update_person(self, person_id: str, new_data: dict):
        """Update existing person with non-NULL fields from CSV."""
        with self.prod_conn.cursor() as cur:
            # Build dynamic UPDATE query for NULL fields only
            updates = []
            params = []
            
            if new_data.get('address'):
                updates.append("address = COALESCE(address, %s)")
                params.append(new_data['address'])
            
            if new_data.get('cedula'):
                updates.append("cedula = COALESCE(cedula, %s)")
                params.append(new_data['cedula'])
            
            if new_data.get('birth_date'):
                updates.append("birth_date = COALESCE(birth_date, %s)")
                params.append(new_data['birth_date'])
            
            if new_data.get('country'):
                updates.append("country = COALESCE(country, %s)")
                params.append(new_data['country'])
            
            # Always mark as CSV enriched
            updates.append("csv_enriched = TRUE")
            updates.append("updated_at = NOW()")
            
            if updates:
                params.append(person_id)
                query = f"UPDATE persons SET {', '.join(updates)} WHERE id = %s"
                cur.execute(query, params)
                self.prod_conn.commit()
                self.stats['persons_updated'] += 1
    
    def migrate_students(self):
        """Migrate all staging_student to production students table."""
        logger.info("Migrating students...")
        
        with self.staging_conn.cursor() as staging_cur:
            staging_cur.execute("""
                SELECT * FROM staging_student
                ORDER BY created_at
            """)
            
            for student in staging_cur:
                try:
                    # Find or create person
                    person_id, created = self.find_or_create_person(student)
                    
                    # Check if student already exists
                    with self.prod_conn.cursor() as prod_cur:
                        prod_cur.execute(
                            "SELECT id FROM students WHERE person_id = %s",
                            (person_id,)
                        )
                        existing_student = prod_cur.fetchone()
                        
                        if existing_student:
                            # Update existing student
                            prod_cur.execute("""
                                UPDATE students
                                SET program = COALESCE(program, %s),
                                    data_source = %s,
                                    csv_enriched = TRUE,
                                    updated_at = NOW()
                                WHERE id = %s
                            """, (
                                student.get('program'),
                                student.get('source', 'CSV'),
                                existing_student['id']
                            ))
                            self.stats['students_updated'] += 1
                        else:
                            # Create new student
                            prod_cur.execute("""
                                INSERT INTO students (
                                    person_id, program, data_source, csv_enriched, status
                                )
                                VALUES (%s, %s, %s, TRUE, 'ACTIVE')
                            """, (
                                person_id,
                                student.get('program'),
                                student.get('source', 'CSV')
                            ))
                            self.stats['students_created'] += 1
                        
                        self.prod_conn.commit()
                        
                except Exception as e:
                    logger.error(f"Error migrating student {student['full_name']}: {e}")
                    self.prod_conn.rollback()
                    continue
        
        logger.info(f"Students migrated: {self.stats['students_created']} created, {self.stats['students_updated']} updated")
    
    def migrate_leads(self):
        """Migrate all staging_lead to production leads table."""
        logger.info("Migrating leads...")
        
        with self.staging_conn.cursor() as staging_cur:
            staging_cur.execute("""
                SELECT * FROM staging_lead
                ORDER BY created_at
            """)
            
            for lead in staging_cur:
                try:
                    # Find or create person
                    person_data = {
                        'full_name': lead['full_name'],
                        'email': lead.get('email'),
                        'phone': lead.get('phone'),
                        'address': lead.get('address'),
                        'cedula': lead.get('cedula'),
                        'birth_date': lead.get('birth_date'),
                        'city': lead.get('city'),
                        'country': lead.get('country'),
                    }
                    person_id, created = self.find_or_create_person(person_data)
                    
                    # Check if lead already exists
                    with self.prod_conn.cursor() as prod_cur:
                        prod_cur.execute("""
                            SELECT id FROM leads
                            WHERE person_id = %s
                            AND program_type = %s
                            AND source_file = %s
                        """, (
                            person_id,
                            lead.get('interest_program'),
                            lead.get('source_file')
                        ))
                        existing_lead = prod_cur.fetchone()
                        
                        if existing_lead:
                            # Update existing lead
                            prod_cur.execute("""
                                UPDATE leads
                                SET lead_status = COALESCE(%s, lead_status),
                                    notes = COALESCE(%s, notes),
                                    updated_at = NOW()
                                WHERE id = %s
                            """, (
                                lead.get('status'),
                                lead.get('notes'),
                                existing_lead['id']
                            ))
                            self.stats['leads_updated'] += 1
                        else:
                            # Create new lead
                            prod_cur.execute("""
                                INSERT INTO leads (
                                    person_id, program_type, lead_status, lead_date,
                                    source_file, source_sheet, notes
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                person_id,
                                lead.get('interest_program'),
                                lead.get('status', 'NEW'),
                                lead.get('created_at'),
                                lead.get('source_file'),
                                lead.get('source_sheet'),
                                lead.get('notes')
                            ))
                            self.stats['leads_created'] += 1
                        
                        self.prod_conn.commit()
                        
                except Exception as e:
                    logger.error(f"Error migrating lead {lead['full_name']}: {e}")
                    self.prod_conn.rollback()
                    continue
        
        logger.info(f"Leads migrated: {self.stats['leads_created']} created, {self.stats['leads_updated']} updated")
    
    def run_full_migration(self):
        """Execute full staging to production migration."""
        logger.info("Starting full migration...")
        
        start_time = datetime.now()
        
        # Order matters: persons → students → leads → documents
        self.migrate_students()  # Creates persons automatically
        self.migrate_leads()     # Creates persons automatically
        # self.migrate_documents()  # TODO: Phase 4
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("="*80)
        logger.info("MIGRATION COMPLETE")
        logger.info(f"Execution time: {elapsed:.2f}s")
        logger.info(f"Persons: {self.stats['persons_created']} created, {self.stats['persons_updated']} updated")
        logger.info(f"Students: {self.stats['students_created']} created, {self.stats['students_updated']} updated")
        logger.info(f"Leads: {self.stats['leads_created']} created, {self.stats['leads_updated']} updated")
        logger.info("="*80)


def main():
    staging_db = os.getenv('STAGING_DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
    production_db = os.getenv('DATABASE_URL')  # ICE bot database
    
    if not production_db:
        raise ValueError("DATABASE_URL not set (ICE-Visa-Rescheduler-Bot database)")
    
    migrator = StagingToProduction(staging_db, production_db)
    migrator.run_full_migration()

if __name__ == '__main__':
    main()
```

### 3.2 Frontend Integration Button

**File**: `/packages/tools/app/(tools)/ice-database/page.tsx`

Add new button alongside existing actions:

```tsx
<button
  onClick={migrateToProduction}
  disabled={isMigrating || !summary || summary.total_students === 0}
  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
>
  {isMigrating ? (
    <>
      <LoadingSpinner size="sm" />
      <span>Migrating to Production...</span>
    </>
  ) : (
    <>
      <Database size={20} />
      <span>Migrate to Production DB</span>
    </>
  )}
</button>
```

---

## 📋 Phase 4: Testing & Validation

### 4.1 Test Scenarios

#### Test 1: New Person Creation
```python
# Scenario: Person doesn't exist in production
staging_data = {
    'full_name': 'MARIA RODRIGUEZ',
    'email': 'maria@email.com',
    'cedula': '12345678',
    'birth_date': '1995-03-15'
}

# Expected:
# - New person created in production
# - All fields populated
# - csv_enriched = TRUE
```

#### Test 2: Existing Person Update
```python
# Scenario: Person exists with partial data
existing_person = {
    'full_name': 'MARIA RODRIGUEZ',
    'email': 'maria@email.com',
    'cedula': None,  # Missing
    'address': None  # Missing
}

staging_data = {
    'full_name': 'MARIA RODRIGUEZ',
    'email': 'maria@email.com',
    'cedula': '12345678',  # New data
    'address': 'Bogotá'   # New data
}

# Expected:
# - Existing person updated
# - cedula and address populated
# - email unchanged (existing value preserved)
# - csv_enriched = TRUE
```

#### Test 3: Duplicate Prevention
```python
# Scenario: Same person appears twice in CSV
csv_row_1 = {'full_name': 'JOHN DOE', 'email': 'john@email.com'}
csv_row_2 = {'full_name': 'JOHN DOE', 'email': 'john@email.com'}

# Expected:
# - Only 1 person created
# - Second row updates/skips
```

---

## 📋 Phase 5: Deployment Checklist

### 5.1 Pre-Deployment

- [ ] **Backup Production Database**
  ```bash
  pg_dump -h localhost -U postgres -d ice_visa_db > backup_$(date +%Y%m%d).sql
  ```

- [ ] **Run Schema Migration**
  ```bash
  cd packages/ICE-Visa-Rescheduler-Bot
  npx prisma migrate dev --name add_staging_fields
  npx prisma generate
  ```

- [ ] **Test Migration on Sample Data**
  ```bash
  # Use 10 staging records for testing
  python integration_to_ice_bot.py --dry-run --limit 10
  ```

- [ ] **Verify Deduplication Logic**
  ```bash
  # Run twice, ensure no duplicates created
  python integration_to_ice_bot.py --dry-run
  python integration_to_ice_bot.py --dry-run
  # Check: persons_created should be 0 on second run
  ```

### 5.2 Deployment Steps

1. **Stop V3 Staging Dashboard** (prevent new data during migration)
   ```bash
   cd packages/tools
   # Stop frontend/backend
   ```

2. **Run Full Migration**
   ```bash
   python integration_to_ice_bot.py
   ```

3. **Verify Results**
   ```sql
   -- Check person counts
   SELECT data_source, COUNT(*) FROM persons GROUP BY data_source;
   
   -- Check CSV enrichment
   SELECT csv_enriched, COUNT(*) FROM persons GROUP BY csv_enriched;
   
   -- Check leads
   SELECT program_type, COUNT(*) FROM leads GROUP BY program_type;
   ```

4. **Update V3 Dashboard** to point to production database
   ```bash
   # In packages/tools/api/python/.env
   DATABASE_URL=<ICE-bot-database-url>
   ```

5. **Restart Services**
   ```bash
   # Restart ICE bot
   cd packages/ICE-Visa-Rescheduler-Bot
   npm run dev
   
   # Restart V3 Dashboard
   cd packages/tools
   npm run dev
   ```

### 5.3 Post-Deployment Validation

- [ ] **Verify Data Integrity**
  ```sql
  -- No orphaned students
  SELECT COUNT(*) FROM students s
  LEFT JOIN persons p ON s.person_id = p.id
  WHERE p.id IS NULL;
  -- Expected: 0
  
  -- No orphaned leads
  SELECT COUNT(*) FROM leads l
  LEFT JOIN persons p ON l.person_id = p.id
  WHERE p.id IS NULL;
  -- Expected: 0
  ```

- [ ] **Test Accumulative Ingestion**
  ```bash
  # Add new CSV files to staging
  # Run V3 Ingestion
  # Run Migration
  # Verify: No duplicates, only new records added
  ```

- [ ] **Monitor Performance**
  ```sql
  -- Check index usage
  SELECT schemaname, tablename, indexname, idx_scan
  FROM pg_stat_user_indexes
  WHERE tablename IN ('persons', 'students', 'leads', 'student_documents')
  ORDER BY idx_scan DESC;
  ```

---

## 📋 Phase 6: Document Migration to MinIO

### 6.1 Document Migration Strategy

```python
def migrate_documents():
    """
    Migrate staging_document to production student_documents with MinIO upload.
    """
    # Step 1: Find student by person match
    # Step 2: Check if document exists (checksum)
    # Step 3: If not exists, upload to MinIO
    # Step 4: Create StudentDocument record
    pass
```

**TODO**: Implement in Phase 6 after MinIO server setup

---

## 🎯 Success Metrics

### Integration Health Indicators

| Metric | Target | Actual |
|--------|--------|---------|
| Duplicate Persons Created | 0% | TBD |
| Data Loss (staging → prod) | 0% | TBD |
| CSV Enrichment Rate | >80% | TBD |
| Lead Capture Rate | >92% | 74% → 92%+ |
| Migration Time (1000 records) | <60s | TBD |
| Failed Migrations | <1% | TBD |

---

## 📝 Next Steps

### Immediate Actions

1. **Review & Approve Schema Changes**
   - Review Prisma schema additions
   - Test migration on dev database
   - Get stakeholder approval

2. **Implement Integration Module**
   - Create `integration_to_ice_bot.py`
   - Implement deduplication logic
   - Add dry-run mode for testing

3. **Test on Sample Data**
   - Use 50-100 staging records
   - Verify deduplication works
   - Check data integrity

4. **Deploy to Production**
   - Follow deployment checklist
   - Monitor for issues
   - Verify accumulative ingestion

### Future Enhancements

- [ ] **Real-time Sync**: WebSocket updates when new data ingested
- [ ] **Conflict Resolution UI**: Manual review for ambiguous matches
- [ ] **Data Lineage Tracking**: Full audit trail of data sources
- [ ] **Advanced Deduplication**: ML-based fuzzy matching
- [ ] **Automated Scheduling**: Cron job for daily migration

---

**Status**: ✅ Plan Complete - Ready for Implementation  
**Estimated Time**: 8-12 hours (including testing)  
**Risk Level**: Medium (requires careful testing)  
**Dependencies**: ICE-Visa-Rescheduler-Bot database access

---

**Last Updated**: November 5, 2025  
**Version**: 1.0  
**Author**: APEX AI Solutions × ICE Colombia Development Team
