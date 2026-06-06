from __future__ import annotations

import json
import os
import queue
import sys
import threading
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

app = Flask(__name__)

_ops: dict[str, queue.Queue] = {}
_structure_lock = threading.Lock()


def _new_op() -> tuple[str, queue.Queue]:
    op_id = uuid.uuid4().hex
    q: queue.Queue = queue.Queue()
    _ops[op_id] = q
    return op_id, q


class _FakeProgress:
    def __init__(self, q: queue.Queue, total: int, interval: int = 50):
        self._q = q
        self._total = total
        self._done = 0
        self._interval = interval

    def update(self, task_id, advance: int = 1):
        self._done += advance
        if self._done % self._interval == 0 or self._done >= self._total:
            self._q.put({"type": "progress", "current": self._done, "total": self._total,
                         "message": f"Elaborati {self._done}/{self._total}…"})

    def advance(self, task_id, advance: int = 1):
        self.update(task_id, advance)


def _build_cascade():
    from drive_organizer.ai.factory import build_cascade
    return build_cascade()


def _sanitize_key(v: str) -> str:
    """Strip newlines/CR to prevent .env injection."""
    return v.replace("\n", "").replace("\r", "").strip()


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
        _ops.pop(op_id, None)

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
    taxonomy_json = data.get("taxonomy_json")  # inline taxonomy dict from UI analysis
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
                if taxonomy_json:
                    taxonomy = taxonomy_json
                    folders = taxonomy.get("folders", [])
                    q.put({"type": "ok", "message": f"Struttura AI caricata: {', '.join(folders)}"})
                elif taxonomy_file:
                    _tax_dir = (Path(__file__).parent / "taxonomies").resolve()
                    _tax_path = (Path(__file__).parent / taxonomy_file).resolve()
                    if not str(_tax_path).startswith(str(_tax_dir)):
                        raise ValueError(f"Invalid taxonomy path: {taxonomy_file}")
                    taxonomy = json.loads(_tax_path.read_text(encoding="utf-8"))
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
            with _structure_lock:
                global _structure_cache
                _structure_cache = None
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
                {
                    "files": [{"name": f.name, "size": f.size, "owned": f.owned_by_me} for f in g.files],
                    "count": len(g.files),
                    "archivable": sum(1 for f in g.to_archive if f.owned_by_me and f.can_move),
                    "reason": g.reason,
                }
                for g in plan.groups[:100]
            ]
            archivable_total = sum(1 for f in plan.files_to_archive if f.owned_by_me and f.can_move)
            q.put({"type": "preview", "groups": groups, "total_groups": len(plan.groups),
                   "total_files": archivable_total,
                   "message": f"{len(plan.groups)} gruppi trovati ({archivable_total} file archiviabili)."})

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


_structure_cache: dict | None = None


@app.route("/api/structure/current")
def api_structure_current():
    global _structure_cache
    with _structure_lock:
        if _structure_cache:
            return jsonify(_structure_cache)

    try:
        from drive_organizer.auth.google_auth import get_drive_service
        from pathlib import Path as _Path
        from collections import defaultdict, Counter

        svc = get_drive_service()

        # Load all folders with parents
        folders: dict[str, dict] = {}
        page_token = None
        while True:
            resp = svc.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="nextPageToken,files(id,name,parents)",
                pageSize=1000, supportsAllDrives=True, includeItemsFromAllDrives=True,
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                folders[f["id"]] = {"name": f["name"], "parents": f.get("parents", [])}
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        def get_top2(fid: str, depth: int = 0) -> tuple[str, str]:
            if depth > 15 or fid not in folders:
                return "(root)", ""
            f = folders[fid]
            if not f["parents"]:
                return f["name"], ""
            p = folders.get(f["parents"][0])
            if not p or not p["parents"]:
                return f["name"], ""
            gp = folders.get(p["parents"][0])
            if not gp or not gp["parents"]:
                return p["name"], f["name"]
            return get_top2(f["parents"][0], depth + 1)

        # Load files
        files = []
        page_token = None
        while True:
            resp = svc.files().list(
                q="mimeType!='application/vnd.google-apps.folder' and trashed=false",
                fields="nextPageToken,files(id,parents,fileExtension,size)",
                pageSize=1000, supportsAllDrives=True, includeItemsFromAllDrives=True,
                pageToken=page_token,
            ).execute()
            files.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        top_count: Counter = Counter()
        sub_count: dict[str, Counter] = defaultdict(Counter)
        type_by_top: dict[str, Counter] = defaultdict(Counter)

        for f in files:
            parents = f.get("parents", [])
            pid = parents[0] if parents else None
            top, sub = get_top2(pid) if pid else ("(root)", "")
            top_count[top] += 1
            if sub:
                sub_count[top][sub] += 1
            ext = (f.get("fileExtension") or "?").lower()
            type_by_top[top][ext] += 1

        tree = []
        for folder, count in sorted(top_count.items(), key=lambda x: -x[1]):
            top_types = [{"ext": t, "count": n}
                         for t, n in sorted(type_by_top[folder].items(), key=lambda x: -x[1])[:4]]
            children = [{"name": s, "count": sc}
                        for s, sc in sorted(sub_count[folder].items(), key=lambda x: -x[1])[:8]]
            tree.append({"name": folder, "count": count, "types": top_types, "children": children})

        result = {"total_files": len(files), "total_folders": len(folders), "tree": tree}
        with _structure_lock:
            _structure_cache = result
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Scan Drive, sample file names, ask AI to propose a personalized taxonomy."""
    data = request.json or {}
    save_as = data.get("save_as", "").strip()
    account = data.get("account") or None
    op_id, q = _new_op()

    def run():
        try:
            from collections import Counter, defaultdict
            from drive_organizer.ai.analyzer import analyze_and_propose
            from drive_organizer.auth.google_auth import get_drive_service
            from drive_organizer.drive.client import DriveClient

            q.put({"type": "info", "message": "Connessione Google Drive..."})
            svc = get_drive_service(account)
            client = DriveClient(svc)

            q.put({"type": "info", "message": "Scansione file (solo metadati)..."})
            files, _ = client.scan_all_files()
            q.put({"type": "ok", "message": f"{len(files)} file trovati."})

            # Build top-folder list — reuse structure cache if available
            q.put({"type": "info", "message": "Analisi struttura esistente..."})
            with _structure_lock:
                cached_tree = _structure_cache
            if cached_tree:
                top_folders = [n["name"] for n in cached_tree.get("tree", [])]
                q.put({"type": "info", "message": f"Struttura caricata da cache ({len(top_folders)} cartelle top-level)."})
            else:
                folders: dict[str, dict] = {}
                page_token = None
                while True:
                    resp = svc.files().list(
                        q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                        fields="nextPageToken,files(id,name,parents)",
                        pageSize=1000, supportsAllDrives=True, includeItemsFromAllDrives=True,
                        pageToken=page_token,
                    ).execute()
                    for f in resp.get("files", []):
                        folders[f["id"]] = {"name": f["name"], "parents": f.get("parents", [])}
                    page_token = resp.get("nextPageToken")
                    if not page_token:
                        break
                top_folders = [
                    info["name"] for fid, info in folders.items()
                    if not info["parents"] or info["parents"][0] not in folders
                ]

            q.put({"type": "info",
                   "message": f"Invio {min(400, len(files))} nomi file all'AI per analisi..."})

            taxonomy = analyze_and_propose(files, sorted(set(top_folders)))

            # Save taxonomy file if requested
            saved_path = None
            if save_as:
                import re as _re
                safe = _re.sub(r"[^\w\-]", "_", save_as).strip("_") or "custom"
                save_path = Path(__file__).parent / "taxonomies" / f"taxonomy_{safe}.json"
                save_path.parent.mkdir(exist_ok=True)
                save_path.write_text(
                    __import__("json").dumps(taxonomy, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                saved_path = str(save_path.relative_to(Path(__file__).parent))

            q.put({
                "type": "taxonomy",
                "taxonomy": taxonomy,
                "saved_path": saved_path,
                "message": f"Taxonomy generata: {len(taxonomy.get('folders', []))} cartelle.",
                "done": True,
            })

        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})


@app.route("/api/taxonomy/save", methods=["POST"])
def api_taxonomy_save():
    """Save a taxonomy dict to a named file."""
    data = request.json or {}
    name = data.get("name", "custom").strip()
    taxonomy = data.get("taxonomy", {})
    import re as _re
    safe = _re.sub(r"[^\w\-]", "_", name).strip("_") or "custom"
    save_path = Path(__file__).parent / "taxonomies" / f"taxonomy_{safe}.json"
    save_path.parent.mkdir(exist_ok=True)
    save_path.write_text(
        __import__("json").dumps(taxonomy, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return jsonify({"ok": True, "path": f"taxonomies/taxonomy_{safe}.json"})


@app.route("/api/structure/cache/clear", methods=["POST"])
def api_structure_cache_clear():
    global _structure_cache
    with _structure_lock:
        _structure_cache = None
    return jsonify({"ok": True})


@app.route("/api/structure/proposed", methods=["POST"])
def api_structure_proposed():
    data = request.json or {}
    strategy = data.get("strategy", "type")
    op_id, q = _new_op()

    def run():
        try:
            from collections import defaultdict, Counter as _Counter
            from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.planner import OrganizationPlanner

            q.put({"type": "info", "message": "Connessione Drive..."})
            svc = get_drive_service()
            email = get_authenticated_email(svc)
            client = DriveClient(svc)

            q.put({"type": "info", "message": "Scansione file..."})
            files, _ = client.scan_all_files()
            q.put({"type": "info", "message": f"{len(files)} file trovati. Classificazione..."})

            if strategy == "type":
                from drive_organizer.strategies.by_type import FileTypeStrategy
                strat = FileTypeStrategy()
            elif strategy == "date":
                from drive_organizer.strategies.by_date import DateStrategy
                strat = DateStrategy()
            else:
                from drive_organizer.strategies.by_type import FileTypeStrategy
                strat = FileTypeStrategy()

            cascade = _build_cascade() if strat.requires_ai() else None
            planner = OrganizationPlanner(cascade=cascade)
            plan = planner.build_plan(files, strat, None, 0)

            top_count: _Counter = _Counter()
            sub_count: dict = defaultdict(_Counter)
            for op in plan.moves:
                if op.skipped:
                    continue
                parts = [p for p in op.target_path.replace("\\", "/").split("/") if p]
                top = parts[0] if parts else "Altro"
                sub = parts[1] if len(parts) > 1 else ""
                top_count[top] += 1
                if sub:
                    sub_count[top][sub] += 1

            tree = []
            for folder, count in sorted(top_count.items(), key=lambda x: -x[1]):
                children = [{"name": s, "count": sc}
                            for s, sc in sorted(sub_count[folder].items(), key=lambda x: -x[1])[:8]]
                tree.append({"name": folder, "count": count, "children": children})

            q.put({"type": "tree", "tree": tree, "total": len(plan.moves),
                   "message": f"Struttura proposta pronta: {len(tree)} cartelle top-level.",
                   "done": True})
        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})


@app.route("/api/config")
def api_config_get():
    from drive_organizer.config import settings

    def mask(v):
        return (v[:8] + "…") if len(v) > 8 else ("(vuota)" if not v else v)

    # Determine active provider
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


@app.route("/api/config", methods=["POST"])
def api_config_save():
    data = request.json or {}
    env_path = Path(__file__).parent / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    updates: dict[str, str] = {}
    if data.get("anthropic_key") and not str(data["anthropic_key"]).endswith("…"):
        updates["ANTHROPIC_API_KEY"] = _sanitize_key(data["anthropic_key"])
    if data.get("gemini_key") and not str(data["gemini_key"]).endswith("…"):
        updates["GEMINI_API_KEY"] = _sanitize_key(data["gemini_key"])
    if data.get("deepseek_key") and not str(data["deepseek_key"]).endswith("…"):
        updates["DEEPSEEK_API_KEY"] = _sanitize_key(data["deepseek_key"])
    if data.get("dashscope_key") and not str(data["dashscope_key"]).endswith("…"):
        updates["DASHSCOPE_API_KEY"] = _sanitize_key(data["dashscope_key"])
    if data.get("ollama_url"):
        updates["OLLAMA_BASE_URL"] = _sanitize_key(data["ollama_url"])
    if data.get("ollama_model"):
        updates["OLLAMA_MODEL"] = _sanitize_key(data["ollama_model"])

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

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Reload live settings so the change takes effect without restart
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
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
        pass  # non-critical — server restart still works

    return jsonify({"ok": True})


@app.route("/api/rename", methods=["POST"])
def api_rename():
    data = request.json or {}
    apply = data.get("apply", False)
    limit = int(data.get("limit", 0))
    offset = int(data.get("offset", 0))
    account = data.get("account") or None

    op_id, q = _new_op()

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


if __name__ == "__main__":
    import webbrowser
    port = 5001
    print(f"\nDrive Organizer Web UI -> http://localhost:{port}\n")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
