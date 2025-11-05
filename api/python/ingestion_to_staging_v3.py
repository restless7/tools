#!/usr/bin/env python3
"""
ICE Data Ingestion to Staging System V3
Enhanced with Excel/CSV extraction for comprehensive data capture
"""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import execute_batch, Json
from dotenv import load_dotenv
import pandas as pd

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_ingestion_loader_v2 import LocalIngestionLoaderV2
from data_extractor import ExcelDataExtractor
from csv_data_processor import PersonDataProcessor, process_classified_data

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/sebastiangarcia/ice-data-staging/reports/ingestion_v3.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class EnhancedStagingIngestionManager:
    """
    Enhanced ingestion manager with Excel/CSV extraction capabilities.
    
    Pipeline:
    1. Extract and classify Excel/CSV data (students, leads, reference)
    2. Scan directory structure for documents
    3. Match and enrich with CSV data
    4. Normalize file names and organization
    5. Populate staging database (students, leads, reference data)
    6. Generate comprehensive reports
    """
    
    def __init__(
        self,
        source_dir: str,
        staging_dir: str,
        db_url: str
    ):
        """
        Initialize enhanced staging ingestion manager.
        
        Args:
            source_dir: Source data directory
            staging_dir: Staging directory for normalized data
            db_url: Database connection URL
        """
        self.source_dir = Path(source_dir)
        self.staging_dir = Path(staging_dir)
        self.db_url = db_url
        
        # Staging subdirectories
        self.documents_dir = self.staging_dir / 'documents'
        self.metadata_dir = self.staging_dir / 'metadata'
        self.reports_dir = self.staging_dir / 'reports'
        self.extracted_csvs_dir = self.staging_dir / 'extracted_csvs'
        
        # Database connection
        self.conn = None
        
        # Statistics
        self.stats = {
            'excel_files_processed': 0,
            'csv_sheets_extracted': 0,
            'students_from_csv': 0,
            'students_from_directories': 0,
            'leads_created': 0,
            'reference_files_stored': 0,
        }
        
        logger.info(f"Initialized EnhancedStagingIngestionManager V3")
        logger.info(f"Source: {self.source_dir}")
        logger.info(f"Staging: {self.staging_dir}")
    
    def connect_db(self):
        """Connect to staging database."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            logger.info("✔ Connected to staging database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close_db(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def extract_excel_csv_data(self) -> Dict[str, Any]:
        """
        Step 1: Extract and classify all Excel/CSV data.
        
        Returns:
            Dict with classified data and statistics
        """
        logger.info("="*80)
        logger.info("STEP 1: EXCEL/CSV DATA EXTRACTION")
        logger.info("="*80)
        
        # Extract data
        extractor = ExcelDataExtractor(
            source_dir=str(self.source_dir),
            output_dir=str(self.extracted_csvs_dir)
        )
        
        classified_data = extractor.extract_all_data()
        extraction_stats = extractor.get_stats()
        
        # Process classified data
        processing_result = process_classified_data(classified_data)
        
        # Update stats
        self.stats['excel_files_processed'] = extraction_stats['files_processed']
        self.stats['csv_sheets_extracted'] = extraction_stats['sheets_extracted']
        self.stats['students_from_csv'] = processing_result['stats']['total_students']
        self.stats['leads_created'] = processing_result['stats']['total_leads']
        self.stats['reference_files_stored'] = processing_result['stats']['total_reference_files']
        
        logger.info("="*80)
        logger.info("EXCEL/CSV EXTRACTION SUMMARY")
        logger.info(f"Excel Files Processed: {self.stats['excel_files_processed']}")
        logger.info(f"CSV Sheets Extracted: {self.stats['csv_sheets_extracted']}")
        logger.info(f"Students Found in CSV: {self.stats['students_from_csv']}")
        logger.info(f"Leads Found: {self.stats['leads_created']}")
        logger.info(f"Reference Files: {self.stats['reference_files_stored']}")
        logger.info("="*80)
        
        return processing_result
    
    def scan_directory_structure(self) -> Dict[str, Any]:
        """
        Step 2: Scan directory structure for documents.
        
        Returns:
            Dict with student records and documents
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 2: DIRECTORY STRUCTURE SCAN")
        logger.info("="*80)
        
        loader = LocalIngestionLoaderV2(str(self.source_dir))
        results = loader.run_ingestion(program="Unknown")
        
        if not results['success']:
            raise Exception(f"Directory scan failed: {results.get('error')}")
        
        self.stats['students_from_directories'] = results['stats']['person_records_created']
        
        logger.info("="*80)
        logger.info("DIRECTORY SCAN SUMMARY")
        logger.info(f"Students from Directories: {self.stats['students_from_directories']}")
        logger.info(f"Documents Found: {results['stats']['documents_indexed']}")
        logger.info("="*80)
        
        return results
    
    def merge_csv_and_directory_data(
        self,
        csv_data: Dict[str, Any],
        directory_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 3: Merge CSV and directory data, enriching where possible.
        
        Args:
            csv_data: Processed CSV data
            directory_data: Directory scan results
            
        Returns:
            Merged dataset
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 3: DATA MERGING & ENRICHMENT")
        logger.info("="*80)
        
        # Create name-based lookup for CSV students
        csv_students_by_name = {}
        for student in csv_data['students']:
            normalized_name = student['full_name']
            csv_students_by_name[normalized_name] = student
        
        # Enrich directory students with CSV data
        enriched_count = 0
        for dir_student in directory_data['student_records']:
            normalized_name = dir_student['normalized_name']
            
            if normalized_name in csv_students_by_name:
                csv_student = csv_students_by_name[normalized_name]
                
                # Enrich with CSV data
                if not dir_student.get('email') and csv_student.get('email'):
                    dir_student['email'] = csv_student['email']
                    enriched_count += 1
                
                if not dir_student.get('phone') and csv_student.get('phone'):
                    dir_student['phone'] = csv_student['phone']
                    enriched_count += 1
                
                # Add additional fields
                dir_student['csv_enriched'] = True
                dir_student['csv_source_file'] = csv_student.get('source_file')
                dir_student['cedula'] = csv_student.get('cedula')
                dir_student['birth_date'] = csv_student.get('birth_date')
                dir_student['address'] = csv_student.get('address')
        
        logger.info(f"✔ Enriched {enriched_count} student records with CSV data")
        logger.info("="*80)
        
        return {
            'students': directory_data['student_records'],
            'documents': directory_data['documents'],
            'leads': csv_data['leads'],
            'reference_files': csv_data['reference_files'],
            'directory_results': directory_data,
        }
    
    def _parse_date_safely(self, date_value: Any) -> Any:
        """
        Enhanced date parsing with multiple format support.
        
        Args:
            date_value: Date value from CSV (string, date object, or None)
            
        Returns:
            Parsed date or None if invalid
        """
        if not date_value or pd.isna(date_value):
            return None
        
        # If already a date/datetime/Timestamp object
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return date_value.date() if hasattr(date_value, 'date') else date_value
        
        if isinstance(date_value, type(date_value)) and hasattr(date_value, 'year'):
            return date_value
        
        # String processing
        if isinstance(date_value, str):
            date_str = date_value.strip()
            
            # Skip invalid patterns
            if not date_str or date_str.lower() in ['nan', 'none', '', 'null']:
                return None
            
            # Skip age patterns (e.g., "26 años", "30 years old")
            if 'año' in date_str.lower() or 'year' in date_str.lower():
                logger.debug(f"Skipping age value: {date_value}")
                return None
            
            # Clean up common formatting issues
            date_str = date_str.replace('/ ', '/').replace(' /', '/')  # "25/ sep" → "25/sep"
            date_str = date_str.replace('  ', ' ')  # Double spaces
            
            # Try parsing with dateutil (flexible parser)
            try:
                from dateutil import parser as date_parser
                parsed = date_parser.parse(date_str, dayfirst=True)
                return parsed.date()
            except:
                logger.debug(f"Cannot parse date string: {date_value}")
                return None
        
        # Handle numeric dates (Excel serial numbers)
        if isinstance(date_value, (int, float)):
            try:
                # Excel epoch is 1899-12-30
                from datetime import timedelta
                excel_epoch = datetime(1899, 12, 30)
                return (excel_epoch + timedelta(days=float(date_value))).date()
            except:
                return None
        
        return None
    
    def insert_leads_to_database(self, leads: List[Dict[str, Any]], run_id: int):
        """
        Insert lead records into staging_lead table.
        Uses individual transactions to prevent cascade failures.
        Logs failures to staging_lead_failures table.
        
        Args:
            leads: List of lead dictionaries
            run_id: Ingestion run ID
        """
        logger.info(f"\nInserting {len(leads)} leads...")
        
        inserted_count = 0
        failed_count = 0
        
        for lead in leads:
            try:
                # Parse birth_date safely
                birth_date = self._parse_date_safely(lead.get('birth_date'))
                
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO staging_lead (
                            id, full_name, email, phone, address, cedula, birth_date,
                            country, city, source_file, source_sheet, status,
                            interest_program, notes, ingestion_run_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (email) WHERE email IS NOT NULL DO UPDATE
                        SET phone = EXCLUDED.phone,
                            address = EXCLUDED.address,
                            updated_at = NOW()
                    """, (
                        lead['id'],
                        lead['full_name'],
                        lead.get('email'),
                        lead.get('phone'),
                        lead.get('address'),
                        lead.get('cedula'),
                        birth_date,  # Use safely parsed date
                        lead.get('country'),
                        lead.get('city'),
                        lead.get('source_file'),
                        lead.get('source_sheet'),
                        lead.get('status', 'NEW'),
                        lead.get('program'),  # interest_program
                        None,  # notes
                        run_id
                    ))
                
                # Commit after each successful insert
                self.conn.commit()
                inserted_count += 1
                
            except Exception as e:
                # Rollback failed transaction to prevent abort state
                self.conn.rollback()
                failed_count += 1
                
                # Determine error type
                error_str = str(e)
                if 'date' in error_str.lower():
                    error_type = 'DATE_PARSE_ERROR'
                elif 'duplicate' in error_str.lower() or 'unique' in error_str.lower():
                    error_type = 'DUPLICATE_ERROR'
                elif 'null' in error_str.lower() or 'not null' in error_str.lower():
                    error_type = 'VALIDATION_ERROR'
                else:
                    error_type = 'DATABASE_ERROR'
                
                # Log failure to staging_lead_failures table
                try:
                    with self.conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO staging_lead_failures (
                                lead_data, error_message, error_type, ingestion_run_id,
                                source_file, source_sheet, row_index
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            Json(lead),  # Store full lead data as JSONB
                            error_str[:500],  # Truncate long error messages
                            error_type,
                            run_id,
                            lead.get('source_file'),
                            lead.get('source_sheet'),
                            lead.get('row_index')
                        ))
                    self.conn.commit()
                except Exception as log_error:
                    logger.error(f"Failed to log lead failure: {log_error}")
                    self.conn.rollback()
                
                logger.warning(f"Error inserting lead {lead['full_name']}: {e}")
                continue
        
        logger.info(f"✔ Inserted {inserted_count} leads ({failed_count} failed)")
    
    def insert_reference_data_to_database(self, reference_files: List[Dict[str, Any]], run_id: int):
        """
        Insert reference data into staging_reference_data table.
        
        Args:
            reference_files: List of reference file dictionaries
            run_id: Ingestion run ID
        """
        logger.info(f"\nInserting {len(reference_files)} reference files...")
        
        with self.conn.cursor() as cur:
            for ref_file in reference_files:
                try:
                    # Determine data type from sheet name
                    sheet_name = ref_file['sheet_name'].lower()
                    
                    if 'price' in sheet_name or 'precio' in sheet_name:
                        data_type = 'PRICE_LIST'
                    elif 'employer' in sheet_name or 'empleador' in sheet_name:
                        data_type = 'EMPLOYER_LIST'
                    elif 'country' in sheet_name or 'pais' in sheet_name:
                        data_type = 'COUNTRY_LIST'
                    else:
                        data_type = 'GENERAL_REFERENCE'
                    
                    cur.execute("""
                        INSERT INTO staging_reference_data (
                            source_file, source_sheet, data_type, data_content,
                            row_count, column_count, columns, ingestion_run_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        ref_file['source_file'],
                        ref_file['sheet_name'],
                        data_type,
                        Json({'csv_path': ref_file['csv_path']}),
                        ref_file['row_count'],
                        ref_file['column_count'],
                        ref_file['columns'],
                        run_id
                    ))
                except Exception as e:
                    logger.warning(f"Error inserting reference file {ref_file['sheet_name']}: {e}")
                    continue
        
        self.conn.commit()
        logger.info(f"✔ Inserted {len(reference_files)} reference files")
    
    def normalize_and_stage_documents(
        self,
        students: List[Dict[str, Any]],
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize documents and copy to staging folders.
        
        Args:
            students: List of student records
            documents: List of raw document metadata from directory loader
            
        Returns:
            List of normalized document dictionaries ready for database insertion
        """
        normalized_docs = []
        student_folders_created = set()
        
        # Create student ID lookup
        student_lookup = {s['student_id']: s for s in students}
        
        for doc in documents:
            try:
                student_id = doc['student_id']
                student = student_lookup.get(student_id)
                
                if not student:
                    logger.warning(f"No student found for document: {doc['file_name']}")
                    continue
                
                # Create student folder with metadata (once per student)
                if student_id not in student_folders_created:
                    student_dir = self.documents_dir / student_id
                    student_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Write student metadata JSON
                    metadata_file = student_dir / 'STUDENT_INFO.json'
                    with open(metadata_file, 'w') as f:
                        json.dump({
                            'student_id': student['student_id'],
                            'person_id': student['person_id'],
                            'full_name': student['full_name'],
                            'email': student.get('email'),
                            'phone': student.get('phone'),
                            'program': student['program'],
                            'source': student['source'],
                        }, f, indent=2, default=str)
                    
                    student_folders_created.add(student_id)
                
                # Count existing documents for this student to get index
                doc_count = sum(1 for d in normalized_docs if d['student_id'] == student_id)
                
                # Normalize filename: DOCTYPE_INDEX.ext
                doc_type = doc['document_type']
                ext = Path(doc['file_name']).suffix.lower()
                normalized_name = f"{doc_type}_{doc_count:02d}{ext}"
                
                # Destination paths
                student_dir = self.documents_dir / student_id
                staging_path = student_dir / normalized_name
                
                # Copy file to staging
                import shutil
                shutil.copy2(doc['file_path'], staging_path)
                
                # Create normalized document record
                normalized_doc = {
                    'student_id': student_id,
                    'original_file_name': doc['file_name'],
                    'normalized_file_name': normalized_name,
                    'original_file_path': doc['file_path'],
                    'staging_file_path': str(staging_path),
                    'file_size': doc['file_size'],
                    'mime_type': doc['mime_type'],
                    'document_type': doc_type,
                    'checksum': doc['checksum']
                }
                
                normalized_docs.append(normalized_doc)
                
            except Exception as e:
                logger.error(f"Error normalizing document {doc.get('file_name', 'unknown')}: {e}")
                continue
        
        logger.info(f"✔ Normalized and staged {len(normalized_docs)} documents")
        logger.info(f"✔ Created {len(student_folders_created)} student folders")
        
        return normalized_docs
    
    def log_ingestion_run(self, merged_data: Dict[str, Any]) -> int:
        """
        Log ingestion run with enhanced statistics.
        
        Args:
            merged_data: Merged ingestion data
            
        Returns:
            int: Run ID
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO staging_ingestion_run (
                    source_directory, total_students, total_documents,
                    csv_files_processed, records_enriched, execution_time_seconds,
                    total_leads, total_reference_files, excel_files_processed,
                    status, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                str(self.source_dir),
                len(merged_data['students']),
                len(merged_data['documents']),
                self.stats['csv_sheets_extracted'],
                sum(1 for s in merged_data['students'] if s.get('csv_enriched')),
                merged_data['directory_results']['stats']['execution_time'],
                len(merged_data['leads']),
                len(merged_data['reference_files']),
                self.stats['excel_files_processed'],
                'COMPLETED',
                f"Enhanced V3 ingestion with Excel/CSV extraction"
            ))
            
            run_id = cur.fetchone()[0]
            self.conn.commit()
            
            logger.info(f"✔ Logged ingestion run (ID: {run_id})")
            
            return run_id
    
    def run_full_ingestion(self):
        """
        Execute complete enhanced ingestion pipeline.
        """
        logger.info("\n" + "="*80)
        logger.info("🚀 ENHANCED INGESTION PIPELINE V3")
        logger.info("="*80)
        
        start_time = datetime.now()
        
        try:
            # Step 1: Extract Excel/CSV data
            csv_data = self.extract_excel_csv_data()
            
            # Step 2: Scan directory structure
            directory_data = self.scan_directory_structure()
            
            # Step 3: Merge and enrich data
            merged_data = self.merge_csv_and_directory_data(csv_data, directory_data)
            
            # Step 4: Normalize and stage documents
            logger.info("\n" + "="*80)
            logger.info("STEP 4: NORMALIZING & STAGING DOCUMENTS")
            logger.info("="*80)
            normalized_documents = self.normalize_and_stage_documents(
                merged_data['students'],
                merged_data['documents']
            )
            
            # Step 5: Connect to database
            logger.info("\n" + "="*80)
            logger.info("STEP 5: DATABASE OPERATIONS")
            logger.info("="*80)
            self.connect_db()
            
            # Step 6: Insert data
            logger.info("\nInserting students and documents...")
            # Note: Using existing ingestion_to_staging.py methods for student/document insertion
            from ingestion_to_staging import StagingIngestionManager
            base_manager = StagingIngestionManager(
                str(self.source_dir),
                str(self.staging_dir),
                self.db_url
            )
            base_manager.conn = self.conn
            base_manager.insert_staging_data(
                merged_data['students'],
                normalized_documents
            )
            
            # Step 7: Log run (get run_id)
            run_id = self.log_ingestion_run(merged_data)
            
            # Step 8: Insert leads
            logger.info("\n" + "="*80)
            logger.info("STEP 6: INSERTING LEADS & REFERENCE DATA")
            logger.info("="*80)
            self.insert_leads_to_database(merged_data['leads'], run_id)
            
            # Step 9: Insert reference data
            self.insert_reference_data_to_database(merged_data['reference_files'], run_id)
            
            # Step 10: Generate final report
            logger.info("\n" + "="*80)
            logger.info("STEP 7: FINAL REPORT")
            logger.info("="*80)
            self.generate_final_report(merged_data, run_id, start_time)
            
            logger.info("\n" + "="*80)
            logger.info("✅ ENHANCED INGESTION V3 COMPLETED SUCCESSFULLY")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}", exc_info=True)
            raise
        
        finally:
            self.close_db()
    
    def generate_final_report(self, merged_data: Dict[str, Any], run_id: int, start_time: datetime):
        """Generate comprehensive final report."""
        execution_time = (datetime.now() - start_time).total_seconds()
        
        report = f"""
{'='*80}
ICE DATA INGESTION - ENHANCED V3 FINAL REPORT
{'='*80}
Run ID: {run_id}
Execution Time: {execution_time:.2f} seconds
Timestamp: {datetime.now().isoformat()}

EXCEL/CSV EXTRACTION
{'='*80}
Excel Files Processed:      {self.stats['excel_files_processed']}
CSV Sheets Extracted:       {self.stats['csv_sheets_extracted']}
Students from CSV:          {self.stats['students_from_csv']}
Leads Found:               {self.stats['leads_created']}
Reference Files:           {self.stats['reference_files_stored']}

DIRECTORY SCAN
{'='*80}
Students from Directories: {self.stats['students_from_directories']}
Documents Found:           {len(merged_data['documents'])}

DATA ENRICHMENT
{'='*80}
Total Unique Students:     {len(merged_data['students'])}
CSV-Enriched Students:     {sum(1 for s in merged_data['students'] if s.get('csv_enriched'))}

FINAL DATABASE RECORDS
{'='*80}
Students Inserted:         {len(merged_data['students'])}
Documents Inserted:        {len(merged_data['documents'])}
Leads Inserted:            {len(merged_data['leads'])}
Reference Files Stored:    {len(merged_data['reference_files'])}

PROGRAM DISTRIBUTION
{'='*80}
"""
        # Program distribution
        program_counts = {}
        for student in merged_data['students']:
            program = student.get('program', 'Unknown')
            program_counts[program] = program_counts.get(program, 0) + 1
        
        for program, count in sorted(program_counts.items(), key=lambda x: x[1], reverse=True):
            report += f"{program:<30} {count:>5}\n"
        
        report += f"\n{'='*80}\n"
        
        # Save report
        report_file = self.reports_dir / f"ingestion_v3_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        
        # Print report
        print(report)
        
        logger.info(f"✔ Report saved: {report_file}")


def main():
    """Main execution."""
    # Configuration
    SOURCE_DIR = os.getenv('SOURCE_DIR', "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001")
    STAGING_DIR = os.getenv('STAGING_DIR', "/home/sebastiangarcia/ice-data-staging")
    DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
    
    # Run enhanced ingestion
    manager = EnhancedStagingIngestionManager(SOURCE_DIR, STAGING_DIR, DB_URL)
    manager.run_full_ingestion()


if __name__ == '__main__':
    main()
