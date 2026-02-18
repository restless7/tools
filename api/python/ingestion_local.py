#!/usr/bin/env python3
"""
Enhanced ICE Data Ingestion Pipeline
Supports both local and remote (Google Drive) ingestion modes.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from db_utils import DatabaseManager
# Local modules
from local_ingestion_loader import LocalIngestionLoader, run_local_ingestion
from storage_adapter import get_storage_adapter


class ICEIngestionPipeline:
    """
    Enhanced ICE ingestion pipeline with local/remote mode support.
    """

    def __init__(self, mode: str = "auto"):
        """
        Initialize the ingestion pipeline.

        Args:
            mode: Ingestion mode ('local', 'remote', 'auto')
        """
        self.mode = mode
        self.base_dir = None
        self.db_manager = None

        # Environment configuration
        self.local_ingestion_dir = os.getenv(
            "LOCAL_INGESTION_DIR", "/mnt/ice-ingestion-data"
        )
        self.database_url = os.getenv("DATABASE_URL")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        self._setup_logging()
        self._determine_mode()
        self._initialize_components()

        logger = logging.getLogger(__name__)
        logger.info(f"ICEIngestionPipeline initialized in {self.mode} mode")

    def _setup_logging(self):
        """Setup enhanced logging with file output."""
        # Create log directory if it doesn't exist
        log_dir = Path("/var/log")
        if not log_dir.exists() or not os.access(log_dir, os.W_OK):
            # Fallback to local log directory
            log_dir = Path.cwd() / "logs"
            log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "ice_ingestion.log"

        # Configure logging with both file and console handlers
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        )

        logger = logging.getLogger(__name__)
        logger.info(f"Logging initialized - Level: {self.log_level}, File: {log_file}")

    def _determine_mode(self):
        """Determine the ingestion mode based on environment and availability."""
        if self.mode != "auto":
            return

        logger = logging.getLogger(__name__)

        # Check for local directory
        local_dir = Path(self.local_ingestion_dir)
        local_available = local_dir.exists()

        # Check for Google Drive credentials
        google_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
        google_folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        remote_available = bool(google_creds and google_folder)

        if local_available:
            self.mode = "local"
            logger.info(f"Auto-detected local mode: {self.local_ingestion_dir} exists")
        elif remote_available:
            self.mode = "remote"
            logger.info("Auto-detected remote mode: Google Drive credentials found")
        else:
            logger.warning("No ingestion sources available - defaulting to local mode")
            self.mode = "local"

    def _initialize_components(self):
        """Initialize required components based on mode."""
        logger = logging.getLogger(__name__)

        try:
            # Initialize database manager
            if self.database_url:
                self.db_manager = DatabaseManager(self.database_url)
                logger.info("Database manager initialized")
            else:
                logger.warning(
                    "DATABASE_URL not set - database operations will be skipped"
                )

            # Set base directory for local mode
            if self.mode == "local":
                self.base_dir = self.local_ingestion_dir
                logger.info(f"Local ingestion directory: {self.base_dir}")

        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise

    def validate_environment(self) -> bool:
        """
        Validate the environment for the selected mode.

        Returns:
            bool: True if environment is valid
        """
        logger = logging.getLogger(__name__)

        try:
            if self.mode == "local":
                return self._validate_local_environment()
            elif self.mode == "remote":
                return self._validate_remote_environment()
            else:
                logger.error(f"Unknown mode: {self.mode}")
                return False

        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            return False

    def _validate_local_environment(self) -> bool:
        """Validate local ingestion environment."""
        logger = logging.getLogger(__name__)

        checks = []

        # Check base directory
        base_path = Path(self.base_dir)
        if base_path.exists():
            logger.info(f"✔ Base directory exists: {base_path}")
            checks.append(True)
        else:
            logger.error(f"✗ Base directory does not exist: {base_path}")
            checks.append(False)

        # Check database connection
        if self.db_manager:
            if self.db_manager.test_connection():
                logger.info("✔ Database connection successful")
                checks.append(True)
            else:
                logger.error("✗ Database connection failed")
                checks.append(False)
        else:
            logger.warning("⚠ Database manager not initialized")
            checks.append(True)  # Don't fail for missing DB in local mode

        all_valid = all(checks)

        if all_valid:
            logger.info("✔ Local environment validation successful")
        else:
            logger.error("✗ Local environment validation failed")

        return all_valid

    def _validate_remote_environment(self) -> bool:
        """Validate remote (Google Drive) ingestion environment."""
        logger = logging.getLogger(__name__)

        # For remote mode, use existing validation from ice_ingestion.py
        # This is a placeholder - the existing logic would be moved here

        google_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
        google_folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

        if not google_creds:
            logger.error("✗ GOOGLE_CREDENTIALS_JSON not set")
            return False

        if not google_folder:
            logger.error("✗ GOOGLE_DRIVE_FOLDER_ID not set")
            return False

        logger.info("✔ Remote environment validation successful")
        return True

    def run_ingestion(self) -> Dict[str, Any]:
        """
        Run the ingestion pipeline.

        Returns:
            Dict[str, Any]: Ingestion results
        """
        logger = logging.getLogger(__name__)
        start_time = datetime.now()

        logger.info("=" * 80)
        logger.info(f"Starting ICE Data Ingestion - Mode: {self.mode.upper()}")
        logger.info("=" * 80)

        try:
            # Validate environment
            if not self.validate_environment():
                return {
                    "success": False,
                    "mode": self.mode,
                    "error": "Environment validation failed",
                    "execution_time": (datetime.now() - start_time).total_seconds(),
                }

            # Run ingestion based on mode
            if self.mode == "local":
                result = self._run_local_ingestion()
            elif self.mode == "remote":
                result = self._run_remote_ingestion()
            else:
                raise ValueError(f"Unsupported mode: {self.mode}")

            # Add mode and timing info
            result["mode"] = self.mode
            result["execution_time"] = (datetime.now() - start_time).total_seconds()

            # Log to database if available
            if self.db_manager and result.get("success"):
                try:
                    self._log_to_database(result, start_time, datetime.now())
                except Exception as e:
                    logger.warning(f"Failed to log to database: {e}")

            return result

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return {
                "success": False,
                "mode": self.mode,
                "error": str(e),
                "execution_time": (datetime.now() - start_time).total_seconds(),
            }

    def _run_local_ingestion(self) -> Dict[str, Any]:
        """Run local filesystem ingestion."""
        logger = logging.getLogger(__name__)

        logger.info(f"Starting local ingestion from: {self.base_dir}")

        # Load data using LocalIngestionLoader
        loader = LocalIngestionLoader(self.base_dir)
        result = loader.load_all_data()

        if not result["success"]:
            return result

        # Save document metadata to database
        if self.db_manager and result.get("document_metadata"):
            logger.info("Saving document metadata to database...")

            try:
                # Ensure tables exist
                self.db_manager.ensure_tables_exist()

                # Insert document metadata
                db_result = self.db_manager.bulk_insert_document_metadata(
                    result["document_metadata"]
                )

                result["database_insert"] = db_result
                logger.info(
                    f"✔ Saved metadata to PostgreSQL: {db_result['inserted']} inserted, "
                    f"{db_result['skipped']} skipped"
                )

            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
                result["database_error"] = str(e)

        return result

    def _run_remote_ingestion(self) -> Dict[str, Any]:
        """Run remote (Google Drive) ingestion."""
        logger = logging.getLogger(__name__)

        # This would integrate with the existing Google Drive ingestion logic
        # For now, return a placeholder

        logger.info("Remote ingestion not yet implemented in this pipeline")
        return {
            "success": False,
            "error": "Remote ingestion not yet implemented",
            "student_records": 0,
            "lead_records": 0,
            "document_metadata": [],
            "stats": {},
        }

    def _log_to_database(
        self, result: Dict[str, Any], start_time: datetime, end_time: datetime
    ):
        """Log ingestion run to database."""
        if not self.db_manager:
            return

        logger = logging.getLogger(__name__)

        stats = result.get("stats", {})
        stats["start_time"] = start_time
        stats["end_time"] = end_time

        status = "SUCCESS" if result.get("success") else "ERROR"
        error_message = result.get("error")

        source_path = self.base_dir if self.mode == "local" else "Google Drive"

        log_id = self.db_manager.log_etl_run(
            ingestion_mode=self.mode,
            source_path=source_path,
            stats=stats,
            status=status,
            error_message=error_message,
        )

        logger.info(f"Logged ingestion run to database: log_id={log_id}")


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ICE Data Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode local                    # Force local mode
  %(prog)s --mode remote                   # Force remote mode
  %(prog)s                                # Auto-detect mode
  %(prog)s --base-dir /path/to/data       # Override base directory
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["local", "remote", "auto"],
        default="auto",
        help="Ingestion mode (default: auto)",
    )

    parser.add_argument(
        "--base-dir",
        type=str,
        help="Base directory for local ingestion (overrides LOCAL_INGESTION_DIR)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Override environment variables with CLI arguments
    if args.base_dir:
        os.environ["LOCAL_INGESTION_DIR"] = args.base_dir

    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level

    # Initialize and run pipeline
    try:
        pipeline = ICEIngestionPipeline(mode=args.mode)
        result = pipeline.run_ingestion()

        # Print final summary
        print("\n" + "=" * 80)
        print("INGESTION COMPLETE")
        print("=" * 80)

        if result["success"]:
            stats = result.get("stats", {})
            print(f"✔ Environment validated")
            print(f"✔ Found {stats.get('student_records', 0)} student records")
            print(f"✔ Found {stats.get('lead_records', 0)} lead records")
            print(f"✔ Indexed {stats.get('document_files', 0)} document files")

            if result.get("database_insert"):
                db_stats = result["database_insert"]
                print(f"✔ Saved metadata to PostgreSQL")

            print(f"⏱ Completed in {result['execution_time']:.2f} seconds")
            print("🎉 Ingestion successful!")

            sys.exit(0)
        else:
            print(f"❌ Ingestion failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠ Ingestion interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
