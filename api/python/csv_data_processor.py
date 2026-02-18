#!/usr/bin/env python3
"""
CSV Data Processor
Processes extracted CSV data to identify and create person records for:
- Students (enrolled in programs)
- Leads (prospects/interested persons)
"""

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from unidecode import unidecode

logger = logging.getLogger(__name__)


class PersonDataProcessor:
    """
    Processes CSV data to extract person information.
    Handles both students and leads.
    """

    # Column mappings (Spanish/English variations) - Enhanced with more cases
    COLUMN_MAPPINGS = {
        "full_name": [
            "NOMBRE COMPLETO",
            "Nombre Completo",
            "nombre completo",
            "Name",
            "Full Name",
            "FULL NAME",
            "full name",
            "NOMBRE",
            "Nombre",
            "nombre",
            "NAME",
            "name",
        ],
        "email": [
            "CORREO",
            "Correo",
            "correo",
            "EMAIL",
            "Email",
            "email",
            "E-mail",
            "e-mail",
            "E-MAIL",
            "Correo electrónico",
            "Correo electronico",
            "CORREO ELECTRONICO",
            "correo electronico",
            "correo electrónico",
        ],
        "phone": [
            "CELULAR",
            "Celular",
            "celular",
            "CEL",
            "Cel",
            "cel",
            "TELEFONO",
            "Teléfono",
            "Telefono",
            "telefono",
            "teléfono",
            "PHONE",
            "Phone",
            "phone",
            "MOVIL",
            "Móvil",
            "Movil",
            "movil",
            "móvil",
            "TEL",
            "Tel",
            "tel",
        ],
        "address": [
            "DIRECCION",
            "Dirección",
            "Direccion",
            "direccion",
            "dirección",
            "ADDRESS",
            "Address",
            "address",
        ],
        "cedula": [
            "CEDULA",
            "Cédula",
            "Cedula",
            "cedula",
            "cédula",
            "ID",
            "id",
            "CC",
            "cc",
            "Document ID",
            "DOCUMENT ID",
        ],
        "birth_date": [
            "FECHA DE NACIMIENTO",
            "Fecha de Nacimiento",
            "fecha de nacimiento",
            "FECHA NACIMIENTO",
            "Fecha Nacimiento",
            "fecha nacimiento",
            "Birth Date",
            "BIRTH DATE",
            "birth date",
            "Birthday",
            "BIRTHDAY",
            "birthday",
            "Nacimiento",
            "NACIMIENTO",
            "nacimiento",
        ],
        "country": [
            "PAIS",
            "País",
            "Pais",
            "pais",
            "país",
            "COUNTRY",
            "Country",
            "country",
        ],
        "city": ["CIUDAD", "Ciudad", "ciudad", "CITY", "City", "city"],
    }

    # Status indicators for students vs leads
    ENROLLED_KEYWORDS = [
        "inscrito",
        "inscrita",
        "enrolled",
        "active",
        "activo",
        "contrato",
    ]
    INTERESTED_KEYWORDS = [
        "interesada",
        "interesado",
        "interested",
        "prospecto",
        "lead",
    ]

    def __init__(self):
        self.processed_persons = {}  # Cache by (name, email) tuple

    def normalize_name(self, name: str) -> str:
        """Normalize person name."""
        if pd.isna(name) or not str(name).strip():
            return ""

        # Remove accents
        name = unidecode(str(name))

        # Uppercase and clean
        name = name.upper().strip()

        # Remove extra spaces
        name = " ".join(name.split())

        # Remove special characters except spaces and hyphens
        name = re.sub(r"[^A-Z\s-]", "", name)

        return name

    def find_column(self, df: pd.DataFrame, field_name: str) -> Optional[str]:
        """Find column name for a given field with enhanced normalization."""
        possible_names = self.COLUMN_MAPPINGS.get(field_name, [])

        # Normalize column names: strip whitespace, lowercase, remove accents
        columns_normalized = {}
        for col in df.columns:
            # Strip whitespace and normalize
            normalized = str(col).strip().lower()
            normalized = unidecode(normalized)  # Remove accents
            columns_normalized[normalized] = col

        # Try to match with normalization
        for possible_name in possible_names:
            normalized_search = unidecode(possible_name.lower().strip())
            if normalized_search in columns_normalized:
                return columns_normalized[normalized_search]

        return None

    def extract_persons_from_csv(
        self, df: pd.DataFrame, source_file: str, sheet_name: str, classification: str
    ) -> List[Dict[str, Any]]:
        """
        Extract person records from DataFrame.

        Args:
            df: Pandas DataFrame
            source_file: Source file path
            sheet_name: Sheet name
            classification: 'STUDENT' or 'LEAD'

        Returns:
            List of person dictionaries
        """
        persons = []

        # Find relevant columns
        name_col = self.find_column(df, "full_name")
        email_col = self.find_column(df, "email")
        phone_col = self.find_column(df, "phone")
        address_col = self.find_column(df, "address")
        cedula_col = self.find_column(df, "cedula")
        birth_col = self.find_column(df, "birth_date")
        country_col = self.find_column(df, "country")
        city_col = self.find_column(df, "city")

        if not name_col:
            logger.warning(f"No name column found in {source_file}/{sheet_name}")
            return persons

        # Process each row
        for idx, row in df.iterrows():
            try:
                # Extract name
                name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None

                if not name or name == "nan":
                    continue

                # Normalize name
                normalized_name = self.normalize_name(name)

                # Relaxed name filtering: allow 2+ characters
                if not normalized_name or len(normalized_name) < 2:
                    continue

                # Extract other fields
                email = (
                    str(row[email_col]).strip().lower()
                    if email_col and pd.notna(row[email_col])
                    else None
                )
                phone = (
                    str(row[phone_col]).strip()
                    if phone_col and pd.notna(row[phone_col])
                    else None
                )
                address = (
                    str(row[address_col]).strip()
                    if address_col and pd.notna(row[address_col])
                    else None
                )
                cedula = (
                    str(row[cedula_col]).strip()
                    if cedula_col and pd.notna(row[cedula_col])
                    else None
                )
                birth_date = (
                    row[birth_col] if birth_col and pd.notna(row[birth_col]) else None
                )
                country = (
                    str(row[country_col]).strip()
                    if country_col and pd.notna(row[country_col])
                    else None
                )
                city = (
                    str(row[city_col]).strip()
                    if city_col and pd.notna(row[city_col])
                    else None
                )

                # Clean email
                if email and (email == "nan" or "@" not in email):
                    email = None

                # Clean phone
                if phone and (phone == "nan" or len(phone) < 7):
                    phone = None

                # Determine program from sheet name
                program = self._extract_program_from_sheet(sheet_name)

                # Determine status from sheet name
                status = self._determine_status_from_sheet(sheet_name, classification)

                # Better deduplication: use cedula first, then email, then name+phone
                person_key = None

                # Priority 1: Cedula (most unique)
                if cedula:
                    person_key = ("cedula", cedula)
                # Priority 2: Email
                elif email:
                    person_key = ("email", email)
                # Priority 3: Name + Phone
                elif phone:
                    person_key = ("name_phone", normalized_name, phone)
                # Priority 4: Name only (creates more duplicates, but captures lead)
                else:
                    person_key = ("name_only", normalized_name)

                if person_key not in self.processed_persons:
                    person_id = str(uuid.uuid4())

                    person = {
                        "id": person_id,
                        "full_name": normalized_name,
                        "original_name": name,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "cedula": cedula,
                        "birth_date": birth_date,
                        "country": country,
                        "city": city,
                        "source_file": source_file,
                        "source_sheet": sheet_name,
                        "classification": classification,
                        "status": status,
                        "program": program,
                        "row_index": idx,
                    }

                    self.processed_persons[person_key] = person
                    persons.append(person)

                else:
                    # Update existing person with additional info
                    existing = self.processed_persons[person_key]
                    if not existing.get("email") and email:
                        existing["email"] = email
                    if not existing.get("phone") and phone:
                        existing["phone"] = phone
                    if not existing.get("address") and address:
                        existing["address"] = address
                    if not existing.get("cedula") and cedula:
                        existing["cedula"] = cedula
                    if not existing.get("birth_date") and birth_date:
                        existing["birth_date"] = birth_date

            except Exception as e:
                logger.error(
                    f"Error processing row {idx} in {source_file}/{sheet_name}: {e}"
                )
                continue

        return persons

    def _extract_program_from_sheet(self, sheet_name: str) -> Optional[str]:
        """Extract program name from sheet name."""
        sheet_lower = sheet_name.lower()

        programs = {
            "au pair": "Au Pair",
            "camp": "Camp Counselor",
            "work and travel": "Work and Travel",
            "h2b": "H-2B",
            "h-2b": "H-2B",
            "intern": "Intern & Trainee",
            "trainee": "Intern & Trainee",
            "canada": "Canada",
        }

        for key, value in programs.items():
            if key in sheet_lower:
                return value

        return None

    def _determine_status_from_sheet(self, sheet_name: str, classification: str) -> str:
        """Determine person status from sheet name."""
        sheet_lower = sheet_name.lower()

        # Check for enrolled/registered
        if any(
            kw in sheet_lower
            for kw in ["inscrita", "inscrito", "registered", "enrolled", "active"]
        ):
            return "ENROLLED"

        # Check for interested/lead
        if any(
            kw in sheet_lower
            for kw in ["interesada", "interesado", "interested", "lead", "prospecto"]
        ):
            return "INTERESTED"

        # Check for cancelled
        if any(kw in sheet_lower for kw in ["cancelad", "cancelled", "lost"]):
            return "CANCELLED"

        # Check for scheduled
        if any(kw in sheet_lower for kw in ["agendad", "scheduled"]):
            return "SCHEDULED"

        # Default based on classification
        if classification == "STUDENT":
            return "ENROLLED"
        else:
            return "NEW"

    def get_all_processed_persons(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all processed persons categorized by status.

        Returns:
            Dict with 'students' and 'leads' keys
        """
        students = []
        leads = []

        for person in self.processed_persons.values():
            if person["status"] in ["ENROLLED", "SCHEDULED"] and person.get("program"):
                students.append(person)
            else:
                leads.append(person)

        return {
            "students": students,
            "leads": leads,
        }


def process_classified_data(
    classified_data: Dict[str, List[Tuple[Path, pd.DataFrame, Dict[str, Any]]]],
) -> Dict[str, Any]:
    """
    Process all classified data and extract person records.

    Args:
        classified_data: Output from ExcelDataExtractor

    Returns:
        Dict with students, leads, and statistics
    """
    logger.info("=" * 60)
    logger.info("Processing extracted CSV data...")
    logger.info("=" * 60)

    processor = PersonDataProcessor()

    all_students = []
    all_leads = []
    reference_files = []

    # Process STUDENT files
    for csv_path, df, metadata in classified_data.get("STUDENT", []):
        logger.info(f"Processing STUDENT file: {metadata['sheet_name']}")

        persons = processor.extract_persons_from_csv(
            df, metadata["source_file"], metadata["sheet_name"], "STUDENT"
        )

        all_students.extend(persons)
        logger.info(f"  → Extracted {len(persons)} persons")

    # Process LEAD files
    for csv_path, df, metadata in classified_data.get("LEAD", []):
        logger.info(f"Processing LEAD file: {metadata['sheet_name']}")

        persons = processor.extract_persons_from_csv(
            df, metadata["source_file"], metadata["sheet_name"], "LEAD"
        )

        all_leads.extend(persons)
        logger.info(f"  → Extracted {len(persons)} persons")

    # Store reference files metadata
    for csv_path, df, metadata in classified_data.get("REFERENCE", []):
        reference_files.append(
            {
                "csv_path": str(csv_path),
                "source_file": metadata["source_file"],
                "sheet_name": metadata["sheet_name"],
                "row_count": metadata["row_count"],
                "column_count": metadata["column_count"],
                "columns": metadata["columns"],
            }
        )

    # Get deduplicated persons
    categorized = processor.get_all_processed_persons()

    logger.info("=" * 60)
    logger.info("CSV Processing Complete!")
    logger.info(f"Total Students Found: {len(categorized['students'])}")
    logger.info(f"Total Leads Found: {len(categorized['leads'])}")
    logger.info(f"Reference Files: {len(reference_files)}")
    logger.info("=" * 60)

    return {
        "students": categorized["students"],
        "leads": categorized["leads"],
        "reference_files": reference_files,
        "stats": {
            "total_students": len(categorized["students"]),
            "total_leads": len(categorized["leads"]),
            "total_reference_files": len(reference_files),
        },
    }


if __name__ == "__main__":
    # Test processing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Import extractor
    from data_extractor import extract_and_classify_data

    source_dir = "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001"
    output_dir = "/home/sebastiangarcia/ice-data-staging/extracted_csvs"

    # Extract data
    extraction_result = extract_and_classify_data(source_dir, output_dir)

    # Process data
    processing_result = process_classified_data(extraction_result["classified_data"])

    print(f"\n{'='*60}")
    print("Final Summary:")
    print(f"{'='*60}")
    print(f"Students: {processing_result['stats']['total_students']}")
    print(f"Leads: {processing_result['stats']['total_leads']}")
    print(f"Reference Files: {processing_result['stats']['total_reference_files']}")

    # Show sample students
    if processing_result["students"]:
        print(f"\nSample Students:")
        for student in processing_result["students"][:5]:
            print(f"  - {student['full_name']} ({student.get('program', 'Unknown')})")

    # Show sample leads
    if processing_result["leads"]:
        print(f"\nSample Leads:")
        for lead in processing_result["leads"][:5]:
            print(f"  - {lead['full_name']} (Status: {lead['status']})")
