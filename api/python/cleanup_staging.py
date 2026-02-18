#!/usr/bin/env python3
"""
Staging Cleanup Utility
Cleans all staging data for fresh V3 ingestion
"""

import logging
import os
import shutil
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class StagingCleaner:
    """
    Cleans staging environment for fresh ingestion.
    """

    def __init__(self, staging_dir: str, db_url: str):
        """
        Initialize staging cleaner.

        Args:
            staging_dir: Staging directory path
            db_url: Database connection URL
        """
        self.staging_dir = Path(staging_dir)
        self.db_url = db_url

        logger.info(f"Initialized StagingCleaner for: {self.staging_dir}")

    def clean_database(self, confirm: bool = False):
        """
        Clean all staging tables in database.

        Args:
            confirm: Must be True to proceed (safety check)
        """
        if not confirm:
            logger.warning(
                "⚠️  Database cleanup requires confirmation. Set confirm=True"
            )
            return False

        logger.info("=" * 60)
        logger.info("CLEANING STAGING DATABASE")
        logger.info("=" * 60)

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            # Get table names - Delete in order respecting foreign keys
            tables = [
                "staging_document",
                "staging_student",
                "staging_lead",  # Added staging_lead
                "staging_person",
                "staging_reference_data",
                "staging_ingestion_run",
                "staging_lead_failures",  # Added failures table
            ]

            # Delete in reverse order (respecting foreign keys)
            for table in tables:
                try:
                    cur.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
                    deleted = cur.fetchone()
                    logger.info(f"✔ Cleaned {table}")
                except Exception as e:
                    logger.warning(f"  Table {table} not found or error: {e}")

            # Reset sequences
            sequences = [
                "staging_document_id_seq",
                "staging_ingestion_run_id_seq",
                "staging_reference_data_id_seq",
                "staging_lead_failures_id_seq",  # Added failures sequence
            ]

            for seq in sequences:
                try:
                    cur.execute(
                        sql.SQL("ALTER SEQUENCE {} RESTART WITH 1").format(
                            sql.Identifier(seq)
                        )
                    )
                    logger.info(f"✔ Reset sequence {seq}")
                except Exception as e:
                    logger.warning(f"  Sequence {seq} not found: {e}")

            conn.commit()
            cur.close()
            conn.close()

            logger.info("=" * 60)
            logger.info("✅ DATABASE CLEANED SUCCESSFULLY")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"❌ Database cleanup failed: {e}")
            return False

    def clean_documents(self, confirm: bool = False):
        """
        Clean documents directory.

        Args:
            confirm: Must be True to proceed (safety check)
        """
        if not confirm:
            logger.warning(
                "⚠️  Document cleanup requires confirmation. Set confirm=True"
            )
            return False

        logger.info("=" * 60)
        logger.info("CLEANING DOCUMENTS DIRECTORY")
        logger.info("=" * 60)

        documents_dir = self.staging_dir / "documents"

        if not documents_dir.exists():
            logger.info("Documents directory doesn't exist. Nothing to clean.")
            return True

        try:
            # Count before deletion
            student_folders = list(documents_dir.iterdir())
            total_files = sum(
                1
                for folder in student_folders
                if folder.is_dir()
                for _ in folder.iterdir()
            )

            logger.info(
                f"Found {len(student_folders)} student folders with {total_files} files"
            )

            # Delete all student folders
            for folder in student_folders:
                if folder.is_dir():
                    shutil.rmtree(folder)

            logger.info("=" * 60)
            logger.info("✅ DOCUMENTS CLEANED SUCCESSFULLY")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"❌ Document cleanup failed: {e}")
            return False

    def clean_extracted_csvs(self, confirm: bool = False):
        """
        Clean extracted CSV directory.

        Args:
            confirm: Must be True to proceed (safety check)
        """
        if not confirm:
            logger.warning("⚠️  CSV cleanup requires confirmation. Set confirm=True")
            return False

        logger.info("=" * 60)
        logger.info("CLEANING EXTRACTED CSVS")
        logger.info("=" * 60)

        csvs_dir = self.staging_dir / "extracted_csvs"

        if not csvs_dir.exists():
            logger.info("Extracted CSVs directory doesn't exist. Nothing to clean.")
            return True

        try:
            # Count before deletion
            csv_files = list(csvs_dir.glob("*.csv"))

            logger.info(f"Found {len(csv_files)} CSV files")

            # Delete all CSV files
            for csv_file in csv_files:
                csv_file.unlink()

            logger.info("=" * 60)
            logger.info("✅ EXTRACTED CSVS CLEANED SUCCESSFULLY")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"❌ CSV cleanup failed: {e}")
            return False

    def clean_reports(self, confirm: bool = False):
        """
        Clean old reports (keep directory).

        Args:
            confirm: Must be True to proceed (safety check)
        """
        if not confirm:
            logger.warning("⚠️  Report cleanup requires confirmation. Set confirm=True")
            return False

        logger.info("=" * 60)
        logger.info("CLEANING OLD REPORTS")
        logger.info("=" * 60)

        reports_dir = self.staging_dir / "reports"

        if not reports_dir.exists():
            logger.info("Reports directory doesn't exist. Nothing to clean.")
            return True

        try:
            # Count before deletion
            report_files = [
                f
                for f in reports_dir.iterdir()
                if f.is_file() and f.suffix in [".txt", ".json"]
            ]

            logger.info(f"Found {len(report_files)} report files")

            # Delete all report files
            for report_file in report_files:
                report_file.unlink()

            logger.info("=" * 60)
            logger.info("✅ REPORTS CLEANED SUCCESSFULLY")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"❌ Report cleanup failed: {e}")
            return False

    def clean_all(self, confirm: bool = False):
        """
        Clean everything (database + files).

        Args:
            confirm: Must be True to proceed (safety check)
        """
        if not confirm:
            logger.error("=" * 60)
            logger.error("⚠️  CLEANUP REQUIRES CONFIRMATION")
            logger.error("=" * 60)
            logger.error("This will DELETE ALL staging data:")
            logger.error("  - All database records")
            logger.error("  - All student documents")
            logger.error("  - All extracted CSVs")
            logger.error("  - All reports")
            logger.error("")
            logger.error("To proceed, call with confirm=True")
            logger.error("=" * 60)
            return False

        logger.info("\n" + "=" * 60)
        logger.info("🧹 STARTING COMPLETE STAGING CLEANUP")
        logger.info("=" * 60)

        results = {
            "database": self.clean_database(confirm=True),
            "documents": self.clean_documents(confirm=True),
            "csvs": self.clean_extracted_csvs(confirm=True),
            "reports": self.clean_reports(confirm=True),
        }

        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP SUMMARY")
        logger.info("=" * 60)
        for component, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            logger.info(f"{component.upper():<20} {status}")

        all_success = all(results.values())

        if all_success:
            logger.info("\n" + "=" * 60)
            logger.info("✅ COMPLETE CLEANUP SUCCESSFUL")
            logger.info("Ready for fresh V3 ingestion!")
            logger.info("=" * 60)
        else:
            logger.error("\n" + "=" * 60)
            logger.error("⚠️  SOME CLEANUP OPERATIONS FAILED")
            logger.error("Check logs above for details")
            logger.error("=" * 60)

        return all_success

    def get_staging_stats(self):
        """
        Get current staging statistics.

        Returns:
            dict: Statistics about current staging state
        """
        stats = {"database": {}, "files": {}}

        # Database stats
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            tables = [
                "staging_person",
                "staging_student",
                "staging_document",
                "staging_lead",
                "staging_reference_data",
                "staging_ingestion_run",
                "staging_lead_failures",
            ]

            for table in tables:
                try:
                    cur.execute(
                        sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                    )
                    count = cur.fetchone()[0]
                    stats["database"][table] = count
                except Exception as e:
                    stats["database"][table] = f"Error: {e}"

            cur.close()
            conn.close()

        except Exception as e:
            stats["database"]["error"] = str(e)

        # File stats
        documents_dir = self.staging_dir / "documents"
        if documents_dir.exists():
            student_folders = [f for f in documents_dir.iterdir() if f.is_dir()]
            total_files = sum(1 for folder in student_folders for _ in folder.iterdir())
            stats["files"]["student_folders"] = len(student_folders)
            stats["files"]["total_documents"] = total_files

        csvs_dir = self.staging_dir / "extracted_csvs"
        if csvs_dir.exists():
            stats["files"]["extracted_csvs"] = len(list(csvs_dir.glob("*.csv")))

        reports_dir = self.staging_dir / "reports"
        if reports_dir.exists():
            stats["files"]["reports"] = len(
                [f for f in reports_dir.iterdir() if f.is_file()]
            )

        return stats


def main():
    """Main execution with interactive confirmation."""
    import sys

    # Configuration
    STAGING_DIR = os.getenv("STAGING_DIR", "/home/sebastiangarcia/ice-data-staging")
    DB_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:224207bB@localhost:5432/leads_project"
    )

    cleaner = StagingCleaner(STAGING_DIR, DB_URL)

    # Show current stats
    print("\n" + "=" * 60)
    print("CURRENT STAGING STATISTICS")
    print("=" * 60)

    stats = cleaner.get_staging_stats()

    print("\nDatabase Records:")
    for table, count in stats["database"].items():
        print(f"  {table:<30} {count:>10}")

    print("\nFiles:")
    for category, count in stats["files"].items():
        print(f"  {category:<30} {count:>10}")

    print("\n" + "=" * 60)

    # Interactive confirmation
    if len(sys.argv) > 1 and sys.argv[1] == "--confirm":
        cleaner.clean_all(confirm=True)
    else:
        print("\n⚠️  DRY RUN MODE")
        print("To actually clean staging data, run:")
        print("  python3 cleanup_staging.py --confirm")
        print("\nOr use programmatically:")
        print("  cleaner.clean_all(confirm=True)")


if __name__ == "__main__":
    main()
