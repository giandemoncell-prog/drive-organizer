from __future__ import annotations

from rich.progress import Progress

from drive_organizer.ai.cascade import AICascade
from drive_organizer.drive.models import DriveFile, MoveOperation, OrganizationPlan
from drive_organizer.strategies.base import OrganizationStrategy


class OrganizationPlanner:
    def __init__(self, cascade: AICascade | None = None):
        self._cascade = cascade

    def build_plan(
        self,
        files: list[DriveFile],
        strategy: OrganizationStrategy,
        progress: Progress | None = None,
        task_id=None,
    ) -> OrganizationPlan:
        movable = [f for f in files if not f.is_shortcut and f.owned_by_me and f.can_move]
        skipped_non_movable = len(files) - len(movable)

        if strategy.requires_ai() and self._cascade:
            results = self._cascade.classify_files(movable, strategy, progress, task_id)
        else:
            results = [strategy.classify_without_ai(f) for f in movable]

        moves: list[MoveOperation] = []
        folders_needed: set[str] = set()
        skipped = skipped_non_movable

        for f, res in zip(movable, results):
            if res is None:
                skipped += 1
                continue
            op = MoveOperation(
                file_id=f.id,
                file_name=f.name,
                source_parents=list(f.parents),
                target_path=res.target_path,
                confidence=res.confidence,
                provider=res.provider,
            )
            moves.append(op)
            folders_needed.add(res.target_path)

        for f in files:
            if f.is_shortcut or not f.owned_by_me or not f.can_move:
                reason = (
                    "shortcut" if f.is_shortcut
                    else "not owned" if not f.owned_by_me
                    else "cannot move"
                )
                moves.append(MoveOperation(
                    file_id=f.id,
                    file_name=f.name,
                    source_parents=list(f.parents),
                    target_path="",
                    confidence=0.0,
                    provider="deterministic",
                    skipped=True,
                    skip_reason=reason,
                ))

        return OrganizationPlan(
            strategy_name=strategy.name,
            moves=moves,
            folders_to_create=sorted(folders_needed),
            total_files=len(files),
            skipped_files=skipped,
        )
