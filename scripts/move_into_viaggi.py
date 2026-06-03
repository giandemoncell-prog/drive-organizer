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

progetti_id = nmap.get("04_📂Progetti_e_Social") or nmap.get("07_📂Viaggi_e_Hobby")
root_id     = "root"

for name in ["03_📂Automazioni_Social"]:
    fid = nmap.get(name)
    if not fid:
        print(f"  [skip] {name}"); continue
    svc.files().update(fileId=fid, addParents=progetti_id,
                       removeParents=root_id, fields="id").execute()
    print(f"  ✓ {name} → 04_📂Progetti_e_Social")
print("✅ Fatto.")
