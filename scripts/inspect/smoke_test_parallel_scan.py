"""Quick smoke test for parallel scan on real Drive account."""
import time
import sys
import os

# SSL fix before any HTTPS
try:
    import certifi
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.drive.client import DriveClient

print("Authenticating...", flush=True)
svc = get_drive_service()
client = DriveClient(svc)

print("Starting parallel scan...", flush=True)
t0 = time.perf_counter()
files, folder_map = client.scan_all_files()
elapsed = time.perf_counter() - t0

print(f"\n--- Parallel scan results ---")
print(f"Files:   {len(files)}")
print(f"Folders: {len(folder_map)}")
print(f"Time:    {elapsed:.2f}s")
print(f"Status:  OK — no SSL errors")
