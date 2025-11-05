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
                SELECT * FROM staging_student
                ORDER BY created_at
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
                        'city': student.get('city'),
                        'country': student.get('country'),
                        'original_name': student.get('original_name'),
                    }
                    person_id, created = self.find_or_create_person(person_data)
                    
                    if not person_id:
                        logger.warning(f"Could not find/create person for student: {student['full_name']}")
                        self.stats['students_skipped'] += 1
                        continue
                    
                    # Check if student already exists
                    with self.prod_conn.cursor() as prod_cur:
                        prod_cur.execute(
                            "SELECT id FROM students WHERE person_id = %s",
                            (person_id,)
                        )
                        existing_student = prod_cur.fetchone()
                        
                        if existing_student:
                            # Update existing student
                            if not self.dry_run:
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
                                self.prod_conn.commit()
                            self.stats['students_updated'] += 1
                            logger.debug(f"Updated student for person: {student['full_name']}")
                        else:
                            # Create new student
                            if not self.dry_run:
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
                    
                    if not person_id:
                        logger.warning(f"Could not find/create person for lead: {lead['full_name']}")
                        self.stats['leads_skipped'] += 1
                        continue
                    
                    # Check if lead already exists
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
                            if not self.dry_run:
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
                            if not self.dry_run:
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
            # self.migrate_documents()  # TODO: Phase 6 (MinIO integration)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info("="*80)
            logger.info("✅ MIGRATION COMPLETE")
            logger.info("="*80)
            logger.info(f"Execution time: {elapsed:.2f}s")
            logger.info(f"Persons: {self.stats['persons_created']} created, {self.stats['persons_updated']} updated")
            logger.info(f"Students: {self.stats['students_created']} created, {self.stats['students_updated']} updated, {self.stats['students_skipped']} skipped")
            logger.info(f"Leads: {self.stats['leads_created']} created, {self.stats['leads_updated']} updated, {self.stats['leads_skipped']} skipped")
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
