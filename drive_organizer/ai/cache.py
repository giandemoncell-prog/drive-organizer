from __future__ import annotations

from drive_organizer.ai.base import ClassificationResult
from drive_organizer.drive.models import DriveFile


def _size_bucket(size: int | None) -> str:
    if size is None:
        return "native"
    if size < 10_000:
        return "tiny"
    if size < 1_000_000:
        return "small"
    if size < 100_000_000:
        return "medium"
    return "large"


class SignatureCache:
    """Caches classification results by (extension, size_bucket, mime_type) key."""

    def __init__(self) -> None:
        self._cache: dict[tuple, ClassificationResult] = {}

    def _key(self, file: DriveFile) -> tuple:
        return (
            (file.file_extension or "").lower(),
            _size_bucket(file.size),
            file.mime_type,
        )

    def get(self, file: DriveFile) -> ClassificationResult | None:
        return self._cache.get(self._key(file))

    def set(self, file: DriveFile, result: ClassificationResult) -> None:
        key = self._key(file)
        if key not in self._cache:
            self._cache[key] = result

    def size(self) -> int:
        return len(self._cache)
