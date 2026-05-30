"""
Single point that constructs ClassificationRequest from DriveFile.
Cloud providers only ever receive ClassificationRequest — never DriveFile or content.
"""
from __future__ import annotations

from drive_organizer.ai.base import ClassificationRequest
from drive_organizer.drive.models import DriveFile


def build_request(file: DriveFile) -> ClassificationRequest:
    return ClassificationRequest(
        file_id=file.id,
        name=file.name,
        mime_type=file.mime_type,
        size=file.size,
        modified_time=file.modified_time,
        extension=file.file_extension,
    )


def build_requests(files: list[DriveFile]) -> list[ClassificationRequest]:
    return [build_request(f) for f in files]
