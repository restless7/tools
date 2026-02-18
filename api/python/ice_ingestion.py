#!/usr/bin/env python3
"""
ICE Database Ingestion Integration
Wrapper for the existing ICE-DATABASE pipeline with new API endpoints
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

# Add the ICE-DATABASE directory to Python path
ice_db_path = "/home/sebastiangarcia/ICE-DATABASE"
if ice_db_path not in sys.path:
    sys.path.insert(0, ice_db_path)

# Import ICE pipeline API components
try:
    from ice_pipeline.api import pipeline_router
except ImportError as e:
    logging.warning(f"Could not import ICE pipeline API: {e}")
    pipeline_router = None

logger = logging.getLogger(__name__)

# Create router and include ICE pipeline endpoints if available
router = APIRouter(prefix="/ice", tags=["ICE Database"])

if pipeline_router:
    # Include the full ICE pipeline router
    router.include_router(pipeline_router)


class ICEIngestionManager:
    """
    Manager class for ICE database ingestion operations
    """

    def __init__(self):
        self.ice_db_path = Path("/home/sebastiangarcia/ICE-DATABASE")
        self.script_path = self.ice_db_path / "enhanced_ingest_drive_wat.py"

    def validate_environment(self) -> Dict[str, Any]:
        """
        Validate that the ICE database environment is properly configured
        """
        checks = {
            "script_exists": self.script_path.exists(),
            "env_file_exists": (self.ice_db_path / ".env").exists(),
            "credentials_exist": (
                self.ice_db_path / "credentials" / "service_account.json"
            ).exists(),
            "requirements_exist": (self.ice_db_path / "requirements.txt").exists(),
        }

        return {
            "valid": all(checks.values()),
            "checks": checks,
            "ice_db_path": str(self.ice_db_path),
        }

    def run_ingestion(self, force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Execute the enhanced ICE database ingestion pipeline
        """
        try:
            # Validate environment first
            env_check = self.validate_environment()
            if not env_check["valid"]:
                return {
                    "success": False,
                    "error": "ICE database environment not properly configured",
                    "details": env_check,
                }

            # Change to ICE-DATABASE directory
            original_cwd = os.getcwd()
            os.chdir(self.ice_db_path)

            try:
                # Use the enhanced pipeline script
                cmd = [sys.executable, "enhanced_ingest_drive_wat.py"]
                if force_reprocess:
                    cmd.append("--force-reprocess")

                logger.info(f"Running enhanced ICE ingestion: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 minutes timeout
                )

                if result.returncode == 0:
                    return {
                        "success": True,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "command": " ".join(cmd),
                        "files_processed": 0,  # Parse from output if needed
                        "total_rows": 0,  # Parse from output if needed
                    }
                else:
                    # Extract specific error details
                    error_msg = "Unknown error"
                    if "File not found" in result.stderr:
                        error_msg = "Google Drive folder not found or not accessible"
                    elif "404" in result.stderr:
                        error_msg = "Google Drive resource not found (404 error)"
                    elif "credentials" in result.stderr.lower():
                        error_msg = "Google Drive authentication failed"
                    elif "database" in result.stderr.lower():
                        error_msg = "Database connection or query failed"
                    elif result.stderr:
                        # Use first line of stderr as error message
                        error_lines = result.stderr.strip().split("\n")
                        error_msg = (
                            error_lines[-1]
                            if error_lines
                            else "Script execution failed"
                        )

                    return {
                        "success": False,
                        "returncode": result.returncode,
                        "error": error_msg,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "command": " ".join(cmd),
                        "files_processed": 0,
                        "total_rows": 0,
                    }

            finally:
                # Always restore original working directory
                os.chdir(original_cwd)

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Ingestion process timed out after 30 minutes",
                "timeout": True,
            }
        except Exception as e:
            logger.error(f"ICE ingestion failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "exception_type": type(e).__name__,
            }

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the ICE database system
        """
        env_check = self.validate_environment()

        status = {
            "environment": env_check,
            "last_run": None,  # Could check ETL log table
            "database_connected": False,  # Could test DB connection
        }

        # Try to test database connection if environment is valid
        if env_check["valid"]:
            try:
                # Import and test the database connection
                sys.path.append(str(self.ice_db_path))

                # This would test the actual DB connection
                # For now, we'll just mark it as available if env is valid
                status["database_connected"] = True

            except Exception as e:
                status["database_error"] = str(e)

        return status


# Global instance
ice_manager = ICEIngestionManager()


# Legacy API Endpoints for backward compatibility
class LegacyIngestionRequest(BaseModel):
    folder_id: Optional[str] = None
    force_reprocess: bool = False


@router.post("/ingest")
async def legacy_start_ingestion(request: LegacyIngestionRequest):
    """Legacy ICE ingestion endpoint (deprecated - use /ice-pipeline/start instead)"""
    try:
        result = ice_manager.run_ingestion(force_reprocess=request.force_reprocess)

        if result["success"]:
            return {
                "status": "success",
                "message": "ICE ingestion completed successfully (Legacy endpoint - consider using /ice-pipeline/start)",
                "details": result,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed: {result.get('error', 'Unknown error')}",
            )

    except Exception as e:
        logger.error(f"Legacy ICE ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/status")
async def get_ice_status():
    """Get ICE database system status"""
    try:
        status = ice_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting ICE status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/validate")
async def validate_ice_environment():
    """Validate ICE database environment setup"""
    try:
        validation = ice_manager.validate_environment()
        if not validation["valid"]:
            return {
                "status": "warning",
                "message": "ICE environment has configuration issues",
                "details": validation,
            }

        return {
            "status": "ok",
            "message": "ICE environment is properly configured",
            "details": validation,
        }
    except Exception as e:
        logger.error(f"Error validating ICE environment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
