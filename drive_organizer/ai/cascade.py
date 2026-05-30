from __future__ import annotations

from typing import TYPE_CHECKING

from rich.progress import Progress

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.ai.cache import SignatureCache
from drive_organizer.ai.privacy import build_request
from drive_organizer.config import settings
from drive_organizer.drive.models import DriveFile
from drive_organizer.strategies.base import OrganizationStrategy

if TYPE_CHECKING:
    from drive_organizer.ai.haiku_provider import HaikuProvider
    from drive_organizer.ai.ollama_provider import OllamaProvider
    from drive_organizer.ai.opus_provider import OpusProvider

_BATCH_SIZE = 20


class AICascade:
    def __init__(
        self,
        ollama: "OllamaProvider",
        haiku: "HaikuProvider",
        opus: "OpusProvider",
    ):
        self._ollama = ollama
        self._haiku = haiku
        self._opus = opus
        self._cache = SignatureCache()
        self._cloud_escalations = 0

    def classify_files(
        self,
        files: list[DriveFile],
        strategy: OrganizationStrategy,
        progress: Progress | None = None,
        task_id=None,
    ) -> list[ClassificationResult]:
        hint = strategy.build_prompt_hint()
        allowed = strategy.allowed_folders() or None

        results: dict[str, ClassificationResult] = {}

        # Step 1: deterministic (no AI)
        needs_ai: list[DriveFile] = []
        for f in files:
            cached = self._cache.get(f)
            if cached:
                results[f.id] = ClassificationResult(
                    file_id=f.id,
                    target_path=cached.target_path,
                    confidence=cached.confidence,
                    reasoning=cached.reasoning,
                    provider=cached.provider,
                )
                continue
            det = strategy.classify_without_ai(f)
            if det is not None:
                results[f.id] = det
                self._cache.set(f, det)
            else:
                needs_ai.append(f)

        if not needs_ai:
            return [results.get(f.id, _fallback(f)) for f in files]

        # Step 2: Ollama (skip entirely if not reachable to avoid per-file timeouts)
        ollama_low: list[DriveFile] = []
        if self._ollama.health_check():
            for batch in _batches(needs_ai, _BATCH_SIZE):
                reqs = [build_request(f) for f in batch]
                batch_results = self._ollama.classify_batch(reqs, hint, allowed)
                for f, res in zip(batch, batch_results):
                    if res.confidence >= settings.ollama_confidence_threshold:
                        results[f.id] = res
                        self._cache.set(f, res)
                    else:
                        ollama_low.append(f)
                        results[f.id] = res  # provisional
                if progress and task_id is not None:
                    progress.advance(task_id, len(batch))
        else:
            ollama_low = needs_ai
            if progress and task_id is not None:
                progress.advance(task_id, len(needs_ai))

        if not ollama_low:
            return [results.get(f.id, _fallback(f)) for f in files]

        # Step 3: Haiku (metadata only, no content)
        haiku_low: list[DriveFile] = []
        _haiku_failed = False
        for batch in _batches(ollama_low, _BATCH_SIZE):
            if self._cloud_escalations >= settings.max_cloud_escalations or _haiku_failed:
                break
            reqs = [build_request(f) for f in batch]
            try:
                batch_results = self._haiku.classify_batch(reqs, hint, allowed)
            except Exception:
                _haiku_failed = True
                break
            self._cloud_escalations += len(batch)
            for f, hres in zip(batch, batch_results):
                ollama_res = results.get(f.id)
                # Agreement bonus
                if ollama_res and hres.target_path == ollama_res.target_path:
                    hres = ClassificationResult(
                        file_id=hres.file_id,
                        target_path=hres.target_path,
                        confidence=min(1.0, hres.confidence + 0.10),
                        reasoning=hres.reasoning + " [agreement bonus]",
                        provider=hres.provider,
                    )
                if hres.confidence >= settings.haiku_confidence_threshold:
                    results[f.id] = hres
                    self._cache.set(f, hres)
                else:
                    haiku_low.append(f)
                    results[f.id] = hres

        if not haiku_low:
            return [results.get(f.id, _fallback(f)) for f in files]

        # Step 4: Opus (metadata only, final)
        for batch in _batches(haiku_low, _BATCH_SIZE):
            if self._cloud_escalations >= settings.max_cloud_escalations:
                break
            reqs = [build_request(f) for f in batch]
            try:
                batch_results = self._opus.classify_batch(reqs, hint, allowed)
            except Exception:
                break
            self._cloud_escalations += len(batch)
            for f, ores in zip(batch, batch_results):
                results[f.id] = ores
                self._cache.set(f, ores)

        return [results.get(f.id, _fallback(f)) for f in files]

    def interpret_custom_strategy(self, description: str) -> dict:
        return self._opus.parse_custom_taxonomy(description)

    @property
    def cloud_escalations(self) -> int:
        return self._cloud_escalations


def _batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i: i + size]


def _fallback(f: DriveFile) -> ClassificationResult:
    return ClassificationResult(
        file_id=f.id,
        target_path="Altro",
        confidence=0.0,
        reasoning="Budget cap reached — fallback to Altro",
        provider="deterministic",
    )
