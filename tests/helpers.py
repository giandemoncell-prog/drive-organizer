from datetime import datetime, timezone

from drive_organizer.drive.models import DriveFile

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
CREATED = datetime(2024, 3, 10, 9, 0, 0, tzinfo=timezone.utc)


def make_file(**kwargs) -> DriveFile:
    return DriveFile(
        id=kwargs.pop("id", "f1"),
        name=kwargs.pop("name", "test.pdf"),
        mime_type=kwargs.pop("mime_type", "application/pdf"),
        modified_time=kwargs.pop("modified_time", NOW),
        created_time=kwargs.pop("created_time", CREATED),
        **kwargs,
    )
