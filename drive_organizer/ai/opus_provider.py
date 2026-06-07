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

_TAXONOMY_SCHEMA = {
    "type": "object",
    "properties": {
        "folders": {"type": "array", "items": {"type": "string"}},
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "match": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["match", "target"],
                "additionalProperties": False,
            },
        },
        "fallback_folder": {"type": "string"},
    },
    "required": ["folders", "rules", "fallback_folder"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are an expert file organization assistant. Classify files using ONLY their metadata "
    "(name, extension, MIME type, size, modification date). "
    "You NEVER receive or process file contents — this is a hard privacy requirement. "
    "Return JSON: target_path (Italian folder path), confidence (0.0-1.0), reasoning. "
    "Set confidence < 0.6 for genuinely ambiguous files."
)


class OpusProvider:
    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = settings.opus_model

    def health_check(self) -> bool:
        return bool(settings.anthropic_api_key)

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not requests_list:
            return []

        folders_text = f"Preferred folders: {', '.join(allowed_folders)}.\n" if allowed_folders else ""
        files_text = "\n".join(
            f"- id={r.file_id!r} name={r.name!r} ext={r.extension!r} "
            f"mime={r.mime_type!r} size={r.size} modified={r.modified_time.date()}"
            for r in requests_list
        )
        user_msg = (
            f"{folders_text}Strategy: {strategy_hint}\n\n"
            f"Files:\n{files_text}\n\n"
            "Return a JSON array, one object per file: file_id, target_path, confidence, reasoning."
        )

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
            max_tokens=8192,
            thinking={"type": "adaptive"},
            output_config={"effort": "xhigh", "format": {"type": "json_schema", "schema": array_schema}},
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
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
                provider="opus",
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
                    reasoning="Opus did not return result",
                    provider="opus",
                ))
        return results

    def parse_custom_taxonomy(self, description: str) -> dict:
        """Parse natural language (IT/EN) description into folder taxonomy."""
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            output_config={"effort": "xhigh", "format": {"type": "json_schema", "schema": _TAXONOMY_SCHEMA}},
            system=(
                "You are a file organization expert. "
                "Convert the user's natural language description of a folder structure into a JSON taxonomy. "
                "Use Italian folder names. Create specific match rules based on the description."
            ),
            messages=[{"role": "user", "content": f"Create a folder taxonomy for: {description}"}],
        )
        raw = next((b.text for b in resp.content if b.type == "text"), "{}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"folders": ["Altro"], "rules": [], "fallback_folder": "Altro"}
