"""
Ollama-ONLY path for content-based classification.
Content is never passed to cloud APIs.
"""
from __future__ import annotations

import atexit
import io
import os
import tempfile
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload


_TEMP_DIRS: list[str] = []


def _cleanup_all():
    import shutil
    for d in _TEMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)


atexit.register(_cleanup_all)


def extract_text_preview(service, file_id: str, mime_type: str, max_chars: int = 500) -> str:
    """Download file temporarily and extract text preview. Cleaned up immediately."""
    tmp_dir = tempfile.mkdtemp()
    _TEMP_DIRS.append(tmp_dir)
    tmp_path = Path(tmp_dir) / "content"
    try:
        if mime_type.startswith("application/vnd.google-apps."):
            export_mime = "text/plain"
            req = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            req = service.files().get_media(fileId=file_id)

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        buf.seek(0)
        raw = buf.read(max_chars * 4)
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        return text[:max_chars]
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if tmp_dir in _TEMP_DIRS:
            _TEMP_DIRS.remove(tmp_dir)
