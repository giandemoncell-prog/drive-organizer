"""Elimina ricorsivamente tutte le sottocartelle vuote dalle 9 cartelle organizzate."""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

TOP_FOLDERS = [
    "00_📂Workflow_Backup", "01_📂BachataVibes", "02_📂Sviluppo_e_Software",
    "03_📂Automazioni_Social", "04_📂Documenti_Personali", "05_📂Casa_e_Immobili",
    "06_📂Scuola_e_Didattica", "07_📂Viaggi_e_Hobby", "99_📂Archivio",
]

def list_children(parent_id, folders_only=False):
    q = f"'{parent_id}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        kw = dict(q=q, fields="files(id,name,mimeType)", pageSize=200)
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items

def delete_empty_recursive(folder_id, folder_name, depth=0):
    """Ritorna True se la cartella è stata eliminata."""
    children = list_children(folder_id)
    sub_folders = [c for c in children if c["mimeType"] == "application/vnd.google-apps.folder"]
    files = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]

    # Prima prova a eliminare le sottocartelle figlie
    for sub in sub_folders:
        delete_empty_recursive(sub["id"], sub["name"], depth + 1)
        time.sleep(0.05)

    # Ricontrolla dopo la pulizia ricorsiva
    remaining = list_children(folder_id)
    if not remaining:
        svc.files().delete(fileId=folder_id).execute()
        indent = "  " * depth
        print(f"{indent}🗑  {folder_name}")
        return True
    return False

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

total_deleted = 0
for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        continue
    subs = list_children(top_id, folders_only=True)
    if not subs:
        continue
    print(f"\n📂 {top_name} ({len(subs)} sottocartelle):")
    for sub in subs:
        if delete_empty_recursive(sub["id"], sub["name"], depth=1):
            total_deleted += 1
        time.sleep(0.1)

print(f"\n✅ Sottocartelle vuote eliminate: {total_deleted}")
