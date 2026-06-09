import os, sys, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
ARCH = nmap.get("99_📂Archivio")

items, token = [], None
while True:
    kw = dict(q=f"'{ARCH}' in parents and trashed=false",
              fields="files(id,name,mimeType)", pageSize=200)
    if token: kw["pageToken"] = token
    r = svc.files().list(**kw).execute()
    items += r.get("files", [])
    token = r.get("nextPageToken")
    if not token: break

files = [i for i in items if i["mimeType"] != "application/vnd.google-apps.folder"]
subs  = [i for i in items if i["mimeType"] == "application/vnd.google-apps.folder"]
print(f"99_📂Archivio: {len(files)} file, {len(subs)} sottocartelle\n")
print("=== FILE ===")
for f in sorted(files, key=lambda x: x["name"]):
    print(f"  {f['name']}")
