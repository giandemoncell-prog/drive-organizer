from __future__ import annotations

from drive_organizer.ai.base import ClassificationResult
from drive_organizer.drive.models import DriveFile
from drive_organizer.strategies.base import OrganizationStrategy

_MIME_MAP: dict[str, str] = {
    # Google native
    "application/vnd.google-apps.document": "Documenti",
    "application/vnd.google-apps.spreadsheet": "Fogli",
    "application/vnd.google-apps.presentation": "Presentazioni",
    "application/vnd.google-apps.form": "Moduli",
    "application/vnd.google-apps.drawing": "Disegni",
    "application/vnd.google-apps.script": "Codice",
    # Office
    "application/msword": "Documenti",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Documenti",
    "application/vnd.ms-excel": "Fogli",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Fogli",
    "application/vnd.ms-powerpoint": "Presentazioni",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "Presentazioni",
    # PDF
    "application/pdf": "PDF",
    # Images
    "image/jpeg": "Immagini",
    "image/png": "Immagini",
    "image/gif": "Immagini",
    "image/webp": "Immagini",
    "image/svg+xml": "Immagini",
    "image/tiff": "Immagini",
    "image/bmp": "Immagini",
    "image/heic": "Immagini",
    # Video
    "video/mp4": "Video",
    "video/quicktime": "Video",
    "video/x-msvideo": "Video",
    "video/mpeg": "Video",
    "video/webm": "Video",
    "video/x-matroska": "Video",
    # Audio
    "audio/mpeg": "Audio",
    "audio/wav": "Audio",
    "audio/flac": "Audio",
    "audio/ogg": "Audio",
    "audio/aac": "Audio",
    "audio/x-m4a": "Audio",
    # Archives
    "application/zip": "Archivi",
    "application/x-rar-compressed": "Archivi",
    "application/x-tar": "Archivi",
    "application/gzip": "Archivi",
    "application/x-7z-compressed": "Archivi",
    # Code
    "text/x-python": "Codice",
    "application/javascript": "Codice",
    "text/html": "Codice",
    "text/css": "Codice",
    "application/json": "Codice",
    "application/xml": "Codice",
    "text/x-java-source": "Codice",
    # Text
    "text/plain": "Testo",
    "text/csv": "Fogli",
    "text/markdown": "Documenti",
}

_EXT_MAP: dict[str, str] = {
    "py": "Codice", "js": "Codice", "ts": "Codice", "java": "Codice",
    "cpp": "Codice", "c": "Codice", "h": "Codice", "go": "Codice",
    "rs": "Codice", "rb": "Codice", "php": "Codice", "sh": "Codice",
    "sql": "Codice", "yaml": "Codice", "yml": "Codice", "toml": "Codice",
    "json": "Codice", "xml": "Codice",
    "pdf": "PDF",
    "jpg": "Immagini", "jpeg": "Immagini", "png": "Immagini",
    "gif": "Immagini", "webp": "Immagini", "svg": "Immagini",
    "bmp": "Immagini", "tiff": "Immagini", "tif": "Immagini",
    "mp4": "Video", "mov": "Video", "avi": "Video", "mkv": "Video",
    "webm": "Video", "mpeg": "Video", "mpg": "Video",
    "mp3": "Audio", "wav": "Audio", "flac": "Audio",
    "ogg": "Audio", "aac": "Audio", "m4a": "Audio",
    "zip": "Archivi", "rar": "Archivi", "tar": "Archivi",
    "gz": "Archivi", "7z": "Archivi", "bz2": "Archivi",
    "doc": "Documenti", "docx": "Documenti", "odt": "Documenti",
    "xls": "Fogli", "xlsx": "Fogli", "ods": "Fogli", "csv": "Fogli",
    "ppt": "Presentazioni", "pptx": "Presentazioni", "odp": "Presentazioni",
    "txt": "Testo", "md": "Documenti", "rtf": "Documenti",
}

_FOLDERS = sorted(set(_MIME_MAP.values()) | set(_EXT_MAP.values()))


class FileTypeStrategy(OrganizationStrategy):
    name = "type"
    description = "Organizza per tipo di file (Documenti, Immagini, Video…)"

    def build_prompt_hint(self) -> str:
        return f"Classify by file type into one of: {', '.join(_FOLDERS)}"

    def allowed_folders(self) -> list[str]:
        return [*_FOLDERS, "Altro"]

    def requires_ai(self) -> bool:
        return False

    def classify_without_ai(self, file: DriveFile) -> ClassificationResult:
        folder = (
            _MIME_MAP.get(file.mime_type)
            or _EXT_MAP.get((file.file_extension or "").lower())
            or "Altro"
        )
        return ClassificationResult(
            file_id=file.id,
            target_path=folder,
            confidence=1.0,
            reasoning=f"MIME: {file.mime_type}",
            provider="deterministic",
        )
