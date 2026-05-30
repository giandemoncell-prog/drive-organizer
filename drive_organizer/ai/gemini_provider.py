from __future__ import annotations

import json

from google import genai
from google.genai import types

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.config import settings

_SYSTEM = (
    "You are a file organization assistant. Classify files using ONLY their metadata "
    "(name, extension, MIME type, size, modification date). "
    "You NEVER receive or process file contents — hard privacy requirement. "
    "Return JSON: target_path (Italian folder path), confidence (0.0-1.0), reasoning. "
    "Set confidence < 0.6 for genuinely ambiguous files."
)


def _make_client(api_key: str | None = None) -> genai.Client:
    return genai.Client(api_key=api_key or settings.gemini_api_key)


def _classify_prompt(
    requests_list: list[ClassificationRequest],
    strategy_hint: str,
    allowed_folders: list[str] | None,
) -> str:
    folders_text = f"Preferred folders: {', '.join(allowed_folders)}.\n" if allowed_folders else ""
    files_text = "\n".join(
        f"- id={r.file_id!r} name={r.name!r} ext={r.extension!r} "
        f"mime={r.mime_type!r} size={r.size} modified={r.modified_time.date()}"
        for r in requests_list
    )
    return (
        f"{folders_text}Strategy: {strategy_hint}\n\n"
        f"Files to classify:\n{files_text}\n\n"
        "Return a JSON array, one object per file: file_id, target_path, confidence, reasoning."
    )


def _parse_results(
    raw: str,
    requests_list: list[ClassificationRequest],
    provider_label: str,
) -> list[ClassificationResult]:
    try:
        items = json.loads(raw)
    except Exception:
        items = []

    id_to_result = {}
    for item in items:
        fid = item.get("file_id", "")
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        id_to_result[fid] = ClassificationResult(
            file_id=fid,
            target_path=item.get("target_path", "Altro"),
            confidence=confidence,
            reasoning=item.get("reasoning", ""),
            provider=provider_label,
        )

    return [
        id_to_result.get(req.file_id, ClassificationResult(
            file_id=req.file_id,
            target_path="Altro",
            confidence=0.0,
            reasoning="Gemini did not return a result",
            provider=provider_label,
        ))
        for req in requests_list
    ]


class GeminiFlashProvider:
    """Gemini Flash — usato come secondo livello nel cascade (al posto di Haiku)."""

    def __init__(self, api_key: str | None = None):
        self._client = _make_client(api_key)
        self._model = settings.gemini_flash_model

    def health_check(self) -> bool:
        return bool(settings.gemini_api_key)

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not requests_list:
            return []
        prompt = _classify_prompt(requests_list, strategy_hint, allowed_folders)
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            return _parse_results(resp.text, requests_list, "haiku")
        except Exception as e:
            return [ClassificationResult(
                file_id=r.file_id, target_path="Altro", confidence=0.0,
                reasoning=f"Gemini Flash error: {e}", provider="haiku",
            ) for r in requests_list]


class GeminiProProvider:
    """Gemini Pro — usato come livello finale nel cascade (al posto di Opus)."""

    def __init__(self, api_key: str | None = None):
        self._client = _make_client(api_key)
        self._model = settings.gemini_pro_model

    def health_check(self) -> bool:
        return bool(settings.gemini_api_key)

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not requests_list:
            return []
        prompt = _classify_prompt(requests_list, strategy_hint, allowed_folders)
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            return _parse_results(resp.text, requests_list, "opus")
        except Exception as e:
            return [ClassificationResult(
                file_id=r.file_id, target_path="Altro", confidence=0.0,
                reasoning=f"Gemini Pro error: {e}", provider="opus",
            ) for r in requests_list]

    def parse_custom_taxonomy(self, description: str) -> dict:
        prompt = (
            "You are a file organization expert. "
            "Convert the user's description into a JSON folder taxonomy. "
            "Use Italian folder names.\n\n"
            f"Create a taxonomy for: {description}"
        )
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are a file organization expert. "
                        "Return only valid JSON with keys: folders (array), rules (array of {match, target}), fallback_folder (string)."
                    ),
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            return json.loads(resp.text)
        except Exception:
            return {"folders": ["Altro"], "rules": [], "fallback_folder": "Altro"}
