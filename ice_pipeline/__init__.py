"""
ICE Pipeline - Student Application Processing System
===================================================

Enterprise-grade pipeline for processing ICE student application data
including WAT (Work and Travel), H2B, J1, and F1 visa programs.

Features:
- Excel/CSV file processing
- Data validation and cleansing
- Google Drive integration
- Database ingestion
- API endpoints
- Comprehensive testing
"""

__version__ = "1.0.0"
__author__ = "PlanMaestro Team"
__email__ = "dev@planmaestro.com"

# Import modules when needed to avoid circular imports
# from .api import main as api_main
# from .ingestion import ice_manager

__all__ = ["api", "ingestion"]
