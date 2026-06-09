import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

MERGE_MAP = {
    "01_📂Immobili":       "05_Casa_e_Immobili",
    "02_📂Spese e Bollette": "05_Casa_e_Immobili",
    "03_📂Veicoli ":       "04_Documenti_Personali",
    "04_📂Personale ":     "04_Documenti_Personali",
    "05_📂Lavoro":         "04_Documenti_Personali",
    "06_📂Progetti e Hobby": "07_Viaggi_e_Hobby",
    "07_📂Viaggio Canarie": "07_Viaggi_e_Hobby",
    "10_📂Software":       "02_Sviluppo_e_Software",
    "99_📂Archivio":       "99_Archivio",
}
DELETE_EMPTY = ["08_📂Libro_IA", "09_📂SerenaInfissi", "2026-05-09", "Colab Notebooks", "DriveOrganizer_Chromebook"]

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)",
    pageSize=200,
).execute()
name_to_id = {f["name"]: f["id"] for f in r.get("files", [])}

print("=== PIANO MERGE ===")
for old_name, new_name in MERGE_MAP.items():
    fid = name_to_id.get(old_name)
    if not fid:
        print(f"\n[NOT FOUND] {old_name}")
        continue
    res = svc.files().list(
        q=f"'{fid}' in parents and trashed=false",
        fields="files(id,name,mimeType)",
        pageSize=200,
    ).execute()
    items = res.get("files", [])
    print(f"\n  {old_name} → {new_name}")
    for item in items:
        kind = "📁" if item["mimeType"] == "application/vnd.google-apps.folder" else "📄"
        print(f"    {kind} {item['name']}")

print("\n=== DA ELIMINARE (vuote) ===")
for name in DELETE_EMPTY:
    fid = name_to_id.get(name)
    print(f"  {'✓' if fid else '?'} {name}")
