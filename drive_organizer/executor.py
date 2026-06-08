from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

from drive_organizer.config import settings
from drive_organizer.drive.client import DriveClient
from drive_organizer.drive.models import MoveOperation, OrganizationPlan, RollbackEntry, RollbackManifest
from drive_organizer.ui.console import shared as _console

logger = logging.getLogger(__name__)


class PlanExecutor:
    def __init__(self, drive_client: DriveClient, user_email: str = ""):
        self._client = drive_client
        self._email = user_email
        self._rollback_dir = Path(settings.rollback_dir)
        self._rollback_dir.mkdir(exist_ok=True)
        self._lock_path = self._rollback_dir / ".lock"

    def _acquire_lock(self) -> None:
        if self._lock_path.exists():
            raise RuntimeError(
                f"Another run is active (lock: {self._lock_path}). "
                "If this is stale, delete it manually."
            )
        self._lock_path.write_text(str(os.getpid()), encoding="utf-8")

    def _release_lock(self) -> None:
        self._lock_path.unlink(missing_ok=True)

    def execute(
        self,
        plan: OrganizationPlan,
        root_id: str = "root",
    ) -> RollbackManifest:
        self._acquire_lock()
        run_id = str(uuid.uuid4())
        manifest = RollbackManifest(
            run_id=run_id,
            strategy=plan.strategy_name,
            started_at=datetime.now(timezone.utc),
            drive_user_email=self._email,
        )
        manifest_path = self._rollback_dir / f"rollback_{run_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        active_count = sum(1 for op in plan.moves if not op.skipped)
        logger.info("Execute run_id=%s strategy=%s files=%d", run_id[:8], plan.strategy_name, active_count)

        try:
            active_moves = [op for op in plan.moves if not op.skipped]

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=_console,
            ) as progress:
                folder_task = progress.add_task("Creazione cartelle…", total=len(plan.folders_to_create))
                move_task = progress.add_task("Spostamento file…", total=len(active_moves))

                path_to_id: dict[str, str] = {}
                for folder_path in sorted(plan.folders_to_create, key=lambda p: p.count("/")):
                    fid = self._client.get_or_create_folder_path(folder_path, root_id)
                    path_to_id[folder_path] = fid
                    manifest.folders_created.append(fid)
                    progress.advance(folder_task)

                for op in active_moves:
                    op.target_parent_id = path_to_id.get(op.target_path)

                failed: list[str] = []

                def on_success(op: MoveOperation) -> None:
                    entry = RollbackEntry(
                        file_id=op.file_id,
                        file_name=op.file_name,
                        moved_from_parents=list(op.source_parents),
                        moved_to_parent_id=op.target_parent_id or "",
                        timestamp=datetime.now(timezone.utc),
                    )
                    manifest.entries.append(entry)
                    self._save_manifest_atomic(manifest, manifest_path)
                    progress.advance(move_task)

                failed = self._client.batch_move(active_moves, on_success=on_success)

            manifest.completed_at = datetime.now(timezone.utc)
            self._save_manifest_atomic(manifest, manifest_path)

            if failed:
                _console.print(f"[yellow]Avviso: {len(failed)} file non spostati. IDs: {failed[:5]}{'…' if len(failed) > 5 else ''}")
                logger.warning("run_id=%s: %d files failed to move", run_id[:8], len(failed))

            logger.info("run_id=%s complete: %d moved, %d failed", run_id[:8], len(manifest.entries), len(failed))
            return manifest

        finally:
            self._release_lock()

    def _save_manifest_atomic(self, manifest: RollbackManifest, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, path)
