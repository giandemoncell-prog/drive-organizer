from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request

from web_app.helpers import sanitize_key

bp = Blueprint("config", __name__)

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"


@bp.route("/api/config")
def api_config_get():
    from drive_organizer.config import settings

    def mask(v):
        return (v[:8] + "…") if len(v) > 8 else (v if v else "(vuota)")

    if settings.anthropic_api_key:
        active = "Anthropic"
    elif settings.gemini_api_key:
        active = "Gemini"
    elif settings.deepseek_api_key:
        active = "DeepSeek"
    elif settings.dashscope_api_key:
        active = "Qwen (DashScope)"
    else:
        active = "Solo Ollama"

    return jsonify({
        "anthropic_key": mask(settings.anthropic_api_key),
        "anthropic_set": bool(settings.anthropic_api_key),
        "gemini_key": mask(settings.gemini_api_key),
        "gemini_set": bool(settings.gemini_api_key),
        "deepseek_key": mask(settings.deepseek_api_key),
        "deepseek_set": bool(settings.deepseek_api_key),
        "dashscope_key": mask(settings.dashscope_api_key),
        "dashscope_set": bool(settings.dashscope_api_key),
        "ollama_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "active_provider": active,
    })


@bp.route("/api/config", methods=["POST"])
def api_config_save():
    data = request.json or {}
    lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []

    updates: dict[str, str] = {}
    if data.get("anthropic_key") and not str(data["anthropic_key"]).endswith("…"):
        updates["ANTHROPIC_API_KEY"] = sanitize_key(data["anthropic_key"])
    if data.get("gemini_key") and not str(data["gemini_key"]).endswith("…"):
        updates["GEMINI_API_KEY"] = sanitize_key(data["gemini_key"])
    if data.get("deepseek_key") and not str(data["deepseek_key"]).endswith("…"):
        updates["DEEPSEEK_API_KEY"] = sanitize_key(data["deepseek_key"])
    if data.get("dashscope_key") and not str(data["dashscope_key"]).endswith("…"):
        updates["DASHSCOPE_API_KEY"] = sanitize_key(data["dashscope_key"])
    if data.get("ollama_url"):
        updates["OLLAMA_BASE_URL"] = sanitize_key(data["ollama_url"])
    if data.get("ollama_model"):
        updates["OLLAMA_MODEL"] = sanitize_key(data["ollama_model"])

    new_lines, updated = [], set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            updated.add(key)
        else:
            new_lines.append(line)
    for key, val in updates.items():
        if key not in updated:
            new_lines.append(f"{key}={val}")

    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_PATH, override=True)
        from drive_organizer.config import settings
        _env_to_attr = {
            "ANTHROPIC_API_KEY": "anthropic_api_key",
            "GEMINI_API_KEY": "gemini_api_key",
            "DEEPSEEK_API_KEY": "deepseek_api_key",
            "DASHSCOPE_API_KEY": "dashscope_api_key",
            "OLLAMA_BASE_URL": "ollama_base_url",
            "OLLAMA_MODEL": "ollama_model",
        }
        for env_key, attr in _env_to_attr.items():
            val = os.environ.get(env_key)
            if val is not None:
                setattr(settings, attr, val)
    except Exception:
        pass

    return jsonify({"ok": True})
