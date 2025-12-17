#!/usr/bin/env python3
"""
V3 Staging to ICE-Visa-Rescheduler-Bot Integration
Transfers staging data to production database with deduplication
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StagingToProduction:
    """
    Migrates data from staging_* tables to production ICE bot tables.
    Implements source-of-truth deduplication and accumulative updates.
    """
    
    def __init__(self, staging_db_url: str, production_db_url: str, dry_run: bool = False):
        self.staging_conn = psycopg2.connect(staging_db_url, cursor_factory=RealDictCursor)
        self.prod_conn = psycopg2.connect(production_db_url, cursor_factory=RealDictCursor)
        self.dry_run = dry_run
        
        self.stats = {
            'persons_created': 0,
            'persons_updated': 0,
            'persons_skipped': 0,
            'students_created': 0,
            'students_updated': 0,
            'students_skipped': 0,
            'leads_created': 0,
            'leads_updated': 0,
            'leads_skipped': 0,
            'documents_created': 0,
            'documents_skipped': 0,
        }
    
    def find_or_create_person(self, staging_data: dict) -> Tuple[Optional[str], bool]:
        """
        Find existing person or create new one using deduplication priority.
        Returns: (person_id, created_new)
        """
        with self.prod_conn.cursor() as cur:
            # Priority 1: Cedula (Colombian ID - most unique)
            if staging_data.get('cedula'):
                cur.execute(
                    "SELECT id FROM persons WHERE cedula = %s",
                    (staging_data['cedula'],)
                )
                result = cur.fetchone()
                if result:
                    logger.debug(f"Found person by cedula: {staging_data['cedula']}")
                    self._update_person(result['id'], staging_data)
                    return (result['id'], False)
            
            # Priority 2: Email
            if staging_data.get('email'):
                cur.execute(
                    "SELECT id FROM persons WHERE email = %s",
                    (staging_data['email'],)
                )
                result = cur.fetchone()
                if result:
                    logger.debug(f"Found person by email: {staging_data['email']}")
                    self._update_person(result['id'], staging_data)
                    return (result['id'], False)
            
            # Priority 3: Name + Birth Date
            if staging_data.get('birth_date'):
                cur.execute(
                    "SELECT id FROM persons WHERE full_name = %s AND birth_date = %s",
                    (staging_data['full_name'], staging_data['birth_date'])
                )
                result = cur.fetchone()
                if result:
                    logger.debug(f"Found person by name+birthdate: {staging_data['full_name']}")
                    self._update_person(result['id'], staging_data)
                    return (result['id'], False)
            
            # Priority 4: Name + Phone
            if staging_data.get('phone'):
                cur.execute(
                    "SELECT id FROM persons WHERE full_name = %s AND phone = %s",
                    (staging_data['full_name'], staging_data['phone'])
                )
                result = cur.fetchone()
                if result:
                    logger.debug(f"Found person by name+phone: {staging_data['full_name']}")
                    self._update_person(result['id'], staging_data)
                    return (result['id'], False)
            
            # Priority 5: Fuzzy name match (for directory-extracted students)
            # Only use this if no contact info is available
            if not staging_data.get('email') and not staging_data.get('phone') and not staging_data.get('cedula'):
                # Try to find by partial name match (remove extra suffixes like city names)
                search_name = staging_data['full_name'].strip()
                cur.execute(
                    "SELECT id, full_name FROM persons WHERE full_name ILIKE %s OR full_name ILIKE %s LIMIT 1",
                    (search_name, f"{search_name}%")
                )
                result = cur.fetchone()
                if result:
                    logger.debug(f"Found person by fuzzy name match: {search_name} → {result['full_name']}")
                    self._update_person(result['id'], staging_data)
                    return (result['id'], False)
            
            # Create new person
            person_id = self._create_person(staging_data)
            return (person_id, True)
    
    def _create_person(self, data: dict) -> str:
        """Create new person record."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create person: {data['full_name']}")
            self.stats['persons_created'] += 1
            return "dry-run-person-id"
        
        with self.prod_conn.cursor() as cur:
            # Generate placeholder email if missing (for directory-extracted students)
            # Format: phone-based-{phone}@noemail.local or name-based-{normalized_name}@noemail.local
            email = data.get('email')
            if not email:
                if data.get('phone'):
                    # Create pseudo-email from phone number
                    email = f"phone-{data['phone'].replace(' ', '').replace('+', '')}@noemail.local"
                else:
                    # Create pseudo-email from normalized name
                    # Remove spaces, convert to lowercase, take first 50 chars
                    import re
                    normalized = re.sub(r'[^a-z0-9]', '', data['full_name'].lower())[:50]
                    email = f"name-{normalized}@noemail.local"
            
            cur.execute("""
                INSERT INTO persons (
                    id, full_name, email, phone, address, cedula, birth_date,
                    city, country, data_source, original_name, csv_enriched,
                    created_at, updated_at
                )
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (
                data['full_name'],
                email,  # Use actual email or generated placeholder
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
            logger.info(f"Created person: {data['full_name']} (ID: {person_id})")
            return person_id
    
    def _update_person(self, person_id: str, new_data: dict):
        """Update existing person with non-NULL fields from CSV."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update person ID: {person_id}")
            self.stats['persons_updated'] += 1
            return
        
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
            
            if new_data.get('city'):
                updates.append("city = COALESCE(city, %s)")
                params.append(new_data['city'])
            
            # Always mark as CSV enriched
            updates.append("csv_enriched = TRUE")
            updates.append("updated_at = NOW()")
            
            if updates:
                params.append(person_id)
                query = f"UPDATE persons SET {', '.join(updates)} WHERE id = %s"
                cur.execute(query, params)
                self.prod_conn.commit()
                self.stats['persons_updated'] += 1
                logger.debug(f"Updated person ID: {person_id}")
    
    def migrate_students(self):
        """Migrate all staging_student to production students table."""
        logger.info("="*80)
        logger.info("MIGRATING STUDENTS")
        logger.info("="*80)
        
        with self.staging_conn.cursor() as staging_cur:
            staging_cur.execute("""
                SELECT 
                    s.id as student_id,
                    s.program,
                    s.status,
                    s.created_at,
                    p.id as person_id,
                    p.full_name,
                    p.normalized_name,
                    p.email,
                    p.phone,
                    p.address,
                    p.id_number as cedula,
                    p.birth_date,
                    p.source,
                    p.directory_path,
                    p.csv_file
                FROM staging_student s
                JOIN staging_person p ON s.person_id = p.id
                ORDER BY s.created_at
            """)
            
            staging_students = staging_cur.fetchall()
            logger.info(f"Found {len(staging_students)} students in staging")
            
            for student in staging_students:
                try:
                    # Find or create person
                    person_data = {
                        'full_name': student['full_name'],
                        'email': student.get('email'),
                        'phone': student.get('phone'),
                        'address': student.get('address'),
                        'cedula': student.get('cedula'),
                        'birth_date': student.get('birth_date'),
                        'city': None,  # Not in staging_person
                        'country': None,  # Not in staging_person
                        'original_name': student.get('full_name'),  # Use full_name as original
                    }
                    person_id, created = self.find_or_create_person(person_data)
                    
                    if not person_id:
                        logger.warning(f"Could not find/create person for student: {student['full_name']}")
                        self.stats['students_skipped'] += 1
                        continue
                    
                    # Check if student already exists (skip in dry-run)
                    if self.dry_run:
                        # In dry-run, assume it's a new student
                        self.stats['students_created'] += 1
                        logger.info(f"[DRY RUN] Would create student for person: {student['full_name']}")
                    else:
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
                                    'CSV',  # Use 'CSV' as data source
                                    existing_student['id']
                                ))
                                self.prod_conn.commit()
                                self.stats['students_updated'] += 1
                                logger.debug(f"Updated student for person: {student['full_name']}")
                            else:
                                # Create new student
                                prod_cur.execute("""
                                    INSERT INTO students (
                                        id, person_id, program, data_source, csv_enriched, status,
                                        created_at, updated_at
                                    )
                                    VALUES (gen_random_uuid(), %s, %s, %s, TRUE, 'ACTIVE', NOW(), NOW())
                                """, (
                                    person_id,
                                    student.get('program'),
                                    'CSV'  # Use 'CSV' as data source
                                ))
                                self.prod_conn.commit()
                                self.stats['students_created'] += 1
                                logger.info(f"Created student for person: {student['full_name']}")
                        
                except Exception as e:
                    logger.error(f"Error migrating student {student['full_name']}: {e}")
                    if not self.dry_run:
                        self.prod_conn.rollback()
                    self.stats['students_skipped'] += 1
                    continue
        
        logger.info(f"Students: {self.stats['students_created']} created, {self.stats['students_updated']} updated, {self.stats['students_skipped']} skipped")
    
    def migrate_leads(self):
        """Migrate all staging_lead to production leads table."""
        logger.info("="*80)
        logger.info("MIGRATING LEADS")
        logger.info("="*80)
        
        with self.staging_conn.cursor() as staging_cur:
            staging_cur.execute("""
                SELECT * FROM staging_lead
                ORDER BY created_at
            """)
            
            staging_leads = staging_cur.fetchall()
            logger.info(f"Found {len(staging_leads)} leads in staging")
            
            for lead in staging_leads:
                try:
                    # Find or create person (staging_lead has limited fields)
                    person_data = {
                        'full_name': lead['full_name'],
                        'email': lead.get('email'),
                        'phone': lead.get('phone'),
                        'address': None,  # Not in staging_lead
                        'cedula': None,  # Not in staging_lead
                        'birth_date': None,  # Not in staging_lead
                        'city': lead.get('city'),
                        'country': lead.get('country'),
                        'original_name': lead.get('full_name'),
                    }
                    person_id, created = self.find_or_create_person(person_data)
                    
                    if not person_id:
                        logger.warning(f"Could not find/create person for lead: {lead['full_name']}")
                        self.stats['leads_skipped'] += 1
                        continue
                    
                    # Check if lead already exists (skip in dry-run)
                    if self.dry_run:
                        # In dry-run, assume it's a new lead
                        self.stats['leads_created'] += 1
                        logger.info(f"[DRY RUN] Would create lead for person: {lead['full_name']}")
                    else:
                        with self.prod_conn.cursor() as prod_cur:
                            prod_cur.execute("""
                                SELECT id FROM leads
                                WHERE person_id = %s
                                AND (program_type = %s OR program_type IS NULL)
                                AND (source_file = %s OR source_file IS NULL)
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
                                    SET program_type = COALESCE(%s, program_type),
                                        lead_status = COALESCE(%s, lead_status),
                                        source_file = COALESCE(%s, source_file),
                                        source_sheet = COALESCE(%s, source_sheet),
                                        notes = COALESCE(%s, notes),
                                        updated_at = NOW()
                                    WHERE id = %s
                                """, (
                                    lead.get('interest_program'),
                                    lead.get('status'),
                                    lead.get('source_file'),
                                    lead.get('source_sheet'),
                                    lead.get('notes'),
                                    existing_lead['id']
                                ))
                                self.prod_conn.commit()
                                self.stats['leads_updated'] += 1
                                logger.debug(f"Updated lead for person: {lead['full_name']}")
                            else:
                                # Create new lead
                                prod_cur.execute("""
                                    INSERT INTO leads (
                                        id, person_id, program_type, lead_status, lead_date,
                                        source_file, source_sheet, notes, created_at, updated_at
                                    )
                                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                                """, (
                                    person_id,
                                    lead.get('interest_program'),
                                    lead.get('status', 'NEW'),
                                    lead.get('created_at'),
                                    lead.get('source_file'),
                                    lead.get('source_sheet'),
                                    lead.get('notes')
                                ))
                                self.prod_conn.commit()
                                self.stats['leads_created'] += 1
                                logger.info(f"Created lead for person: {lead['full_name']}")
                        
                except Exception as e:
                    logger.error(f"Error migrating lead {lead['full_name']}: {e}")
                    if not self.dry_run:
                        self.prod_conn.rollback()
                    self.stats['leads_skipped'] += 1
                    continue
        
        logger.info(f"Leads: {self.stats['leads_created']} created, {self.stats['leads_updated']} updated, {self.stats['leads_skipped']} skipped")
    
    def migrate_documents(self):
        """Migrate staging_document to production student_documents table."""
        logger.info("="*80)
        logger.info("MIGRATING DOCUMENTS")
        logger.info("="*80)
        
        with self.staging_conn.cursor() as staging_cur:
            # Get documents with student info for person matching
            staging_cur.execute("""
                SELECT 
                    d.id as doc_id,
                    d.student_id as staging_student_id,
                    d.original_file_name,
                    d.normalized_file_name,
                    d.original_file_path,
                    d.staging_file_path,
                    d.file_size,
                    d.mime_type,
                    d.document_type,
                    d.checksum,
                    d.created_at,
                    s.program,
                    p.full_name,
                    p.email,
                    p.phone,
                    p.id_number as cedula
                FROM staging_document d
                JOIN staging_student s ON d.student_id = s.id
                JOIN staging_person p ON s.person_id = p.id
                ORDER BY d.created_at
            """)
            
            staging_documents = staging_cur.fetchall()
            logger.info(f"Found {len(staging_documents)} documents in staging")
            
            for doc in staging_documents:
                try:
                    # Find the production student for this document
                    with self.prod_conn.cursor() as prod_cur:
                        # Try to find student by person matching (use same deduplication logic)
                        student_id = None
                        
                        # Priority 1: Cedula
                        if doc.get('cedula'):
                            prod_cur.execute("""
                                SELECT s.id FROM students s
                                JOIN persons p ON s.person_id = p.id
                                WHERE p.cedula = %s
                            """, (doc['cedula'],))
                            result = prod_cur.fetchone()
                            if result:
                                student_id = result['id']
                        
                        # Priority 2: Email
                        if not student_id and doc.get('email'):
                            prod_cur.execute("""
                                SELECT s.id FROM students s
                                JOIN persons p ON s.person_id = p.id
                                WHERE p.email = %s
                            """, (doc['email'],))
                            result = prod_cur.fetchone()
                            if result:
                                student_id = result['id']
                        
                        # Priority 3: Phone
                        if not student_id and doc.get('phone'):
                            prod_cur.execute("""
                                SELECT s.id FROM students s
                                JOIN persons p ON s.person_id = p.id
                                WHERE p.phone = %s
                            """, (doc['phone'],))
                            result = prod_cur.fetchone()
                            if result:
                                student_id = result['id']
                        
                        # Priority 4: Exact name match (for directory-extracted students)
                        if not student_id:
                            prod_cur.execute("""
                                SELECT s.id FROM students s
                                JOIN persons p ON s.person_id = p.id
                                WHERE p.full_name = %s
                            """, (doc['full_name'],))
                            result = prod_cur.fetchone()
                            if result:
                                student_id = result['id']
                        
                        # Priority 5: Fuzzy name match (handle city suffixes)
                        if not student_id:
                            prod_cur.execute("""
                                SELECT s.id FROM students s
                                JOIN persons p ON s.person_id = p.id
                                WHERE p.full_name ILIKE %s
                                LIMIT 1
                            """, (f"{doc['full_name']}%",))
                            result = prod_cur.fetchone()
                            if result:
                                student_id = result['id']
                        
                        if not student_id:
                            logger.warning(f"Could not find student for document: {doc['original_file_name']} (person: {doc['full_name']})")
                            self.stats['documents_skipped'] += 1
                            continue
                        
                        # Check if document already exists by checksum
                        prod_cur.execute(
                            "SELECT id FROM student_documents WHERE checksum = %s",
                            (doc['checksum'],)
                        )
                        existing_doc = prod_cur.fetchone()
                        
                        if existing_doc:
                            logger.debug(f"Document already exists (checksum match): {doc['original_file_name']}")
                            self.stats['documents_skipped'] += 1
                        else:
                            if self.dry_run:
                                self.stats['documents_created'] += 1
                                logger.info(f"[DRY RUN] Would create document: {doc['original_file_name']}")
                            else:
                                # Create MinIO object_key from staging_file_path or normalized_file_name
                                # Format: students/{student_id}/{normalized_file_name}
                                object_key = f"students/{student_id}/{doc['normalized_file_name']}"
                                
                                prod_cur.execute("""
                                    INSERT INTO student_documents (
                                        id, student_id, document_type, file_name, object_key,
                                        bucket, file_size, mime_type, checksum, original_file_path,
                                        status, uploaded_at, created_at, updated_at
                                    )
                                    VALUES (
                                        gen_random_uuid(), %s, %s, %s, %s, 'apex-ice-docs',
                                        %s, %s, %s, %s, 'PENDING', %s, NOW(), NOW()
                                    )
                                """, (
                                    student_id,
                                    doc.get('document_type') or 'OTHER',
                                    doc['original_file_name'],
                                    object_key,
                                    doc.get('file_size'),
                                    doc.get('mime_type'),
                                    doc['checksum'],
                                    doc.get('original_file_path'),
                                    doc.get('created_at')
                                ))
                                self.prod_conn.commit()
                                self.stats['documents_created'] += 1
                                logger.info(f"Created document: {doc['original_file_name']} for student {student_id}")
                        
                except Exception as e:
                    logger.error(f"Error migrating document {doc.get('original_file_name', 'unknown')}: {e}")
                    if not self.dry_run:
                        self.prod_conn.rollback()
                    self.stats['documents_skipped'] += 1
                    continue
        
        logger.info(f"Documents: {self.stats['documents_created']} created, {self.stats['documents_skipped']} skipped")
    
    def run_full_migration(self):
        """Execute full staging to production migration."""
        logger.info("="*80)
        logger.info(f"🚀 V3 STAGING → PRODUCTION MIGRATION {'(DRY RUN)' if self.dry_run else ''}")
        logger.info("="*80)
        
        start_time = datetime.now()
        
        try:
            # Order matters: persons → students → leads → documents
            self.migrate_students()  # Creates persons automatically
            self.migrate_leads()     # Creates persons automatically
            self.migrate_documents()  # Migrates documents with MinIO object_key references
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info("="*80)
            logger.info("✅ MIGRATION COMPLETE")
            logger.info("="*80)
            logger.info(f"Execution time: {elapsed:.2f}s")
            logger.info(f"Persons: {self.stats['persons_created']} created, {self.stats['persons_updated']} updated")
            logger.info(f"Students: {self.stats['students_created']} created, {self.stats['students_updated']} updated, {self.stats['students_skipped']} skipped")
            logger.info(f"Leads: {self.stats['leads_created']} created, {self.stats['leads_updated']} updated, {self.stats['leads_skipped']} skipped")
            logger.info(f"Documents: {self.stats['documents_created']} created, {self.stats['documents_skipped']} skipped")
            logger.info("="*80)
            
            return {
                'success': True,
                'stats': self.stats,
                'execution_time': elapsed,
                'dry_run': self.dry_run
            }
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats,
                'dry_run': self.dry_run
            }
        finally:
            self.staging_conn.close()
            self.prod_conn.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate V3 staging data to production ICE bot database')
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    parser.add_argument('--staging-db', default=os.getenv('STAGING_DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project'))
    parser.add_argument('--production-db', default=os.getenv('DATABASE_URL'))
    
    args = parser.parse_args()
    
    if not args.production_db:
        logger.error("DATABASE_URL not set (ICE-Visa-Rescheduler-Bot database)")
        logger.error("Set it in environment or use --production-db flag")
        sys.exit(1)
    
    logger.info(f"Staging DB: {args.staging_db.split('@')[1] if '@' in args.staging_db else args.staging_db}")
    logger.info(f"Production DB: {args.production_db.split('@')[1] if '@' in args.production_db else args.production_db}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")
    
    migrator = StagingToProduction(args.staging_db, args.production_db, dry_run=args.dry_run)
    result = migrator.run_full_migration()
    
    sys.exit(0 if result['success'] else 1)

if __name__ == '__main__':
    main()
