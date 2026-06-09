"""Thin shim — imports the Flask app from web_app package.

Keep this file so existing callers (`from web import app`, `python web.py`)
continue to work unchanged.
"""
from web_app import app

if __name__ == "__main__":
    import os
    import threading
    import webbrowser

    port = int(os.environ.get("WEB_PORT", "5001"))
    # Default to loopback only: the UI controls the user's Google Drive, so it must
    # not be reachable from the local network. Set WEB_HOST=0.0.0.0 to opt in to
    # LAN exposure (only sensible together with WEB_AUTH_TOKEN).
    host = os.environ.get("WEB_HOST", "127.0.0.1")
    print(f"\nDrive Organizer Web UI -> http://localhost:{port}\n")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host=host, port=port, debug=False, threaded=True)
