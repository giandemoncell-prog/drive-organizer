from __future__ import annotations

from pathlib import Path

from googleapiclient.errors import HttpError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from drive_organizer.config import settings
from drive_organizer.drive.client import DriveClient
from drive_organizer.drive.models import RollbackManifest
from drive_organizer.ui.console import shared as _console


class RollbackManager:
    def __init__(self, drive_client: DriveClient):
        self._client = drive_client
        self._rollback_dir = Path(settings.rollback_dir)

    def list_available(self) -> list[RollbackManifest]:
        manifests = []
        for p in sorted(self._rollback_dir.glob("rollback_*.json"), reverse=True):
            try:
                m = RollbackManifest.model_validate_json(p.read_text(encoding="utf-8"))
                manifests.append(m)
            except Exception:
                pass
        return manifests

    def print_table(self, console: Console) -> list[RollbackManifest]:
        manifests = self.list_available()
        if not manifests:
            console.print("[yellow]Nessun rollback disponibile.")
            return []

        table = Table(title="Rollback disponibili", show_lines=True)
        table.add_column("#", style="bold")
        table.add_column("Run ID")
        table.add_column("Strategia")
        table.add_column("Data")
        table.add_column("File mossi")
        table.add_column("Utente")

        for i, m in enumerate(manifests, 1):
            table.add_row(
                str(i),
                m.run_id[:8],
                m.strategy,
                m.started_at.strftime("%Y-%m-%d %H:%M"),
                str(len(m.entries)),
                m.drive_user_email,
            )
        console.print(table)
        return manifests

    def execute_rollback(self, manifest: RollbackManifest) -> None:
        entries = manifest.entries
        if not entries:
            _console.print("[yellow]Nessun file da ripristinare.")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=_console,
        ) as progress:
            task = progress.add_task(f"Ripristino {len(entries)} file…", total=len(entries))
            failed = 0
            deleted = 0
            for entry in reversed(entries):
                try:
                    self._client.move_file(
                        file_id=entry.file_id,
                        new_parent_id=entry.moved_from_parents[0] if entry.moved_from_parents else "root",
                        old_parent_id=entry.moved_to_parent_id,
                    )
                except HttpError as e:
                    if e.resp.status == 404:
                        deleted += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                progress.advance(task)

        restored = len(entries) - failed - deleted
        _console.print(f"[green]Rollback completato: {restored}/{len(entries)} file ripristinati.")
        if deleted:
            _console.print(f"[yellow]{deleted} file eliminati dal Drive dopo l'organizzazione — non ripristinabili.")
        if failed:
            _console.print(f"[red]{failed} file non ripristinati per errori API.")
