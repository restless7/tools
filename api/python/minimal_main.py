"""
Minimal FastAPI backend for testing the frontend
Provides basic endpoints without heavy dependencies
"""

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Tools Platform API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3005", "http://127.0.0.1:3005"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {"excel_converter": "active", "ice_ingestion": "active"},
    }


@app.post("/excel/convert")
async def convert_excel_to_csv(file: UploadFile = File(...)):
    """Mock Excel to CSV conversion"""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload an Excel file."
        )

    # Simulate processing time
    await asyncio.sleep(2)

    # Mock response
    return {
        "success": True,
        "filename": file.filename,
        "sheets_processed": 3,
        "files_created": [
            f"{file.filename}_Sheet1.csv",
            f"{file.filename}_Sheet2.csv",
            f"{file.filename}_Sheet3.csv",
        ],
        "message": "Excel file converted successfully to CSV files",
        "processing_time": 2.1,
    }


@app.get("/excel/sheets/{filename}")
async def get_excel_sheets(filename: str):
    """Mock get Excel sheets"""
    return {
        "filename": filename,
        "sheets": ["Sheet1", "Sheet2", "Sheet3"],
        "sheet_count": 3,
    }


@app.get("/download/{filename}")
async def download_file(filename: str):
    """Mock file download - creates a sample CSV"""
    # Create a sample CSV file
    sample_csv = "Name,Age,City\nJohn Doe,30,New York\nJane Smith,25,Los Angeles\nBob Johnson,35,Chicago\n"

    file_path = OUTPUT_DIR / filename
    with open(file_path, "w") as f:
        f.write(sample_csv)

    return FileResponse(file_path, media_type="text/csv", filename=filename)


@app.post("/ice/ingest")
async def trigger_ice_ingestion(options: Optional[Dict[str, Any]] = None):
    """Mock ICE database ingestion"""
    if options is None:
        options = {}

    # Simulate processing time
    processing_time = 5.5
    await asyncio.sleep(1)  # Short delay for demo

    return {
        "success": True,
        "files_processed": 12,
        "total_rows": 1547,
        "message": "ICE database ingestion completed successfully. Processed 12 files with 1,547 total rows.",
        "processing_time": processing_time,
    }


@app.delete("/cleanup")
async def cleanup_files():
    """Cleanup temporary files"""
    upload_count = len(list(UPLOAD_DIR.glob("*")))
    output_count = len(list(OUTPUT_DIR.glob("*")))

    # Clean up files
    for file in UPLOAD_DIR.glob("*"):
        file.unlink()
    for file in OUTPUT_DIR.glob("*"):
        file.unlink()

    return {
        "message": "Cleanup completed successfully",
        "upload_files_removed": upload_count,
        "output_files_removed": output_count,
    }


# Add asyncio import
import asyncio

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")  # nosec B104
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, reload=True)
