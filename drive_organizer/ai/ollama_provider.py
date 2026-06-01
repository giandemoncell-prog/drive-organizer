from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.config import settings

_PARALLEL_WORKERS = 2

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "target_path": {"type": "string"},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["target_path", "confidence", "reasoning"],
}

_SYSTEM = (
    "You are a file organization assistant. Classify files based ONLY on their metadata "
    "(name, extension, MIME type, size, date). "
    "Respond with JSON: target_path (folder path), confidence (0.0-1.0), reasoning (brief). "
    "Set confidence below 0.6 when the file purpose is genuinely ambiguous. "
    "Use Italian folder names."
)


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


class OllamaProvider:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self._model = model or settings.ollama_model
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _classify_one(
        self,
        req: ClassificationRequest,
        strategy_hint: str,
        allowed_folders: list[str] | None,
    ) -> ClassificationResult:
        folders_text = f"Preferred folders: {', '.join(allowed_folders)}. " if allowed_folders else ""
        user_msg = (
            f"{folders_text}"
            f"File: name={req.name!r} ext={req.extension!r} "
            f"mime={req.mime_type!r} size={req.size} "
            f"modified={req.modified_time.date()}\n"
            f"Strategy hint: {strategy_hint}"
        )
        payload: dict = {
            "model": self._model,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.0},
            "format": _RESPONSE_SCHEMA,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        }
        # think=false must be top-level (Ollama 0.6.4+), not inside options
        if "qwen3" in self._model:
            payload["think"] = False

        resp = requests.post(f"{self._base_url}/api/chat", json=payload, timeout=60)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        parsed = _extract_json(raw)

        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            file_id=req.file_id,
            target_path=parsed.get("target_path", "Altro"),
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
            provider="ollama",
        )

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        id_to_result: dict[str, ClassificationResult] = {}

        def _safe_classify(req: ClassificationRequest) -> ClassificationResult:
            try:
                return self._classify_one(req, strategy_hint, allowed_folders)
            except Exception as e:
                return ClassificationResult(
                    file_id=req.file_id,
                    target_path="Altro",
                    confidence=0.0,
                    reasoning=f"Ollama error: {e}",
                    provider="ollama",
                )

        with ThreadPoolExecutor(max_workers=_PARALLEL_WORKERS) as pool:
            futures = {pool.submit(_safe_classify, req): req for req in requests_list}
            for future in as_completed(futures):
                result = future.result()
                id_to_result[result.file_id] = result

        return [id_to_result[r.file_id] for r in requests_list]

    def classify_with_content(
        self,
        req: ClassificationRequest,
        content_preview: str,
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> ClassificationResult:
        """Ollama-only path: classify using file content preview."""
        folders_text = f"Preferred folders: {', '.join(allowed_folders)}. " if allowed_folders else ""
        user_msg = (
            f"{folders_text}"
            f"File: name={req.name!r} ext={req.extension!r} mime={req.mime_type!r}\n"
            f"Content preview (first 500 chars):\n{content_preview[:500]}\n"
            f"Strategy hint: {strategy_hint}"
        )
        payload = {
            "model": self._model,
            "stream": False,
            "options": {"temperature": 0.0},
            "format": _RESPONSE_SCHEMA,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        }
        resp = requests.post(f"{self._base_url}/api/chat", json=payload, timeout=60)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        parsed = _extract_json(raw)
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        return ClassificationResult(
            file_id=req.file_id,
            target_path=parsed.get("target_path", "Altro"),
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
            provider="ollama",
            used_content=True,
        )
