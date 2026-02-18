"""
ICE Pipeline API Module.

FastAPI application for processing Excel files and managing ICE ingestion.
"""

import json
import logging
import os
from datetime import datetime
from enum import Enum as PyEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import ingestion manager
try:
    from .ingestion import ICEIngestionManager, IngestionResult, IngestionStatus

    # Create global ingestion manager instance
    ingestion_manager = ICEIngestionManager()
except ImportError as e:
    logger.warning(f"Could not import ingestion manager: {e}")
    ingestion_manager = None

# FastAPI app instance
app = FastAPI(
    title="ICE Pipeline API",
    description="Enterprise ICE pipeline for student application processing",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Enums for validation
class OutputFormat(PyEnum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"


# Pydantic models
class ExcelConversionRequest(BaseModel):
    file_path: str = Field(
        ..., min_length=1, max_length=1000, description="Path to the Excel file"
    )
    output_format: str = Field(
        default="csv", description="Output format (csv, json, parquet)"
    )
    include_metadata: bool = Field(
        default=False, description="Whether to include file metadata"
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v):
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        if not v.endswith((".xlsx", ".xls")):
            raise ValueError("File must be an Excel file (.xlsx or .xls)")
        return v.strip()

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v):
        valid_formats = [fmt.value for fmt in OutputFormat]
        if v not in valid_formats:
            raise ValueError(f"Output format must be one of: {valid_formats}")
        return v


class ExcelConversionResponse(BaseModel):
    success: bool = Field(..., description="Whether the conversion was successful")
    output_file: str = Field(
        ..., min_length=1, description="Path to the converted output file"
    )
    rows_processed: int = Field(..., ge=0, description="Number of rows processed")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="File metadata if requested"
    )
    processing_time: Optional[float] = Field(
        default=None, ge=0, description="Processing time in seconds"
    )

    @field_validator("output_file")
    @classmethod
    def validate_output_file(cls, v):
        if not v or not v.strip():
            raise ValueError("Output file path cannot be empty")
        return v.strip()


class ICEIngestionResponse(BaseModel):
    success: bool
    status: str
    message: str
    execution_time: Optional[float] = None


class ICEStatusResponse(BaseModel):
    status: str
    last_result: Optional[Dict[str, Any]] = None
    timestamp: str


class ICECleanupResponse(BaseModel):
    status: str
    files_cleaned: int
    temp_dirs_removed: int
    cache_cleared: bool
    space_freed_mb: Optional[int] = None
    warnings: Optional[List[str]] = None


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {"ice_ingestion": "active" if ingestion_manager else "unavailable"},
    }


@app.post("/convert-excel", response_model=ExcelConversionResponse)
async def convert_excel(request: ExcelConversionRequest):
    """Convert Excel file to specified format."""
    try:
        result = process_excel_conversion(
            file_path=request.file_path,
            output_format=request.output_format,
            include_metadata=request.include_metadata,
        )
        return ExcelConversionResponse(**result)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/ice/trigger", response_model=ICEIngestionResponse)
async def trigger_ice_ingestion(background_tasks: BackgroundTasks):
    """Trigger ICE ingestion process."""
    if not ingestion_manager:
        raise HTTPException(
            status_code=503, detail="ICE ingestion manager not available"
        )

    current_status = ingestion_manager.get_status()
    if current_status == IngestionStatus.RUNNING:
        raise HTTPException(status_code=409, detail="ICE ingestion already running")

    # Start ingestion in background
    background_tasks.add_task(run_ingestion_background)

    return ICEIngestionResponse(
        success=True, status="triggered", message="ICE ingestion started in background"
    )


@app.get("/ice/status", response_model=ICEStatusResponse)
async def get_ice_status():
    """Get ICE ingestion status."""
    if not ingestion_manager:
        raise HTTPException(
            status_code=503, detail="ICE ingestion manager not available"
        )

    status = ingestion_manager.get_status()
    last_result = ingestion_manager.get_last_result()

    # Convert result to dict for JSON serialization
    last_result_dict = None
    if last_result:
        last_result_dict = {
            "success": last_result.success,
            "status": last_result.status.value,
            "output": last_result.output,
            "error_message": last_result.error_message,
            "return_code": last_result.return_code,
            "execution_time": last_result.execution_time,
            "timestamp": last_result.timestamp.isoformat(),
        }

    return ICEStatusResponse(
        status=status.value,
        last_result=last_result_dict,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/ice/cleanup", response_model=ICECleanupResponse)
async def cleanup_ice_ingestion():
    """Clean up ICE ingestion resources."""
    try:
        result = cleanup_ingestion_resources()
        return ICECleanupResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# Helper functions
def process_excel_conversion(
    file_path: str, output_format: str, include_metadata: bool
) -> Dict[str, Any]:
    """
    Process Excel file conversion.

    This is a placeholder that should be implemented with actual conversion logic.
    """
    import time
    from pathlib import Path

    import pandas as pd

    start_time = time.time()

    # Validate file exists
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Validate output format
    valid_formats = ["csv", "json", "parquet"]
    if output_format not in valid_formats:
        raise ValueError(f"Invalid output format. Must be one of: {valid_formats}")

    try:
        # Read Excel file
        df = pd.read_excel(file_path)

        # Generate output file path
        output_file = file_path_obj.with_suffix(f".{output_format}")

        # Convert to specified format
        if output_format == "csv":
            df.to_csv(output_file, index=False)
        elif output_format == "json":
            df.to_json(output_file, orient="records", indent=2)
        elif output_format == "parquet":
            df.to_parquet(output_file, index=False)

        # Prepare metadata if requested
        metadata = None
        if include_metadata:
            metadata = {
                "sheets": ["Sheet1"],  # Simplified for example
                "columns": len(df.columns),
                "file_size": file_path_obj.stat().st_size,
            }

        processing_time = time.time() - start_time

        return {
            "success": True,
            "output_file": str(output_file),
            "rows_processed": len(df),
            "metadata": metadata,
            "processing_time": processing_time,
        }

    except Exception as e:
        raise Exception(f"Excel processing failed: {str(e)}")


async def run_ingestion_background():
    """Run ICE ingestion in background."""
    if ingestion_manager:
        try:
            result = await ingestion_manager.run_ingestion()
            logger.info(f"Background ingestion completed: {result.success}")
        except Exception as e:
            logger.error(f"Background ingestion failed: {e}")


def cleanup_ingestion_resources() -> Dict[str, Any]:
    """
    Clean up ICE ingestion resources.

    This is a placeholder that should be implemented with actual cleanup logic.
    """
    import shutil
    import tempfile
    from pathlib import Path

    files_cleaned = 0
    temp_dirs_removed = 0
    cache_cleared = True
    space_freed_mb = 0
    warnings = []

    try:
        # Clean up temp files
        temp_dir = Path(tempfile.gettempdir())
        ice_temp_files = list(temp_dir.glob("ice_*"))

        for temp_file in ice_temp_files:
            try:
                if temp_file.is_file():
                    size_mb = temp_file.stat().st_size / (1024 * 1024)
                    temp_file.unlink()
                    files_cleaned += 1
                    space_freed_mb += size_mb
                elif temp_file.is_dir():
                    shutil.rmtree(temp_file)
                    temp_dirs_removed += 1
            except Exception as e:
                warnings.append(f"Could not remove {temp_file}: {str(e)}")

        # Try to clear cache (placeholder)
        try:
            # This would clear Redis cache or other caching systems
            pass
        except Exception as e:
            cache_cleared = False
            warnings.append(f"Could not clear cache: {str(e)}")

        return {
            "status": "completed",
            "files_cleaned": files_cleaned,
            "temp_dirs_removed": temp_dirs_removed,
            "cache_cleared": cache_cleared,
            "space_freed_mb": int(space_freed_mb),
            "warnings": warnings if warnings else None,
        }

    except Exception as e:
        raise Exception(f"Cleanup operation failed: {str(e)}")


# Main function for running the app
def main():
    """Main function to run the FastAPI app."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
