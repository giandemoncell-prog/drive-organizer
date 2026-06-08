from __future__ import annotations

import threading

from flask import Blueprint, jsonify, request

from web_app.helpers import _FakeProgress, new_op

bp = Blueprint("duplicates", __name__)


@bp.route("/api/duplicates", methods=["POST"])
def api_duplicates():
    data = request.json or {}
    apply = data.get("apply", False)
    archive_folder = data.get("archive_folder", "99_Archivio/Duplicati")
    account = data.get("account") or None

    op_id, q = new_op()

    def run():
        try:
            from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.duplicate_finder import find_duplicates

            q.put({"type": "info", "message": "Connessione Google Drive…"})
            svc = get_drive_service(account)
            email = get_authenticated_email(svc)
            client = DriveClient(svc)
            q.put({"type": "ok", "message": f"Connesso come: {email}"})

            q.put({"type": "info", "message": "Scansione file…"})
            files, _ = client.scan_all_files()
            q.put({"type": "info", "message": f"{len(files)} file trovati. Ricerca duplicati…"})

            plan = find_duplicates(files)

            groups = [
                {
                    "files": [{"name": f.name, "size": f.size, "owned": f.owned_by_me} for f in g.files],
                    "count": len(g.files),
                    "archivable": sum(1 for f in g.to_archive if f.owned_by_me and f.can_move),
                    "reason": g.reason,
                }
                for g in plan.groups[:100]
            ]
            archivable_total = sum(1 for f in plan.files_to_archive if f.owned_by_me and f.can_move)
            not_owned = sum(1 for g in plan.groups for f in g.to_archive if not f.owned_by_me)
            not_movable = sum(1 for g in plan.groups for f in g.to_archive if f.owned_by_me and not f.can_move)
            q.put({"type": "preview", "groups": groups, "total_groups": len(plan.groups),
                   "total_files": archivable_total,
                   "not_owned": not_owned, "not_movable": not_movable,
                   "message": (
                       f"{len(plan.groups)} gruppi trovati — "
                       f"{archivable_total} archiviabili"
                       + (f", {not_owned} non tuoi" if not_owned else "")
                       + (f", {not_movable} non spostabili" if not_movable else "")
                       + "."
                   )})

            if not apply:
                q.put({"type": "ok", "message": "Anteprima pronta.", "done": True})
                return

            if not plan.files_to_archive:
                q.put({"type": "ok", "message": "Nessun duplicato trovato.", "done": True})
                return

            from drive_organizer.drive.models import MoveOperation, OrganizationPlan
            from drive_organizer.executor import PlanExecutor

            moves = [
                MoveOperation(file_id=f.id, file_name=f.name,
                              source_parents=list(f.parents),
                              target_path=archive_folder,
                              confidence=1.0, provider="deterministic")
                for f in plan.files_to_archive if f.owned_by_me and f.can_move
            ]
            dup_plan = OrganizationPlan(strategy_name="duplicates", moves=moves,
                                        folders_to_create=[archive_folder], total_files=len(moves))
            manifest = PlanExecutor(client, email).execute(dup_plan)
            q.put({"type": "ok", "message": f"Completato! {len(manifest.entries)} duplicati archiviati.", "done": True})

        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})
