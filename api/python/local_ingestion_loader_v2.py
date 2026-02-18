#!/usr/bin/env python3
"""
Local Ingestion Loader V2 Module
Enhanced to handle real-world non-normalized data:
- Creates Person and Student records with UUIDs
- Matches documents to students by directory name
- Handles various CSV column name formats
"""

import hashlib
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from storage_adapter import DocumentMetadata, get_storage_adapter
from unidecode import unidecode

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Statistics from the ingestion process."""

    person_records_created: int = 0
    student_records_created: int = 0
    records_enriched_from_csv: int = 0
    document_files: int = 0
    documents_indexed: int = 0
    csv_files_processed: int = 0
    errors: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def execution_time(self) -> float:
        """Calculate execution time in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["execution_time"] = self.execution_time
        return data


def normalize_name(name: str) -> str:
    """
    Normalize a name for matching:
    - Remove accents/diacritics
    - Convert to uppercase
    - Remove extra whitespace
    - Remove special characters

    Args:
        name: Full name to normalize

    Returns:
        str: Normalized name
    """
    if not name or pd.isna(name):
        return ""

    # Convert to string and strip
    name = str(name).strip()

    # Remove accents
    name = unidecode(name)

    # Convert to uppercase
    name = name.upper()

    # Remove special characters, keep only letters and spaces
    name = re.sub(r"[^A-Z\s]", "", name)

    # Remove extra whitespace
    name = re.sub(r"\s+", " ", name)

    return name.strip()


class LocalIngestionLoaderV2:
    """
    Enhanced loader for local filesystem-based ICE data ingestion.

    Handles real-world data structure:
    - Creates Person and Student records from CSV data
    - Matches documents to students by directory name
    - Handles various column name formats
    - Normalizes names for matching
    """

    # Column name mappings for different CSV formats
    COLUMN_MAPPINGS = {
        "full_name": [
            "NOMBRE COMPLETO",
            "Nombre Completo",
            "Name",
            "Full Name",
            "full_name",
            "fullname",
        ],
        "email": ["CORREO", "Correo", "Email", "E-mail", "email", "correo"],
        "phone": [
            "CELULAR",
            "Celular",
            "Teléfono",
            "Telefono",
            "Phone",
            "phone",
            "celular",
        ],
        "address": [
            "DIRECCION",
            "Dirección",
            "Direccion",
            "Address",
            "address",
            "direccion",
        ],
        "id_number": ["CEDULA", "Cédula", "Cedula", "ID", "id_number", "cedula"],
        "birth_date": [
            "FECHA DE NACIMIENTO",
            "Fecha de Nacimiento",
            "Birth Date",
            "birth_date",
        ],
        "program": ["PROGRAMA", "Programa", "Program", "program"],
    }

    def __init__(self, base_dir: str):
        """
        Initialize the local ingestion loader.

        Args:
            base_dir: Base directory containing data files and document folders
        """
        self.base_dir = Path(base_dir)

        # Initialize storage adapter
        self.storage_adapter = get_storage_adapter(
            "local", base_path=str(self.base_dir)
        )

        # Stats tracking
        self.stats = IngestionStats()

        # Name to UUID mapping (for matching documents to students)
        self.name_to_student_uuid: Dict[str, str] = {}

        logger.info(
            f"LocalIngestionLoaderV2 initialized with base_dir: {self.base_dir}"
        )

    def _find_column(self, df: pd.DataFrame, field_name: str) -> Optional[str]:
        """
        Find a column in the DataFrame using various name formats.

        Args:
            df: DataFrame to search
            field_name: Field name key (from COLUMN_MAPPINGS)

        Returns:
            Optional[str]: Column name if found, None otherwise
        """
        if field_name not in self.COLUMN_MAPPINGS:
            return None

        possible_names = self.COLUMN_MAPPINGS[field_name]

        for col_name in possible_names:
            if col_name in df.columns:
                return col_name

        return None

    def _extract_field_value(
        self, row: Dict, df: pd.DataFrame, field_name: str
    ) -> Optional[str]:
        """
        Extract a field value from a row using column mapping.

        Args:
            row: DataFrame row as dict
            df: Original DataFrame (for column lookup)
            field_name: Field name key

        Returns:
            Optional[str]: Field value or None
        """
        col_name = self._find_column(df, field_name)
        if not col_name:
            return None

        value = row.get(col_name)

        # Handle NaN and empty values
        if pd.isna(value) or value == "":
            return None

        return str(value).strip()

    def _parse_excel_csv(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        Parse Excel or CSV file into a DataFrame.

        Args:
            file_path: Path to the file

        Returns:
            Optional[pd.DataFrame]: Parsed data or None on error
        """
        try:
            if file_path.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
            elif file_path.suffix.lower() == ".csv":
                df = pd.read_csv(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_path}")
                return None

            logger.debug(f"Parsed {len(df)} rows from {file_path.name}")
            return df

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            self.stats.errors += 1
            return None

    def _scan_csv_files(self, directory: Path) -> List[Path]:
        """
        Recursively scan directory for CSV/Excel files.

        Args:
            directory: Directory to scan

        Returns:
            List[Path]: List of found files
        """
        files = []
        file_types = [".xlsx", ".xls", ".csv"]

        try:
            if not directory.exists():
                logger.warning(f"Directory does not exist: {directory}")
                return files

            # Recursive search
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in file_types:
                    files.append(file_path)
                    logger.debug(f"Found data file: {file_path.relative_to(directory)}")

            logger.info(f"Found {len(files)} data files in {directory}")

        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")

        return files

    def _scan_document_directories(self, base_path: Path) -> List[Tuple[str, Path]]:
        """
        Scan for directories containing student documents.
        Assumes directory names are student names.

        Args:
            base_path: Base path to scan

        Returns:
            List[Tuple[str, Path]]: List of (student_name, directory_path) tuples
        """
        student_dirs = []

        try:
            if not base_path.exists():
                logger.warning(f"Base path does not exist: {base_path}")
                return student_dirs

            # Look for directories (potential student folders)
            for item in base_path.rglob("*"):
                if item.is_dir():
                    # Check if directory contains documents
                    has_docs = any(f.is_file() for f in item.iterdir())

                    if has_docs:
                        # Use directory name as student name
                        student_name = item.name
                        student_dirs.append((student_name, item))
                        logger.debug(f"Found student directory: {student_name}")

            logger.info(f"Found {len(student_dirs)} student document directories")

        except Exception as e:
            logger.error(f"Error scanning document directories: {e}")

        return student_dirs

    def match_documents_to_students(
        self, student_dirs: List[Tuple[str, Path]]
    ) -> List[DocumentMetadata]:
        """
        Match documents to students by directory name.

        Args:
            student_dirs: List of (student_name, directory_path) tuples

        Returns:
            List[DocumentMetadata]: List of document metadata with matched student IDs
        """
        logger.info(
            f"Matching documents from {len(student_dirs)} directories to students..."
        )

        all_documents = []
        matched_count = 0
        unmatched_count = 0

        for student_name, doc_dir in student_dirs:
            normalized_name = normalize_name(student_name)

            # Try to match to student UUID
            student_id = self.name_to_student_uuid.get(normalized_name)

            if not student_id:
                logger.warning(
                    f"Could not match directory '{student_name}' to any student"
                )
                logger.debug(f"Normalized name: '{normalized_name}'")
                unmatched_count += 1
                continue

            # Scan documents in directory
            try:
                for doc_file in doc_dir.iterdir():
                    if not doc_file.is_file():
                        continue

                    # Create document metadata
                    doc_metadata = DocumentMetadata(
                        file_name=doc_file.name,
                        file_path=str(doc_file),
                        file_size=doc_file.stat().st_size,
                        mime_type=self._get_mime_type(doc_file),
                        document_type=self._infer_document_type(doc_file.name),
                        checksum=self._compute_checksum(doc_file),
                        student_id=student_id,
                    )

                    all_documents.append(doc_metadata)
                    self.stats.document_files += 1

                    logger.debug(f"Matched document: {doc_file.name} → {student_id}")

                matched_count += 1

            except Exception as e:
                logger.error(f"Error scanning documents in {doc_dir}: {e}")
                self.stats.errors += 1

        self.stats.documents_indexed = len(all_documents)

        logger.info(f"✔ Matched {matched_count} student directories")
        logger.info(f"✔ Found {len(all_documents)} total documents")

        if unmatched_count > 0:
            logger.warning(
                f"⚠ {unmatched_count} directories could not be matched to students"
            )

        return all_documents

    def _get_mime_type(self, file_path: Path) -> str:
        """
        Infer MIME type from file extension.

        Args:
            file_path: Path to the file

        Returns:
            str: MIME type
        """
        extension = file_path.suffix.lower()

        mime_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
        }

        return mime_types.get(extension, "application/octet-stream")

    def _compute_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """
        Compute file checksum.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm

        Returns:
            str: Hex digest of the file checksum
        """
        try:
            hash_func = hashlib.new(algorithm)

            with open(file_path, "rb") as f:
                # Read in chunks for memory efficiency
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)

            return hash_func.hexdigest()

        except Exception as e:
            logger.error(f"Error computing checksum for {file_path}: {e}")
            return ""

    def _infer_document_type(self, file_name: str) -> str:
        """
        Infer document type from filename.

        Args:
            file_name: Name of the file

        Returns:
            str: Document type
        """
        file_name_lower = file_name.lower()

        if any(keyword in file_name_lower for keyword in ["passport", "pasaporte"]):
            return "PASSPORT"
        elif any(keyword in file_name_lower for keyword in ["visa"]):
            return "VISA"
        elif any(
            keyword in file_name_lower
            for keyword in ["diploma", "certificate", "certificado"]
        ):
            return "DIPLOMA"
        elif any(
            keyword in file_name_lower for keyword in ["resume", "cv", "hoja de vida"]
        ):
            return "OTHER"
        elif any(keyword in file_name_lower for keyword in ["photo", "foto"]):
            return "PHOTO"
        elif any(keyword in file_name_lower for keyword in ["antecedentes"]):
            return "OTHER"
        else:
            return "OTHER"

    def create_students_from_directories(
        self, student_dirs: List[Tuple[str, Path]], program: str = "Unknown"
    ) -> List[Dict[str, Any]]:
        """
        Create Person and Student records from directory names.
        This is the PRIMARY source - directories define who the students are.

        Args:
            student_dirs: List of (student_name, directory_path) tuples
            program: Default program name

        Returns:
            List[Dict[str, Any]]: List of created student records
        """
        logger.info(
            f"Creating Person and Student records from {len(student_dirs)} directories..."
        )

        all_records = []

        for student_name, doc_dir in student_dirs:
            # Generate UUIDs
            person_id = str(uuid.uuid4())
            student_id = str(uuid.uuid4())

            # Normalize name for matching
            normalized_name = normalize_name(student_name)

            # Extract program from directory path if possible
            program_inferred = self._infer_program_from_path(doc_dir) or program

            # Create record
            record = {
                "person_id": person_id,
                "student_id": student_id,
                "full_name": student_name,
                "normalized_name": normalized_name,
                "email": None,  # Will be enriched from CSV if available
                "phone": None,  # Will be enriched from CSV if available
                "address": None,
                "id_number": None,
                "birth_date": None,
                "program": program_inferred,
                "source": "directory",
                "directory_path": str(doc_dir),
            }

            all_records.append(record)

            # Store in name mapping
            self.name_to_student_uuid[normalized_name] = student_id

            logger.debug(
                f"Created record from directory: {student_name} (student_id: {student_id})"
            )

        self.stats.person_records_created = len(all_records)
        self.stats.student_records_created = len(all_records)

        logger.info(
            f"✔ Created {len(all_records)} Person/Student records from directories"
        )

        return all_records

    def _infer_program_from_path(self, path: Path) -> Optional[str]:
        """
        Infer program name from directory path.

        Args:
            path: Directory path

        Returns:
            Optional[str]: Inferred program name
        """
        path_str = str(path).lower()

        if "au pair" in path_str or "aupair" in path_str:
            return "Au Pair"
        elif "wat" in path_str or "work and travel" in path_str:
            return "Work and Travel"
        elif "h2b" in path_str or "h-2b" in path_str:
            return "H-2B"
        elif "intern" in path_str or "trainee" in path_str:
            return "Intern & Trainee"
        elif "camp" in path_str or "counselor" in path_str:
            return "Camp Counselor"
        elif "canada" in path_str or "canadá" in path_str:
            return "Canada"
        else:
            return None

    def enrich_from_csv(
        self, student_records: List[Dict[str, Any]], csv_files: List[Path]
    ) -> int:
        """
        Enrich existing student records with data from CSV files.
        Matches by normalized name.

        Args:
            student_records: List of student records to enrich
            csv_files: List of CSV/Excel files to process

        Returns:
            int: Number of records enriched
        """
        if not csv_files:
            logger.info("No CSV files to enrich from")
            return 0

        logger.info(f"Enriching student records from {len(csv_files)} CSV files...")

        enriched_count = 0

        for csv_file in csv_files:
            try:
                df = self._parse_excel_csv(csv_file)

                if df is None or df.empty:
                    logger.warning(f"Skipping empty or invalid file: {csv_file.name}")
                    continue

                logger.info(f"Processing {len(df)} rows from {csv_file.name}")

                # Process each CSV row
                for idx, row in df.iterrows():
                    row_dict = row.to_dict()

                    # Extract name from CSV
                    full_name = self._extract_field_value(row_dict, df, "full_name")

                    if not full_name:
                        continue

                    normalized_csv_name = normalize_name(full_name)

                    # Find matching student record
                    matching_record = None
                    for record in student_records:
                        if record["normalized_name"] == normalized_csv_name:
                            matching_record = record
                            break

                    if not matching_record:
                        logger.debug(f"No directory match for CSV entry: {full_name}")
                        continue

                    # Enrich the record with CSV data
                    matching_record["email"] = self._extract_field_value(
                        row_dict, df, "email"
                    )
                    matching_record["phone"] = self._extract_field_value(
                        row_dict, df, "phone"
                    )
                    matching_record["address"] = self._extract_field_value(
                        row_dict, df, "address"
                    )
                    matching_record["id_number"] = self._extract_field_value(
                        row_dict, df, "id_number"
                    )

                    # Parse birth date
                    birth_date_str = self._extract_field_value(
                        row_dict, df, "birth_date"
                    )
                    if birth_date_str:
                        try:
                            matching_record["birth_date"] = pd.to_datetime(
                                birth_date_str
                            ).date()
                        except:
                            logger.warning(
                                f"Could not parse birth date: {birth_date_str}"
                            )

                    # Update program if available in CSV
                    program_csv = self._extract_field_value(row_dict, df, "program")
                    if program_csv:
                        matching_record["program"] = program_csv

                    matching_record["source"] = "directory+csv"
                    matching_record["csv_file"] = csv_file.name

                    enriched_count += 1
                    logger.debug(f"Enriched record: {full_name}")

                self.stats.csv_files_processed += 1

            except Exception as e:
                logger.error(f"Error processing CSV file {csv_file}: {e}")
                self.stats.errors += 1

        logger.info(f"✔ Enriched {enriched_count} student records with CSV data")

        return enriched_count

    def run_ingestion(
        self,
        csv_files: Optional[List[Path]] = None,
        document_dirs: Optional[List[Tuple[str, Path]]] = None,
        program: str = "Unknown",
    ) -> Dict[str, Any]:
        """
        Run the complete ingestion process.

        NEW APPROACH:
        1. Scan directories to find students (PRIMARY source)
        2. Optionally enrich with CSV data if available
        3. Match documents to students

        Args:
            csv_files: List of CSV files to process (auto-discovered if None)
            document_dirs: List of document directories (auto-discovered if None)
            program: Default program name

        Returns:
            Dict[str, Any]: Ingestion results including stats and data
        """
        self.stats.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("Starting Local ICE Data Ingestion (V2 - Directory-First)")
        logger.info("=" * 60)

        try:
            # Auto-discover document directories (PRIMARY source)
            if document_dirs is None:
                document_dirs = self._scan_document_directories(self.base_dir)

            # Auto-discover CSV files (OPTIONAL enrichment)
            if csv_files is None:
                csv_files = self._scan_csv_files(self.base_dir)

            # Step 1: Create Person and Student records from directories
            student_records = self.create_students_from_directories(
                document_dirs, program
            )

            # Step 2: Enrich with CSV data if available
            enriched_count = self.enrich_from_csv(student_records, csv_files)
            self.stats.records_enriched_from_csv = enriched_count

            # Step 3: Match documents to students
            documents = self.match_documents_to_students(document_dirs)

            self.stats.end_time = datetime.now()

            logger.info("=" * 60)
            logger.info("Ingestion Complete!")
            logger.info(f"Execution Time: {self.stats.execution_time:.2f}s")
            logger.info(f"Person Records Created: {self.stats.person_records_created}")
            logger.info(
                f"Student Records Created: {self.stats.student_records_created}"
            )
            logger.info(
                f"Records Enriched from CSV: {self.stats.records_enriched_from_csv}"
            )
            logger.info(f"Documents Indexed: {self.stats.documents_indexed}")
            logger.info(f"CSV Files Processed: {self.stats.csv_files_processed}")
            logger.info(f"Errors: {self.stats.errors}")
            logger.info("=" * 60)

            return {
                "success": True,
                "stats": self.stats.to_dict(),
                "student_records": student_records,
                "documents": [asdict(doc) for doc in documents],
            }

        except Exception as e:
            logger.error(f"Fatal error during ingestion: {e}")
            self.stats.end_time = datetime.now()
            self.stats.errors += 1

            return {
                "success": False,
                "error": str(e),
                "stats": self.stats.to_dict(),
            }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Example usage
    base_dir = "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001/Au Pair"

    loader = LocalIngestionLoaderV2(base_dir)

    # Specify CSV file explicitly
    csv_files = [
        Path(
            "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001/Au Pair/AU PAIR.xlsx"
        )
    ]

    # Run ingestion
    results = loader.run_ingestion(csv_files=csv_files, program="Au Pair")

    print("\n" + "=" * 60)
    print("Ingestion Results:")
    print(f"Success: {results['success']}")
    print(f"Person/Student Records: {len(results.get('student_records', []))}")
    print(f"Documents: {len(results.get('documents', []))}")
    print("=" * 60)
