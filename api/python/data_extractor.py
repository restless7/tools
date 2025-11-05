#!/usr/bin/env python3
"""
Data Extractor Module
Extracts and classifies ALL data from Excel/CSV files including:
- Student data (enrolled in programs)
- Lead data (prospects not yet enrolled)
- Reference data (metadata, lists, configurations)
"""

import os
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class DataClassifier:
    """
    Classifies Excel/CSV data into categories: STUDENT, LEAD, REFERENCE
    """
    
    # Keywords that indicate student data
    STUDENT_KEYWORDS = [
        'student', 'estudiante', 'participant', 'participante',
        'enrolled', 'inscrito', 'active', 'activo',
        'visa', 'passport', 'pasaporte', 'program'
    ]
    
    # Keywords that indicate lead data
    LEAD_KEYWORDS = [
        'lead', 'prospecto', 'inquiry', 'consulta',
        'interested', 'interesado', 'pending', 'pendiente',
        'contact', 'contacto'
    ]
    
    # Required columns for person data (name + contact)
    PERSON_REQUIRED = ['name', 'nombre', 'full_name', 'fullname']
    CONTACT_COLUMNS = ['email', 'correo', 'phone', 'celular', 'telefono']
    
    def __init__(self):
        self.classification_cache = {}
    
    def classify_file(self, file_path: Path, df: pd.DataFrame) -> str:
        """
        Classify the entire file based on filename and content.
        
        Returns:
            str: 'STUDENT', 'LEAD', or 'REFERENCE'
        """
        filename_lower = file_path.name.lower()
        columns_lower = [str(col).lower() for col in df.columns]
        
        # Check filename
        if any(kw in filename_lower for kw in self.STUDENT_KEYWORDS):
            return 'STUDENT'
        
        if any(kw in filename_lower for kw in self.LEAD_KEYWORDS):
            return 'LEAD'
        
        # Check column names
        has_person_data = any(
            any(req in col for req in self.PERSON_REQUIRED)
            for col in columns_lower
        )
        
        has_contact_data = any(
            any(contact in col for contact in self.CONTACT_COLUMNS)
            for col in columns_lower
        )
        
        # If has name + contact columns, likely person data
        if has_person_data and has_contact_data:
            # Check for student-specific columns
            student_indicators = ['program', 'visa', 'passport', 'status', 'enrolled']
            if any(indicator in ' '.join(columns_lower) for indicator in student_indicators):
                return 'STUDENT'
            else:
                return 'LEAD'
        
        # Default to reference if no person data
        return 'REFERENCE'
    
    def has_person_data(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame contains person/contact data."""
        columns_lower = [str(col).lower() for col in df.columns]
        
        has_name = any(
            any(req in col for req in self.PERSON_REQUIRED)
            for col in columns_lower
        )
        
        has_contact = any(
            any(contact in col for contact in self.CONTACT_COLUMNS)
            for col in columns_lower
        )
        
        return has_name or has_contact


class ExcelDataExtractor:
    """
    Comprehensive Excel/CSV data extractor.
    Converts all Excel files to CSV and extracts structured data.
    """
    
    def __init__(self, source_dir: str, output_dir: str):
        """
        Initialize extractor.
        
        Args:
            source_dir: Source directory with Excel/CSV files
            output_dir: Output directory for converted CSVs
        """
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.classifier = DataClassifier()
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'sheets_extracted': 0,
            'student_files': 0,
            'lead_files': 0,
            'reference_files': 0,
            'errors': 0,
        }
    
    def find_excel_files(self) -> List[Path]:
        """Find all Excel files recursively."""
        extensions = ['.xlsx', '.xls', '.csv']
        files = []
        
        for ext in extensions:
            files.extend(self.source_dir.rglob(f'*{ext}'))
        
        logger.info(f"Found {len(files)} Excel/CSV files")
        return files
    
    def convert_excel_to_csv(self, excel_path: Path) -> List[Tuple[Path, pd.DataFrame, Dict[str, Any]]]:
        """
        Convert Excel file to CSV(s) and return DataFrame(s) with metadata.
        
        Args:
            excel_path: Path to Excel file
            
        Returns:
            List of (csv_path, dataframe, metadata) tuples
        """
        results = []
        
        try:
            # Handle CSV files directly
            if excel_path.suffix.lower() == '.csv':
                df = pd.read_csv(excel_path)
                csv_path = self.output_dir / excel_path.name
                df.to_csv(csv_path, index=False)
                
                metadata = {
                    'source_file': str(excel_path),
                    'sheet_name': 'Sheet1',
                    'classification': self.classifier.classify_file(excel_path, df),
                    'row_count': len(df),
                    'column_count': len(df.columns),
                    'columns': list(df.columns),
                }
                
                results.append((csv_path, df, metadata))
                self.stats['sheets_extracted'] += 1
                
            # Handle Excel files with multiple sheets
            else:
                excel_file = pd.ExcelFile(excel_path)
                
                for sheet_name in excel_file.sheet_names:
                    try:
                        df = pd.read_excel(excel_path, sheet_name=sheet_name)
                        
                        # Skip empty sheets
                        if df.empty:
                            logger.debug(f"Skipping empty sheet: {sheet_name}")
                            continue
                        
                        # Create CSV filename
                        clean_sheet = re.sub(r'[^\w\s-]', '', sheet_name).strip()
                        clean_file = excel_path.stem
                        csv_filename = f"{clean_file}_{clean_sheet}.csv"
                        csv_path = self.output_dir / csv_filename
                        
                        # Save to CSV
                        df.to_csv(csv_path, index=False)
                        
                        metadata = {
                            'source_file': str(excel_path),
                            'sheet_name': sheet_name,
                            'classification': self.classifier.classify_file(excel_path, df),
                            'row_count': len(df),
                            'column_count': len(df.columns),
                            'columns': list(df.columns),
                        }
                        
                        results.append((csv_path, df, metadata))
                        self.stats['sheets_extracted'] += 1
                        
                        logger.debug(f"Extracted: {sheet_name} ({len(df)} rows)")
                        
                    except Exception as e:
                        logger.error(f"Error processing sheet '{sheet_name}': {e}")
                        self.stats['errors'] += 1
            
            self.stats['files_processed'] += 1
            
        except Exception as e:
            logger.error(f"Error processing file {excel_path}: {e}")
            self.stats['errors'] += 1
        
        return results
    
    def extract_all_data(self) -> Dict[str, List[Tuple[Path, pd.DataFrame, Dict[str, Any]]]]:
        """
        Extract all data from Excel files and classify.
        
        Returns:
            Dict with 'STUDENT', 'LEAD', 'REFERENCE' keys containing extracted data
        """
        logger.info("="*60)
        logger.info("Starting comprehensive data extraction...")
        logger.info("="*60)
        
        classified_data = {
            'STUDENT': [],
            'LEAD': [],
            'REFERENCE': [],
        }
        
        # Find all Excel files
        excel_files = self.find_excel_files()
        
        # Process each file
        for excel_path in excel_files:
            logger.info(f"Processing: {excel_path.relative_to(self.source_dir)}")
            
            results = self.convert_excel_to_csv(excel_path)
            
            # Classify and organize
            for csv_path, df, metadata in results:
                classification = metadata['classification']
                classified_data[classification].append((csv_path, df, metadata))
                
                # Update stats
                if classification == 'STUDENT':
                    self.stats['student_files'] += 1
                elif classification == 'LEAD':
                    self.stats['lead_files'] += 1
                else:
                    self.stats['reference_files'] += 1
        
        logger.info("="*60)
        logger.info("Data Extraction Complete!")
        logger.info(f"Files Processed: {self.stats['files_processed']}")
        logger.info(f"Sheets Extracted: {self.stats['sheets_extracted']}")
        logger.info(f"Student Files: {self.stats['student_files']}")
        logger.info(f"Lead Files: {self.stats['lead_files']}")
        logger.info(f"Reference Files: {self.stats['reference_files']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
        return classified_data
    
    def get_stats(self) -> Dict[str, int]:
        """Get extraction statistics."""
        return self.stats.copy()


def extract_and_classify_data(source_dir: str, output_dir: str) -> Dict[str, Any]:
    """
    Main function to extract and classify all data.
    
    Args:
        source_dir: Source directory with Excel files
        output_dir: Output directory for CSVs
        
    Returns:
        Dict with classified data and statistics
    """
    extractor = ExcelDataExtractor(source_dir, output_dir)
    classified_data = extractor.extract_all_data()
    stats = extractor.get_stats()
    
    return {
        'classified_data': classified_data,
        'stats': stats,
    }


if __name__ == '__main__':
    # Test extraction
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    source_dir = "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001"
    output_dir = "/home/sebastiangarcia/ice-data-staging/extracted_csvs"
    
    result = extract_and_classify_data(source_dir, output_dir)
    
    print(f"\n{'='*60}")
    print("Classification Summary:")
    print(f"{'='*60}")
    for category, data in result['classified_data'].items():
        print(f"{category}: {len(data)} files")
