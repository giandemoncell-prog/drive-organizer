import os, sys, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()
from drive_organizer.auth.google_auth import get_drive_service
svc = get_drive_service()
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200).execute()
folders = sorted(r.get("files", []), key=lambda x: x["name"])
print(f"Cartelle top-level: {len(folders)}\n")
for f in folders:
    kids = svc.files().list(
        q=f"'{f['id']}' in parents and trashed=false",
        fields="files(id,mimeType)", pageSize=200).execute().get("files", [])
    files = sum(1 for k in kids if k["mimeType"] != "application/vnd.google-apps.folder")
    subs  = sum(1 for k in kids if k["mimeType"] == "application/vnd.google-apps.folder")
    bar = "█" * min(files // 5, 30)
    print(f"  {f['name']:<35} {files:>4} file  {subs:>2} sotto  {bar}")
