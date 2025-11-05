"""
ICE Pipeline Ingestion Module.

Manages the ingestion of ICE student application data including
environment validation, script execution, and result tracking.
"""

import os
import json
import asyncio
import logging
import subprocess
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionStatus(Enum):
    """Enumeration of ingestion status values."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class IngestionResult:
    """Data class for ingestion operation results."""
    success: bool
    status: IngestionStatus
    output: str
    error_message: Optional[str]
    return_code: int
    execution_time: float
    timestamp: datetime


class ICEIngestionManager:
    """
    Manages ICE ingestion operations including environment validation,
    script execution, and result tracking.
    """
    
    def __init__(self):
        """Initialize the ICE ingestion manager."""
        self.status = IngestionStatus.IDLE
        self._last_result: Optional[IngestionResult] = None
        
        # Environment configuration
        self.google_credentials = os.getenv('GOOGLE_CREDENTIALS_JSON')
        self.google_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        self.ice_script_path = os.getenv('ICE_SCRIPT_PATH', '/app/ice_enhanced_ingestion.py')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        logger.info("ICE Ingestion Manager initialized")
    
    def validate_environment(self) -> bool:
        """
        Validate the ICE ingestion environment.
        
        Returns:
            bool: True if environment is valid, False otherwise.
        """
        try:
            # Refresh environment variables (for testing)
            self.google_credentials = os.getenv('GOOGLE_CREDENTIALS_JSON')
            self.google_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
            self.ice_script_path = os.getenv('ICE_SCRIPT_PATH', '/app/ice_enhanced_ingestion.py')
            
            # Check Google credentials
            if not self.google_credentials:
                logger.error("GOOGLE_CREDENTIALS_JSON environment variable not set")
                return False
            
            # Validate JSON format
            try:
                json.loads(self.google_credentials)
            except json.JSONDecodeError:
                logger.error("GOOGLE_CREDENTIALS_JSON is not valid JSON")
                return False
            
            # Check Google Drive folder ID
            if not self.google_folder_id:
                logger.error("GOOGLE_DRIVE_FOLDER_ID environment variable not set")
                return False
            
            # Check ICE script exists (only if not None)
            if self.ice_script_path:
                script_path = Path(self.ice_script_path)
                if not script_path.exists():
                    logger.error(f"ICE script not found at {self.ice_script_path}")
                    return False
            else:
                logger.error("ICE_SCRIPT_PATH environment variable not set")
                return False
            
            logger.info("Environment validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            return False
    
    async def run_ingestion(self) -> IngestionResult:
        """
        Run the ICE ingestion process.
        
        Returns:
            IngestionResult: The result of the ingestion operation.
        """
        if self.status == IngestionStatus.RUNNING:
            logger.warning("Ingestion already running")
            return IngestionResult(
                success=False,
                status=IngestionStatus.ERROR,
                output="",
                error_message="Ingestion already running",
                return_code=-1,
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        start_time = datetime.now()
        self.status = IngestionStatus.RUNNING
        
        try:
            # Validate environment
            if not self.validate_environment():
                result = IngestionResult(
                    success=False,
                    status=IngestionStatus.ERROR,
                    output="",
                    error_message="Environment validation failed",
                    return_code=-1,
                    execution_time=0.0,
                    timestamp=datetime.now()
                )
                self._last_result = result
                self.status = IngestionStatus.IDLE
                return result
            
            # Prepare environment variables for subprocess
            env = os.environ.copy()
            env.update({
                'GOOGLE_CREDENTIALS_JSON': self.google_credentials,
                'GOOGLE_DRIVE_FOLDER_ID': self.google_folder_id,
                'LOG_LEVEL': self.log_level
            })
            
            # Execute ICE ingestion script
            logger.info(f"Starting ICE ingestion script: {self.ice_script_path}")
            
            process = await asyncio.create_subprocess_exec(
                'python3', self.ice_script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Wait for completion and capture output
            stdout, stderr = await process.communicate()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Process results
            output = stdout.decode('utf-8') if stdout else ""
            error_output = stderr.decode('utf-8') if stderr else ""
            
            if process.returncode == 0:
                logger.info(f"ICE ingestion completed successfully in {execution_time:.2f}s")
                result = IngestionResult(
                    success=True,
                    status=IngestionStatus.COMPLETED,
                    output=output,
                    error_message=None,
                    return_code=process.returncode,
                    execution_time=execution_time,
                    timestamp=datetime.now()
                )
            else:
                logger.error(f"ICE ingestion failed with return code {process.returncode}")
                result = IngestionResult(
                    success=False,
                    status=IngestionStatus.ERROR,
                    output=output,
                    error_message=error_output,
                    return_code=process.returncode,
                    execution_time=execution_time,
                    timestamp=datetime.now()
                )
            
            self._last_result = result
            self.status = IngestionStatus.IDLE
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"ICE ingestion exception: {e}")
            
            result = IngestionResult(
                success=False,
                status=IngestionStatus.ERROR,
                output="",
                error_message=str(e),
                return_code=-1,
                execution_time=execution_time,
                timestamp=datetime.now()
            )
            
            self._last_result = result
            self.status = IngestionStatus.IDLE
            return result
    
    def get_status(self) -> IngestionStatus:
        """
        Get the current ingestion status.
        
        Returns:
            IngestionStatus: Current status of the ingestion manager.
        """
        return self.status
    
    def get_last_result(self) -> Optional[IngestionResult]:
        """
        Get the last ingestion result.
        
        Returns:
            Optional[IngestionResult]: The last ingestion result or None if no ingestion has been run.
        """
        return self._last_result
    
    def reset(self):
        """Reset the ingestion manager state."""
        self.status = IngestionStatus.IDLE
        self._last_result = None
        logger.info("ICE Ingestion Manager reset")


# Global instance for backward compatibility
ice_manager = ICEIngestionManager()

# Export key classes and instances
__all__ = [
    'ICEIngestionManager',
    'IngestionStatus', 
    'IngestionResult',
    'ice_manager'
]