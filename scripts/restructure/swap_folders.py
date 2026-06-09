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

def rename(fid, new_name):
    svc.files().update(fileId=fid, body={"name": new_name}, fields="id,name").execute()
    print(f"  ✏  → {new_name}")

# Swap 00 ↔ 04 tramite nome temporaneo
wf_id  = nmap["00_📂Workflow_Backup"]
doc_id = nmap["04_📂Documenti_Personali"]

rename(wf_id,  "_TEMP_Workflow_Backup")
time.sleep(0.3)
rename(doc_id, "00_📂Documenti_Personali")
time.sleep(0.3)
rename(wf_id,  "04_📂Workflow_Backup")
print("\n✅ Swap completato.")
