from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from rich.progress import Progress

from drive_organizer.ai.base import ClassificationResult
from drive_organizer.ai.cache import SignatureCache
from drive_organizer.ai.privacy import build_request
from drive_organizer.config import settings
from drive_organizer.drive.models import DriveFile
from drive_organizer.strategies.base import OrganizationStrategy

if TYPE_CHECKING:
    from drive_organizer.ai.haiku_provider import HaikuProvider
    from drive_organizer.ai.ollama_provider import OllamaProvider
    from drive_organizer.ai.opus_provider import OpusProvider

logger = logging.getLogger(__name__)

_BATCH_SIZE = 30
_OLLAMA_PARALLEL = 3           # concurrent batch calls to Ollama
_CLOUD_INTER_BATCH_SLEEP = 0.25  # seconds between cloud batches to avoid rate limits
_CLOUD_RETRY_ATTEMPTS = 2


class AICascade:
    def __init__(
        self,
        ollama: OllamaProvider,
        haiku: HaikuProvider,
        opus: OpusProvider,
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
        # Custom strategy uses keyword matching per file name — caching by (ext, size, mime)
        # would conflate unrelated files and hurt classification quality.
        use_cache = strategy.name != "custom"

        # Adaptive cap: at least max_cloud_escalations, but scales to 20% of file count
        # so large Drives don't hit the ceiling prematurely.
        _effective_cap = max(
            settings.max_cloud_escalations,
            int(len(files) * settings.max_cloud_escalations_pct),
        )

        logger.info(
            "classify_files: %d files, strategy=%s, cloud_cap=%d",
            len(files), strategy.name, _effective_cap,
        )
        results: dict[str, ClassificationResult] = {}

        try:
            # Step 1: deterministic (no AI)
            needs_ai: list[DriveFile] = []
            for f in files:
                if use_cache:
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
                    if use_cache:
                        self._cache.set(f, det)
                else:
                    needs_ai.append(f)

            cache_hits = len(files) - len(needs_ai)
            if cache_hits:
                logger.debug("Cache/deterministic hits: %d/%d", cache_hits, len(files))
            if not needs_ai:
                return [results.get(f.id, _fallback(f)) for f in files]

            # Step 2: Ollama — parallel batches (worker threads call Ollama, main thread
            # updates results/cache so no locking needed on those data structures).
            ollama_low: list[DriveFile] = []
            if self._ollama.health_check():
                all_batches = list(_batches(needs_ai, _BATCH_SIZE))
                # ordered[i] = (batch, results_or_None)
                ordered: list[tuple[list[DriveFile], list | None]] = [([], None)] * len(all_batches)

                def _run_ollama_batch(args: tuple[int, list[DriveFile]]) -> tuple[int, list[DriveFile], list | None]:
                    idx, batch = args
                    reqs = [build_request(f) for f in batch]
                    try:
                        return idx, batch, self._ollama.classify_batch(reqs, hint, allowed)
                    except Exception:
                        return idx, batch, None

                with ThreadPoolExecutor(max_workers=_OLLAMA_PARALLEL) as pool:
                    futures = {pool.submit(_run_ollama_batch, (i, b)): i for i, b in enumerate(all_batches)}
                    for fut in as_completed(futures):
                        idx, batch, batch_results = fut.result()
                        ordered[idx] = (batch, batch_results)
                        if progress and task_id is not None:
                            progress.advance(task_id, len(batch))

                for batch, batch_results in ordered:
                    if batch_results is None:
                        ollama_low.extend(batch)
                        continue
                    for f, res in zip(batch, batch_results):
                        if res.confidence >= settings.ollama_confidence_threshold:
                            results[f.id] = res
                            if use_cache:
                                self._cache.set(f, res)
                        else:
                            ollama_low.append(f)
                            results[f.id] = res  # provisional
            else:
                logger.warning("Ollama unreachable — escalating all %d files to cloud", len(needs_ai))
                ollama_low = needs_ai
                if progress and task_id is not None:
                    progress.advance(task_id, len(needs_ai))

            ollama_resolved = len(needs_ai) - len(ollama_low)
            if ollama_resolved:
                logger.info("Ollama resolved: %d files", ollama_resolved)
            if not ollama_low:
                return [results.get(f.id, _fallback(f)) for f in files]

            # Step 3: Haiku (metadata only, no content)
            haiku_low: list[DriveFile] = []
            for batch in _batches(ollama_low, _BATCH_SIZE):
                if self._cloud_escalations >= _effective_cap:
                    break
                reqs = [build_request(f) for f in batch]
                batch_results = _retry_classify(self._haiku, reqs, hint, allowed)
                if batch_results is None:
                    continue  # skip this batch only, not all remaining
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
                        if use_cache:
                            self._cache.set(f, hres)
                    else:
                        haiku_low.append(f)
                        results[f.id] = hres
                time.sleep(_CLOUD_INTER_BATCH_SLEEP)

            haiku_resolved = len(ollama_low) - len(haiku_low)
            if haiku_resolved:
                logger.info("Haiku resolved: %d files (escalations so far: %d)", haiku_resolved, self._cloud_escalations)
            if not haiku_low:
                return [results.get(f.id, _fallback(f)) for f in files]

            # Step 4: Opus (metadata only, final)
            logger.info("Escalating %d files to Opus", len(haiku_low))
            for batch in _batches(haiku_low, _BATCH_SIZE):
                if self._cloud_escalations >= _effective_cap:
                    break
                reqs = [build_request(f) for f in batch]
                batch_results = _retry_classify(self._opus, reqs, hint, allowed)
                if batch_results is None:
                    continue
                self._cloud_escalations += len(batch)
                for f, ores in zip(batch, batch_results):
                    results[f.id] = ores
                    if use_cache:
                        self._cache.set(f, ores)
                time.sleep(_CLOUD_INTER_BATCH_SLEEP)

            logger.info(
                "classify_files done: total_cloud_escalations=%d (cap=%d)",
                self._cloud_escalations, _effective_cap,
            )
            return [results.get(f.id, _fallback(f)) for f in files]

        finally:
            self._cache.save()

    def interpret_custom_strategy(self, description: str) -> dict:
        return self._opus.parse_custom_taxonomy(description)

    @property
    def cloud_escalations(self) -> int:
        return self._cloud_escalations


def _batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i: i + size]


def _retry_classify(provider, reqs, hint, allowed, *, attempts=_CLOUD_RETRY_ATTEMPTS):
    """Call provider.classify_batch with exponential-backoff retries.

    Returns None if all attempts fail so the caller can skip that batch
    without aborting remaining ones.
    """
    delay = 1.0
    for i in range(attempts + 1):
        try:
            return provider.classify_batch(reqs, hint, allowed)
        except Exception:
            if i == attempts:
                return None
            time.sleep(delay)
            delay *= 2
    return None  # unreachable, satisfies type checker


def _fallback(f: DriveFile) -> ClassificationResult:
    return ClassificationResult(
        file_id=f.id,
        target_path="Altro",
        confidence=0.0,
        reasoning="Budget cap reached — fallback to Altro",
        provider="deterministic",
    )
