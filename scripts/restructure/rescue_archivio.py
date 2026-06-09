"""
Analizza 99_📂Archivio e sposta tutto il possibile nelle cartelle giuste.
Cascade: qwen3:8b (GPU) → DeepSeek fallback.
"""
import json, os, sys, time, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

import httpx
from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings

svc = get_drive_service()

OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "huihui_ai/qwen3-abliterated:14b-v2"
DS_URL       = "https://api.deepseek.com/v1/chat/completions"
DS_MODEL     = "deepseek-chat"

TARGET_FOLDERS = [
    "01_📂Documenti_Personali",
    "02_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social",
    "05_📂Workflow_Backup",
    "99_📂Archivio",   # rimane qui se davvero archivio
]

# ─── helpers ─────────────────────────────────────────────────────────────────

def root_map():
    r = svc.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}


def list_children(parent_id, folders_only=False):
    q = f"'{parent_id}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    r = svc.files().list(q=q, fields="files(id,name,mimeType)", pageSize=200).execute()
    return r.get("files", [])


def move_item(item_id, from_p, to_p):
    if from_p == to_p:
        return
    svc.files().update(fileId=item_id, addParents=to_p,
                       removeParents=from_p, fields="id").execute()


def find_subfolder(name, parent_id):
    subs = list_children(parent_id, folders_only=True)
    for f in subs:
        if f["name"] == name:
            return f["id"]
    return None


def get_or_create_sub(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        fid = find_subfolder(name, parent_id)
        if not fid:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
        cache[key] = fid
    return cache[key]

# ─── AI ──────────────────────────────────────────────────────────────────────

def _call_ollama(prompt):
    r = httpx.post(OLLAMA_URL,
        headers={"Content-Type": "application/json"},
        json={"model": OLLAMA_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1, "options": {"num_predict": 2048}},
        timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_deepseek(prompt):
    r = httpx.post(DS_URL,
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                 "Content-Type": "application/json"},
        json={"model": DS_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1},
        timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _parse(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "```" in text:
        for part in text.split("```")[1::2]:
            text = part.lstrip("json").strip()
            break
    return json.loads(text)


def classify_items(items_with_samples):
    """
    items_with_samples: list of {name, sample_files: [str]}
    Returns list of {name, target, reason}
    """
    items_text = "\n".join(
        f'- "{it["name"]}" (file esempio: {", ".join(it["sample_files"][:4]) or "nessuno"})'
        for it in items_with_samples
    )
    targets_text = "\n".join(f"- {t}" for t in TARGET_FOLDERS)
    prompt = f"""Sei un assistente per l'organizzazione di Google Drive.

Cartella attuale: 99_📂Archivio (fallback — contiene file non classificati in precedenza)

Cartelle di destinazione disponibili:
{targets_text}

- 01_📂Documenti_Personali: identità, salute, lavoro, veicoli, CV, legale, fiscale
- 02_📂Casa_e_Immobili: bollette, IMU, aste, ristrutturazioni, affitti, immobili
- 03_📂Scuola_e_Didattica: libri, materiali didattici, KDP, DSA, pratiche docente
- 04_📂Progetti_e_Social: bachata, sviluppo sw, social, automazioni, viaggi, hobby
- 05_📂Workflow_Backup: n8n, backup, workflow automazioni

Per ogni sottocartella/file sotto elencato, indica la cartella di destinazione più adatta.
Usa "99_📂Archivio" SOLO se il contenuto è davvero obsoleto/archivio senza categoria specifica.

Elementi da classificare:
{items_text}

Rispondi SOLO con JSON array:
[{{"name":"nome_esatto","target":"cartella_destinazione","reason":"breve motivo"}}, ...]"""

    for attempt in range(2):
        try:
            return _parse(_call_ollama(prompt))
        except Exception as e:
            time.sleep(1)
    # fallback DeepSeek
    for attempt in range(3):
        try:
            return _parse(_call_deepseek(prompt))
        except Exception as e:
            time.sleep(3)
    raise RuntimeError("Tutti i provider AI falliti")

# ─── main ─────────────────────────────────────────────────────────────────────

nmap = root_map()
ARCHIVIO = nmap.get("99_📂Archivio")
if not ARCHIVIO:
    print("ERRORE: 99_📂Archivio non trovata"); sys.exit(1)

# Raccoglie tutti gli elementi diretti dell'archivio
all_items = list_children(ARCHIVIO)
folders = [i for i in all_items if i["mimeType"] == "application/vnd.google-apps.folder"]
flat_files = [i for i in all_items if i["mimeType"] != "application/vnd.google-apps.folder"]

print(f"99_📂Archivio: {len(folders)} sottocartelle, {len(flat_files)} file flat\n")

# Costruisce snapshot con campione file per cartella
items_info = []
for f in folders:
    kids = list_children(f["id"])
    sample = [k["name"] for k in kids[:5]]
    items_info.append({"name": f["name"], "id": f["id"],
                       "type": "folder", "sample_files": sample,
                       "count": len(kids)})
    print(f"  📁 {f['name']} ({len(kids)} figli) — {', '.join(sample[:3])}")

for f in flat_files:
    items_info.append({"name": f["name"], "id": f["id"],
                       "type": "file", "sample_files": [], "count": 0})

print(f"\n→ Classifico {len(items_info)} elementi via AI…\n")

# Classifica in batch da 15
BATCH = 15
all_assignments = {}
for i in range(0, len(items_info), BATCH):
    batch = items_info[i:i+BATCH]
    print(f"  batch {i//BATCH+1}/{(len(items_info)-1)//BATCH+1}…", end=" ", flush=True)
    try:
        results = classify_items(batch)
        name_map = {r["name"]: r for r in results}
        for item in batch:
            r = name_map.get(item["name"])
            if r:
                all_assignments[item["name"]] = (item["id"], r["target"], r.get("reason",""))
        print(f"ok ({len(name_map)}/{len(batch)})")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

# Mostra piano
print("\n=== PIANO SPOSTAMENTI ===")
stay = []
move_plan = []
for name, (fid, target, reason) in all_assignments.items():
    if target == "99_📂Archivio":
        stay.append(name)
    else:
        move_plan.append((name, fid, target, reason))
        print(f"  {name} → {target}  [{reason}]")

print(f"\nRimangono in archivio: {len(stay)}")
for n in stay:
    print(f"  - {n}")

# Esegue spostamenti
print(f"\n=== ESECUZIONE ({len(move_plan)} spostamenti) ===")
moved = 0
errors = 0
for name, fid, target, reason in move_plan:
    target_id = nmap.get(target)
    if not target_id:
        print(f"  [ERR] target '{target}' non trovato per '{name}'")
        errors += 1
        continue
    try:
        move_item(fid, ARCHIVIO, target_id)
        print(f"  ✓ {name} → {target}")
        moved += 1
    except HttpError as e:
        print(f"  [ERR] {name}: {e}")
        errors += 1
    time.sleep(0.15)

print(f"\n✅ Completato: {moved} spostati, {errors} errori, {len(stay)} rimasti in archivio.")
