import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name,ownedByMe)",
    pageSize=200,
    orderBy="name",
).execute()

folders = r.get("files", [])
print(f"Cartelle top-level: {len(folders)}")
for f in folders:
    owned = "own   " if f.get("ownedByMe") else "shared"
    print(f"  [{owned}] {f['name']}")
