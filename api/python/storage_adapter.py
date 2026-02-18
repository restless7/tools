#!/usr/bin/env python3
"""
Storage Adapter Abstraction Layer
Provides a unified interface for document storage operations.
"""

import hashlib
import logging
import mimetypes
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Document metadata structure."""

    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    document_type: str
    checksum: str
    student_id: Optional[str] = None


class StorageAdapter(ABC):
    """
    Abstract base class for storage operations.

    Future implementations:
    - MinIOStorageAdapter: For object storage with MinIO
    - S3StorageAdapter: For AWS S3 storage
    - AzureStorageAdapter: For Azure Blob storage
    """

    @abstractmethod
    def validate_file(self, file_path: str) -> bool:
        """Validate that a file exists and is accessible."""
        pass

    @abstractmethod
    def get_metadata(
        self, file_path: str, student_id: Optional[str] = None
    ) -> DocumentMetadata:
        """Extract metadata from a file."""
        pass

    @abstractmethod
    def upload(self, file_path: str, destination: str) -> Dict[str, Any]:
        """Upload a file to storage (future implementation)."""
        pass

    @abstractmethod
    def get_public_url(self, file_path: str) -> Optional[str]:
        """Get public URL for a stored file (future implementation)."""
        pass

    @abstractmethod
    def delete(self, file_path: str) -> bool:
        """Delete a file from storage (future implementation)."""
        pass


class LocalStorageAdapter(StorageAdapter):
    """
    Local filesystem storage adapter.

    This adapter works with files stored on the local filesystem.
    It validates file existence and extracts metadata without moving files.
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize local storage adapter.

        Args:
            base_path: Base directory for local storage operations
        """
        self.base_path = Path(base_path) if base_path else None
        logger.info(f"LocalStorageAdapter initialized with base_path: {self.base_path}")

    def validate_file(self, file_path: str) -> bool:
        """
        Validate that a file exists and is accessible.

        Args:
            file_path: Path to the file

        Returns:
            bool: True if file exists and is accessible
        """
        try:
            path = Path(file_path)

            # Make absolute if base_path is set
            if self.base_path and not path.is_absolute():
                path = self.base_path / path

            exists = path.exists() and path.is_file()

            if exists:
                logger.debug(f"File validated: {path}")
            else:
                logger.warning(f"File not found or not accessible: {path}")

            return exists

        except Exception as e:
            logger.error(f"Error validating file {file_path}: {e}")
            return False

    def _compute_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """
        Compute file checksum for idempotency checks.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm (sha256, md5, etc.)

        Returns:
            str: Hex digest of the file checksum
        """
        try:
            hash_func = hashlib.new(algorithm)

            with open(file_path, "rb") as f:
                # Read in chunks for memory efficiency
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)

            return hash_func.hexdigest()

        except Exception as e:
            logger.error(f"Error computing checksum for {file_path}: {e}")
            return ""

    def _infer_document_type(
        self, file_name: str, student_id: Optional[str] = None
    ) -> str:
        """
        Infer document type from filename.

        Args:
            file_name: Name of the file
            student_id: Optional student ID for context

        Returns:
            str: Inferred document type
        """
        file_name_lower = file_name.lower()

        # Document type inference rules
        if "passport" in file_name_lower:
            return "passport"
        elif "transcript" in file_name_lower or "academic" in file_name_lower:
            return "transcript"
        elif "visa" in file_name_lower:
            return "visa_form"
        elif "photo" in file_name_lower or "picture" in file_name_lower:
            return "photo"
        elif "certificate" in file_name_lower or "cert" in file_name_lower:
            return "certificate"
        elif "diploma" in file_name_lower:
            return "diploma"
        elif "recommendation" in file_name_lower or "letter" in file_name_lower:
            return "recommendation_letter"
        elif "statement" in file_name_lower:
            return "personal_statement"
        elif "financial" in file_name_lower or "bank" in file_name_lower:
            return "financial_document"
        elif "id" in file_name_lower or "identification" in file_name_lower:
            return "identification"
        else:
            return "other"

    def get_metadata(
        self, file_path: str, student_id: Optional[str] = None
    ) -> DocumentMetadata:
        """
        Extract metadata from a file.

        Args:
            file_path: Path to the file
            student_id: Optional student ID

        Returns:
            DocumentMetadata: Extracted file metadata
        """
        try:
            path = Path(file_path)

            # Make absolute if base_path is set
            if self.base_path and not path.is_absolute():
                path = self.base_path / path

            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            # Get file stats
            stats = path.stat()
            file_size = stats.st_size

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(path))
            if mime_type is None:
                mime_type = "application/octet-stream"

            # Compute checksum for idempotency
            checksum = self._compute_checksum(path)

            # Infer document type
            document_type = self._infer_document_type(path.name, student_id)

            metadata = DocumentMetadata(
                file_name=path.name,
                file_path=str(path.absolute()),
                file_size=file_size,
                mime_type=mime_type,
                document_type=document_type,
                checksum=checksum,
                student_id=student_id,
            )

            logger.debug(
                f"Extracted metadata for {path.name}: {document_type}, {file_size} bytes"
            )

            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}")
            raise

    def upload(self, file_path: str, destination: str) -> Dict[str, Any]:
        """
        Upload operation (not implemented for local storage).

        For local storage, files are already in place.
        Future MinIO implementation will handle actual uploads.

        Args:
            file_path: Source file path
            destination: Destination path

        Returns:
            dict: Upload result (placeholder)
        """
        logger.info(
            f"Upload operation called for local storage (no-op): {file_path} -> {destination}"
        )

        return {
            "success": True,
            "message": "Local storage - file already in place",
            "source": file_path,
            "destination": destination,
            "adapter": "LocalStorageAdapter",
        }

    def get_public_url(self, file_path: str) -> Optional[str]:
        """
        Get public URL for a file (not applicable for local storage).

        Future MinIO implementation will return actual URLs.

        Args:
            file_path: Path to the file

        Returns:
            Optional[str]: None for local storage (no public URL)
        """
        logger.debug(f"get_public_url called for local storage: {file_path}")
        return None

    def delete(self, file_path: str) -> bool:
        """
        Delete a file (not implemented for local storage to prevent data loss).

        Args:
            file_path: Path to the file

        Returns:
            bool: False (deletion not supported in local mode)
        """
        logger.warning(
            f"Delete operation not supported in local storage mode: {file_path}"
        )
        return False


def get_storage_adapter(mode: str = "local", **kwargs) -> StorageAdapter:
    """
    Factory function to get the appropriate storage adapter.

    Args:
        mode: Storage mode ('local', 'minio', 's3', etc.)
        **kwargs: Additional configuration for the adapter

    Returns:
        StorageAdapter: Configured storage adapter instance
    """
    if mode == "local":
        return LocalStorageAdapter(base_path=kwargs.get("base_path"))
    elif mode == "minio":
        # Future implementation
        raise NotImplementedError("MinIO storage adapter not yet implemented")
    elif mode == "s3":
        # Future implementation
        raise NotImplementedError("S3 storage adapter not yet implemented")
    else:
        raise ValueError(f"Unknown storage mode: {mode}")


if __name__ == "__main__":
    # Test the adapter
    logging.basicConfig(level=logging.DEBUG)

    adapter = get_storage_adapter("local", base_path="/mnt/ice-ingestion-data")

    print("LocalStorageAdapter test initialized")
    print(f"Base path: {adapter.base_path}")
