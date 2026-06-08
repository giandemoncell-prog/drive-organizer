from __future__ import annotations

import threading

from flask import Blueprint, jsonify, request

from web_app.helpers import new_op

bp = Blueprint("rollback", __name__)


@bp.route("/api/rollbacks")
def api_rollbacks():
    try:
        from drive_organizer.auth.google_auth import get_drive_service
        from drive_organizer.drive.client import DriveClient
        from drive_organizer.rollback import RollbackManager

        svc = get_drive_service()
        client = DriveClient(svc)
        mgr = RollbackManager(client)
        return jsonify([{
            "run_id": m.run_id,
            "short": m.run_id[:8],
            "date": m.started_at.strftime("%Y-%m-%d %H:%M"),
            "entries": len(m.entries),
            "email": m.drive_user_email,
        } for m in mgr.list_available()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/rollback", methods=["POST"])
def api_rollback():
    data = request.json or {}
    run_id = data.get("run_id")
    account = data.get("account") or None
    op_id, q = new_op()

    def run():
        try:
            from drive_organizer.auth.google_auth import get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.rollback import RollbackManager

            svc = get_drive_service(account)
            client = DriveClient(svc)
            mgr = RollbackManager(client)
            manifests = mgr.list_available()
            chosen = next((m for m in manifests if m.run_id == run_id), None)
            if not chosen:
                q.put({"type": "error", "message": "Sessione non trovata.", "done": True})
                return
            q.put({"type": "info", "message": f"Rollback {run_id[:8]}…"})
            mgr.execute_rollback(chosen)
            q.put({"type": "ok", "message": f"Ripristinati {len(chosen.entries)} file.", "done": True})
        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})
