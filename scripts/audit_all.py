"""
Audit ciclico di tutte le cartelle top-level:
- Legge ricorsivamente tutti i file con il loro percorso attuale
- Chiede all'AI se ogni file è nella sottocartella giusta
- Sposta i file mal collocati nella destinazione corretta (dentro la stessa cartella top)
Cascade: huihui_ai/qwen3-abliterated:14b-v2 (GPU) -> DeepSeek fallback.
"""
import json, os, sys, time, re, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

import httpx
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings

svc = get_drive_service()
OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "huihui_ai/qwen3-abliterated:14b-v2"
BATCH        = 15

TOP_FOLDERS = [
    "01_📂Documenti_Personali",
    "02_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social",
    "05_📂Workflow_Backup",
]

# ─── helpers ─────────────────────────────────────────────────────────────────

def list_children(pid, folders_only=False):
    q = f"'{pid}' in parents and trashed=false"
    if folders_only: q += " and mimeType='application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        kw = dict(q=q, fields="files(id,name,mimeType,parents)", pageSize=200)
        if token: kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token: break
    return items

def get_all_files_recursive(folder_id, path=""):
    """Ritorna lista di (file_dict, parent_id, path_str)."""
    result = []
    children = list_children(folder_id)
    for c in children:
        if c["mimeType"] == "application/vnd.google-apps.folder":
            sub_path = f"{path}/{c['name']}" if path else c["name"]
            result.extend(get_all_files_recursive(c["id"], sub_path))
        else:
            result.append((c, folder_id, path))
    return result

def get_subfolders_map(folder_id):
    """Mappa nome->id di tutte le sottocartelle dirette."""
    return {f["name"]: f["id"] for f in list_children(folder_id, folders_only=True)}

def get_or_create_subfolder(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        existing = [f for f in list_children(parent_id, folders_only=True) if f["name"] == name]
        if existing:
            cache[key] = existing[0]["id"]
        else:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
            print(f"      📁+ {name}")
            cache[key] = fid
    return cache[key]

def move_file(fid, from_p, to_p):
    if from_p == to_p: return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def call_ai(prompt):
    for _ in range(2):
        try:
            r = httpx.post(OLLAMA_URL, headers={"Content-Type": "application/json"},
                json={"model": OLLAMA_MODEL, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}],
                      "options": {"num_predict": 3000}}, timeout=180)
            r.raise_for_status()
            text = re.sub(r"<think>.*?</think>", "",
                r.json()["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except Exception as e:
            print(f" [ollama:{e}]", end=""); time.sleep(2)
    for _ in range(3):
        try:
            r = httpx.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                         "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]}, timeout=90)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if "```" in text: text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except Exception: time.sleep(3)
    raise RuntimeError("AI fallita")

# ─── main ─────────────────────────────────────────────────────────────────────

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

grand_total_moved = 0

for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        print(f"\n[SKIP] {top_name} — non trovata")
        continue

    print(f"\n{'='*60}")
    print(f"📂 {top_name}")

    # Ottieni sottocartelle dirette della top-level
    direct_subs = get_subfolders_map(top_id)
    if not direct_subs:
        print(f"  Nessuna sottocartella — skip")
        continue

    subs_text = "\n".join(f"- {s}" for s in direct_subs.keys())
    print(f"  Sottocartelle: {', '.join(direct_subs.keys())}")

    # Scansione ricorsiva
    all_files = get_all_files_recursive(top_id)
    print(f"  File totali: {len(all_files)}")

    if not all_files:
        continue

    folder_moved = 0
    n_batches = (len(all_files) - 1) // BATCH + 1

    for i in range(0, len(all_files), BATCH):
        batch = all_files[i:i+BATCH]
        n = i // BATCH + 1

        file_list = "\n".join(
            f'- "{f["name"]}" (attuale: {path or "[root]"})'
            for f, _, path in batch
        )

        prompt = f"""Sei un assistente per organizzare Google Drive.
Cartella principale: "{top_name}"

Sottocartelle disponibili (usa SOLO queste):
{subs_text}

Per ogni file indica la sottocartella corretta.
Se il file è già nella cartella giusta, ripeti il nome della sottocartella corrente.

Regola: non spostare file se sono già nel posto giusto.

File con posizione attuale:
{file_list}

Rispondi SOLO con JSON:
[{{"file":"nome_esatto","subfolder":"nome_sottocartella_diretta"}}, ...]"""

        print(f"  batch {n}/{n_batches} ({len(batch)} file)…", end=" ", flush=True)
        try:
            results = call_ai(prompt)
            name_map = {r["file"]: r.get("subfolder") for r in results}
            moved = 0
            for f_dict, parent_id, current_path in batch:
                dest_sub = name_map.get(f_dict["name"])
                if not dest_sub or dest_sub not in direct_subs:
                    continue
                dest_id = direct_subs[dest_sub]
                # Controlla se è già nella cartella corretta
                current_sub = current_path.split("/")[0] if "/" in current_path else current_path
                if current_sub == dest_sub:
                    continue
                try:
                    move_file(f_dict["id"], parent_id, dest_id)
                    print(f"\n    → {f_dict['name']} [{current_path}] → {dest_sub}", end="")
                    moved += 1
                    folder_moved += 1
                    grand_total_moved += 1
                except Exception as e:
                    print(f"\n    [ERR] {f_dict['name']}: {e}", end="")
                time.sleep(0.08)
            print(f"  ok ({moved} spostati)")
        except Exception as e:
            print(f"ERR: {e}")
        time.sleep(0.5)

    print(f"  ✅ {top_name}: {folder_moved} file riposizionati")

print(f"\n{'='*60}")
print(f"✅ Audit completato: {grand_total_moved} file riposizionati in totale.")
