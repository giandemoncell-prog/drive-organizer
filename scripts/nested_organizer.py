"""
Organizza in profondità: per ogni cartella top-level,
classifica i file flat nelle sottocartelle (esistenti o nuove) via Gemini.
"""
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from googleapiclient.errors import HttpError
import httpx
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings

svc = get_drive_service()
_DS_URL = "https://api.deepseek.com/v1/chat/completions"
_DS_MODEL = "deepseek-chat"

TOP_FOLDERS = [
    "00_📂Workflow_Backup",
    "01_📂BachataVibes",
    "02_📂Sviluppo_e_Software",
    "03_📂Automazioni_Social",
    "04_📂Documenti_Personali",
    "05_📂Casa_e_Immobili",
    "06_📂Scuola_e_Didattica",
    "07_📂Viaggi_e_Hobby",
    "99_📂Archivio",
]

# ─── helpers ─────────────────────────────────────────────────────────────────

def root_folders():
    r = svc.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}


def list_children(folder_id):
    items, token = [], None
    while True:
        kw = dict(q=f"'{folder_id}' in parents and trashed=false",
                  fields="files(id,name,mimeType)", pageSize=200)
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items


def get_or_create_subfolder(name, parent_id, cache):
    key = (name, parent_id)
    if key in cache:
        return cache[key]
    # check if exists
    r = svc.files().list(
        q=f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)", pageSize=2,
    ).execute()
    existing = r.get("files", [])
    if existing:
        fid = existing[0]["id"]
    else:
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        fid = svc.files().create(body=meta, fields="id").execute()["id"]
        print(f"      📁+ {name}")
    cache[key] = fid
    return fid


def move_file(file_id, from_parent, to_parent):
    if from_parent == to_parent:
        return
    svc.files().update(
        fileId=file_id, addParents=to_parent, removeParents=from_parent, fields="id",
    ).execute()


def classify_batch(folder_name, flat_files, subfolders):
    """Ask Gemini to assign each flat file to a subfolder (existing or new)."""
    file_list = "\n".join(f"- {f['name']}" for f in flat_files)
    sub_list = "\n".join(f"- {s}" for s in subfolders) if subfolders else "(nessuna ancora)"
    prompt = f"""Sei un assistente di organizzazione file.
Cartella corrente: "{folder_name}"
Sottocartelle esistenti:
{sub_list}

File da classificare (senza sottocartella):
{file_list}

Per ogni file suggerisci la sottocartella più adatta.
Usa sottocartelle esistenti quando possibile; proponi nomi nuovi brevi (max 30 caratteri) solo se necessario.
Rispondi SOLO con JSON array: [{{"file":"nome","subfolder":"nome_cartella"}}, ...]
Niente testo extra fuori dal JSON."""
    for attempt in range(3):
        try:
            r = httpx.post(
                _DS_URL,
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                         "Content-Type": "application/json"},
                json={"model": _DS_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.1},
                timeout=60,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(3)


# ─── main ────────────────────────────────────────────────────────────────────

nmap = root_folders()
total_moved = 0
folder_cache = {}

for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        print(f"\n[SKIP] {top_name} — non trovata")
        continue

    children = list_children(top_id)
    flat_files = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]
    subfolders = [c for c in children if c["mimeType"] == "application/vnd.google-apps.folder"]
    subfolder_names = [s["name"] for s in subfolders]

    if not flat_files:
        print(f"\n✓ {top_name} — nessun file flat")
        continue

    print(f"\n{'='*60}")
    print(f"📂 {top_name}: {len(flat_files)} file flat, {len(subfolders)} sottocartelle")
    print(f"   Sottocartelle esistenti: {', '.join(subfolder_names) or 'nessuna'}")

    # Classifica in batch da 30
    BATCH = 30
    assignments = []
    for i in range(0, len(flat_files), BATCH):
        batch = flat_files[i:i+BATCH]
        print(f"   → Classifico batch {i//BATCH + 1}/{(len(flat_files)-1)//BATCH + 1} ({len(batch)} file)…")
        try:
            result = classify_batch(top_name, batch, subfolder_names)
            assignments.extend([(b, r["subfolder"]) for b, r in zip(batch, result) if "subfolder" in r])
        except Exception as e:
            print(f"   [ERR Gemini] {e} — batch saltato")
        time.sleep(1)

    # Esegui spostamenti
    moved = 0
    for file_item, subfolder_name in assignments:
        sub_id = get_or_create_subfolder(subfolder_name, top_id, folder_cache)
        try:
            move_file(file_item["id"], top_id, sub_id)
            moved += 1
            total_moved += 1
            # aggiorna nomi sottocartelle per batch successivi
            if subfolder_name not in subfolder_names:
                subfolder_names.append(subfolder_name)
        except HttpError as e:
            print(f"   [ERR move] {file_item['name']}: {e}")
        time.sleep(0.12)

    print(f"   ✅ {moved}/{len(flat_files)} file spostati in sottocartelle")

print(f"\n{'='*60}")
print(f"✅ Nesting completato: {total_moved} file organizzati in sottocartelle.")
