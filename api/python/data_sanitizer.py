#!/usr/bin/env python3
"""
Data Sanitization Module
Filters out false positive "student" records that are actually:
- Program names, years, organizations, locations, administrative folders
"""

import os
import logging
import re
from typing import List, Dict, Any, Set
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class DataSanitizer:
    """
    Sanitizes staging data by removing false positive student records.
    """
    
    # Comprehensive blacklist of false positive patterns
    BLACKLIST = {
        # Years (numeric patterns)
        '2015', '2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026', '2027',
        
        # Organizations & Agencies (with number prefixes)
        'LA LIFE ADVENTURES', 'LALIFE ADVENTURES', 'L A LIFE ADVENTURES',
        '1. LA LIFE ADVENTURES', '1.LA LIFE ADVENTURES',
        'AAG ALLIANCE ABROAD GROUP', 'ALLIANCE ABROAD GROUP',
        '2.AAG ALLIANCE ABROAD GROUP', '2. AAG ALLIANCE ABROAD GROUP',
        'IEE INTERNATIONAL EDUCATIONAL EXCHANGE', 'INTERNATIONAL EDUCATIONAL EXCHANGE',
        '3. IEE INTERNATIONAL EDUCATIONAL EXCHANGE', '3.IEE INTERNATIONAL EDUCATIONAL EXCHANGE',
        
        # Programs (exact matches)
        'AU PAIR', 'AUPAIR',
        'WORK AND TRAVEL', 'WORKANDTRAVEL', 'WORK & TRAVEL',
        'CAMP COUNSELOR', 'CAMPCOUNSELOR',
        'INTERN & TRAINEE', 'INTERN AND TRAINEE', 'INTERNANDTRAINEE', 'INTERN&TRAINEE',
        'H2B', 'H-2B', 'H 2B',
        'WAT', 'W&T', 'W & T',
        
        # Countries & Locations
        'AUSTRALIA', 'CANADA', 'USA', 'IRLANDA', 'IRELAND', 'DUBAI',
        
        # Administrative/Generic Terms (with variations)
        'LISTA DE ESPERA', 'LISTADEESPERA',
        '5. LISTA DE ESPERA', '5.LISTA DE ESPERA',
        'CORREO DE BIENVENIDA', 'CORREO BIENVENIDA',
        'CURSO DE INGLES', 'CURSO INGLES',
        'FORMATOS CORREO BIENVENIDA WAT',
        'ESTUDIOS ICE', 'ESTUDIOSICE',
        'PREGUNTAS WORK AND TRAVEL', 'PREGUNTAS WORK AND TRAVEL 2024',
        'VIDEOS DE PANTALLA', 'VIDEOSDE PANTALLA',
        'OFICINA',
        'TODOS',
        'EB',
        
        # Document/File types
        'DOCS AU PAIR', 'DOCS AUPAIR', 'DOCSAUPAIR',
        'VISAS', 'VISA',
        
        # Program-specific admin terms
        'PPM', 'PPM 2023', 'PPM2023',
        'WAT 2020', 'WAT 2018', 'WAT ICE 2018', 'WATICE2018',
        'COTIZACIONES', 'QUOTATIONS',
        
        # Numbered entries (common false positives)
        '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
    }
    
    # Pattern-based filters (regex patterns)
    BLACKLIST_PATTERNS = [
        r'^\d{4}$',  # Four-digit years
        r'^\d{1,2}\.?\s*',  # Numbers with optional period (1., 2., etc.)
        r'^WAT\s*\d{4}$',  # WAT + year
        r'^PPM\s*\d{4}$',  # PPM + year
        r'^DOCS?\s+',  # Starts with DOC or DOCS
        r'CORREO.*BIENVENIDA',  # Email welcome variations
        r'FORMATO.*',  # Format-related folders
        r'VIDEO.*PANTALLA',  # Screen video variations
        r'^PREGUNTAS\s+WORK\s+AND\s+TRAVEL',  # Questions about W&T program
        r'^\d+\.\s*',  # Numbered list entries (1. , 2. , etc.)
    ]
    
    def __init__(self, db_url: str, whitelist: Set[str] = None):
        """
        Initialize data sanitizer.
        
        Args:
            db_url: PostgreSQL database connection URL
            whitelist: Set of student IDs to exclude from sanitization
        """
        self.db_url = db_url
        self.conn = None
        self.whitelist = whitelist or set()
        
        # Statistics
        self.stats = {
            'students_checked': 0,
            'false_positives_found': 0,
            'students_deleted': 0,
            'persons_deleted': 0,
            'documents_orphaned': 0,
        }
        
        logger.info("DataSanitizer initialized")
    
    def connect_db(self):
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            logger.info("✓ Connected to database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close_db(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def is_false_positive(self, full_name: str) -> bool:
        """
        Check if a name matches false positive patterns.
        
        Args:
            full_name: Student's full name
            
        Returns:
            bool: True if this is a false positive
        """
        # Normalize name for comparison
        normalized = full_name.upper().strip()
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        
        # Check exact matches in blacklist
        if normalized in self.BLACKLIST:
            return True
        
        # Check pattern matches
        for pattern in self.BLACKLIST_PATTERNS:
            if re.search(pattern, normalized):
                return True
        
        # Additional heuristics
        
        # Check if it's ONLY a number
        if normalized.replace('.', '').replace(',', '').isdigit():
            return True
        
        # Check if it contains only 1-2 characters (likely abbreviations)
        if len(normalized.replace(' ', '')) <= 2:
            return True
        
        # Check for WAT variations
        if normalized.startswith('WAT') and len(normalized) <= 12:
            return True
        
        # Check for single word that looks like an acronym (all caps, short)
        words = normalized.split()
        if len(words) == 1 and len(normalized) <= 10 and normalized.isupper():
            # Likely an acronym or abbreviation
            return True
        
        return False
    
    def get_all_students(self) -> List[Dict[str, Any]]:
        """
        Fetch all student records from staging.
        
        Returns:
            List of student dictionaries
        """
        query = """
            SELECT 
                s.id as student_id,
                p.id as person_id,
                p.full_name,
                p.normalized_name,
                s.program,
                p.directory_path,
                (SELECT COUNT(*) FROM staging_document d WHERE d.student_id = s.id) as document_count
            FROM staging_student s
            JOIN staging_person p ON s.person_id = p.id
            ORDER BY p.full_name
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query)
            students = cur.fetchall()
        
        return [dict(s) for s in students]
    
    def identify_false_positives(self, students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify which students are false positives.
        
        Args:
            students: List of student records
            
        Returns:
            List of false positive student records
        """
        false_positives = []
        
        for student in students:
            self.stats['students_checked'] += 1
            
            # Skip if in whitelist (manually marked as valid)
            if student['student_id'] in self.whitelist:
                logger.debug(f"Skipping whitelisted: {student['full_name']}")
                continue
            
            if self.is_false_positive(student['full_name']):
                false_positives.append(student)
                self.stats['false_positives_found'] += 1
                logger.debug(f"False positive: {student['full_name']}")
        
        return false_positives
    
    def delete_false_positives(self, false_positives: List[Dict[str, Any]], dry_run: bool = False):
        """
        Delete false positive records from database.
        
        Args:
            false_positives: List of false positive student records
            dry_run: If True, only simulate deletion
        """
        if not false_positives:
            logger.info("No false positives to delete")
            return
        
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Deleting {len(false_positives)} false positive records...")
        
        with self.conn.cursor() as cur:
            for fp in false_positives:
                student_id = fp['student_id']
                person_id = fp['person_id']
                full_name = fp['full_name']
                doc_count = fp['document_count']
                
                logger.info(f"{'[DRY RUN] ' if dry_run else ''}Deleting: {full_name} (student_id={student_id}, {doc_count} docs)")
                
                if not dry_run:
                    # Delete documents first (foreign key constraint)
                    cur.execute("DELETE FROM staging_document WHERE student_id = %s", (student_id,))
                    docs_deleted = cur.rowcount
                    self.stats['documents_orphaned'] += docs_deleted
                    
                    # Delete student
                    cur.execute("DELETE FROM staging_student WHERE id = %s", (student_id,))
                    self.stats['students_deleted'] += cur.rowcount
                    
                    # Delete person
                    cur.execute("DELETE FROM staging_person WHERE id = %s", (person_id,))
                    self.stats['persons_deleted'] += cur.rowcount
            
            if not dry_run:
                self.conn.commit()
    
    def delete_student_by_id(self, student_id: str) -> Dict[str, Any]:
        """
        Manually delete a specific student by ID.
        
        Args:
            student_id: Student ID to delete
            
        Returns:
            Dict with deletion result
        """
        try:
            self.connect_db()
            
            with self.conn.cursor() as cur:
                # Get student info first
                cur.execute("""
                    SELECT s.id, p.id as person_id, p.full_name, s.program,
                           (SELECT COUNT(*) FROM staging_document d WHERE d.student_id = s.id) as doc_count
                    FROM staging_student s
                    JOIN staging_person p ON s.person_id = p.id
                    WHERE s.id = %s
                """, (student_id,))
                
                student = cur.fetchone()
                if not student:
                    return {'success': False, 'error': 'Student not found'}
                
                # Delete documents
                cur.execute("DELETE FROM staging_document WHERE student_id = %s", (student_id,))
                docs_deleted = cur.rowcount
                
                # Delete student
                cur.execute("DELETE FROM staging_student WHERE id = %s", (student_id,))
                
                # Delete person
                cur.execute("DELETE FROM staging_person WHERE id = %s", (student['person_id'],))
                
                self.conn.commit()
                
                logger.info(f"Manually deleted: {student['full_name']} ({docs_deleted} docs)")
                
                return {
                    'success': True,
                    'student_name': student['full_name'],
                    'documents_deleted': docs_deleted
                }
                
        except Exception as e:
            logger.error(f"Failed to delete student {student_id}: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            self.close_db()
    
    def sanitize(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run complete sanitization process.
        
        Args:
            dry_run: If True, only identify false positives without deleting
            
        Returns:
            Dict with sanitization results and statistics
        """
        logger.info("="*60)
        logger.info(f"STARTING DATA SANITIZATION {'(DRY RUN)' if dry_run else ''}")
        logger.info("="*60)
        
        try:
            self.connect_db()
            
            # Step 1: Fetch all students
            logger.info("Fetching all student records...")
            students = self.get_all_students()
            logger.info(f"Found {len(students)} student records")
            
            # Step 2: Identify false positives
            logger.info("Identifying false positives...")
            false_positives = self.identify_false_positives(students)
            
            logger.info("="*60)
            logger.info(f"FALSE POSITIVES IDENTIFIED: {len(false_positives)}")
            logger.info("="*60)
            
            if false_positives:
                # Print summary
                logger.info("\nFalse Positive Records:")
                for fp in false_positives:
                    logger.info(f"  - {fp['full_name']:<40} ({fp['program']:<20} | {fp['document_count']} docs)")
            
            # Step 3: Delete false positives
            if not dry_run:
                logger.info("\n" + "="*60)
                logger.info("DELETING FALSE POSITIVES")
                logger.info("="*60)
            
            self.delete_false_positives(false_positives, dry_run=dry_run)
            
            # Final stats
            logger.info("\n" + "="*60)
            logger.info("SANITIZATION SUMMARY")
            logger.info("="*60)
            logger.info(f"Students Checked:       {self.stats['students_checked']}")
            logger.info(f"False Positives Found:  {self.stats['false_positives_found']}")
            
            if not dry_run:
                logger.info(f"Students Deleted:       {self.stats['students_deleted']}")
                logger.info(f"Persons Deleted:        {self.stats['persons_deleted']}")
                logger.info(f"Documents Removed:      {self.stats['documents_orphaned']}")
            
            logger.info("="*60)
            
            if not dry_run:
                logger.info("✅ SANITIZATION COMPLETED SUCCESSFULLY")
            else:
                logger.info("ℹ️  DRY RUN COMPLETED (no changes made)")
            
            logger.info("="*60)
            
            return {
                'success': True,
                'dry_run': dry_run,
                'false_positives': [
                    {
                        'full_name': fp['full_name'],
                        'program': fp['program'],
                        'document_count': fp['document_count'],
                        'student_id': fp['student_id']
                    }
                    for fp in false_positives
                ],
                'stats': self.stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Sanitization failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats.copy()
            }
        
        finally:
            self.close_db()


def main():
    """Main execution with dry run by default."""
    import sys
    
    # Configuration
    DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
    
    # Check for --execute flag
    dry_run = '--execute' not in sys.argv
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE")
        print("No changes will be made to the database.")
        print("To actually delete false positives, run:")
        print("  python3 data_sanitizer.py --execute")
        print("")
    
    # Run sanitization
    sanitizer = DataSanitizer(DB_URL)
    result = sanitizer.sanitize(dry_run=dry_run)
    
    # Print final result
    if result['success']:
        print(f"\n✅ Sanitization {'completed' if not dry_run else 'preview complete'}")
        print(f"Found {result['stats']['false_positives_found']} false positives")
        if not dry_run:
            print(f"Deleted {result['stats']['students_deleted']} student records")
    else:
        print(f"\n❌ Sanitization failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
