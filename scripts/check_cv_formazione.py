"""Legge tutti i file in 01_📂Documenti_Personali/📄 CV_Formazione e ne stampa nome + tipo."""
import sys, os, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

# Trova 01_📂Documenti_Personali
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
top_id = nmap.get("01_📂Documenti_Personali")
if not top_id:
    print("01_📂Documenti_Personali non trovata")
    sys.exit(1)

# Trova la sottocartella CV_Formazione
r2 = svc.files().list(
    q=f"'{top_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
subs = {f["name"]: f["id"] for f in r2.get("files", [])}
cv_id = subs.get("📄 CV_Formazione")
if not cv_id:
    print(f"📄 CV_Formazione non trovata. Sottocartelle: {list(subs.keys())}")
    sys.exit(1)

print(f"📄 CV_Formazione id={cv_id}\n")

# Lista tutti i file (ricorsivo)
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
            mime_short = f["mimeType"].split(".")[-1].replace("vnd.google-apps.", "")
            print(f"  [{mime_short}] {full_path}")

list_all(cv_id)
