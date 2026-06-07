from __future__ import annotations

import json
from pathlib import Path

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


_DEFAULT_CACHE_PATH = Path(".drive_organizer_cache.json")


class SignatureCache:
    """Caches classification results by (extension, size_bucket, mime_type).

    Persists to disk between sessions — avoids redundant AI calls on repeated runs.
    Key is a pipe-separated string so it survives JSON serialization.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_CACHE_PATH
        self._cache: dict[str, ClassificationResult] = {}
        self._dirty = False
        self._load()

    def _key(self, file: DriveFile) -> str:
        return f"{(file.file_extension or '').lower()}|{_size_bucket(file.size)}|{file.mime_type}"

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    try:
                        self._cache[k] = ClassificationResult.model_validate(v)
                    except Exception:
                        pass
        except Exception:
            pass

    def save(self) -> None:
        """Persist cache to disk atomically. No-op if nothing changed."""
        if not self._dirty:
            return
        try:
            data = {k: v.model_dump(mode="json") for k, v in self._cache.items()}
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(self._path)
            self._dirty = False
        except Exception:
            pass

    def get(self, file: DriveFile) -> ClassificationResult | None:
        return self._cache.get(self._key(file))

    def set(self, file: DriveFile, result: ClassificationResult) -> None:
        key = self._key(file)
        if key not in self._cache:
            self._cache[key] = result
            self._dirty = True

    def size(self) -> int:
        return len(self._cache)
