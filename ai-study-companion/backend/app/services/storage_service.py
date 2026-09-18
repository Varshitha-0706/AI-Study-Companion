"""
StorageService abstraction for file storage.
Supports local filesystem (dev) and S3 (prod) backends.
Configured via STORAGE_BACKEND env var: "local" | "s3"

This abstraction means switching to S3 in production requires
only setting STORAGE_BACKEND=s3 and S3 credentials — no app code changes.
"""
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.core.config import settings


class StorageService(ABC):
    """Abstract storage interface. All implementations must enforce this contract."""

    @abstractmethod
    async def save(self, file_data: bytes, user_id: str, project_id: str, filename: str) -> str:
        """Save file and return the storage key/path."""
        ...

    @abstractmethod
    async def read(self, storage_key: str) -> bytes:
        """Read file by storage key."""
        ...

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        """Delete file by storage key."""
        ...

    @abstractmethod
    def get_storage_key(self, user_id: str, project_id: str, filename: str) -> str:
        """Generate a consistent storage key."""
        ...


class LocalStorageService(StorageService):
    """
    Local filesystem storage for development.
    Files stored at: {UPLOAD_DIR}/{user_id}/{project_id}/{filename}
    This path structure enforces user/project isolation at the OS level.
    """

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_storage_key(self, user_id: str, project_id: str, filename: str) -> str:
        return f"{user_id}/{project_id}/{filename}"

    async def save(self, file_data: bytes, user_id: str, project_id: str, filename: str) -> str:
        storage_key = self.get_storage_key(user_id, project_id, filename)
        full_path = self.base_dir / storage_key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(file_data)
        return storage_key

    async def read(self, storage_key: str) -> bytes:
        full_path = self.base_dir / storage_key
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {storage_key}")
        return full_path.read_bytes()

    async def delete(self, storage_key: str) -> None:
        full_path = self.base_dir / storage_key
        if full_path.exists():
            full_path.unlink()

    def get_full_path(self, storage_key: str) -> str:
        """Get full filesystem path (needed by PyMuPDF)."""
        return str(self.base_dir / storage_key)


class S3StorageService(StorageService):
    """
    AWS S3 (or S3-compatible) storage for production.
    Requires: S3_BUCKET, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    """

    def __init__(self):
        # Import boto3 only when S3 backend is selected
        import boto3
        self.s3 = boto3.client(
            "s3",
             endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = settings.S3_BUCKET

    def get_storage_key(self, user_id: str, project_id: str, filename: str) -> str:
        return f"uploads/{user_id}/{project_id}/{filename}"

    async def save(self, file_data: bytes, user_id: str, project_id: str, filename: str) -> str:
        storage_key = self.get_storage_key(user_id, project_id, filename)
        self.s3.put_object(Bucket=self.bucket, Key=storage_key, Body=file_data)
        return storage_key

    async def read(self, storage_key: str) -> bytes:
        response = self.s3.get_object(Bucket=self.bucket, Key=storage_key)
        return response["Body"].read()

    async def delete(self, storage_key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=storage_key)


def get_storage_service() -> StorageService:
    """Factory — returns configured storage backend."""
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "s3":
        return S3StorageService()
    else:
        return LocalStorageService(base_dir=settings.UPLOAD_DIR)


# Singleton
storage_service: StorageService = get_storage_service()
