from __future__ import annotations

import threading

from flask import Blueprint, jsonify, request

from web_app.helpers import _FakeProgress, new_op

bp = Blueprint("rename", __name__)


@bp.route("/api/rename", methods=["POST"])
def api_rename():
    data = request.json or {}
    apply = data.get("apply", False)
    limit = int(data.get("limit", 0))
    offset = int(data.get("offset", 0))
    account = data.get("account") or None

    op_id, q = new_op()

    def run():
        try:
            from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.renamer import FileRenamer

            q.put({"type": "info", "message": "Connessione Google Drive…"})
            svc = get_drive_service(account)
            email = get_authenticated_email(svc)
            client = DriveClient(svc)
            q.put({"type": "ok", "message": f"Connesso come: {email}"})

            renamer = FileRenamer(svc)
            if not renamer.health_check():
                q.put({"type": "error",
                       "message": "Ollama non raggiungibile. La rinomina usa solo Ollama locale.",
                       "done": True})
                return

            q.put({"type": "info", "message": "Scansione file…"})
            files, _ = client.scan_all_files()
            movable = [f for f in files if not f.is_folder and not f.is_shortcut and f.owned_by_me]
            if offset:
                movable = movable[offset:]
            if limit:
                movable = movable[:limit]
            q.put({"type": "ok", "message": f"{len(movable)} file da analizzare."})

            q.put({"type": "info", "message": f"Analisi nomi con Ollama ({renamer._model})…"})
            prog = _FakeProgress(q, len(movable), interval=10)
            plan = renamer.build_plan(movable, prog, 0)

            active = [op for op in plan.operations if not op.skipped]
            preview = [
                {"old_name": op.old_name, "new_name": op.new_name,
                 "confidence": round(op.confidence, 2), "reasoning": op.reasoning}
                for op in active[:300]
            ]
            q.put({"type": "preview", "renames": preview, "total": len(active),
                   "message": f"Piano: {len(active)} file da rinominare."})

            if not apply:
                q.put({"type": "ok", "message": "Anteprima pronta. Premi Applica per procedere.", "done": True})
                return

            q.put({"type": "info", "message": f"Rinomina in corso ({len(active)} file)…"})
            from drive_organizer.rename_executor import RenameExecutor
            executor = RenameExecutor(client, email)
            manifest = executor.execute(plan)
            q.put({"type": "ok", "message": f"Completato! {len(manifest.entries)} file rinominati.", "done": True})

        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})
