#!/usr/bin/env python3
"""
Database Utilities for ICE Ingestion
Handles database operations with idempotency checks.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import asdict

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from contextlib import contextmanager

from storage_adapter import DocumentMetadata

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database operations for ICE ingestion.
    
    Handles:
    - Student and lead data insertion
    - Document metadata storage with idempotency
    - ETL logging
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided and not found in environment")
        
        logger.info("DatabaseManager initialized")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        
        Yields:
            psycopg2.connection: Database connection
        """
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            bool: True if connection successful
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    logger.info("Database connection successful")
                    return result[0] == 1
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def ensure_tables_exist(self):
        """
        Verify that required tables exist in the database.
        Note: All tables are managed by Prisma schema.
        """
        logger.info("Using existing Prisma schema tables (student_documents, etl_logs)")
    
    def check_document_exists(self, student_id: str, object_key: str) -> Optional[str]:
        """
        Check if a document already exists based on student_id and object_key.
        
        Args:
            student_id: Student UUID
            object_key: MinIO object key (unique identifier)
            
        Returns:
            Optional[str]: Document UUID if exists, None otherwise
        """
        query = """
            SELECT id FROM student_documents 
            WHERE student_id = %s AND object_key = %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (student_id, object_key))
                    result = cursor.fetchone()
                    
                    if result:
                        logger.debug(f"Document already exists: student_id={student_id}, id={result[0]}")
                        return str(result[0])  # Return UUID as string
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Error checking document existence: {e}")
            raise
    
    def insert_document_metadata(
        self, 
        metadata: DocumentMetadata,
        storage_provider: str = 'LOCAL',
        bucket: str = 'apex-ice-docs',
        skip_duplicates: bool = True
    ) -> Optional[str]:
        """
        Insert document metadata into the database using Prisma schema.
        
        Args:
            metadata: Document metadata
            storage_provider: Storage type (LOCAL, MINIO, GDRIVE)
            bucket: MinIO bucket name
            skip_duplicates: If True, skip documents that already exist
            
        Returns:
            Optional[str]: Inserted document UUID or None if skipped
        """
        if not metadata.student_id:
            logger.warning(f"Skipping document without student_id: {metadata.file_name}")
            return None
        
        # Generate object_key from file_path (use checksum for uniqueness)
        object_key = f"{metadata.student_id}/{metadata.document_type}/{metadata.checksum[:12]}-{metadata.file_name}"
        
        # Check for duplicates
        if skip_duplicates:
            existing_id = self.check_document_exists(metadata.student_id, object_key)
            if existing_id:
                logger.debug(f"Skipping duplicate document: {metadata.file_name}")
                return existing_id
        
        # Insert using Prisma schema columns
        insert_query = """
            INSERT INTO student_documents (
                id, student_id, document_type, file_name, object_key,
                bucket, file_size, mime_type, storage_provider, status,
                uploaded_at, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, 
                %s, %s, %s, %s, %s,
                NOW(), 1, NOW(), NOW()
            )
            RETURNING id
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        insert_query,
                        (
                            metadata.student_id,
                            metadata.document_type,
                            metadata.file_name,
                            object_key,
                            bucket,
                            metadata.file_size,
                            metadata.mime_type,
                            storage_provider,
                            'PENDING'
                        )
                    )
                    
                    result = cursor.fetchone()
                    if result:
                        document_id = str(result[0])  # Return UUID as string
                        logger.debug(f"Inserted document metadata: id={document_id}, file={metadata.file_name}")
                        return document_id
                    else:
                        logger.debug(f"Document already exists (conflict): {metadata.file_name}")
                        return None
                    
        except Exception as e:
            logger.error(f"Error inserting document metadata: {e}")
            raise
    
    def bulk_insert_document_metadata(
        self,
        metadata_list: List[DocumentMetadata],
        storage_provider: str = 'LOCAL',
        bucket: str = 'apex-ice-docs',
        skip_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Bulk insert document metadata.
        
        Args:
            metadata_list: List of document metadata
            storage_provider: Storage type (LOCAL, MINIO, GDRIVE)
            bucket: MinIO bucket name
            skip_duplicates: If True, skip documents that already exist
            
        Returns:
            Dict[str, Any]: Insertion results with counts
        """
        results = {
            'inserted': 0,
            'skipped': 0,
            'errors': 0,
            'total': len(metadata_list)
        }
        
        for metadata in metadata_list:
            try:
                doc_id = self.insert_document_metadata(
                    metadata, 
                    storage_provider=storage_provider,
                    bucket=bucket,
                    skip_duplicates=skip_duplicates
                )
                if doc_id:
                    results['inserted'] += 1
                else:
                    results['skipped'] += 1
            except Exception as e:
                logger.error(f"Error inserting document {metadata.file_name}: {e}")
                results['errors'] += 1
        
        logger.info(
            f"Bulk insert complete: {results['inserted']} inserted, "
            f"{results['skipped']} skipped, {results['errors']} errors"
        )
        
        return results
    
    def log_etl_run(
        self,
        ingestion_mode: str,
        source_path: str,
        stats: Dict[str, Any],
        status: str = 'SUCCESS',
        error_message: Optional[str] = None
    ) -> str:
        """
        Log an ETL ingestion run.
        
        Args:
            ingestion_mode: Mode of ingestion (local, remote, etc.)
            source_path: Source path for data
            stats: Statistics dictionary
            status: Run status (SUCCESS, ERROR, etc.)
            error_message: Error message if any
            
        Returns:
            str: ETL log UUID
        """
        # Use Prisma schema: id, process_name, status, records_count, error_message, started_at, completed_at, created_at
        insert_query = """
            INSERT INTO etl_logs (
                id, process_name, status, records_count,
                error_message, started_at, completed_at, created_at
            ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        try:
            # Calculate total records for Prisma schema
            records_count = (
                stats.get('student_records', 0) + 
                stats.get('lead_records', 0) + 
                stats.get('document_files', 0)
            )
            process_name = f"ICE_LOCAL_INGESTION_{ingestion_mode.upper()}"
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        insert_query,
                        (
                            process_name,
                            status,
                            records_count,
                            error_message,
                            stats.get('start_time'),
                            stats.get('end_time')
                        )
                    )
                    
                    result = cursor.fetchone()
                    log_id = str(result[0])  # Return UUID as string
                    
                    logger.info(f"ETL run logged: id={log_id}, status={status}")
                    return log_id
                    
        except Exception as e:
            logger.error(f"Error logging ETL run: {e}")
            raise
    
    def get_recent_etl_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent ETL logs.
        
        Args:
            limit: Number of logs to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of ETL log records
        """
        query = """
            SELECT * FROM etl_logs
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (limit,))
                    logs = cursor.fetchall()
                    return [dict(log) for log in logs]
                    
        except Exception as e:
            logger.error(f"Error retrieving ETL logs: {e}")
            raise
    
    def get_document_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored documents.
        
        Returns:
            Dict[str, Any]: Document statistics
        """
        query = """
            SELECT 
                COUNT(*) as total_documents,
                COUNT(DISTINCT student_id) as unique_students,
                SUM(file_size) as total_size,
                status,
                document_type
            FROM student_documents
            GROUP BY status, document_type
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    
                    stats = {
                        'by_status_type': [dict(row) for row in results],
                        'overall': {}
                    }
                    
                    # Get overall stats
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_documents,
                            COUNT(DISTINCT student_id) as unique_students,
                            SUM(file_size) as total_size
                        FROM student_documents
                    """)
                    
                    overall = cursor.fetchone()
                    stats['overall'] = dict(overall) if overall else {}
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"Error getting document stats: {e}")
            raise


if __name__ == '__main__':
    # Test the database manager
    logging.basicConfig(level=logging.INFO)
    
    try:
        db = DatabaseManager()
        
        print("Testing database connection...")
        if db.test_connection():
            print("✅ Database connection successful")
            
            print("\nEnsuring tables exist...")
            db.ensure_tables_exist()
            print("✅ Tables verified/created")
            
            print("\nGetting document stats...")
            stats = db.get_document_stats()
            print(f"Document stats: {stats}")
            
        else:
            print("❌ Database connection failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
