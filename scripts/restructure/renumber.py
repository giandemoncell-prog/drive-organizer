import os, sys, time, certifi
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

PLAN = [
    ("02_📂Documenti_Personali", "01_📂Documenti_Personali"),
    ("05_📂Casa_e_Immobili",     "02_📂Casa_e_Immobili"),
    ("06_📂Scuola_e_Didattica",  "03_📂Scuola_e_Didattica"),
    ("07_📂Viaggi_e_Hobby",      "04_📂Progetti_e_Social"),
    ("04_📂Workflow_Backup",     "05_📂Workflow_Backup"),
]

def rename(fid, name):
    svc.files().update(fileId=fid, body={"name": name}, fields="id").execute()

# Rename via temp
for old, new in PLAN:
    fid = nmap.get(old)
    if not fid: print(f"  [skip] {old}"); continue
    rename(fid, f"_T_{new}"); time.sleep(0.2)

nmap = {f["name"]: f["id"] for f in svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200).execute().get("files", [])}

for _, new in PLAN:
    fid = nmap.get(f"_T_{new}")
    if not fid: continue
    rename(fid, new)
    print(f"  ✏  → {new}")
    time.sleep(0.2)

print("\n✅ Rinumerazione completata.")
