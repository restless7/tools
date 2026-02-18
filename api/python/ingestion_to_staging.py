#!/usr/bin/env python3
"""
ICE Data Ingestion to Staging System
Processes all data, creates normalized staging structure, and populates staging database
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import psycopg2
from dotenv import load_dotenv
from local_ingestion_loader_v2 import LocalIngestionLoaderV2
from psycopg2.extras import execute_batch

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            "/home/sebastiangarcia/ice-data-staging/reports/ingestion.log"
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class StagingIngestionManager:
    """
    Manages the complete ingestion pipeline to staging:
    1. Scan and ingest data
    2. Normalize file names and organization
    3. Populate staging database
    4. Generate reports
    """

    def __init__(self, source_dir: str, staging_dir: str, db_url: str):
        """
        Initialize staging ingestion manager.

        Args:
            source_dir: Source data directory
            staging_dir: Staging directory for normalized data
            db_url: Database connection URL
        """
        self.source_dir = Path(source_dir)
        self.staging_dir = Path(staging_dir)
        self.db_url = db_url

        # Staging subdirectories
        self.documents_dir = self.staging_dir / "documents"
        self.metadata_dir = self.staging_dir / "metadata"
        self.reports_dir = self.staging_dir / "reports"

        # Database connection
        self.conn = None

        logger.info(f"Initialized StagingIngestionManager")
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

    def create_staging_tables(self):
        """Create staging tables in database."""
        logger.info("Creating staging tables...")

        with self.conn.cursor() as cur:
            # Staging Person table
            cur.execute("""
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
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_staging_person_normalized_name 
                ON staging_person(normalized_name)
            """)

            # Staging Student table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS staging_student (
                    id UUID PRIMARY KEY,
                    person_id UUID NOT NULL REFERENCES staging_person(id),
                    program TEXT,
                    status TEXT DEFAULT 'PENDING_REVIEW',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Staging Document table
            cur.execute("""
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
                )
            """)

            # Staging Ingestion Run table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS staging_ingestion_run (
                    id SERIAL PRIMARY KEY,
                    run_date TIMESTAMP DEFAULT NOW(),
                    source_directory TEXT NOT NULL,
                    total_students INTEGER,
                    total_documents INTEGER,
                    csv_files_processed INTEGER,
                    records_enriched INTEGER,
                    execution_time_seconds FLOAT,
                    status TEXT DEFAULT 'COMPLETED',
                    notes TEXT
                )
            """)

            self.conn.commit()
            logger.info("✔ Staging tables created/verified")

    def normalize_file_name(
        self,
        student_name: str,
        student_id: str,
        original_filename: str,
        document_type: str,
        index: int = 0,
    ) -> str:
        """
        Generate normalized filename.

        Format: {STUDENT_ID}_{DOCUMENT_TYPE}_{INDEX}.{ext}
        Example: 550e8400-e29b-41d4-a716-446655440000_PASSPORT_01.pdf

        Args:
            student_name: Student full name
            student_id: Student UUID
            original_filename: Original file name
            document_type: Document type
            index: Index for multiple files of same type

        Returns:
            str: Normalized filename
        """
        # Get file extension
        ext = Path(original_filename).suffix.lower()

        # Format: STUDENTID_DOCTYPE_INDEX.ext
        normalized = f"{student_id}_{document_type}_{index:02d}{ext}"

        return normalized

    def improve_document_classification(
        self, file_path: str, original_type: str
    ) -> str:
        """
        Improve document classification using filename analysis and basic OCR.

        Args:
            file_path: Path to document
            original_type: Original classification

        Returns:
            str: Improved document type
        """
        filename_lower = Path(file_path).name.lower()

        # Enhanced keyword matching with more specific patterns
        type_keywords = {
            "PASSPORT": ["passport", "pasaporte", "pasport", "pp ", "passp"],
            "VISA": ["visa", "visa americana", "visa form", "ds-160", "ds160"],
            "DIPLOMA": ["diploma", "degree", "titulo", "grado", "certificate of"],
            "TRANSCRIPT": [
                "transcript",
                "notas",
                "grades",
                "academic record",
                "certificado de notas",
                "student status",
                "proof of student",
            ],
            "PHOTO": ["photo", "foto", "picture", "imagen", "2x2", "passport photo"],
            "FINANCIAL": [
                "bank",
                "banco",
                "financial",
                "balance",
                "solvencia",
                "sponsorship",
                "fee",
                "refund",
                "disclosure",
            ],
            "MEDICAL": [
                "medical",
                "medico",
                "health",
                "salud",
                "vaccination",
                "vacuna",
            ],
            "ID_CARD": [
                "cedula",
                "id card",
                "identification",
                "dni",
                "id ",
                "identif",
                "ssn",
                "social security",
            ],
            "LETTER": [
                "letter",
                "carta",
                "recommendation",
                "recomendacion",
                "job offer",
                "offer letter",
            ],
            "RESUME": ["resume", "cv", "hoja de vida", "curriculum", "resume "],
            "CONTRACT": [
                "contract",
                "contrato",
                "agreement",
                "acuerdo",
                "cu digital",
                "cu-",
                "cu20",
            ],
            "BACKGROUND_CHECK": ["antecedentes", "background", "police", "policia"],
            "EMERGENCY_CONTACT": ["contacto", "contact", "emergencia", "emergency"],
            "QUOTATION": ["cotizacion", "quotation", "quote", "proposal", "asesorias"],
        }

        # Check each type's keywords
        for doc_type, keywords in type_keywords.items():
            if any(keyword in filename_lower for keyword in keywords):
                logger.debug(
                    f"Improved classification: {original_type} → {doc_type} for {Path(file_path).name}"
                )
                return doc_type

        # If still OTHER, keep it but log
        if original_type == "OTHER":
            logger.debug(
                f"Could not improve classification for: {Path(file_path).name}"
            )

        return original_type

    def copy_and_normalize_document(
        self, student_record: Dict[str, Any], document: Dict[str, Any], index: int
    ) -> Dict[str, Any]:
        """
        Copy document to staging with normalized name.
        FIXED: Organize by STUDENT folder, not program!

        Args:
            student_record: Student record
            document: Document metadata
            index: Index for this document

        Returns:
            Dict with staging file info
        """
        student_id = student_record["student_id"]
        student_name = student_record["full_name"]

        # Create STUDENT subdirectory in staging (not program!)
        student_dir = self.documents_dir / student_id
        student_dir.mkdir(parents=True, exist_ok=True)

        # Improve document classification
        improved_type = self.improve_document_classification(
            document["file_path"], document["document_type"]
        )

        # Generate normalized filename WITHOUT UUID prefix (redundant in student folder)
        # Format: {DOCTYPE}_{INDEX}.{ext}
        ext = Path(document["file_name"]).suffix.lower()
        normalized_name = f"{improved_type}_{index:02d}{ext}"

        # Destination path
        staging_path = student_dir / normalized_name

        # Copy file
        try:
            shutil.copy2(document["file_path"], staging_path)
            logger.debug(f"Copied: {document['file_name']} -> {normalized_name}")
        except Exception as e:
            logger.error(f"Failed to copy {document['file_name']}: {e}")
            raise

        return {
            "original_file_name": document["file_name"],
            "normalized_file_name": normalized_name,
            "original_file_path": document["file_path"],
            "staging_file_path": str(staging_path),
            "checksum": document["checksum"],
        }

    def insert_staging_data(
        self, student_records: List[Dict[str, Any]], documents: List[Dict[str, Any]]
    ):
        """
        Insert data into staging database.

        Args:
            student_records: List of student records
            documents: List of document metadata
        """
        logger.info("Inserting data into staging database...")

        with self.conn.cursor() as cur:
            # Insert persons
            person_data = [
                (
                    rec["person_id"],
                    rec["full_name"],
                    rec["normalized_name"],
                    rec.get("email"),
                    rec.get("phone"),
                    rec.get("address"),
                    rec.get("id_number"),
                    rec.get("birth_date"),
                    rec["source"],
                    rec.get("directory_path"),
                    rec.get("csv_file"),
                )
                for rec in student_records
            ]

            execute_batch(
                cur,
                """
                INSERT INTO staging_person (
                    id, full_name, normalized_name, email, phone,
                    address, id_number, birth_date, source, directory_path, csv_file
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """,
                person_data,
            )

            logger.info(f"✔ Inserted {len(person_data)} person records")

            # Insert students
            student_data = [
                (rec["student_id"], rec["person_id"], rec["program"])
                for rec in student_records
            ]

            execute_batch(
                cur,
                """
                INSERT INTO staging_student (id, person_id, program)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """,
                student_data,
            )

            logger.info(f"✔ Inserted {len(student_data)} student records")

            # Insert documents
            document_data = [
                (
                    doc["student_id"],
                    doc["original_file_name"],
                    doc["normalized_file_name"],
                    doc["original_file_path"],
                    doc["staging_file_path"],
                    doc["file_size"],
                    doc["mime_type"],
                    doc["document_type"],
                    doc["checksum"],
                )
                for doc in documents
            ]

            execute_batch(
                cur,
                """
                INSERT INTO staging_document (
                    student_id, original_file_name, normalized_file_name,
                    original_file_path, staging_file_path, file_size,
                    mime_type, document_type, checksum
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (checksum) DO NOTHING
            """,
                document_data,
            )

            logger.info(f"✔ Inserted {len(document_data)} document records")

            self.conn.commit()

    def save_metadata(self, results: Dict[str, Any]):
        """
        Save ingestion metadata to JSON files.

        Args:
            results: Ingestion results
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save full results
        results_file = self.metadata_dir / f"ingestion_results_{timestamp}.json"
        with open(results_file, "w") as f:
            # Convert dates to strings for JSON serialization
            serializable_results = {
                "success": results["success"],
                "stats": results["stats"],
                "student_count": len(results["student_records"]),
                "document_count": len(results["documents"]),
                "timestamp": timestamp,
            }
            json.dump(serializable_results, f, indent=2, default=str)

        logger.info(f"✔ Saved metadata to {results_file}")

        # Save student records
        students_file = self.metadata_dir / f"students_{timestamp}.json"
        with open(students_file, "w") as f:
            json.dump(results["student_records"], f, indent=2, default=str)

        logger.info(f"✔ Saved student records to {students_file}")

    def generate_report(self, results: Dict[str, Any], run_id: int):
        """
        Generate human-readable ingestion report.

        Args:
            results: Ingestion results
            run_id: Database run ID
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_lines = [
            "=" * 80,
            f"ICE DATA INGESTION REPORT",
            f"Generated: {timestamp}",
            f"Run ID: {run_id}",
            "=" * 80,
            "",
            "SUMMARY",
            "-" * 80,
            f"Source Directory: {self.source_dir}",
            f"Staging Directory: {self.staging_dir}",
            f"Execution Time: {results['stats']['execution_time']:.2f}s",
            "",
            "STATISTICS",
            "-" * 80,
            f"Total Students Discovered: {results['stats']['person_records_created']}",
            f"Records Enriched from CSV: {results['stats']['records_enriched_from_csv']}",
            f"Total Documents Indexed: {results['stats']['documents_indexed']}",
            f"CSV Files Processed: {results['stats']['csv_files_processed']}",
            f"Errors: {results['stats']['errors']}",
            "",
        ]

        # Program breakdown
        from collections import Counter

        programs = Counter(rec["program"] for rec in results["student_records"])

        report_lines.extend(["PROGRAMS", "-" * 80])

        for program, count in programs.most_common():
            report_lines.append(f"{program}: {count} students")

        report_lines.extend(["", "SOURCE BREAKDOWN", "-" * 80])

        sources = Counter(rec["source"] for rec in results["student_records"])
        for source, count in sources.items():
            report_lines.append(f"{source}: {count} records")

        report_lines.extend(
            [
                "",
                "=" * 80,
                "NEXT STEPS",
                "-" * 80,
                "1. Review staging database: psql leads_project",
                "2. Query: SELECT * FROM staging_student LIMIT 10;",
                "3. Verify documents in: " + str(self.documents_dir),
                "4. Access frontend dashboard at: http://localhost:3005/ice-database",
                "5. When ready, approve records for production ingestion",
                "=" * 80,
            ]
        )

        report_text = "\n".join(report_lines)

        # Save to file
        report_file = (
            self.reports_dir
            / f'ingestion_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )
        with open(report_file, "w") as f:
            f.write(report_text)

        logger.info(f"✔ Generated report: {report_file}")

        # Print to console
        print("\n" + report_text)

    def log_ingestion_run(self, results: Dict[str, Any]) -> int:
        """
        Log ingestion run to database.

        Args:
            results: Ingestion results

        Returns:
            int: Run ID
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO staging_ingestion_run (
                    source_directory, total_students, total_documents,
                    csv_files_processed, records_enriched, execution_time_seconds,
                    status, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    str(self.source_dir),
                    results["stats"]["person_records_created"],
                    results["stats"]["documents_indexed"],
                    results["stats"]["csv_files_processed"],
                    results["stats"]["records_enriched_from_csv"],
                    results["stats"]["execution_time"],
                    "COMPLETED",
                    f"Full ingestion from {self.source_dir}",
                ),
            )

            run_id = cur.fetchone()[0]
            self.conn.commit()

            logger.info(f"✔ Logged ingestion run (ID: {run_id})")

            return run_id

    def run_full_ingestion(self):
        """
        Execute complete ingestion pipeline.
        """
        logger.info("=" * 80)
        logger.info("STARTING FULL INGESTION TO STAGING")
        logger.info("=" * 80)

        try:
            # Step 1: Scan and ingest data
            logger.info("\n[1/6] Scanning source data...")
            loader = LocalIngestionLoaderV2(str(self.source_dir))
            results = loader.run_ingestion(program="Unknown")

            if not results["success"]:
                raise Exception(f"Ingestion failed: {results.get('error')}")

            # Step 2: Connect to database
            logger.info("\n[2/6] Connecting to staging database...")
            self.connect_db()
            self.create_staging_tables()

            # Step 3: Normalize and copy documents
            logger.info("\n[3/6] Normalizing and copying documents...")
            normalized_documents = []
            student_folders_created = set()

            for doc in results["documents"]:
                # Find matching student
                student = next(
                    (
                        s
                        for s in results["student_records"]
                        if s["student_id"] == doc["student_id"]
                    ),
                    None,
                )

                if not student:
                    logger.warning(f"No student found for document: {doc['file_name']}")
                    continue

                # Create student metadata file (once per student)
                if student["student_id"] not in student_folders_created:
                    student_dir = self.documents_dir / student["student_id"]
                    student_dir.mkdir(parents=True, exist_ok=True)

                    # Write student metadata JSON
                    metadata_file = student_dir / "STUDENT_INFO.json"
                    with open(metadata_file, "w") as f:
                        json.dump(
                            {
                                "student_id": student["student_id"],
                                "person_id": student["person_id"],
                                "full_name": student["full_name"],
                                "email": student.get("email"),
                                "phone": student.get("phone"),
                                "program": student["program"],
                                "source": student["source"],
                            },
                            f,
                            indent=2,
                            default=str,
                        )

                    student_folders_created.add(student["student_id"])

                # Count documents for this student
                student_doc_count = sum(
                    1
                    for d in normalized_documents
                    if d["student_id"] == doc["student_id"]
                )

                # Copy and normalize
                normalized_doc = self.copy_and_normalize_document(
                    student, doc, student_doc_count
                )

                # Merge with original metadata
                full_doc = {**doc, **normalized_doc}
                normalized_documents.append(full_doc)

            logger.info(f"✔ Normalized {len(normalized_documents)} documents")
            logger.info(
                f"✔ Created {len(student_folders_created)} student folders with metadata"
            )

            # Step 4: Insert into staging database
            logger.info("\n[4/6] Inserting data into staging database...")
            self.insert_staging_data(results["student_records"], normalized_documents)

            # Step 5: Log run
            logger.info("\n[5/6] Logging ingestion run...")
            run_id = self.log_ingestion_run(results)

            # Step 6: Save metadata and generate report
            logger.info("\n[6/6] Generating reports...")
            self.save_metadata(results)
            self.generate_report(results, run_id)

            logger.info("\n" + "=" * 80)
            logger.info("✔ INGESTION TO STAGING COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            raise

        finally:
            self.close_db()


def main():
    """Main execution."""
    # Configuration - can be overridden by environment variables
    SOURCE_DIR = os.getenv(
        "SOURCE_DIR",
        "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001",
    )
    STAGING_DIR = os.getenv("STAGING_DIR", "/home/sebastiangarcia/ice-data-staging")
    DB_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:224207bB@localhost:5432/leads_project"
    )

    # Run ingestion
    manager = StagingIngestionManager(SOURCE_DIR, STAGING_DIR, DB_URL)
    manager.run_full_ingestion()


if __name__ == "__main__":
    main()
