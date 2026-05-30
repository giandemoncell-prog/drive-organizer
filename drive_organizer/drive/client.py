from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from googleapiclient.errors import HttpError
from rich.progress import Progress

from drive_organizer.drive.models import DriveFile, MoveOperation
from drive_organizer.config import settings

_FIELDS = (
    "nextPageToken, files("
    "id,name,mimeType,size,modifiedTime,createdTime,parents,"
    "fileExtension,trashed,ownedByMe,"
    "capabilities/canMoveItemWithinDrive,"
    "driveId,shortcutDetails,md5Checksum"
    ")"
)


class DriveClient:
    def __init__(self, service):
        self._svc = service
        self._folder_cache: dict[str, str] = {}

    def scan_all_files(
        self,
        progress: Progress | None = None,
        task_id=None,
    ) -> tuple[list[DriveFile], dict[str, str]]:
        """Returns (files, folder_id_to_name). Never downloads content."""
        files: list[DriveFile] = []
        folder_map: dict[str, str] = {}
        page_token: str | None = None

        while True:
            kwargs: dict = dict(
                pageSize=1000,
                fields=_FIELDS,
                q="trashed=false",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            if page_token:
                kwargs["pageToken"] = page_token

            resp = self._svc.files().list(**kwargs).execute()
            items = resp.get("files", [])

            for item in items:
                caps = item.get("capabilities", {})
                shortcut = item.get("shortcutDetails")
                f = DriveFile(
                    id=item["id"],
                    name=item["name"],
                    mime_type=item["mimeType"],
                    size=int(item["size"]) if item.get("size") else None,
                    modified_time=item["modifiedTime"],
                    created_time=item["createdTime"],
                    parents=item.get("parents", []),
                    file_extension=item.get("fileExtension"),
                    owned_by_me=item.get("ownedByMe", True),
                    can_move=caps.get("canMoveItemWithinDrive", True),
                    drive_id=item.get("driveId"),
                    is_shortcut=shortcut is not None,
                    md5=item.get("md5Checksum"),
                )
                if f.is_folder:
                    folder_map[f.id] = f.name
                else:
                    files.append(f)

            if progress and task_id is not None:
                progress.advance(task_id, len(items))

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return files, folder_map

    def create_folder(self, name: str, parent_id: str) -> str:
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        result = self._svc.files().create(body=body, fields="id", supportsAllDrives=True).execute()
        return result["id"]

    def _find_folder(self, name: str, parent_id: str) -> str | None:
        q = (
            f"name={name!r} and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents and trashed=false"
        )
        resp = self._svc.files().list(q=q, fields="files(id)", pageSize=1, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items = resp.get("files", [])
        return items[0]["id"] if items else None

    def get_or_create_folder_path(self, path: str, root_id: str = "root") -> str:
        """Walk/create folder hierarchy, returns leaf folder ID. Idempotent."""
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        current_id = root_id

        for part in parts:
            cache_key = f"{current_id}/{part}"
            if cache_key in self._folder_cache:
                current_id = self._folder_cache[cache_key]
                continue

            found = self._find_folder(part, current_id)
            if found:
                current_id = found
            else:
                current_id = self.create_folder(part, current_id)

            self._folder_cache[cache_key] = current_id

        return current_id

    def rename_file(self, file_id: str, new_name: str) -> None:
        self._svc.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields="id,name",
            supportsAllDrives=True,
        ).execute()

    def move_file(self, file_id: str, new_parent_id: str, old_parent_id: str) -> None:
        self._svc.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=old_parent_id,
            fields="id,parents",
            supportsAllDrives=True,
        ).execute()

    def batch_move(
        self,
        operations: list[MoveOperation],
        progress: Progress | None = None,
        task_id=None,
        on_success: Callable[[MoveOperation], None] | None = None,
    ) -> list[str]:
        """Execute moves one by one. Returns list of failed file_ids."""
        failed: list[str] = []
        for op in operations:
            if op.skipped or not op.target_parent_id:
                continue
            try:
                old_parent = op.source_parents[0] if op.source_parents else "root"
                self.move_file(op.file_id, op.target_parent_id, old_parent)
                if on_success:
                    on_success(op)
            except HttpError as e:
                if e.resp.status == 429:
                    time.sleep(5)
                    try:
                        old_parent = op.source_parents[0] if op.source_parents else "root"
                        self.move_file(op.file_id, op.target_parent_id, old_parent)
                        if on_success:
                            on_success(op)
                    except Exception:
                        failed.append(op.file_id)
                else:
                    failed.append(op.file_id)
            except Exception:
                failed.append(op.file_id)

            if progress and task_id is not None:
                progress.advance(task_id)

        return failed

    def get_about(self) -> dict:
        return self._svc.about().get(fields="user,storageQuota").execute()
