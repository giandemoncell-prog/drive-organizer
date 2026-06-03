"""
PipelineRollback — registrazione manifest e undo universale per la pipeline.

Ogni operazione di spostamento eseguita dalla pipeline (classify/execute, audit,
rescue, nest) viene registrata in un `RollbackManifest` identico a quello prodotto
da `PlanExecutor`. Questo garantisce **compatibilità totale** con il sistema di
rollback esistente (`drive_organizer.rollback.RollbackManager`): i manifest scritti
qui finiscono nella stessa cartella (`settings.rollback_dir`) col prefisso
`rollback_*.json`, quindi compaiono nella stessa lista e sono ripristinabili sia da
questa classe sia dalla UI principale dell'app.

Caratteristiche:
  - manifest persistito in modo **atomico e incrementale** (ogni move è salvato
    subito, così un crash a metà run lascia comunque un manifest valido).
  - undo in ordine inverso (LIFO), tollerante ai file già spostati/eliminati.
  - context-manager: `with PipelineRollback(...) as rb: rb.record_move(...)`.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Iterator

from drive_organizer.config import settings
from drive_organizer.drive.client import DriveClient
from drive_organizer.drive.models import RollbackEntry, RollbackManifest


class PipelineRollback:
    """Registra ogni move della pipeline e permette undo completo.

    Esempio:
        rb = PipelineRollback(client, strategy="pipeline-maintenance",
                              user_email="user@gmail.com")
        with rb:
            client.move_file(fid, new_parent, old_parent)
            rb.record_move(file_id=fid, file_name="x.pdf",
                           from_parents=[old_parent], to_parent=new_parent)
        # ... in seguito, anche in un altro processo:
        PipelineRollback.undo_last(client)
    """

    def __init__(
        self,
        drive_client: DriveClient,
        strategy: str = "pipeline",
        user_email: str = "",
        run_id: str | None = None,
    ) -> None:
        self._client = drive_client
        self._rollback_dir = Path(settings.rollback_dir)
        self._rollback_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = run_id or str(uuid.uuid4())
        self._manifest = RollbackManifest(
            run_id=self.run_id,
            strategy=strategy,
            started_at=datetime.utcnow(),
            drive_user_email=user_email,
        )
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._path = self._rollback_dir / f"rollback_{self.run_id[:8]}_{ts}.json"
        self._closed = False

    # ── context manager ───────────────────────────────────────────────────
    def __enter__(self) -> "PipelineRollback":
        self._flush()  # crea subito un manifest vuoto ma valido su disco
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ── registrazione ─────────────────────────────────────────────────────
    def record_folder_created(self, folder_id: str) -> None:
        """Annota una cartella creata durante la run (per pulizia/audit)."""
        if folder_id and folder_id not in self._manifest.folders_created:
            self._manifest.folders_created.append(folder_id)
            self._flush()

    def record_move(
        self,
        file_id: str,
        file_name: str,
        from_parents: list[str],
        to_parent: str,
    ) -> None:
        """Registra un singolo spostamento già eseguito su Drive.

        Va chiamato DOPO che `move_file` è andato a buon fine, così il manifest
        contiene solo move realmente applicati (undo idempotente)."""
        entry = RollbackEntry(
            file_id=file_id,
            file_name=file_name,
            moved_from_parents=list(from_parents) or ["root"],
            moved_to_parent_id=to_parent,
            timestamp=datetime.utcnow(),
        )
        self._manifest.entries.append(entry)
        self._flush()

    def move_and_record(
        self,
        file_id: str,
        file_name: str,
        from_parent: str,
        to_parent: str,
    ) -> bool:
        """Esegue lo spostamento e lo registra in un colpo solo.

        Ritorna True se il file è stato spostato, False se sorgente==destinazione
        (no-op) o se lo spostamento è fallito."""
        if not to_parent or from_parent == to_parent:
            return False
        try:
            self._client.move_file(file_id, to_parent, from_parent)
        except Exception:
            return False
        self.record_move(file_id, file_name, [from_parent], to_parent)
        return True

    @property
    def entries_count(self) -> int:
        return len(self._manifest.entries)

    @property
    def manifest(self) -> RollbackManifest:
        return self._manifest

    @property
    def manifest_path(self) -> Path:
        return self._path

    def close(self) -> None:
        if self._closed:
            return
        self._manifest.completed_at = datetime.utcnow()
        self._flush()
        self._closed = True

    # ── undo ──────────────────────────────────────────────────────────────
    def undo(self) -> tuple[int, int]:
        """Ripristina tutti i file di QUESTA run nelle posizioni originali.

        Ritorna (ripristinati, falliti)."""
        return _undo_manifest(self._client, self._manifest)

    @classmethod
    def undo_manifest_file(cls, drive_client: DriveClient, path: str | Path) -> tuple[int, int]:
        """Ripristina da un file manifest su disco."""
        manifest = RollbackManifest.model_validate_json(
            Path(path).read_text(encoding="utf-8")
        )
        return _undo_manifest(drive_client, manifest)

    @classmethod
    def list_manifests(cls) -> list[Path]:
        """Tutti i manifest disponibili, più recenti per primi."""
        rollback_dir = Path(settings.rollback_dir)
        if not rollback_dir.exists():
            return []
        return sorted(rollback_dir.glob("rollback_*.json"), reverse=True)

    @classmethod
    def undo_last(cls, drive_client: DriveClient) -> tuple[int, int]:
        """Ripristina l'ultima run registrata (qualunque sia stata: nest/audit/…)."""
        manifests = cls.list_manifests()
        if not manifests:
            return (0, 0)
        return cls.undo_manifest_file(drive_client, manifests[0])

    # ── persistenza ───────────────────────────────────────────────────────
    def _flush(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(self._manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self._path)


def _undo_manifest(client: DriveClient, manifest: RollbackManifest) -> tuple[int, int]:
    entries = manifest.entries
    restored = 0
    failed = 0
    for entry in reversed(entries):  # LIFO: undo in ordine inverso
        target_parent = (
            entry.moved_from_parents[0] if entry.moved_from_parents else "root"
        )
        try:
            client.move_file(
                file_id=entry.file_id,
                new_parent_id=target_parent,
                old_parent_id=entry.moved_to_parent_id,
            )
            restored += 1
        except Exception:
            failed += 1
    return (restored, failed)


def iter_recorded_files(manifest: RollbackManifest) -> Iterator[str]:
    """Helper di test: itera gli ID file registrati in un manifest."""
    for entry in manifest.entries:
        yield entry.file_id
