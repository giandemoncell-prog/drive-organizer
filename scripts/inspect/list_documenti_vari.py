"""Legge tutti i file in 01_📂Documenti_Personali/📋 Documenti_Vari."""
import sys, os, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
top_id = nmap.get("01_📂Documenti_Personali")

r2 = svc.files().list(
    q=f"'{top_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
subs = {f["name"]: f["id"] for f in r2.get("files", [])}
dv_id = subs.get("📋 Documenti_Vari")
if not dv_id:
    print(f"📋 Documenti_Vari non trovata. Subs: {list(subs.keys())}")
    sys.exit(1)

print(f"📋 Documenti_Vari id={dv_id}\n")

def list_all(pid, path=""):
    r = svc.files().list(
        q=f"'{pid}' in parents and trashed=false",
        fields="files(id,name,mimeType,size,modifiedTime)",
        pageSize=200,
    ).execute()
    for f in r.get("files", []):
        full_path = f"{path}/{f['name']}" if path else f["name"]
        if f["mimeType"] == "application/vnd.google-apps.folder":
            list_all(f["id"], full_path)
        else:
            mime_short = f["mimeType"].split("/")[-1].replace("vnd.google-apps.", "")
            size_kb = int(f.get("size", 0)) // 1024 if f.get("size") else 0
            modified = (f.get("modifiedTime", "") or "")[:10]
            print(f"  [{mime_short}] [{modified}] [{size_kb}KB] {full_path}")

list_all(dv_id)
