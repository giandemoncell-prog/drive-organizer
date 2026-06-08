from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable

from googleapiclient.errors import HttpError
from rich.progress import Progress

from drive_organizer.drive.models import DriveFile, MoveOperation
from drive_organizer.config import settings

logger = logging.getLogger(__name__)

_FIELDS = (
    "nextPageToken, files("
    "id,name,mimeType,size,modifiedTime,createdTime,parents,"
    "fileExtension,trashed,ownedByMe,"
    "capabilities/canMoveItemWithinDrive,"
    "driveId,shortcutDetails,md5Checksum"
    ")"
)

_FOLDER_FIELDS = "nextPageToken, files(id,name,mimeType,parents)"

_CHANGE_FILE_FIELDS = (
    "id,name,mimeType,size,modifiedTime,createdTime,parents,"
    "fileExtension,trashed,ownedByMe,"
    "capabilities/canMoveItemWithinDrive,"
    "driveId,shortcutDetails,md5Checksum"
)

_STATE_VERSION = 1

# Characters forbidden in Windows sync paths (Drive for Desktop compatibility)
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _sanitize_folder_name(name: str) -> str:
    """Strip chars that break Windows Drive sync and trailing dots/spaces."""
    sanitized = _UNSAFE_CHARS.sub("_", name).rstrip(". ")
    return sanitized or "Senza_nome"


def _escape_drive_query(value: str) -> str:
    """Escape backslashes and single quotes for Drive API query strings."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _is_rate_limited(e: HttpError) -> bool:
    """Return True for HTTP 429 or 403 rateLimitExceeded/userRateLimitExceeded."""
    if e.resp.status == 429:
        return True
    if e.resp.status == 403:
        try:
            content = json.loads(e.content.decode())
            reason = content.get("error", {}).get("errors", [{}])[0].get("reason", "")
            return reason in ("rateLimitExceeded", "userRateLimitExceeded")
        except Exception:
            pass
    return False


def _drive_call(fn: Callable, *, max_attempts: int = 4, base_delay: float = 1.0):
    """Execute a Drive API call with exponential backoff on rate-limit errors."""
    delay = base_delay
    for attempt in range(max_attempts):
        try:
            return fn()
        except HttpError as e:
            if _is_rate_limited(e) and attempt < max_attempts - 1:
                logger.warning(
                    "Rate limit (HTTP %d), retry in %.1fs (%d/%d)",
                    e.resp.status, delay, attempt + 1, max_attempts,
                )
                time.sleep(delay)
                delay *= 2
            else:
                raise


class DriveClient:
    def __init__(self, service):
        self._svc = service
        self._folder_cache: dict[str, str] = {}

    def scan_all_files(
        self,
        progress: Progress | None = None,
        task_id=None,
    ) -> tuple[list[DriveFile], dict[str, str]]:
        """Returns (files, folder_id_to_name). Never downloads content.

        Runs two concurrent queries — folders (minimal fields) and files (full
        fields) — to halve wall-clock time on large Drives.  Both threads share
        `self._svc`; googleapiclient creates independent HttpRequest objects per
        call so concurrent reads are safe.
        """
        logger.info("Full scan started (parallel queries)")

        def _fetch_pages(q_filter: str, fields: str) -> list[dict]:
            items: list[dict] = []
            page_token: str | None = None
            while True:
                kwargs: dict = dict(
                    pageSize=1000,
                    fields=fields,
                    q=f"trashed=false and {q_filter}",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                if page_token:
                    kwargs["pageToken"] = page_token
                resp = _drive_call(lambda kw=kwargs: self._svc.files().list(**kw).execute())
                items.extend(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    return items

        _FOLDER_Q = "mimeType='application/vnd.google-apps.folder'"
        _FILE_Q = "mimeType!='application/vnd.google-apps.folder'"

        with ThreadPoolExecutor(max_workers=2) as pool:
            folder_future = pool.submit(_fetch_pages, _FOLDER_Q, _FOLDER_FIELDS)
            file_future = pool.submit(_fetch_pages, _FILE_Q, _FIELDS)
            folder_items = folder_future.result()
            file_items = file_future.result()

        folder_map: dict[str, str] = {item["id"]: item["name"] for item in folder_items}
        files: list[DriveFile] = [self._parse_file_item(item) for item in file_items]

        if progress and task_id is not None:
            progress.advance(task_id, len(files) + len(folder_map))

        logger.info("Full scan complete: %d files, %d folders", len(files), len(folder_map))
        return files, folder_map

    def scan_incremental(
        self,
        state_path: Path,
        progress: Progress | None = None,
        task_id=None,
    ) -> tuple[list[DriveFile], dict[str, str]]:
        """Incremental scan using Drive changes API. Falls back to full scan if state absent or stale."""
        if state_path.exists():
            try:
                return self._scan_with_state(state_path, progress, task_id)
            except Exception as exc:
                logger.warning("Incremental scan failed (%s), falling back to full scan", exc)

        files, folder_map = self.scan_all_files(progress, task_id)
        self._save_scan_state(state_path, files, folder_map)
        return files, folder_map

    def _scan_with_state(
        self,
        state_path: Path,
        progress: Progress | None,
        task_id,
    ) -> tuple[list[DriveFile], dict[str, str]]:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        if raw.get("version") != _STATE_VERSION:
            raise ValueError(f"unsupported state version {raw.get('version')}")

        saved_token: str = raw["page_token"]
        files_by_id: dict[str, DriveFile] = {
            item["id"]: DriveFile.model_validate(item) for item in raw["files"]
        }
        folder_map: dict[str, str] = raw["folder_map"]

        new_token, changes = self._fetch_all_changes(saved_token)

        if not changes:
            logger.info("No Drive changes — using cached scan (%d files)", len(files_by_id))
            if progress and task_id is not None:
                progress.advance(task_id, len(files_by_id))
            return list(files_by_id.values()), folder_map

        logger.info("Applying %d Drive changes to cached scan", len(changes))
        for change in changes:
            if change.get("type") != "file":
                continue
            fid = change["fileId"]
            if change.get("removed"):
                files_by_id.pop(fid, None)
                folder_map.pop(fid, None)
                continue
            item = change.get("file")
            if not item or item.get("trashed"):
                files_by_id.pop(fid, None)
                folder_map.pop(fid, None)
                continue
            f = self._parse_file_item(item)
            if f.is_folder:
                folder_map[fid] = f.name
                files_by_id.pop(fid, None)
            else:
                files_by_id[fid] = f
                folder_map.pop(fid, None)

        files = list(files_by_id.values())
        self._save_scan_state(state_path, files, folder_map, page_token=new_token)

        if progress and task_id is not None:
            progress.advance(task_id, len(files))

        return files, folder_map

    def _fetch_all_changes(self, saved_token: str) -> tuple[str, list[dict]]:
        """Paginate through changes since saved_token. Returns (new_page_token, changes)."""
        changes: list[dict] = []
        page_token = saved_token

        while True:
            resp = _drive_call(
                lambda pt=page_token: self._svc.changes().list(
                    pageToken=pt,
                    fields=(
                        "nextPageToken,newStartPageToken,"
                        f"changes(type,removed,fileId,file({_CHANGE_FILE_FIELDS}))"
                    ),
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    includeRemoved=True,
                ).execute()
            )
            changes.extend(resp.get("changes", []))
            if "nextPageToken" not in resp:
                return resp["newStartPageToken"], changes
            page_token = resp["nextPageToken"]

    def _get_start_page_token(self) -> str:
        resp = _drive_call(
            lambda: self._svc.changes().getStartPageToken(supportsAllDrives=True).execute()
        )
        return resp["startPageToken"]

    def _save_scan_state(
        self,
        path: Path,
        files: list[DriveFile],
        folder_map: dict[str, str],
        *,
        page_token: str | None = None,
    ) -> None:
        if page_token is None:
            try:
                page_token = self._get_start_page_token()
            except Exception as exc:
                logger.warning("Cannot get startPageToken (%s); incremental scan unavailable", exc)
                return

        state = {
            "version": _STATE_VERSION,
            "page_token": page_token,
            "saved_at": datetime.utcnow().isoformat(),
            "files": [f.model_dump(mode="json") for f in files],
            "folder_map": folder_map,
        }
        path.parent.mkdir(exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        logger.info("Scan state saved: %s (%d files)", path.name, len(files))

    @staticmethod
    def _parse_file_item(item: dict) -> DriveFile:
        caps = item.get("capabilities", {})
        shortcut = item.get("shortcutDetails")
        return DriveFile(
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

    def create_folder(self, name: str, parent_id: str) -> str:
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        result = _drive_call(
            lambda: self._svc.files().create(body=body, fields="id", supportsAllDrives=True).execute()
        )
        return result["id"]

    def _find_folder(self, name: str, parent_id: str) -> str | None:
        q = (
            f"name='{_escape_drive_query(name)}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents and trashed=false"
        )
        resp = _drive_call(
            lambda: self._svc.files().list(
                q=q, fields="files(id)", pageSize=1,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
        )
        items = resp.get("files", [])
        return items[0]["id"] if items else None

    def get_or_create_folder_path(self, path: str, root_id: str = "root") -> str:
        """Walk/create folder hierarchy, returns leaf folder ID. Idempotent."""
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        current_id = root_id

        for part in parts:
            part = _sanitize_folder_name(part)
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
        _drive_call(
            lambda: self._svc.files().update(
                fileId=file_id,
                body={"name": new_name},
                fields="id,name",
                supportsAllDrives=True,
            ).execute()
        )

    def move_file(self, file_id: str, new_parent_id: str, old_parent_id: str) -> None:
        _drive_call(
            lambda: self._svc.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=old_parent_id,
                fields="id,parents",
                supportsAllDrives=True,
            ).execute()
        )

    def _move_with_retry(self, op: MoveOperation, *, max_attempts: int = 3) -> bool:
        """Move a file with exponential backoff on 429. Returns True on success."""
        old_parent = op.source_parents[0] if op.source_parents else "root"
        delay = 5.0
        for attempt in range(max_attempts):
            try:
                self.move_file(op.file_id, op.target_parent_id, old_parent)
                return True
            except HttpError as e:
                if _is_rate_limited(e) and attempt < max_attempts - 1:
                    logger.warning(
                        "Rate limit on move '%s' (%s), retry in %.1fs",
                        op.file_name, op.file_id, delay,
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(
                        "Move failed for '%s' (%s): HTTP %d",
                        op.file_name, op.file_id, e.resp.status,
                    )
                    return False
            except Exception as exc:
                logger.error("Move failed for '%s' (%s): %s", op.file_name, op.file_id, exc)
                return False
        return False

    def batch_move(
        self,
        operations: list[MoveOperation],
        progress: Progress | None = None,
        task_id=None,
        on_success: Callable[[MoveOperation], None] | None = None,
    ) -> list[str]:
        """Execute moves with exponential-backoff retry. Returns list of failed file_ids."""
        failed: list[str] = []
        for op in operations:
            if op.skipped or not op.target_parent_id:
                continue
            old_parent = op.source_parents[0] if op.source_parents else "root"
            if old_parent == op.target_parent_id:
                if progress and task_id is not None:
                    progress.advance(task_id)
                continue
            if self._move_with_retry(op):
                if on_success:
                    on_success(op)
            else:
                failed.append(op.file_id)
            if progress and task_id is not None:
                progress.advance(task_id)
        if failed:
            logger.warning("batch_move: %d/%d files failed", len(failed), len(operations))
        return failed

    def get_about(self) -> dict:
        return _drive_call(lambda: self._svc.about().get(fields="user,storageQuota").execute())
