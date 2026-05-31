from __future__ import annotations

import json
import queue
import sys
import threading
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

app = Flask(__name__)

_ops: dict[str, queue.Queue] = {}


def _new_op() -> tuple[str, queue.Queue]:
    op_id = uuid.uuid4().hex
    q: queue.Queue = queue.Queue()
    _ops[op_id] = q
    return op_id, q


class _FakeProgress:
    def __init__(self, q: queue.Queue, total: int):
        self._q = q
        self._total = total
        self._done = 0

    def update(self, task_id, advance: int = 1):
        self._done += advance
        if self._done % 100 == 0 or self._done >= self._total:
            self._q.put({"type": "progress", "current": self._done, "total": self._total,
                         "message": f"Classificati {self._done}/{self._total}…"})


def _build_cascade():
    from drive_organizer.ai.cascade import AICascade
    from drive_organizer.ai.ollama_provider import OllamaProvider
    from drive_organizer.config import settings

    if settings.gemini_api_key and not settings.anthropic_api_key:
        from drive_organizer.ai.gemini_provider import GeminiFlashProvider, GeminiProProvider
        haiku, opus = GeminiFlashProvider(), GeminiProProvider()
    else:
        from drive_organizer.ai.haiku_provider import HaikuProvider
        from drive_organizer.ai.opus_provider import OpusProvider
        haiku, opus = HaikuProvider(), OpusProvider()

    return AICascade(ollama=OllamaProvider(), haiku=haiku, opus=opus)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    try:
        from drive_organizer.ai.ollama_provider import OllamaProvider
        from drive_organizer.auth.google_auth import (
            get_authenticated_email, get_drive_service, list_accounts,
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


@app.route("/api/stream/<op_id>")
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

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/organize", methods=["POST"])
def api_organize():
    data = request.json or {}
    strategy = data.get("strategy", "type")
    apply = data.get("apply", False)
    custom_prompt = data.get("custom_prompt", "")
    taxonomy_file = data.get("taxonomy_file")
    year_only = data.get("year_only", False)
    account = data.get("account") or None

    op_id, q = _new_op()

    def run():
        try:
            from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.planner import OrganizationPlanner

            q.put({"type": "info", "message": "Connessione Google Drive…"})
            svc = get_drive_service(account)
            email = get_authenticated_email(svc)
            client = DriveClient(svc)
            q.put({"type": "ok", "message": f"Connesso come: {email}"})

            q.put({"type": "info", "message": "Scansione file (metadati)…"})
            files, _ = client.scan_all_files()
            q.put({"type": "ok", "message": f"{len(files)} file trovati."})

            if strategy == "type":
                from drive_organizer.strategies.by_type import FileTypeStrategy
                strat = FileTypeStrategy()
            elif strategy == "date":
                from drive_organizer.strategies.by_date import DateStrategy
                strat = DateStrategy(year_only=year_only)
            elif strategy == "project":
                from drive_organizer.strategies.by_project import ProjectTopicStrategy
                strat = ProjectTopicStrategy()
            elif strategy == "custom":
                from drive_organizer.strategies.custom import CustomNLStrategy
                from drive_organizer.config import settings
                if taxonomy_file:
                    import json as _j
                    taxonomy = _j.loads(Path(taxonomy_file).read_text())
                else:
                    q.put({"type": "info", "message": "AI interpreta la struttura desiderata…"})
                    if settings.gemini_api_key and not settings.anthropic_api_key:
                        from drive_organizer.ai.gemini_provider import GeminiProProvider
                        parser = GeminiProProvider()
                    else:
                        from drive_organizer.ai.opus_provider import OpusProvider
                        parser = OpusProvider()
                    taxonomy = parser.parse_custom_taxonomy(custom_prompt)
                    folders = taxonomy.get("folders", [])
                    q.put({"type": "ok", "message": f"Struttura: {', '.join(folders)}"})
                strat = CustomNLStrategy(description=custom_prompt, taxonomy=taxonomy)
            else:
                q.put({"type": "error", "message": f"Strategia sconosciuta: {strategy}", "done": True})
                return

            cascade = _build_cascade() if strat.requires_ai() else None
            q.put({"type": "info", "message": f"Classificazione '{strategy}' in corso…"})

            movable = [f for f in files if not f.is_shortcut and f.owned_by_me and f.can_move]
            prog = _FakeProgress(q, len(movable))
            planner = OrganizationPlanner(cascade=cascade)
            plan = planner.build_plan(files, strat, prog, 0)

            active = [op for op in plan.moves if not op.skipped]
            preview = [
                {"file_name": op.file_name, "target_path": op.target_path,
                 "provider": op.provider, "confidence": round(op.confidence, 2)}
                for op in active[:300]
            ]
            q.put({"type": "preview", "moves": preview, "total": len(active),
                   "message": f"Piano: {len(active)} file da spostare."})

            if not apply:
                q.put({"type": "ok", "message": "Anteprima pronta. Premi Applica per procedere.", "done": True})
                return

            q.put({"type": "info", "message": f"Applicazione in corso ({len(active)} file)…"})
            from drive_organizer.executor import PlanExecutor
            executor = PlanExecutor(client, email)
            manifest = executor.execute(plan)
            q.put({"type": "ok", "message": f"Completato! {len(manifest.entries)} file spostati.", "done": True})

        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})


@app.route("/api/duplicates", methods=["POST"])
def api_duplicates():
    data = request.json or {}
    apply = data.get("apply", False)
    archive_folder = data.get("archive_folder", "99_Archivio/Duplicati")
    account = data.get("account") or None

    op_id, q = _new_op()

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
                {"files": [{"name": f.name, "size": f.size} for f in g.files], "count": len(g.files)}
                for g in plan.groups[:100]
            ]
            q.put({"type": "preview", "groups": groups, "total_groups": len(plan.groups),
                   "total_files": len(plan.files_to_archive),
                   "message": f"{len(plan.groups)} gruppi trovati ({len(plan.files_to_archive)} file da archiviare)."})

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


@app.route("/api/rollbacks")
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
        return jsonify([])


@app.route("/api/rollback", methods=["POST"])
def api_rollback():
    data = request.json or {}
    run_id = data.get("run_id")
    op_id, q = _new_op()

    def run():
        try:
            from drive_organizer.auth.google_auth import get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.rollback import RollbackManager

            svc = get_drive_service()
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


if __name__ == "__main__":
    import webbrowser
    port = 5001
    print(f"\nDrive Organizer Web UI → http://localhost:{port}\n")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
