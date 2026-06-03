"""
Riporta 99_📂Archivio alla posizione iniziale:
- Sposta i file da tutte le sottocartelle NUOVE al piano superiore (flat)
- Conserva le 6 sottocartelle originali (Estero, Romanzo distopico,
  Idee e proggetti, Software, HorizonWorlds, Meditazione)
- Elimina le sottocartelle vuote create dal nested organizer
"""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

# Sottocartelle originali da CONSERVARE
ORIGINAL_SUBS = {
    "Estero", "Romanzo distopico", "Idee e proggetti",
    "Software", "HorizonWorlds", "Meditazione",
}

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


def move_item(item_id, from_p, to_p):
    if from_p == to_p:
        return
    svc.files().update(
        fileId=item_id, addParents=to_p, removeParents=from_p, fields="id"
    ).execute()


# Trova l'archivio
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
ARCHIVIO = nmap.get("99_📂Archivio")
if not ARCHIVIO:
    print("ERRORE: 99_📂Archivio non trovata"); sys.exit(1)

subs = [f for f in list_children(ARCHIVIO, folders_only=True)]
new_subs = [f for f in subs if f["name"] not in ORIGINAL_SUBS]
orig_subs = [f for f in subs if f["name"] in ORIGINAL_SUBS]

print(f"Sottocartelle originali (conservate): {[f['name'] for f in orig_subs]}")
print(f"Sottocartelle da appiattire: {len(new_subs)}\n")

total_moved = 0
total_deleted = 0

for sub in new_subs:
    kids = list_children(sub["id"])
    print(f"  📁 {sub['name']} ({len(kids)} elementi) → flat")
    for kid in kids:
        try:
            move_item(kid["id"], sub["id"], ARCHIVIO)
            total_moved += 1
        except HttpError as e:
            print(f"    [ERR] {kid['name']}: {e}")
        time.sleep(0.08)
    # Elimina se ora vuota
    remaining = list_children(sub["id"])
    if not remaining:
        try:
            svc.files().delete(fileId=sub["id"]).execute()
            print(f"    🗑  {sub['name']} eliminata")
            total_deleted += 1
        except HttpError as e:
            print(f"    [ERR delete] {sub['name']}: {e}")
    else:
        print(f"    ⚠  {sub['name']} ha ancora {len(remaining)} figli — non eliminata")

print(f"\n✅ File rimessi flat: {total_moved} | Cartelle eliminate: {total_deleted}")
print(f"Sottocartelle originali intatte: {[f['name'] for f in orig_subs]}")
