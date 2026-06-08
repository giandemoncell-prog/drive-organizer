from __future__ import annotations

import csv
import json
from pathlib import Path

from drive_organizer.drive.models import OrganizationPlan


def export_plan(
    plan: OrganizationPlan,
    path: Path,
    folder_map: dict[str, str] | None = None,
) -> None:
    """Export an OrganizationPlan to CSV or JSON based on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        _export_json(plan, path)
    elif suffix == ".csv":
        _export_csv(plan, path, folder_map or {})
    else:
        raise ValueError(f"Formato non supportato: {suffix!r}. Usa .csv o .json")


def _export_json(plan: OrganizationPlan, path: Path) -> None:
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")


def _export_csv(plan: OrganizationPlan, path: Path, folder_map: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["file_name", "source_folder", "target_path", "confidence", "provider", "skipped", "skip_reason"],
        )
        writer.writeheader()
        for op in plan.moves:
            source_folder = folder_map.get(op.source_parents[0], op.source_parents[0]) if op.source_parents else ""
            writer.writerow({
                "file_name": op.file_name,
                "source_folder": source_folder,
                "target_path": op.target_path,
                "confidence": round(op.confidence, 3),
                "provider": op.provider,
                "skipped": op.skipped,
                "skip_reason": op.skip_reason or "",
            })
