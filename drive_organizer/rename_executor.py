from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from drive_organizer.config import settings
from drive_organizer.drive.client import DriveClient
from drive_organizer.drive.models import RenameManifest, RenameManifestEntry, RenamePlan
from drive_organizer.ui.console import shared as _console


class RenameExecutor:
    def __init__(self, drive_client: DriveClient, user_email: str = ""):
        self._client = drive_client
        self._email = user_email
        self._rollback_dir = Path(settings.rollback_dir)
        self._rollback_dir.mkdir(exist_ok=True)

    def execute(self, plan: RenamePlan) -> RenameManifest:
        active = [op for op in plan.operations if not op.skipped]
        run_id = str(uuid.uuid4())
        manifest = RenameManifest(
            run_id=run_id,
            started_at=datetime.utcnow(),
            drive_user_email=self._email,
        )
        manifest_path = (
            self._rollback_dir
            / f"rename_{run_id[:8]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )

        failed = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=_console,
        ) as progress:
            task = progress.add_task("Rinomina file…", total=len(active))
            for op in active:
                try:
                    self._client.rename_file(op.file_id, op.new_name)
                    entry = RenameManifestEntry(
                        file_id=op.file_id,
                        old_name=op.old_name,
                        new_name=op.new_name,
                    )
                    manifest.entries.append(entry)
                    self._save_manifest_atomic(manifest, manifest_path)
                except Exception:
                    failed += 1
                progress.advance(task)

        manifest.completed_at = datetime.utcnow()
        self._save_manifest_atomic(manifest, manifest_path)

        if failed:
            _console.print(f"[yellow]{failed} file non rinominati.[/yellow]")

        return manifest

    def _save_manifest_atomic(self, manifest: RenameManifest, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, path)


class RenameRollbackManager:
    def __init__(self, drive_client: DriveClient):
        self._client = drive_client
        self._rollback_dir = Path(settings.rollback_dir)

    def list_available(self) -> list[RenameManifest]:
        manifests = []
        for p in sorted(self._rollback_dir.glob("rename_*.json"), reverse=True):
            try:
                m = RenameManifest.model_validate_json(p.read_text(encoding="utf-8"))
                manifests.append(m)
            except Exception:
                pass
        return manifests

    def execute_rollback(self, manifest: RenameManifest) -> None:
        entries = manifest.entries
        if not entries:
            _console.print("[yellow]Nessun file da ripristinare.[/yellow]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=_console,
        ) as progress:
            task = progress.add_task("Ripristino nomi…", total=len(entries))
            failed = 0
            for entry in reversed(entries):
                try:
                    self._client.rename_file(entry.file_id, entry.old_name)
                except Exception:
                    failed += 1
                progress.advance(task)

        if failed:
            _console.print(f"[yellow]{failed} nomi non ripristinati.[/yellow]")
        _console.print(
            f"[green]Rollback completato: {len(entries) - failed}/{len(entries)} file ripristinati.[/green]"
        )
