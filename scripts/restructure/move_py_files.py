"""Trova tutti i *.py in 01_📂Documenti_Personali e li sposta in 00_📂Sviluppo_e_Software."""
import sys, os, certifi, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service
from googleapiclient.errors import HttpError

svc = get_drive_service()

# Root map
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
top01 = nmap["01_📂Documenti_Personali"]
top04 = nmap["04_📂Progetti_e_Social"]

r4 = svc.files().list(
    q=f"'{top04}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
subs04 = {f["name"]: f["id"] for f in r4.get("files", [])}
sviluppo_id = subs04["00_📂Sviluppo_e_Software"]

# Cerca ricorsivamente tutti i *.py sotto top01
def find_py_files(parent_id):
    results = []
    # Cerca file .py
    r = svc.files().list(
        q=f"'{parent_id}' in parents and name contains '.py' and trashed=false and "
          f"mimeType!='application/vnd.google-apps.folder'",
        fields="files(id,name,parents,mimeType)", pageSize=100,
    ).execute()
    for f in r.get("files", []):
        if f["name"].endswith(".py"):
            results.append((f["id"], f["name"], parent_id))
    # Ricursione nelle sottocartelle
    subs = svc.files().list(
        q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=100,
    ).execute()
    for sub in subs.get("files", []):
        results.extend(find_py_files(sub["id"]))
    return results

print("Ricerca *.py in 01_📂Documenti_Personali…")
py_files = find_py_files(top01)
print(f"Trovati: {len(py_files)} file .py\n")

for fid, fname, parent_id in py_files:
    try:
        svc.files().update(fileId=fid, addParents=sviluppo_id, removeParents=parent_id, fields="id").execute()
        print(f"  ✓ {fname}")
    except HttpError as e:
        print(f"  [ERR] {fname}: {e}")
    time.sleep(0.1)

print(f"\n✅ {len(py_files)} file .py spostati in 00_📂Sviluppo_e_Software")
