"""Legge tutti i file in Bollette_Utenze e Lavori_Ristrutturazione."""
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
top02 = nmap["02_📂Casa_e_Immobili"]

r2 = svc.files().list(
    q=f"'{top02}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
subs02 = {f["name"]: f["id"] for f in r2.get("files", [])}

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
            size_kb = int(f.get("size", 0)) // 1024 if f.get("size") else 0
            modified = (f.get("modifiedTime", "") or "")[:10]
            print(f"  [{modified}] [{size_kb}KB] {full_path}")

for folder_name in ["💡 Bollette_Utenze", "🔨 Lavori_Ristrutturazione"]:
    fid = subs02.get(folder_name)
    if not fid:
        print(f"\n{folder_name}: NON TROVATA (subs: {list(subs02.keys())})")
        continue
    print(f"\n{'='*60}")
    print(f"{folder_name} (id={fid})")
    print("="*60)
    list_all(fid)
