from __future__ import annotations

import json
import queue

from flask import Blueprint, Response, jsonify, render_template, stream_with_context

from web_app.state import _ops

bp = Blueprint("status", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/status")
def api_status():
    try:
        from drive_organizer.ai.ollama_provider import OllamaProvider
        from drive_organizer.auth.google_auth import (
            get_authenticated_email,
            get_drive_service,
            list_accounts,
        )
        from drive_organizer.config import settings
        from drive_organizer.drive.client import DriveClient

        accounts = list_accounts()
        if not accounts:
            return jsonify({"connected": False, "error": "Nessun account autenticato"})

        svc = get_drive_service()
        email = get_authenticated_email(svc)
        client = DriveClient(svc)
        about = client.get_about()
        quota = about.get("storageQuota", {})
        used = int(quota.get("usage", 0))
        limit = int(quota.get("limit", 0))

        ollama = OllamaProvider()
        return jsonify({
            "connected": True,
            "email": email,
            "accounts": accounts,
            "storage": {
                "used_gb": round(used / 1e9, 2),
                "limit_gb": round(limit / 1e9, 0) if limit else 0,
            },
            "ai": {
                "ollama": ollama.health_check(),
                "ollama_model": settings.ollama_model,
                "anthropic": bool(settings.anthropic_api_key),
                "gemini": bool(settings.gemini_api_key),
            },
        })
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


@bp.route("/api/stream/<op_id>")
def api_stream(op_id):
    q = _ops.get(op_id)
    if not q:
        return Response("data: {\"type\":\"error\",\"message\":\"op not found\",\"done\":true}\n\n",
                        mimetype="text/event-stream")

    def generate():
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("done"):
                    break
            except queue.Empty:
                yield "data: {\"type\":\"ping\"}\n\n"
        _ops.pop(op_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
