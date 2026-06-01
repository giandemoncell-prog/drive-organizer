from __future__ import annotations

import json
import re

import httpx

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.config import settings

_BASE_URL = "https://api.deepseek.com/v1/chat/completions"

_SYSTEM = (
    "You are a file organization assistant. Classify files using ONLY their metadata "
    "(name, extension, MIME type, size, modification date). "
    "You NEVER receive or process file contents — hard privacy requirement. "
    "Return a JSON array, one object per file: file_id, target_path (Italian folder path), "
    "confidence (0.0-1.0), reasoning. Set confidence < 0.6 for ambiguous files."
)


def _build_prompt(
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
        "Return ONLY a JSON array."
    )


def _parse(raw: str, requests_list: list[ClassificationRequest], label: str) -> list[ClassificationResult]:
    # Strip markdown fences if present
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    try:
        items = json.loads(raw)
    except Exception:
        items = []
    id_map = {}
    for item in items:
        fid = item.get("file_id", "")
        conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        id_map[fid] = ClassificationResult(
            file_id=fid,
            target_path=item.get("target_path", "Altro"),
            confidence=conf,
            reasoning=item.get("reasoning", ""),
            provider=label,
        )
    return [
        id_map.get(r.file_id, ClassificationResult(
            file_id=r.file_id, target_path="Altro", confidence=0.0,
            reasoning="no result", provider=label,
        ))
        for r in requests_list
    ]


def _call(model: str, prompt: str) -> str:
    resp = httpx.post(
        _BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.0,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


class DeepSeekFlashProvider:
    def health_check(self) -> bool:
        return bool(settings.deepseek_api_key)

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not requests_list:
            return []
        raw = _call(settings.deepseek_flash_model, _build_prompt(requests_list, strategy_hint, allowed_folders))
        return _parse(raw, requests_list, "deepseek-flash")


class DeepSeekProProvider:
    def health_check(self) -> bool:
        return bool(settings.deepseek_api_key)

    def classify_batch(
        self,
        requests_list: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not requests_list:
            return []
        raw = _call(settings.deepseek_pro_model, _build_prompt(requests_list, strategy_hint, allowed_folders))
        return _parse(raw, requests_list, "deepseek-pro")

    def parse_custom_taxonomy(self, description: str) -> dict:
        prompt = (
            f"Build a Google Drive folder taxonomy in Italian for: {description}\n"
            "Return JSON: {\"folders\": [\"folder1\", \"folder2\", ...], "
            "\"rules\": {\"keyword\": \"folder\"}}"
        )
        raw = _call(settings.deepseek_pro_model, prompt)
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        try:
            return json.loads(raw)
        except Exception:
            return {"folders": ["Altro"], "rules": {}}
