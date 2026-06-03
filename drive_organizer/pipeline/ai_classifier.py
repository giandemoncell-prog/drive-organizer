"""
AIClassifier — cascade AI robusto per la pipeline di organizzazione.

Differenze rispetto a `drive_organizer.ai.cascade.AICascade`:
  - pensato per la classificazione di **sottocartelle** (livello 2), dove le
    cartelle ammesse sono note e ristrette;
  - cascade configurabile **Ollama → DeepSeek → Gemini** (l'ordine può cambiare a
    seconda di quali provider sono raggiungibili / hanno quota);
  - **content reading** opt-in per file con nomi ambigui (legge i primi N char,
    solo via Ollama locale — il contenuto non lascia mai la macchina);
  - **confidence scoring** con bonus di accordo tra provider e penalità per nomi
    ambigui;
  - **batch processing** ottimizzato: un solo prompt per batch sui provider cloud
    (DeepSeek/Gemini), parallelismo limitato su Ollama.

La classe è importabile e testabile in isolamento: i provider sono iniettati
(duck-typing sul metodo `classify_batch(requests, hint, allowed_folders)`), quindi
nei test si possono passare dei fake.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.config import settings
from drive_organizer.drive.models import DriveFile

# Estensioni/pattern che rendono un nome "ambiguo" → conviene leggere il contenuto.
_AMBIGUOUS_PATTERNS = [
    re.compile(r"^(tr|tav|doc|img|scan|foto|file|nuovo|copia|untitled|senza titolo)", re.I),
    re.compile(r"^[a-z]{1,4}[\W_]*\d*\.[a-z0-9]+$", re.I),  # es. "tr.pdf", "s.u.pdf"
    re.compile(r"^[\d\W_]+\.[a-z0-9]+$"),                    # nomi solo numerici
    re.compile(r"^.{0,4}\.[a-z0-9]+$", re.I),                # base nome <= 4 char
]

# MIME types da cui ha senso estrarre testo.
_TEXT_LIKE_MIMES = (
    "application/pdf",
    "text/",
    "application/vnd.google-apps.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml",
    "application/msword",
)

_DEFAULT_CONFIDENCE_THRESHOLD = 0.6
_OLLAMA_BATCH = 12
_CLOUD_BATCH = 30


@runtime_checkable
class _BatchProvider(Protocol):
    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]: ...

    def health_check(self) -> bool: ...


@dataclass
class ClassifierConfig:
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD
    ollama_min_confidence: float = 0.75
    read_content_for_ambiguous: bool = True
    content_chars: int = 500
    max_cloud_calls: int = 200
    agreement_bonus: float = 0.10
    ambiguous_penalty: float = 0.15


@dataclass
class ClassifierStats:
    total: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)
    content_reads: int = 0
    cloud_calls: int = 0
    review_queue: int = 0

    def bump(self, provider: str) -> None:
        self.by_provider[provider] = self.by_provider.get(provider, 0) + 1


def is_ambiguous_name(name: str) -> bool:
    """True se il nome è troppo generico per classificare in modo affidabile."""
    base = name.strip()
    if len(base) <= 4:
        return True
    return any(p.search(base) for p in _AMBIGUOUS_PATTERNS)


def request_from_file(f: DriveFile) -> ClassificationRequest:
    """Costruisce una ClassificationRequest (solo metadati) da un DriveFile."""
    return ClassificationRequest(
        file_id=f.id,
        name=f.name,
        mime_type=f.mime_type,
        size=f.size,
        modified_time=f.modified_time if isinstance(f.modified_time, datetime) else datetime.utcnow(),
        extension=f.file_extension,
    )


class AIClassifier:
    """Cascade Ollama → DeepSeek → Gemini con content reading e confidence scoring.

    Parametri:
        ollama:   provider locale veloce (può essere None → cascade salta il livello).
        deepseek: provider cloud fallback (può essere None).
        gemini:   provider cloud finale (può essere None).
        drive_service: googleapiclient service, necessario SOLO per content reading.
        config:   ClassifierConfig.
    """

    def __init__(
        self,
        ollama: _BatchProvider | None = None,
        deepseek: _BatchProvider | None = None,
        gemini: _BatchProvider | None = None,
        drive_service=None,
        config: ClassifierConfig | None = None,
    ) -> None:
        self._ollama = ollama
        self._deepseek = deepseek
        self._gemini = gemini
        self._svc = drive_service
        self.config = config or ClassifierConfig()
        self.stats = ClassifierStats()
        self._cloud_calls = 0

    # ── API principale ────────────────────────────────────────────────────
    def classify(
        self,
        files: list[DriveFile],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        """Classifica una lista di file restituendo un risultato per ciascuno,
        nello stesso ordine di input. I file con confidence finale sotto soglia
        vanno trattati dal chiamante come review-queue (vedi `split_by_confidence`)."""
        if not files:
            return []

        self.stats.total += len(files)
        results: dict[str, ClassificationResult] = {}

        # ── Livello 1: Ollama (metadati, batch parallelo) ─────────────────
        pending = files
        if self._ollama is not None and _safe_health(self._ollama):
            low: list[DriveFile] = []
            for batch in _chunks(pending, _OLLAMA_BATCH):
                reqs = [request_from_file(f) for f in batch]
                batch_res = _safe_batch(self._ollama, reqs, strategy_hint, allowed_folders, "ollama")
                by_id = {r.file_id: r for r in batch_res}
                for f in batch:
                    res = by_id.get(f.id)
                    if res and res.confidence >= self.config.ollama_min_confidence:
                        results[f.id] = res
                    else:
                        if res:
                            results[f.id] = res  # provvisorio
                        low.append(f)
            pending = low

        # ── Content reading per nomi ambigui (solo Ollama, privacy) ───────
        if (
            self.config.read_content_for_ambiguous
            and self._ollama is not None
            and self._svc is not None
            and pending
        ):
            still_low: list[DriveFile] = []
            for f in pending:
                if is_ambiguous_name(f.name) and self._is_text_like(f):
                    res = self._classify_with_content(f, strategy_hint, allowed_folders)
                    if res and res.confidence >= self.config.confidence_threshold:
                        results[f.id] = res
                        continue
                    if res:
                        results[f.id] = res
                still_low.append(f)
            pending = still_low

        # ── Livello 2: DeepSeek (cloud, batch unico) ──────────────────────
        if self._deepseek is not None and pending and _safe_health(self._deepseek):
            pending = self._cloud_pass(
                self._deepseek, pending, strategy_hint, allowed_folders, results
            )

        # ── Livello 3: Gemini (cloud finale) ──────────────────────────────
        if self._gemini is not None and pending and _safe_health(self._gemini):
            pending = self._cloud_pass(
                self._gemini, pending, strategy_hint, allowed_folders, results
            )

        # ── Finalizzazione: scoring + fallback ────────────────────────────
        out: list[ClassificationResult] = []
        for f in files:
            res = results.get(f.id)
            if res is None:
                res = ClassificationResult(
                    file_id=f.id,
                    target_path="Altro",
                    confidence=0.0,
                    reasoning="Nessun provider disponibile / budget esaurito",
                    provider="deterministic",
                )
            res = self._apply_scoring(f, res)
            self.stats.bump(res.provider)
            if res.confidence < self.config.confidence_threshold:
                self.stats.review_queue += 1
            out.append(res)
        return out

    # ── helpers cascade ───────────────────────────────────────────────────
    def _cloud_pass(
        self,
        provider: _BatchProvider,
        files: list[DriveFile],
        strategy_hint: str,
        allowed_folders: list[str] | None,
        results: dict[str, ClassificationResult],
    ) -> list[DriveFile]:
        """Esegue un passaggio cloud su `files`, aggiorna `results`, ritorna i file
        ancora sotto soglia (da passare al provider successivo)."""
        low: list[DriveFile] = []
        for batch in _chunks(files, _CLOUD_BATCH):
            if self._cloud_calls >= self.config.max_cloud_calls:
                low.extend(batch)
                continue
            reqs = [request_from_file(f) for f in batch]
            label = _provider_label(provider)
            batch_res = _safe_batch(provider, reqs, strategy_hint, allowed_folders, label)
            self._cloud_calls += len(batch)
            self.stats.cloud_calls += len(batch)
            by_id = {r.file_id: r for r in batch_res}
            for f in batch:
                new = by_id.get(f.id)
                if new is None:
                    low.append(f)
                    continue
                prev = results.get(f.id)
                # Bonus accordo: se il provider locale aveva lo stesso target.
                if prev and prev.target_path == new.target_path:
                    new = _with_confidence(
                        new, min(1.0, new.confidence + self.config.agreement_bonus),
                        new.reasoning + " [accordo provider]",
                    )
                results[f.id] = new
                if new.confidence < self.config.confidence_threshold:
                    low.append(f)
        return low

    def _classify_with_content(
        self,
        f: DriveFile,
        strategy_hint: str,
        allowed_folders: list[str] | None,
    ) -> ClassificationResult | None:
        """Legge i primi N char del file e chiede a Ollama (path content-aware)."""
        try:
            from drive_organizer.content_extractor import extract_text_preview

            preview = extract_text_preview(
                self._svc, f.id, f.mime_type, max_chars=self.config.content_chars
            )
        except Exception:
            return None
        if not preview.strip():
            return None
        self.stats.content_reads += 1
        req = request_from_file(f)
        try:
            res = self._ollama.classify_with_content(  # type: ignore[union-attr]
                req, preview, strategy_hint, allowed_folders
            )
            return res
        except Exception:
            return None

    def _apply_scoring(self, f: DriveFile, res: ClassificationResult) -> ClassificationResult:
        """Aggiusta la confidence: penalità per nomi ambigui non risolti via contenuto."""
        conf = res.confidence
        if is_ambiguous_name(f.name) and not res.used_content:
            conf = max(0.0, conf - self.config.ambiguous_penalty)
        if conf == res.confidence:
            return res
        return _with_confidence(res, conf, res.reasoning + " [penalità ambiguità]")

    def _is_text_like(self, f: DriveFile) -> bool:
        return any(f.mime_type.startswith(m) for m in _TEXT_LIKE_MIMES)

    # ── utility statiche ──────────────────────────────────────────────────
    @staticmethod
    def split_by_confidence(
        files: list[DriveFile],
        results: list[ClassificationResult],
        threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> tuple[
        list[tuple[DriveFile, ClassificationResult]],
        list[tuple[DriveFile, ClassificationResult]],
    ]:
        """Divide in (confident, review_queue) in base alla soglia di confidence."""
        confident: list[tuple[DriveFile, ClassificationResult]] = []
        review: list[tuple[DriveFile, ClassificationResult]] = []
        by_id = {r.file_id: r for r in results}
        for f in files:
            r = by_id.get(f.id)
            if r is None:
                continue
            (confident if r.confidence >= threshold else review).append((f, r))
        return confident, review


# ── funzioni libere ───────────────────────────────────────────────────────
def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _safe_health(provider: _BatchProvider) -> bool:
    try:
        return bool(provider.health_check())
    except Exception:
        return False


def _safe_batch(
    provider: _BatchProvider,
    reqs: list[ClassificationRequest],
    hint: str,
    allowed: list[str] | None,
    label: str,
) -> list[ClassificationResult]:
    try:
        return provider.classify_batch(reqs, hint, allowed)
    except Exception as e:
        return [
            ClassificationResult(
                file_id=r.file_id,
                target_path="Altro",
                confidence=0.0,
                reasoning=f"{label} error: {e}",
                provider=label if label in ("ollama", "haiku", "opus", "deterministic") else "deterministic",
            )
            for r in reqs
        ]


def _provider_label(provider: _BatchProvider) -> str:
    name = type(provider).__name__.lower()
    if "deepseek" in name:
        return "haiku"  # i provider DeepSeek emettono già label 'deepseek-*'/'haiku'
    if "gemini" in name:
        return "opus"
    return "deterministic"


def _with_confidence(res: ClassificationResult, conf: float, reasoning: str) -> ClassificationResult:
    return ClassificationResult(
        file_id=res.file_id,
        target_path=res.target_path,
        confidence=max(0.0, min(1.0, conf)),
        reasoning=reasoning,
        provider=res.provider,
        used_content=res.used_content,
    )
