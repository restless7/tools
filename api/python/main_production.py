#!/usr/bin/env python3
"""
Enterprise Tools Platform - Production Backend
FastAPI application with full Excel processing, ICE integration, and enterprise features
"""

import os
import io
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Only import what's available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PlanMaestro Tools API",
    description="Enterprise tools platform for Excel processing, CSV conversion, and data pipeline management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3006",
        "http://localhost:3005", 
        "http://localhost:3004", 
        "http://localhost:3000",
        "http://127.0.0.1:3006",
        "http://127.0.0.1:3005",
        "http://127.0.0.1:3004",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class ConversionResult(BaseModel):
    success: bool
    filename: str
    sheets_processed: int
    files_created: List[str]
    message: str
    processing_time: float

class ICEIngestionResult(BaseModel):
    success: bool
    files_processed: int
    total_rows: int
    message: str
    processing_time: float

class HealthStatus(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]
    dependencies: Dict[str, bool]

# Storage directories
UPLOAD_DIR = Path("/tmp/tools_uploads")
OUTPUT_DIR = Path("/tmp/tools_output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Dependency checks
def check_dependencies():
    """Check available dependencies and features"""
    deps = {
        "pandas": HAS_PANDAS,
        "openpyxl": HAS_OPENPYXL,
        "ice_pipeline": False
    }
    
    # Check ICE pipeline availability
    try:
        ice_db_path = Path("/home/sebastiangarcia/ICE-DATABASE")
        deps["ice_pipeline"] = ice_db_path.exists() and (ice_db_path / "enhanced_ingest_drive_wat.py").exists()
    except:
        pass
    
    return deps

@app.get("/")
async def root():
    deps = check_dependencies()
    return {
        "message": "PlanMaestro Tools API - Production Ready",
        "version": "2.0.0",
        "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        "features": {
            "excel_conversion": deps["pandas"] and deps["openpyxl"],
            "ice_integration": deps["ice_pipeline"],
            "file_processing": True
        },
        "endpoints": [
            "/health",
            "/excel/convert",
            "/excel/sheets/{filename}",
            "/download/{filename}",
            "/ice/ingest",
            "/cleanup"
        ]
    }

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Comprehensive health check with dependency validation"""
    deps = check_dependencies()
    
    # Check ICE system status
    ice_status = "maintenance"
    if deps["ice_pipeline"]:
        try:
            # Try to import ICE components
            import sys
            ice_path = "/home/sebastiangarcia/ICE-DATABASE"
            if ice_path not in sys.path:
                sys.path.append(ice_path)
            
            # Check environment file
            env_file = Path(ice_path) / ".env"
            if env_file.exists():
                ice_status = "active"
        except Exception as e:
            logger.debug(f"ICE status check: {e}")
    
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        services={
            "excel_converter": "active" if (deps["pandas"] and deps["openpyxl"]) else "maintenance",
            "ice_ingestion": ice_status
        },
        dependencies=deps
    )

@app.post("/excel/convert", response_model=ConversionResult)
async def convert_excel_to_csv(file: UploadFile = File(...)):
    """Convert Excel file with multiple sheets to separate CSV files"""
    
    if not HAS_PANDAS or not HAS_OPENPYXL:
        raise HTTPException(
            status_code=503, 
            detail="Excel conversion not available - missing pandas or openpyxl"
        )
    
    start_time = datetime.now()
    
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400, 
            detail="File must be an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        content = await file.read()
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(f"Processing Excel file: {file.filename} ({len(content)} bytes)")
        
        # Process Excel file
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
        created_files = []
        
        logger.info(f"Found {len(sheet_names)} sheets: {sheet_names}")
        
        for sheet_name in sheet_names:
            try:
                # Read sheet
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Clean sheet name for filename
                clean_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_')).strip()
                if not clean_name:
                    clean_name = f"Sheet_{len(created_files) + 1}"
                
                csv_filename = f"{Path(file.filename).stem}_{clean_name}.csv"
                csv_path = OUTPUT_DIR / csv_filename
                
                # Convert to CSV with proper encoding
                df.to_csv(csv_path, index=False, encoding='utf-8')
                created_files.append(csv_filename)
                
                logger.info(f"Created: {csv_filename} ({len(df)} rows, {len(df.columns)} columns)")
                
            except Exception as sheet_error:
                logger.error(f"Error processing sheet '{sheet_name}': {sheet_error}")
                continue
        
        # Cleanup uploaded file
        try:
            file_path.unlink()
        except:
            pass
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if not created_files:
            raise HTTPException(
                status_code=422,
                detail="No sheets could be processed. Please check your Excel file format."
            )
        
        return ConversionResult(
            success=True,
            filename=file.filename,
            sheets_processed=len(created_files),
            files_created=created_files,
            message=f"Successfully converted {len(created_files)} sheets to CSV format",
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel conversion error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Conversion failed: {str(e)}"
        )

@app.get("/excel/sheets/{filename}")
async def get_excel_sheets(filename: str):
    """Get sheet names from an Excel file"""
    
    if not HAS_PANDAS or not HAS_OPENPYXL:
        raise HTTPException(
            status_code=503,
            detail="Excel analysis not available - missing dependencies"
        )
    
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        excel_file = pd.ExcelFile(file_path)
        return {
            "filename": filename,
            "sheets": excel_file.sheet_names,
            "sheet_count": len(excel_file.sheet_names)
        }
    except Exception as e:
        logger.error(f"Error reading Excel sheets: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error reading file: {str(e)}"
        )

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download a converted CSV file"""
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/ice/ingest", response_model=ICEIngestionResult)
async def trigger_ice_ingestion(
    background_tasks: BackgroundTasks,
    force_reprocess: bool = False
):
    """Trigger ICE database ingestion pipeline"""
    
    deps = check_dependencies()
    if not deps["ice_pipeline"]:
        raise HTTPException(
            status_code=503,
            detail="ICE pipeline not available - check system configuration"
        )
    
    start_time = datetime.now()
    
    try:
        # Import ICE ingestion manager
        import sys
        ice_path = "/home/sebastiangarcia/ICE-DATABASE"
        if ice_path not in sys.path:
            sys.path.append(ice_path)
        
        # Dynamic import
        from ice_ingestion import ICEIngestionManager
        manager = ICEIngestionManager()
        
        # Run ingestion
        result = manager.run_ingestion(force_reprocess=force_reprocess)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if result["success"]:
            return ICEIngestionResult(
                success=True,
                files_processed=result.get("files_processed", 0),
                total_rows=result.get("total_rows", 0),
                message="ICE database ingestion completed successfully",
                processing_time=processing_time
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"ICE ingestion failed: {result.get('error', 'Unknown error')}"
            )
            
    except ImportError as e:
        logger.error(f"ICE import error: {e}")
        raise HTTPException(
            status_code=503,
            detail="ICE pipeline components not available"
        )
    except Exception as e:
        logger.error(f"ICE ingestion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )

@app.delete("/cleanup")
async def cleanup_files():
    """Cleanup temporary files"""
    try:
        upload_files = list(UPLOAD_DIR.glob("*"))
        output_files = list(OUTPUT_DIR.glob("*"))
        
        upload_count = len(upload_files)
        output_count = len(output_files)
        
        # Clean up files
        for file_path in upload_files:
            try:
                file_path.unlink()
            except:
                pass
                
        for file_path in output_files:
            try:
                file_path.unlink()
            except:
                pass
        
        return {
            "message": "Cleanup completed successfully",
            "upload_files_removed": upload_count,
            "output_files_removed": output_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting PlanMaestro Tools API - Production Mode")
    logger.info(f"Dependencies: {check_dependencies()}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,  # Production mode
        access_log=True
    )