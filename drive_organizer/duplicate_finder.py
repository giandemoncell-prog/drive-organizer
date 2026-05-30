"""
Trova file duplicati nel Drive:
- Duplicati esatti: stesso md5 (file binari identici)
- Duplicati per nome: stesso nome normalizzato (versioni, copie)

I duplicati vengono spostati in 99_Archivio/Duplicati — mai eliminati.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from drive_organizer.drive.models import DriveFile


_COPY_PATTERNS = [
    re.compile(r"\s*\(\d+\)\s*$"),           # "file (1)", "file (2)"
    re.compile(r"\s*-\s*copia\s*$", re.I),   # "file - Copia"
    re.compile(r"\s*copy\s*$", re.I),         # "file copy"
    re.compile(r"\s*-\s*copy\s*$", re.I),    # "file - Copy"
    re.compile(r"\s*copia\s+di\s+", re.I),   # "Copia di file"
    re.compile(r"^copia\s+di\s+", re.I),     # "Copia di file"
]


def _normalize_name(name: str) -> str:
    """Rimuove suffissi tipo (1), - Copia, ecc. per confronto."""
    # Rimuovi estensione
    if "." in name:
        base, _ = name.rsplit(".", 1)
    else:
        base = name
    base = base.strip()
    for pattern in _COPY_PATTERNS:
        base = pattern.sub("", base)
    return base.strip().lower()


def _score_file(f: DriveFile) -> int:
    """Punteggio per scegliere quale file tenere. Più alto = preferito."""
    score = 0
    # Nomi più lunghi e descrittivi sono preferiti
    score += min(len(f.name), 60)
    # File più vecchi sono probabilmente gli originali
    if f.created_time:
        score -= int(f.created_time.timestamp() / 86400)  # giorni dall'epoch (meno = prima)
    # File in cartelle specifiche (non root) sono già organizzati
    if len(f.parents) > 0:
        score += 10
    # Penalizza nomi generici
    lower = f.name.lower()
    for keyword in ["untitled", "senza titolo", "copia", "copy", "(1)", "(2)", "(3)"]:
        if keyword in lower:
            score -= 20
    return score


@dataclass
class DuplicateGroup:
    group_id: int
    reason: str                  # "md5" o "nome"
    files: list[DriveFile]
    keep: DriveFile | None = None  # file da tenere (migliore)
    to_archive: list[DriveFile] = field(default_factory=list)
    excepted: bool = False       # True = utente ha scelto di tenere tutti

    def __post_init__(self):
        if not self.keep and self.files:
            scored = sorted(self.files, key=_score_file, reverse=True)
            self.keep = scored[0]
            self.to_archive = scored[1:]


@dataclass
class DuplicatePlan:
    groups: list[DuplicateGroup]
    total_files_analyzed: int = 0

    @property
    def total_groups(self) -> int:
        return len(self.groups)

    @property
    def active_groups(self) -> list[DuplicateGroup]:
        return [g for g in self.groups if not g.excepted]

    @property
    def files_to_archive(self) -> list[DriveFile]:
        result = []
        for g in self.active_groups:
            result.extend(g.to_archive)
        return result

    @property
    def excepted_count(self) -> int:
        return sum(1 for g in self.groups if g.excepted)


def find_duplicates(files: list[DriveFile]) -> DuplicatePlan:
    """
    Trova duplicati esatti (md5) e per nome normalizzato.
    Restituisce un piano con i gruppi trovati.
    """
    groups: list[DuplicateGroup] = []
    group_id = 0

    # ── Duplicati esatti: stesso md5 ──────────────────────────────────────
    md5_map: dict[str, list[DriveFile]] = defaultdict(list)
    no_md5: list[DriveFile] = []

    for f in files:
        if f.is_folder or f.is_shortcut:
            continue
        if f.md5:
            md5_map[f.md5].append(f)
        else:
            no_md5.append(f)

    for md5, file_list in md5_map.items():
        if len(file_list) > 1:
            group_id += 1
            groups.append(DuplicateGroup(
                group_id=group_id,
                reason="md5",
                files=file_list,
            ))

    # ── Duplicati per nome: file senza md5 (Google Docs, ecc.) ───────────
    name_map: dict[str, list[DriveFile]] = defaultdict(list)
    for f in no_md5:
        normalized = _normalize_name(f.name)
        if normalized:
            name_map[normalized].append(f)

    for norm_name, file_list in name_map.items():
        if len(file_list) > 1:
            # Verifica che siano davvero candidati: almeno uno deve sembrare una copia
            has_copy = any(
                any(p.search(f.name) for p in _COPY_PATTERNS)
                for f in file_list
            )
            if has_copy:
                group_id += 1
                groups.append(DuplicateGroup(
                    group_id=group_id,
                    reason="nome",
                    files=file_list,
                ))

    return DuplicatePlan(groups=groups, total_files_analyzed=len(files))
