"""
Script storico (one-off): scambia i prefissi numerici di
00_📂Documenti_Personali ↔ 02_📂Sviluppo_e_Software.
Eseguito una sola volta durante la rinumerazione top-level.
"""
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

def rename(fid, name):
    svc.files().update(fileId=fid, body={"name": name}, fields="id").execute()
    print(f"  ✏  → {name}")

doc_id  = nmap.get("00_📂Documenti_Personali")
svil_id = nmap.get("02_📂Sviluppo_e_Software")

# Swap 00 ↔ 02 via nome temporaneo
rename(doc_id,  "_TEMP_Documenti")
time.sleep(0.3)
rename(svil_id, "00_📂Sviluppo_e_Software")
time.sleep(0.3)
rename(doc_id,  "02_📂Documenti_Personali")
print("\n✅ Fatto.")
