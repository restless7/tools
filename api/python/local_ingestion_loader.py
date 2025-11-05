#!/usr/bin/env python3
"""
Local Ingestion Loader Module
Scans local filesystem directories for student/lead data and documents.
"""

import os
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging
from datetime import datetime

from storage_adapter import get_storage_adapter, DocumentMetadata

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Statistics from the ingestion process."""
    student_records: int = 0
    lead_records: int = 0
    document_files: int = 0
    student_files_processed: int = 0
    lead_files_processed: int = 0
    documents_indexed: int = 0
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
        data['execution_time'] = self.execution_time
        return data


class LocalIngestionLoader:
    """
    Loader for local filesystem-based ICE data ingestion.
    
    Scans directories for:
    - Student data (Excel/CSV files in students/)
    - Lead data (Excel/CSV files in leads/)
    - Document files (in documents/<student_id>/)
    """
    
    def __init__(self, base_dir: str):
        """
        Initialize the local ingestion loader.
        
        Args:
            base_dir: Base directory containing leads/, students/, documents/
        """
        self.base_dir = Path(base_dir)
        self.leads_dir = self.base_dir / 'leads'
        self.students_dir = self.base_dir / 'students'
        self.documents_dir = self.base_dir / 'documents'
        
        # Initialize storage adapter
        self.storage_adapter = get_storage_adapter('local', base_path=str(self.base_dir))
        
        # Stats tracking
        self.stats = IngestionStats()
        
        logger.info(f"LocalIngestionLoader initialized with base_dir: {self.base_dir}")
    
    def validate_directory_structure(self) -> bool:
        """
        Validate that the required directory structure exists.
        
        Returns:
            bool: True if structure is valid
        """
        try:
            if not self.base_dir.exists():
                logger.error(f"Base directory does not exist: {self.base_dir}")
                return False
            
            # Check for required subdirectories
            required_dirs = {
                'leads': self.leads_dir,
                'students': self.students_dir,
                'documents': self.documents_dir
            }
            
            missing_dirs = []
            for name, path in required_dirs.items():
                if not path.exists():
                    logger.warning(f"Directory does not exist: {path}")
                    missing_dirs.append(name)
            
            if missing_dirs:
                logger.warning(f"Missing directories: {', '.join(missing_dirs)}")
                logger.info("Will attempt to create missing directories...")
                
                for name in missing_dirs:
                    path = required_dirs[name]
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {path}")
            
            logger.info("✔ Directory structure validated")
            return True
            
        except Exception as e:
            logger.error(f"Error validating directory structure: {e}")
            return False
    
    def _scan_data_files(self, directory: Path, file_types: List[str] = None) -> List[Path]:
        """
        Scan a directory for data files (Excel, CSV).
        
        Args:
            directory: Directory to scan
            file_types: List of file extensions to look for
            
        Returns:
            List[Path]: List of found files
        """
        if file_types is None:
            file_types = ['.xlsx', '.xls', '.csv']
        
        files = []
        
        try:
            if not directory.exists():
                logger.warning(f"Directory does not exist: {directory}")
                return files
            
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in file_types:
                    files.append(file_path)
                    logger.debug(f"Found data file: {file_path.name}")
            
            logger.info(f"Found {len(files)} data files in {directory.name}/")
            
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return files
    
    def _parse_excel_csv(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        Parse Excel or CSV file into a DataFrame.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Optional[pd.DataFrame]: Parsed data or None on error
        """
        try:
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_path.suffix.lower() == '.csv':
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
    
    def load_student_data(self) -> List[Dict[str, Any]]:
        """
        Load student data from students/ directory.
        
        Returns:
            List[Dict[str, Any]]: List of student records
        """
        logger.info("Loading student data...")
        student_records = []
        
        try:
            student_files = self._scan_data_files(self.students_dir)
            
            for file_path in student_files:
                df = self._parse_excel_csv(file_path)
                
                if df is not None:
                    # Convert DataFrame to list of dicts
                    records = df.to_dict('records')
                    student_records.extend(records)
                    self.stats.student_files_processed += 1
                    logger.info(f"Loaded {len(records)} student records from {file_path.name}")
            
            self.stats.student_records = len(student_records)
            logger.info(f"✔ Loaded {len(student_records)} total student records from {self.stats.student_files_processed} files")
            
        except Exception as e:
            logger.error(f"Error loading student data: {e}")
            self.stats.errors += 1
        
        return student_records
    
    def load_lead_data(self) -> List[Dict[str, Any]]:
        """
        Load lead data from leads/ directory.
        
        Returns:
            List[Dict[str, Any]]: List of lead records
        """
        logger.info("Loading lead data...")
        lead_records = []
        
        try:
            lead_files = self._scan_data_files(self.leads_dir)
            
            for file_path in lead_files:
                df = self._parse_excel_csv(file_path)
                
                if df is not None:
                    # Convert DataFrame to list of dicts
                    records = df.to_dict('records')
                    lead_records.extend(records)
                    self.stats.lead_files_processed += 1
                    logger.info(f"Loaded {len(records)} lead records from {file_path.name}")
            
            self.stats.lead_records = len(lead_records)
            logger.info(f"✔ Loaded {len(lead_records)} total lead records from {self.stats.lead_files_processed} files")
            
        except Exception as e:
            logger.error(f"Error loading lead data: {e}")
            self.stats.errors += 1
        
        return lead_records
    
    def scan_document_files(self) -> List[DocumentMetadata]:
        """
        Scan documents/ directory for student documents.
        
        Expected structure: documents/<student_id>/<files>
        
        Returns:
            List[DocumentMetadata]: List of document metadata
        """
        logger.info("Scanning document files...")
        document_metadata_list = []
        
        try:
            if not self.documents_dir.exists():
                logger.warning(f"Documents directory does not exist: {self.documents_dir}")
                return document_metadata_list
            
            # Iterate through student directories
            for student_dir in self.documents_dir.iterdir():
                if not student_dir.is_dir():
                    continue
                
                student_id = student_dir.name
                logger.debug(f"Scanning documents for student: {student_id}")
                
                # Scan all files in student directory
                for file_path in student_dir.iterdir():
                    if not file_path.is_file():
                        continue
                    
                    try:
                        # Extract metadata using storage adapter
                        metadata = self.storage_adapter.get_metadata(
                            str(file_path),
                            student_id=student_id
                        )
                        
                        document_metadata_list.append(metadata)
                        self.stats.document_files += 1
                        
                        logger.debug(
                            f"Indexed document: {file_path.name} "
                            f"(type: {metadata.document_type}, size: {metadata.file_size} bytes)"
                        )
                        
                    except Exception as e:
                        logger.error(f"Error extracting metadata from {file_path}: {e}")
                        self.stats.errors += 1
            
            logger.info(f"✔ Indexed {len(document_metadata_list)} document files")
            
        except Exception as e:
            logger.error(f"Error scanning document files: {e}")
            self.stats.errors += 1
        
        return document_metadata_list
    
    def load_all_data(self) -> Dict[str, Any]:
        """
        Load all data from local filesystem.
        
        Returns:
            Dict[str, Any]: Dictionary containing all loaded data
        """
        self.stats.start_time = datetime.now()
        
        logger.info("=" * 80)
        logger.info("Starting Local ICE Data Ingestion")
        logger.info("=" * 80)
        
        # Validate directory structure
        if not self.validate_directory_structure():
            logger.error("Directory validation failed")
            return {
                'success': False,
                'error': 'Directory structure validation failed',
                'stats': self.stats.to_dict()
            }
        
        # Load data
        student_records = self.load_student_data()
        lead_records = self.load_lead_data()
        document_metadata = self.scan_document_files()
        
        self.stats.end_time = datetime.now()
        
        # Generate report
        logger.info("=" * 80)
        logger.info("Ingestion Complete - Summary")
        logger.info("=" * 80)
        logger.info(f"✔ Found {self.stats.student_records} student records from {self.stats.student_files_processed} files")
        logger.info(f"✔ Found {self.stats.lead_records} lead records from {self.stats.lead_files_processed} files")
        logger.info(f"✔ Indexed {self.stats.document_files} document files")
        logger.info(f"⏱ Completed in {self.stats.execution_time:.2f} seconds")
        
        if self.stats.errors > 0:
            logger.warning(f"⚠ {self.stats.errors} errors occurred during ingestion")
        
        return {
            'success': True,
            'student_records': student_records,
            'lead_records': lead_records,
            'document_metadata': document_metadata,
            'stats': self.stats.to_dict()
        }


def run_local_ingestion(base_dir: str) -> Dict[str, Any]:
    """
    Convenience function to run local ingestion.
    
    Args:
        base_dir: Base directory for ingestion
        
    Returns:
        Dict[str, Any]: Ingestion results
    """
    loader = LocalIngestionLoader(base_dir)
    return loader.load_all_data()


if __name__ == '__main__':
    # Test the loader
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_base_dir = '/mnt/ice-ingestion-data'
    
    print(f"Testing LocalIngestionLoader with base_dir: {test_base_dir}")
    
    result = run_local_ingestion(test_base_dir)
    
    if result['success']:
        print("\n✅ Local ingestion test completed successfully")
        print(f"\nStatistics: {result['stats']}")
    else:
        print("\n❌ Local ingestion test failed")
        print(f"Error: {result.get('error')}")
