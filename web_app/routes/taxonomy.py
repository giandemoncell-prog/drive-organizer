from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("taxonomy", __name__)

_TAX_DIR = Path(__file__).parent.parent.parent / "taxonomies"


@bp.route("/api/taxonomy/presets")
def api_taxonomy_presets():
    presets = []
    if _TAX_DIR.exists():
        for f in sorted(_TAX_DIR.glob("taxonomy_*.json")):
            name = f.stem[len("taxonomy_"):]
            presets.append({"name": name, "file": f"taxonomies/{f.name}"})
    return jsonify(presets)


@bp.route("/api/taxonomy/save", methods=["POST"])
def api_taxonomy_save():
    data = request.json or {}
    name = data.get("name", "custom").strip()
    taxonomy = data.get("taxonomy", {})
    safe = re.sub(r"[^\w\-]", "_", name).strip("_") or "custom"
    save_path = _TAX_DIR / f"taxonomy_{safe}.json"
    save_path.parent.mkdir(exist_ok=True)
    save_path.write_text(
        __import__("json").dumps(taxonomy, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return jsonify({"ok": True, "path": f"taxonomies/taxonomy_{safe}.json"})
