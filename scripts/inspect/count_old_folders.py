import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

OLD_FOLDERS = [
    "01_📂Immobili",
    "02_📂Spese e Bollette",
    "03_📂Veicoli ",
    "04_📂Personale ",
    "05_📂Lavoro",
    "06_📂Progetti e Hobby",
    "07_📂Viaggio Canarie",
    "08_📂Libro_IA",
    "09_📂SerenaInfissi",
    "10_📂Software",
    "99_📂Archivio",
    "2026-05-09",
    "Colab Notebooks",
    "DriveOrganizer_Chromebook",
]

# Get folder IDs
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)",
    pageSize=200,
).execute()
name_to_id = {f["name"]: f["id"] for f in r.get("files", [])}

for name in OLD_FOLDERS:
    fid = name_to_id.get(name)
    if not fid:
        print(f"  [NOT FOUND] {name}")
        continue
    # Count files (not recursive, just direct children)
    res = svc.files().list(
        q=f"'{fid}' in parents and trashed=false",
        fields="files(id,name,mimeType)",
        pageSize=200,
    ).execute()
    items = res.get("files", [])
    folders = [f for f in items if f["mimeType"] == "application/vnd.google-apps.folder"]
    files = [f for f in items if f["mimeType"] != "application/vnd.google-apps.folder"]
    print(f"  {name}: {len(files)} file, {len(folders)} sottocartelle")
    for f in files[:3]:
        print(f"    - {f['name']}")
    if len(files) > 3:
        print(f"    … e altri {len(files)-3}")
