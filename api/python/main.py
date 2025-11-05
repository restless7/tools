#!/usr/bin/env python3
"""
Enterprise Tools Platform - Python Backend
FastAPI application for processing Excel files, CSV conversion, and ICE database ingestion
"""

import os, io, json, logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PlanMaestro Tools API",
    description="Enterprise tools platform for Excel processing, CSV conversion, and data pipeline management",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3005", "http://localhost:3004", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class ConversionRequest(BaseModel):
    filename: str
    options: Dict[str, Any] = {}

class ConversionResult(BaseModel):
    success: bool
    filename: str
    sheets_processed: int
    files_created: List[str]
    message: str
    processing_time: float

class ICEIngestionRequest(BaseModel):
    folder_id: Optional[str] = None
    force_reprocess: bool = False

class ICEIngestionResult(BaseModel):
    success: bool
    files_processed: int
    total_rows: int
    message: str
    processing_time: float

# Storage directories
UPLOAD_DIR = Path("/tmp/tools_uploads")
OUTPUT_DIR = Path("/tmp/tools_output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

@app.get("/")
async def root():
    return {
        "message": "PlanMaestro Tools API",
        "version": "1.0.0",
        "endpoints": [
            "/excel/convert",
            "/excel/sheets",
            "/ice/ingest",
            "/health"
        ]
    }

@app.get("/health")
async def health_check():
    # Check ICE V3 system status
    ice_status = "active"  # V3 system is production-ready
    try:
        # Verify V3 script exists
        from pathlib import Path
        v3_script = Path(__file__).parent / "ingestion_to_staging_v3.py"
        if not v3_script.exists():
            ice_status = "maintenance"
    except Exception as e:
        logger.warning(f"ICE V3 status check failed: {e}")
        ice_status = "maintenance"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "excel_converter": "active",
            "ice_ingestion_v3": ice_status,
            "staging_cleanup": "active"
        },
        "version": "1.1.0 - V3 Enhanced"
    }

@app.post("/excel/convert", response_model=ConversionResult)
async def convert_excel_to_csv(file: UploadFile = File(...)):
    """
    Convert an Excel file with multiple sheets to separate CSV files
    """
    start_time = datetime.now()
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process Excel file
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
        created_files = []
        
        logger.info(f"Processing {file.filename} with {len(sheet_names)} sheets")
        
        for sheet_name in sheet_names:
            try:
                # Read sheet
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Clean sheet name for filename
                clean_sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                csv_filename = f"{Path(file.filename).stem}_{clean_sheet_name}.csv"
                csv_path = OUTPUT_DIR / csv_filename
                
                # Convert to CSV
                df.to_csv(csv_path, index=False, encoding='utf-8')
                created_files.append(csv_filename)
                
                logger.info(f"Created CSV: {csv_filename} with {len(df)} rows")
                
            except Exception as e:
                logger.error(f"Error processing sheet '{sheet_name}': {str(e)}")
                continue
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Clean up uploaded file
        file_path.unlink()
        
        return ConversionResult(
            success=True,
            filename=file.filename,
            sheets_processed=len(created_files),
            files_created=created_files,
            message=f"Successfully converted {len(created_files)} sheets to CSV",
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Error converting file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.get("/excel/sheets/{filename}")
async def get_excel_sheets(filename: str):
    """
    Get the list of sheet names from an Excel file
    """
    try:
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        excel_file = pd.ExcelFile(file_path)
        return {
            "filename": filename,
            "sheets": excel_file.sheet_names,
            "sheet_count": len(excel_file.sheet_names)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a converted CSV file
    """
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv'
    )

@app.post("/ice/ingest", response_model=ICEIngestionResult)
async def ingest_ice_database(
    background_tasks: BackgroundTasks,
    request: ICEIngestionRequest
):
    """
    Trigger ICE database ingestion pipeline
    """
    start_time = datetime.now()
    
    try:
        from ice_ingestion import ice_manager
        
        logger.info(f"Starting ICE ingestion with force_reprocess={request.force_reprocess}")
        
        # Run the ingestion in the background
        def run_ingestion_task():
            result = ice_manager.run_ingestion(force_reprocess=request.force_reprocess)
            logger.info(f"ICE ingestion completed: {result.get('success', False)}")
            return result
        
        # For now, run synchronously (could be made async with background_tasks)
        ingestion_result = run_ingestion_task()
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if ingestion_result["success"]:
            # Parse output for file/row counts if available
            stdout = ingestion_result.get("stdout", "")
            files_processed = 1  # Default fallback
            total_rows = 0  # Default fallback
            
            # Try to extract counts from stdout if the script outputs them
            # This would need to be adjusted based on the actual script output
            
            return ICEIngestionResult(
                success=True,
                files_processed=files_processed,
                total_rows=total_rows,
                message="ICE ingestion pipeline completed successfully",
                processing_time=processing_time
            )
        else:
            error_msg = ingestion_result.get("error", "Unknown error")
            stderr = ingestion_result.get("stderr", "")
            if stderr:
                error_msg += f" - {stderr}"
            
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {error_msg}")
        
    except Exception as e:
        logger.error(f"ICE ingestion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.get("/ice/status")
async def get_ice_status():
    """
    Get detailed status of the ICE database system
    """
    try:
        from ice_ingestion import ice_manager
        status = ice_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get ICE status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

# Database helper
def get_db_connection():
    """Get PostgreSQL database connection."""
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# Staging data endpoints
@app.get("/staging/summary")
async def get_staging_summary():
    """
    Get summary statistics for staging database
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get student count by program
        cur.execute("""
            SELECT s.program, COUNT(*) as count
            FROM staging_student s
            GROUP BY s.program
            ORDER BY count DESC
        """)
        programs = cur.fetchall()
        
        # Get total counts
        cur.execute("SELECT COUNT(*) as count FROM staging_student")
        total_students = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM staging_document")
        total_documents = cur.fetchone()['count']
        
        # Get leads count
        cur.execute("SELECT COUNT(*) as count FROM staging_lead")
        total_leads = cur.fetchone()['count']
        
        # Get reference files count
        cur.execute("SELECT COUNT(*) as count FROM staging_reference_data")
        total_reference_files = cur.fetchone()['count']
        
        # Get source breakdown
        cur.execute("""
            SELECT p.source, COUNT(*) as count
            FROM staging_person p
            GROUP BY p.source
            ORDER BY count DESC
        """)
        sources = cur.fetchall()
        
        # Get latest ingestion run
        cur.execute("""
            SELECT * FROM staging_ingestion_run
            ORDER BY run_date DESC
            LIMIT 1
        """)
        latest_run = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return {
            "total_students": total_students,
            "total_documents": total_documents,
            "total_leads": total_leads,
            "total_reference_files": total_reference_files,
            "programs": programs,
            "sources": sources,
            "latest_run": dict(latest_run) if latest_run else None
        }
        
    except Exception as e:
        logger.error(f"Error getting staging summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/students")
async def get_staging_students(
    program: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Get list of staging students with optional filters
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build query with filters
        query = """
            SELECT 
                p.id, p.full_name, p.email, p.phone,
                s.program, p.source, p.directory_path,
                (SELECT COUNT(*) FROM staging_document d WHERE d.student_id = s.id) as document_count
            FROM staging_person p
            JOIN staging_student s ON p.id = s.person_id
            WHERE 1=1
        """
        
        params = []
        
        if program:
            query += " AND s.program = %s"
            params.append(program)
        
        if source:
            query += " AND p.source = %s"
            params.append(source)
        
        query += " ORDER BY p.full_name LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        students = cur.fetchall()
        
        # Get total count
        count_query = """
            SELECT COUNT(*)
            FROM staging_person p
            JOIN staging_student s ON p.id = s.person_id
            WHERE 1=1
        """
        
        count_params = []
        if program:
            count_query += " AND s.program = %s"
            count_params.append(program)
        if source:
            count_query += " AND p.source = %s"
            count_params.append(source)
        
        cur.execute(count_query, count_params)
        total = cur.fetchone()['count']
        
        cur.close()
        conn.close()
        
        return {
            "students": [dict(s) for s in students],
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting staging students: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/students/{student_id}")
async def get_staging_student_details(student_id: str):
    """
    Get detailed information for a specific student including documents
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get student and person info
        cur.execute("""
            SELECT 
                p.*, s.program, s.status
            FROM staging_person p
            JOIN staging_student s ON p.id = s.person_id
            WHERE s.id = %s
        """, (student_id,))
        
        student = cur.fetchone()
        
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Get documents
        cur.execute("""
            SELECT *
            FROM staging_document
            WHERE student_id = %s
            ORDER BY document_type, created_at
        """, (student_id,))
        
        documents = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "student": dict(student),
            "documents": [dict(d) for d in documents]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting student details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/leads")
async def get_staging_leads(
    limit: int = 50,
    offset: int = 0
):
    """
    Get list of staging leads
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get leads
        cur.execute("""
            SELECT 
                id, full_name, email, phone, address, cedula,
                birth_date, country, city, source_file, source_sheet,
                status, interest_program, created_at
            FROM staging_lead
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        leads = cur.fetchall()
        
        # Get total count
        cur.execute("SELECT COUNT(*) as count FROM staging_lead")
        total = cur.fetchone()['count']
        
        cur.close()
        conn.close()
        
        return {
            "leads": [dict(l) for l in leads],
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting staging leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/reference-data")
async def get_reference_data(
    limit: int = 50,
    offset: int = 0
):
    """
    Get list of reference data files
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get reference data
        cur.execute("""
            SELECT 
                id, source_file, source_sheet, data_type, category,
                row_count, column_count, columns, created_at
            FROM staging_reference_data
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        reference_data = cur.fetchall()
        
        # Get total count
        cur.execute("SELECT COUNT(*) as count FROM staging_reference_data")
        total = cur.fetchone()['count']
        
        cur.close()
        conn.close()
        
        return {
            "reference_data": [dict(r) for r in reference_data],
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting reference data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/reference-data/{ref_id}")
async def get_reference_data_details(ref_id: int):
    """
    Get detailed information for a specific reference data file including content preview
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get reference data details
        cur.execute("""
            SELECT *
            FROM staging_reference_data
            WHERE id = %s
        """, (ref_id,))
        
        ref_data = cur.fetchone()
        
        if not ref_data:
            raise HTTPException(status_code=404, detail="Reference data not found")
        
        cur.close()
        conn.close()
        
        return dict(ref_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reference data details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/runs")
async def get_ingestion_runs(limit: int = 10):
    """
    Get list of ingestion runs
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT *
            FROM staging_ingestion_run
            ORDER BY run_date DESC
            LIMIT %s
        """, (limit,))
        
        runs = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "runs": [dict(r) for r in runs]
        }
        
    except Exception as e:
        logger.error(f"Error getting ingestion runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/staging/trigger-ingestion")
async def trigger_staging_ingestion(
    background_tasks: BackgroundTasks,
    source_directory: str = "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001"
):
    """
    Trigger full staging ingestion pipeline
    """
    try:
        import subprocess
        from pathlib import Path
        
        # Verify source directory exists
        if not Path(source_directory).exists():
            raise HTTPException(status_code=400, detail=f"Source directory does not exist: {source_directory}")
        
        # Run ingestion script
        script_path = Path(__file__).parent / "ingestion_to_staging.py"
        
        logger.info(f"Starting staging ingestion from: {source_directory}")
        
        # Update source directory in the script or pass as env var
        env = os.environ.copy()
        env['SOURCE_DIR'] = source_directory
        
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(script_path.parent),
            env=env
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": "Ingestion pipeline completed successfully",
                "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed: {result.stderr}"
            )
            
    except Exception as e:
        logger.error(f"Failed to trigger ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/staging/trigger-v3-ingestion")
async def trigger_v3_ingestion(
    background_tasks: BackgroundTasks,
    source_directory: str = "/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001"
):
    """
    Trigger V3 enhanced staging ingestion pipeline with Excel/CSV extraction
    """
    try:
        import subprocess
        from pathlib import Path
        
        # Verify source directory exists
        if not Path(source_directory).exists():
            raise HTTPException(status_code=400, detail=f"Source directory does not exist: {source_directory}")
        
        # Run V3 ingestion script
        script_path = Path(__file__).parent / "ingestion_to_staging_v3.py"
        
        logger.info(f"Starting V3 enhanced ingestion from: {source_directory}")
        
        # Update source directory in the script or pass as env var
        env = os.environ.copy()
        env['SOURCE_DIR'] = source_directory
        
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(script_path.parent),
            env=env,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": "V3 Enhanced ingestion pipeline completed successfully",
                "stdout": result.stdout[-2000:] if result.stdout else "",  # Last 2000 chars
                "pipeline_version": "v3"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"V3 Ingestion failed: {result.stderr[-1000:]}"
            )
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Ingestion timeout (>5min)")
    except Exception as e:
        logger.error(f"Failed to trigger V3 ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/staging/stats")
async def get_staging_stats():
    """
    Get comprehensive staging statistics including leads and reference data
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cleanup_staging import StagingCleaner
        
        staging_dir = os.getenv('STAGING_DIR', '/home/sebastiangarcia/ice-data-staging')
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
        
        cleaner = StagingCleaner(staging_dir, db_url)
        stats = cleaner.get_staging_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting staging stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/staging/sanitize")
async def sanitize_staging_data(execute: bool = False):
    """
    Sanitize staging data by removing false positive student records.
    
    Args:
        execute: If False, runs dry-run (preview only). If True, actually deletes.
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from data_sanitizer import DataSanitizer
        
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
        
        sanitizer = DataSanitizer(db_url)
        result = sanitizer.sanitize(dry_run=not execute)
        
        if result['success']:
            # Format false positives for frontend display
            records_to_delete = [
                {
                    "name": fp['full_name'],
                    "program": fp['program'],
                    "document_count": fp['document_count'],
                    "student_id": fp['student_id']
                }
                for fp in result['false_positives']
            ]
            
            return {
                "success": True,
                "dry_run": not execute,
                "false_positives_count": result['stats']['false_positives_found'],
                "records_to_delete": records_to_delete,
                "students_deleted": result['stats'].get('students_deleted', 0) if execute else 0,
                "documents_removed": result['stats'].get('documents_orphaned', 0) if execute else 0,
                "message": f"{'Successfully sanitized' if execute else 'Found'} {result['stats']['false_positives_found']} false positive records",
                "stats": result['stats']
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Sanitization failed'))
            
    except Exception as e:
        logger.error(f"Sanitization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/staging/student/{student_id}")
async def delete_student_manually(student_id: str):
    """
    Manually delete a specific student record (for false negatives).
    
    Args:
        student_id: UUID of the student to delete
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from data_sanitizer import DataSanitizer
        
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
        
        sanitizer = DataSanitizer(db_url)
        result = sanitizer.delete_student_by_id(student_id)
        
        if result['success']:
            return {
                "success": True,
                "message": f"Successfully deleted student: {result['student_name']}",
                "student_name": result['student_name'],
                "documents_deleted": result['documents_deleted']
            }
        else:
            raise HTTPException(status_code=404, detail=result.get('error', 'Student not found'))
            
    except Exception as e:
        logger.error(f"Manual deletion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/staging/sanitize/whitelist")
async def sanitize_with_whitelist(whitelist: List[str] = [], execute: bool = False):
    """
    Sanitize staging data with whitelist support (excludes specific student IDs).
    
    Args:
        whitelist: List of student IDs to exclude from sanitization
        execute: If False, runs dry-run (preview only). If True, actually deletes.
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from data_sanitizer import DataSanitizer
        
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
        
        sanitizer = DataSanitizer(db_url, whitelist=set(whitelist))
        result = sanitizer.sanitize(dry_run=not execute)
        
        if result['success']:
            # Format false positives for frontend display
            records_to_delete = [
                {
                    "name": fp['full_name'],
                    "program": fp['program'],
                    "document_count": fp['document_count'],
                    "student_id": fp['student_id']
                }
                for fp in result['false_positives']
            ]
            
            return {
                "success": True,
                "dry_run": not execute,
                "false_positives_count": result['stats']['false_positives_found'],
                "records_to_delete": records_to_delete,
                "whitelisted_count": len(whitelist),
                "students_deleted": result['stats'].get('students_deleted', 0) if execute else 0,
                "documents_removed": result['stats'].get('documents_orphaned', 0) if execute else 0,
                "message": f"{'Successfully sanitized' if execute else 'Found'} {result['stats']['false_positives_found']} false positive records",
                "stats": result['stats']
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Sanitization failed'))
            
    except Exception as e:
        logger.error(f"Sanitization with whitelist failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/staging/cleanup")
async def cleanup_staging_data(confirm: bool = False):
    """
    Clean all staging data (database + files) for fresh V3 ingestion
    
    Args:
        confirm: Must be true to proceed (safety check)
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cleanup_staging import StagingCleaner
        
        if not confirm:
            # Return current stats without cleaning
            staging_dir = os.getenv('STAGING_DIR', '/home/sebastiangarcia/ice-data-staging')
            db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
            
            cleaner = StagingCleaner(staging_dir, db_url)
            stats = cleaner.get_staging_stats()
            
            return {
                "success": False,
                "message": "Cleanup requires confirmation. Set confirm=true to proceed.",
                "current_stats": stats,
                "warning": "This will DELETE all staging data: database records, documents, CSVs, and reports"
            }
        
        # Perform cleanup
        staging_dir = os.getenv('STAGING_DIR', '/home/sebastiangarcia/ice-data-staging')
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:224207bB@localhost:5432/leads_project')
        
        cleaner = StagingCleaner(staging_dir, db_url)
        success = cleaner.clean_all(confirm=True)
        
        if success:
            return {
                "success": True,
                "message": "Staging environment cleaned successfully. Ready for fresh V3 ingestion.",
                "cleaned": {
                    "database": True,
                    "documents": True,
                    "extracted_csvs": True,
                    "reports": True
                }
            }
        else:
            raise HTTPException(status_code=500, detail="Some cleanup operations failed")
            
    except Exception as e:
        logger.error(f"Staging cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/cleanup")
async def cleanup_files():
    """
    Clean up temporary files
    """
    try:
        upload_count = len(list(UPLOAD_DIR.glob("*")))
        output_count = len(list(OUTPUT_DIR.glob("*")))
        
        # Clean upload directory
        for file_path in UPLOAD_DIR.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        
        # Clean output directory
        for file_path in OUTPUT_DIR.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        
        return {
            "message": f"Cleaned up {upload_count} uploaded files and {output_count} output files",
            "upload_files_removed": upload_count,
            "output_files_removed": output_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)