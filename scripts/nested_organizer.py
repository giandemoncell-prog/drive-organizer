"""
Organizza in profondità: per ogni cartella top-level,
classifica i file flat in sottocartelle (esistenti o nuove).
Provider cascade: Ollama qwen3:8b (GPU locale) → DeepSeek (cloud fallback).
"""
import json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

import httpx
from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings

svc = get_drive_service()

# ─── AI providers ─────────────────────────────────────────────────────────────

OLLAMA_URL  = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen3:8b"
DS_URL      = "https://api.deepseek.com/v1/chat/completions"
DS_MODEL    = "deepseek-chat"

TOP_FOLDERS = [
    # 00/01/03 già privi di file flat — skip
    # precedente run ha completato 01_Documenti
    "02_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social",
    "99_📂Archivio",
]

# ─── helpers Drive ────────────────────────────────────────────────────────────

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
    # List all subfolders and match in Python to avoid query escaping issues
    r = svc.files().list(
        q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    for f in r.get("files", []):
        if f["name"] == name:
            cache[key] = f["id"]
            return f["id"]
    # Not found — create
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]}
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

# ─── AI classification ────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    r = httpx.post(
        OLLAMA_URL,
        headers={"Content-Type": "application/json"},
        json={"model": OLLAMA_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1,
              "options": {"num_predict": 2048}},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_deepseek(prompt: str) -> str:
    r = httpx.post(
        DS_URL,
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                 "Content-Type": "application/json"},
        json={"model": DS_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _parse_json(text: str) -> list:
    if "```" in text:
        parts = text.split("```")
        for i, p in enumerate(parts):
            if i % 2 == 1:
                text = p.lstrip("json").strip()
                break
    # strip <think>...</think> tags (deepseek-r1 style)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return json.loads(text)


def classify_batch(folder_name: str, flat_files: list, subfolders: list) -> list:
    """
    Classifica i file flat in sottocartelle.
    Restituisce lista di dict: {file: nome, subfolder: nome_cartella}
    """
    file_list  = "\n".join(f"- {f['name']}" for f in flat_files)
    sub_list   = "\n".join(f"- {s}" for s in subfolders) if subfolders else "(nessuna)"
    prompt = f"""Sei un assistente di organizzazione file per Google Drive.

Cartella corrente: "{folder_name}"

Sottocartelle esistenti (preferiscile):
{sub_list}

File da classificare (senza sottocartella):
{file_list}

Regole:
1. Usa sottocartelle esistenti quando il file ci appartiene chiaramente.
2. Crea nuovi nomi BREVI (max 25 caratteri) solo se nessuna esistente è adatta.
3. Raggruppa per CATEGORIA LOGICA, non per tipo file.
4. Ogni file DEVE avere una sottocartella assegnata.
5. Rispondi SOLO con JSON array, zero testo extra:
[{{"file":"nome_esatto","subfolder":"nome_cartella"}}, ...]"""

    last_err = None
    # 1. Try Ollama (GPU locale)
    for attempt in range(2):
        try:
            text = _call_ollama(prompt)
            return _parse_json(text)
        except Exception as e:
            last_err = e
            time.sleep(1)
    print(f"      [Ollama fail: {last_err}] → DeepSeek fallback")

    # 2. Fallback DeepSeek
    for attempt in range(3):
        try:
            text = _call_deepseek(prompt)
            return _parse_json(text)
        except Exception as e:
            last_err = e
            time.sleep(3)
    raise RuntimeError(f"Tutti i provider falliti: {last_err}")

# ─── main ─────────────────────────────────────────────────────────────────────

nmap = root_folders()
total_moved = 0
folder_cache = {}

for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        print(f"\n[SKIP] {top_name} — non trovata")
        continue

    children = list_children(top_id)
    flat_files = [c for c in children
                  if c["mimeType"] != "application/vnd.google-apps.folder"]
    subfolders = [c for c in children
                  if c["mimeType"] == "application/vnd.google-apps.folder"]
    subfolder_names = [s["name"] for s in subfolders]

    if not flat_files:
        print(f"\n✓ {top_name} — nessun file flat")
        continue

    print(f"\n{'='*60}")
    print(f"📂 {top_name}: {len(flat_files)} file flat | "
          f"sottocartelle: {', '.join(subfolder_names) or 'nessuna'}")

    BATCH = 10  # smaller = più affidabile con LLM locale
    assignments = []
    for i in range(0, len(flat_files), BATCH):
        batch = flat_files[i:i+BATCH]
        n_batch = i // BATCH + 1
        tot_batch = (len(flat_files) - 1) // BATCH + 1
        print(f"   → batch {n_batch}/{tot_batch} ({len(batch)} file)…", end=" ", flush=True)
        try:
            result = classify_batch(top_name, batch, subfolder_names)
            # align by file name (AI might reorder)
            name_map = {r["file"]: r["subfolder"] for r in result if "subfolder" in r}
            for item in batch:
                sub = name_map.get(item["name"])
                if sub:
                    assignments.append((item, sub))
            print(f"ok ({len(name_map)}/{len(batch)} classificati)")
        except Exception as e:
            print(f"ERR: {e}")
        time.sleep(0.5)

    moved = 0
    for file_item, subfolder_name in assignments:
        sub_id = get_or_create_subfolder(subfolder_name.strip(), top_id, folder_cache)
        try:
            move_file(file_item["id"], top_id, sub_id)
            moved += 1
            total_moved += 1
            if subfolder_name not in subfolder_names:
                subfolder_names.append(subfolder_name)
        except HttpError as e:
            print(f"   [ERR move] {file_item['name']}: {e}")
        time.sleep(0.10)

    print(f"   ✅ {moved}/{len(flat_files)} file → sottocartelle")

print(f"\n{'='*60}")
print(f"✅ Nesting completato: {total_moved} file organizzati in sottocartelle.")
