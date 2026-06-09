"""
Rinomina file via Ollama locale.
Il contenuto viene letto solo da Ollama — non esce mai verso API cloud.
"""
from __future__ import annotations

import re

import requests

from drive_organizer.config import settings
from drive_organizer.drive.models import DriveFile, RenameOperation, RenamePlan

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "suggested_name": {"type": "string"},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["suggested_name", "confidence", "reasoning"],
}

_SYSTEM = (
    "You are a file naming assistant. "
    "Based on the file name and content preview, suggest a clear, human-readable filename in Italian. "
    "Rules: keep the same file extension; use only letters, numbers, spaces, hyphens and underscores; "
    "max 80 characters; no special characters; descriptive but concise. "
    "If the current name is already good, return it unchanged with confidence=1.0. "
    "Set confidence < 0.6 if you are unsure about the content."
)

_METADATA_SYSTEM = (
    "You are a file naming assistant. "
    "Based ONLY on the filename and metadata, suggest a cleaner, more readable filename in Italian. "
    "Rules: keep the same extension; use only letters, numbers, spaces, hyphens, underscores; max 80 chars. "
    "If the current name is already good, return it unchanged with confidence=0.7. "
    "Set confidence < 0.5 for generic names like 'document(1)', 'Untitled', etc."
)

_SKIP_MIMES = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
}

_CONTENT_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
    "text/x-python",
    "application/javascript",
    "text/html",
}

_MIN_CONFIDENCE = 0.65


def _sanitize(name: str, extension: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if extension and not name.lower().endswith(f".{extension.lower()}"):
        name = f"{name}.{extension}"
    return name[:120]


def _extract_extension(file: DriveFile) -> str:
    if file.file_extension:
        return file.file_extension.lower()
    if file.is_google_doc:
        mime_to_ext = {
            "application/vnd.google-apps.document": "",
            "application/vnd.google-apps.spreadsheet": "",
            "application/vnd.google-apps.presentation": "",
        }
        return mime_to_ext.get(file.mime_type, "")
    return ""


def _ollama_rename(
    prompt_user: str,
    system: str,
    base_url: str,
    model: str,
) -> dict:
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0.2},
        "format": _RESPONSE_SCHEMA,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt_user},
        ],
    }
    resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=60)
    resp.raise_for_status()
    import json
    import re as re2
    raw = resp.json()["message"]["content"]
    try:
        return json.loads(raw)
    except Exception:
        match = re2.search(r"\{[^{}]*\}", raw, re2.DOTALL)
        if match:
            return json.loads(match.group())
        raise


class FileRenamer:
    def __init__(self, drive_service, confidence_threshold: float = _MIN_CONFIDENCE):
        self._svc = drive_service
        self._threshold = confidence_threshold
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def build_plan(
        self,
        files: list[DriveFile],
        progress=None,
        task_id=None,
    ) -> RenamePlan:
        plan = RenamePlan(total_files=len(files))

        for f in files:
            if progress and task_id is not None:
                progress.advance(task_id)

            # Skip folders, shortcuts, non-owned
            if f.mime_type in _SKIP_MIMES or f.is_folder or not f.owned_by_me:
                plan.operations.append(RenameOperation(
                    file_id=f.id, old_name=f.name, new_name=f.name,
                    confidence=0.0, skipped=True,
                    skip_reason="cartella / shortcut / non owned",
                ))
                plan.skipped_files += 1
                continue

            extension = _extract_extension(f)

            try:
                op = self._suggest_rename(f, extension)
            except Exception as e:
                op = RenameOperation(
                    file_id=f.id, old_name=f.name, new_name=f.name,
                    confidence=0.0, skipped=True, skip_reason=f"errore Ollama: {e}",
                )

            # Skip if confidence too low or name unchanged
            if not op.skipped and (op.confidence < self._threshold or op.new_name == op.old_name):
                op.skipped = True
                op.skip_reason = (
                    "nome già ottimale" if op.new_name == op.old_name
                    else f"confidenza bassa ({op.confidence:.2f})"
                )

            if op.skipped:
                plan.skipped_files += 1

            plan.operations.append(op)

        return plan

    def _suggest_rename(self, file: DriveFile, extension: str) -> RenameOperation:
        use_content = file.mime_type in _CONTENT_MIMES

        if use_content:
            content = self._get_content_preview(file)
            prompt = (
                f"File: {file.name!r}\n"
                f"Extension: {extension!r}\n"
                f"MIME: {file.mime_type!r}\n"
                f"Content preview:\n{content}\n\n"
                "Suggest a clear, descriptive Italian filename."
            )
            system = _SYSTEM
        else:
            prompt = (
                f"File: {file.name!r}\n"
                f"Extension: {extension!r}\n"
                f"MIME: {file.mime_type!r}\n"
                f"Size: {file.size} bytes\n"
                f"Modified: {file.modified_time.date()}\n\n"
                "Suggest a cleaner Italian filename based on these metadata."
            )
            system = _METADATA_SYSTEM

        parsed = _ollama_rename(prompt, system, self._base_url, self._model)
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        suggested = _sanitize(parsed.get("suggested_name", file.name), extension)

        return RenameOperation(
            file_id=file.id,
            old_name=file.name,
            new_name=suggested,
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
        )

    def _get_content_preview(self, file: DriveFile, max_chars: int = 600) -> str:
        try:
            from drive_organizer.content_extractor import extract_text_preview
            return extract_text_preview(self._svc, file.id, file.mime_type, max_chars)
        except Exception:
            return ""
