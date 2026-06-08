"""Thin shim — imports the Flask app from web_app package.

Keep this file so existing callers (`from web import app`, `python web.py`)
continue to work unchanged.
"""
from web_app import app  # noqa: F401  re-export

if __name__ == "__main__":
    import threading
    import webbrowser

    port = 5001
    print(f"\nDrive Organizer Web UI -> http://localhost:{port}\n")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
