"""Storage abstraction — local filesystem MVP, interface for S3 later."""

from __future__ import annotations
import abc
from pathlib import Path
from typing import Optional

from .config import settings


class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def save(self, key: str, data: bytes, content_type: str = "image/png") -> str: ...
    @abc.abstractmethod
    def get(self, key: str) -> Optional[bytes]: ...
    @abc.abstractmethod
    def url(self, key: str) -> str: ...
    @abc.abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path, base_url: str):
        self.base_dir = base_dir
        self.base_url = base_url.rstrip("/")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base_dir / key

    def save(self, key: str, data: bytes, content_type: str = "image/png") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    def get(self, key: str) -> Optional[bytes]:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    def url(self, key: str) -> str:
        return f"{self.base_url}/files/{key}"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


def create_storage() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorage(base_dir=settings.resolved_output_dir, base_url=settings.base_url)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")
