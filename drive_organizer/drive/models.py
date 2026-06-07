from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class DriveFile(BaseModel):
    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: datetime
    created_time: datetime
    parents: list[str] = Field(default_factory=list)
    file_extension: str | None = None
    owned_by_me: bool = True
    can_move: bool = True
    drive_id: str | None = None
    is_shortcut: bool = False
    md5: str | None = None

    @property
    def is_google_doc(self) -> bool:
        return self.mime_type.startswith("application/vnd.google-apps.") and self.mime_type != "application/vnd.google-apps.folder"

    @property
    def is_folder(self) -> bool:
        return self.mime_type == "application/vnd.google-apps.folder"


class RollbackEntry(BaseModel):
    file_id: str
    file_name: str
    moved_from_parents: list[str]
    moved_to_parent_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MoveOperation(BaseModel):
    file_id: str
    file_name: str
    source_parents: list[str]
    target_path: str
    target_parent_id: str | None = None
    confidence: float
    provider: str
    skipped: bool = False
    skip_reason: str | None = None


class OrganizationPlan(BaseModel):
    strategy_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    moves: list[MoveOperation] = Field(default_factory=list)
    folders_to_create: list[str] = Field(default_factory=list)
    total_files: int = 0
    skipped_files: int = 0


class RollbackManifest(BaseModel):
    schema_version: int = 1
    run_id: str
    strategy: str
    started_at: datetime
    completed_at: datetime | None = None
    drive_user_email: str = ""
    entries: list[RollbackEntry] = Field(default_factory=list)
    folders_created: list[str] = Field(default_factory=list)


class RenameOperation(BaseModel):
    file_id: str
    old_name: str
    new_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    skipped: bool = False
    skip_reason: str | None = None


class RenamePlan(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    operations: list[RenameOperation] = Field(default_factory=list)
    total_files: int = 0
    skipped_files: int = 0


class RenameManifestEntry(BaseModel):
    file_id: str
    old_name: str
    new_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RenameManifest(BaseModel):
    schema_version: int = 1
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    drive_user_email: str = ""
    entries: list[RenameManifestEntry] = Field(default_factory=list)
