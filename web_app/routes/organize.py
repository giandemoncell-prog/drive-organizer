from __future__ import annotations

import json
import tempfile
import threading
from collections import Counter, defaultdict
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

from web_app.helpers import _FakeProgress, build_cascade, new_op
from web_app.state import _plans, _structure_lock

bp = Blueprint("organize", __name__)


@bp.route("/api/organize", methods=["POST"])
def api_organize():
    data = request.json or {}
    strategy = data.get("strategy", "type")
    apply = data.get("apply", False)
    custom_prompt = data.get("custom_prompt", "")
    taxonomy_file = data.get("taxonomy_file")
    taxonomy_json = data.get("taxonomy_json")
    taxonomy_preset = data.get("taxonomy_preset")
    year_only = data.get("year_only", False)
    account = data.get("account") or None

    op_id, q = new_op()

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

            if strategy == "custom":
                import re as _re

                from pydantic import ValidationError as _VE

                from drive_organizer.config import settings
                from drive_organizer.strategies.custom import CustomNLStrategy, Taxonomy

                tax_file = taxonomy_file
                if taxonomy_preset and not tax_file:
                    safe = _re.sub(r"[^\w\-]", "_", taxonomy_preset).strip("_")
                    tax_file = f"taxonomies/taxonomy_{safe}.json"

                if taxonomy_json:
                    try:
                        taxonomy = Taxonomy.model_validate(taxonomy_json).model_dump()
                    except _VE:
                        taxonomy = taxonomy_json
                    q.put({"type": "ok", "message": f"Struttura AI caricata: {', '.join(taxonomy.get('folders', []))}"})
                elif tax_file:
                    _tax_dir = (Path(__file__).parent.parent.parent / "taxonomies").resolve()
                    _tax_path = (Path(__file__).parent.parent.parent / tax_file).resolve()
                    if not str(_tax_path).startswith(str(_tax_dir)):
                        raise ValueError(f"Invalid taxonomy path: {tax_file}")
                    raw = json.loads(_tax_path.read_text(encoding="utf-8"))
                    try:
                        taxonomy = Taxonomy.model_validate(raw).model_dump()
                    except _VE:
                        taxonomy = raw
                    q.put({"type": "ok", "message": f"Tassonomia caricata: {', '.join(taxonomy.get('folders', []))}"})
                else:
                    q.put({"type": "info", "message": "AI interpreta la struttura desiderata…"})
                    if settings.gemini_api_key and not settings.anthropic_api_key:
                        from drive_organizer.ai.gemini_provider import GeminiProProvider
                        parser = GeminiProProvider()
                    else:
                        from drive_organizer.ai.opus_provider import OpusProvider
                        parser = OpusProvider()
                    taxonomy = parser.parse_custom_taxonomy(custom_prompt)
                    q.put({"type": "ok", "message": f"Struttura: {', '.join(taxonomy.get('folders', []))}"})
                strat = CustomNLStrategy(description=custom_prompt, taxonomy=taxonomy)
            else:
                try:
                    from drive_organizer.strategies.factory import build as _build_strat
                    strat = _build_strat(strategy, year_only=year_only)
                except ValueError:
                    q.put({"type": "error", "message": f"Strategia sconosciuta: {strategy}", "done": True})
                    return

            cascade = build_cascade() if strat.requires_ai() else None
            q.put({"type": "info", "message": f"Classificazione '{strategy}' in corso…"})

            movable = [f for f in files if not f.is_shortcut and f.owned_by_me and f.can_move]
            prog = _FakeProgress(q, len(movable))
            planner = OrganizationPlanner(cascade=cascade)
            plan = planner.build_plan(files, strat, prog, 0)

            _plans[op_id] = plan  # store for export

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
                import web_app.state as _st
                _st._structure_cache = None
            q.put({"type": "ok", "message": f"Completato! {len(manifest.entries)} file spostati.", "done": True})

        except Exception as e:
            q.put({"type": "error", "message": str(e), "done": True})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"op_id": op_id})


@bp.route("/api/plan/export/<op_id>")
def api_plan_export(op_id: str):
    """Download the organize plan as CSV or JSON."""
    from drive_organizer.exporter import export_plan

    plan = _plans.get(op_id)
    if not plan:
        return jsonify({"error": "Piano non trovato o scaduto"}), 404

    fmt = request.args.get("fmt", "csv").lower()
    if fmt not in ("csv", "json"):
        return jsonify({"error": "fmt deve essere csv o json"}), 400

    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tf:
        tmp = Path(tf.name)
    try:
        export_plan(plan, tmp)
        content = tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)

    mime = "text/csv" if fmt == "csv" else "application/json"
    filename = f"piano_organizzazione.{fmt}"
    return Response(
        content,
        mimetype=mime,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/api/structure/current")
def api_structure_current():
    global _structure_loading
    import web_app.state as _st

    with _structure_lock:
        if _st._structure_cache:
            return jsonify(_st._structure_cache)
        if _st._structure_loading:
            return jsonify({"error": "scan in corso, riprova tra qualche secondo"}), 503
        _st._structure_loading = True

    try:
        from drive_organizer.auth.google_auth import get_drive_service

        svc = get_drive_service()

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
            _st._structure_cache = result
            _st._structure_loading = False
        return jsonify(result)
    except Exception as e:
        with _structure_lock:
            _st._structure_loading = False
        return jsonify({"error": str(e)}), 500


@bp.route("/api/structure/cache/clear", methods=["POST"])
def api_structure_cache_clear():
    import web_app.state as _st
    with _structure_lock:
        _st._structure_cache = None
    return jsonify({"ok": True})


@bp.route("/api/structure/proposed", methods=["POST"])
def api_structure_proposed():
    data = request.json or {}
    strategy = data.get("strategy", "type")
    account = data.get("account") or None
    op_id, q = new_op()

    def run():
        try:
            from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
            from drive_organizer.drive.client import DriveClient
            from drive_organizer.planner import OrganizationPlanner

            q.put({"type": "info", "message": "Connessione Drive..."})
            svc = get_drive_service(account)
            get_authenticated_email(svc)  # validate auth early (preview route, email unused)
            client = DriveClient(svc)

            q.put({"type": "info", "message": "Scansione file..."})
            files, _ = client.scan_all_files()
            q.put({"type": "info", "message": f"{len(files)} file trovati. Classificazione..."})

            from drive_organizer.strategies.factory import build as _build_strat
            try:
                strat = _build_strat(strategy)
            except ValueError:
                strat = _build_strat("type")

            cascade = build_cascade() if strat.requires_ai() else None
            planner = OrganizationPlanner(cascade=cascade)
            plan = planner.build_plan(files, strat, None, 0)

            top_count: Counter = Counter()
            sub_count: dict = defaultdict(Counter)
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


@bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.json or {}
    save_as = data.get("save_as", "").strip()
    account = data.get("account") or None
    op_id, q = new_op()

    def run():
        try:
            import web_app.state as _st
            from drive_organizer.ai.analyzer import analyze_and_propose
            from drive_organizer.auth.google_auth import get_drive_service
            from drive_organizer.drive.client import DriveClient

            q.put({"type": "info", "message": "Connessione Google Drive..."})
            svc = get_drive_service(account)
            client = DriveClient(svc)

            q.put({"type": "info", "message": "Scansione file (solo metadati)..."})
            files, _ = client.scan_all_files()
            q.put({"type": "ok", "message": f"{len(files)} file trovati."})

            q.put({"type": "info", "message": "Analisi struttura esistente..."})
            with _structure_lock:
                cached_tree = _st._structure_cache
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

            saved_path = None
            if save_as:
                import re as _re
                safe = _re.sub(r"[^\w\-]", "_", save_as).strip("_") or "custom"
                save_path = Path(__file__).parent.parent.parent / "taxonomies" / f"taxonomy_{safe}.json"
                save_path.parent.mkdir(exist_ok=True)
                save_path.write_text(
                    __import__("json").dumps(taxonomy, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                saved_path = str(save_path.relative_to(Path(__file__).parent.parent.parent))

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
