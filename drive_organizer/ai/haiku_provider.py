from __future__ import annotations

import json

import anthropic

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.config import settings

_SCHEMA = {
    "type": "object",
    "properties": {
        "target_path": {"type": "string"},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["target_path", "confidence", "reasoning"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a file organization assistant. Classify files using ONLY their metadata "
    "(name, extension, MIME type, size, modification date). "
    "You NEVER receive or process file contents. "
    "Return JSON: target_path (Italian folder path), confidence (0.0-1.0), reasoning. "
    "Set confidence < 0.6 for genuinely ambiguous files."
)


class HaikuProvider:
    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = settings.haiku_model

    def health_check(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _build_user_message(
        self,
        reqs: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None,
    ) -> str:
        folders_text = f"Preferred folders: {', '.join(allowed_folders)}.\n" if allowed_folders else ""
        files_text = "\n".join(
            f"- id={r.file_id!r} name={r.name!r} ext={r.extension!r} "
            f"mime={r.mime_type!r} size={r.size} modified={r.modified_time.date()}"
            for r in reqs
        )
        return (
            f"{folders_text}"
            f"Strategy: {strategy_hint}\n\n"
            f"Files to classify:\n{files_text}\n\n"
            "Return a JSON array, one object per file, each with: file_id, target_path, confidence, reasoning."
        )

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not requests_list:
            return []

        user_msg = self._build_user_message(requests_list, strategy_hint, allowed_folders)
        array_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string"},
                    "target_path": {"type": "string"},
                    "confidence": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": ["file_id", "target_path", "confidence", "reasoning"],
                "additionalProperties": False,
            },
        }

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            output_config={"format": {"type": "json_schema", "schema": array_schema}},
        )

        raw = next((b.text for b in resp.content if b.type == "text"), "[]")
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
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
                provider="haiku",
            )

        results = []
        for req in requests_list:
            if req.file_id in id_to_result:
                results.append(id_to_result[req.file_id])
            else:
                results.append(ClassificationResult(
                    file_id=req.file_id,
                    target_path="Altro",
                    confidence=0.0,
                    reasoning="Haiku did not return a result for this file",
                    provider="haiku",
                ))
        return results
