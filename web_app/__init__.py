from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import certifi
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

from flask import Flask, jsonify, request

app = Flask(__name__, template_folder=str(Path(__file__).parent.parent / "templates"))

# ── Auth middleware ────────────────────────────────────────────────────────────
_OPEN_PATHS = {"/", "/api/status"}
_OPEN_PREFIXES = ("/static/",)


@app.before_request
def _check_auth():
    import hmac

    from drive_organizer.config import settings
    if not settings.web_auth_token:
        return
    if request.path in _OPEN_PATHS or any(request.path.startswith(p) for p in _OPEN_PREFIXES):
        return
    token = request.headers.get("X-Auth-Token") or request.args.get("token") or ""
    # Constant-time comparison avoids leaking the token via response timing.
    if not hmac.compare_digest(token, settings.web_auth_token):
        return jsonify({"error": "Unauthorized — set X-Auth-Token header or ?token= query param"}), 401


# ── Background TTL cleanup ────────────────────────────────────────────────────
def _ops_cleanup():
    import time

    from web_app.state import _ops, _ops_ts
    while True:
        time.sleep(300)
        cutoff = time.monotonic() - 1800
        stale = [oid for oid, ts in list(_ops_ts.items()) if ts < cutoff]
        for oid in stale:
            _ops.pop(oid, None)
            _ops_ts.pop(oid, None)


threading.Thread(target=_ops_cleanup, daemon=True, name="ops-cleanup").start()

# ── Register blueprints ───────────────────────────────────────────────────────
from web_app.routes.config import bp as config_bp
from web_app.routes.duplicates import bp as duplicates_bp
from web_app.routes.organize import bp as organize_bp
from web_app.routes.rename import bp as rename_bp
from web_app.routes.rollback import bp as rollback_bp
from web_app.routes.status import bp as status_bp
from web_app.routes.taxonomy import bp as taxonomy_bp

app.register_blueprint(status_bp)
app.register_blueprint(organize_bp)
app.register_blueprint(taxonomy_bp)
app.register_blueprint(duplicates_bp)
app.register_blueprint(rollback_bp)
app.register_blueprint(config_bp)
app.register_blueprint(rename_bp)
