"""
FULL DRIVE ORGANIZE — pipeline completa:
1. Rinumerazione top-level (01→05 + 99)
2. Scan di ogni cartella per file flat
3. Nesting con huihui_ai/qwen3-abliterated:14b-v2 (GPU) / DeepSeek fallback
"""
import json, os, sys, time, re, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

import httpx
from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings

svc = get_drive_service()
OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "huihui_ai/qwen3-abliterated:14b-v2"
MIN_FLAT     = 4   # non annidare cartelle con meno di N file flat

# ─── helpers ─────────────────────────────────────────────────────────────────

def root_map():
    r = svc.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}

def list_children(pid, folders_only=False):
    q = f"'{pid}' in parents and trashed=false"
    if folders_only: q += " and mimeType='application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        kw = dict(q=q, fields="files(id,name,mimeType)", pageSize=200)
        if token: kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token: break
    return items

def rename(fid, name):
    svc.files().update(fileId=fid, body={"name": name}, fields="id").execute()

def move(fid, from_p, to_p):
    if from_p == to_p: return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def get_or_create_sub(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        existing = [f for f in list_children(parent_id, folders_only=True) if f["name"] == name]
        cache[key] = existing[0]["id"] if existing else svc.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                  "parents": [parent_id]}, fields="id").execute()["id"]
    return cache[key]

def call_ai(prompt):
    for _ in range(2):
        try:
            r = httpx.post(OLLAMA_URL, headers={"Content-Type": "application/json"},
                json={"model": OLLAMA_MODEL, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}],
                      "options": {"num_predict": 2048}}, timeout=180)
            r.raise_for_status()
            text = re.sub(r"<think>.*?</think>", "",
                          r.json()["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except Exception: time.sleep(1)
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

def nest_folder(folder_id, folder_name, max_subs=7):
    """Crea sottocartelle per i file flat in folder_id."""
    children = list_children(folder_id)
    flat = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]
    subs = {c["name"]: c["id"] for c in children if c["mimeType"] == "application/vnd.google-apps.folder"}

    if len(flat) < MIN_FLAT:
        print(f"    → {len(flat)} file flat, skip nesting")
        return 0

    print(f"    → {len(flat)} file flat | {len(subs)} sotto esistenti")

    # Chiedi all'AI le categorie ideali
    file_list = "\n".join(f"- {f['name']}" for f in flat)
    subs_text = "\n".join(f"- {s}" for s in subs.keys()) if subs else "(nessuna)"
    prompt = f"""Cartella Google Drive: "{folder_name}"
Sottocartelle esistenti:
{subs_text}

File da organizzare:
{file_list}

Crea MAX {max_subs} sottocartelle semantiche e assegna ogni file.
Usa sottocartelle esistenti quando adatte; proponi nuovi nomi brevi (max 25 car) solo se necessario.
Rispondi SOLO con JSON:
[{{"file":"nome_esatto","subfolder":"nome_cartella"}}, ...]"""

    BATCH = 15
    total = 0
    for i in range(0, len(flat), BATCH):
        batch = flat[i:i+BATCH]
        batch_prompt = prompt.replace(file_list,
            "\n".join(f"- {f['name']}" for f in batch))
        try:
            results = call_ai(batch_prompt)
            name_map = {r["file"]: r["subfolder"] for r in results if "subfolder" in r}
            for f in batch:
                sub_name = name_map.get(f["name"])
                if sub_name:
                    sub_id = get_or_create_sub(sub_name, folder_id)
                    move(f["id"], folder_id, sub_id)
                    if sub_name not in subs:
                        subs[sub_name] = sub_id
                    total += 1
                time.sleep(0.08)
        except Exception as e:
            print(f"      [ERR batch {i//BATCH+1}]: {e}")
        time.sleep(0.3)
    return total

# ═══════════════════════════════════════════════════════════════════
# STEP 1 — Rinumerazione top-level
# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1 — Rinumerazione cartelle top-level")
print("=" * 60)

nmap = root_map()

# Mappa desiderata: nuovo_nome → vecchio_nome_attuale
RENUMBER = {
    "01_📂Documenti_Personali": "02_📂Documenti_Personali",
    "02_📂Casa_e_Immobili":     "05_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica":  "06_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social":   "07_📂Viaggi_e_Hobby",
    "05_📂Workflow_Backup":     "04_📂Workflow_Backup",
    # 99_📂Archivio resta invariato
}

# Rinomina via temp per evitare conflitti
for new_name, old_name in RENUMBER.items():
    fid = nmap.get(old_name)
    if not fid:
        print(f"  [skip] {old_name} non trovata")
        continue
    rename(fid, f"_TEMP_{new_name}")
    time.sleep(0.15)

nmap = root_map()  # refresh
for new_name in RENUMBER:
    fid = nmap.get(f"_TEMP_{new_name}")
    if not fid: continue
    rename(fid, new_name)
    print(f"  ✏  {RENUMBER[new_name]} → {new_name}")
    time.sleep(0.15)

# ═══════════════════════════════════════════════════════════════════
# STEP 2 — Scan e nesting di tutte le cartelle
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2 — Nesting file flat")
print("=" * 60)

nmap = root_map()
grand_total = 0

# Cartelle top-level da processare
TOP_PROCESS = [
    "01_📂Documenti_Personali",
    "02_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social",
    "05_📂Workflow_Backup",
    "99_📂Archivio",
]

for top_name in TOP_PROCESS:
    top_id = nmap.get(top_name)
    if not top_id:
        print(f"\n[skip] {top_name}")
        continue
    print(f"\n📂 {top_name}")

    # Prima processa i file flat della cartella top
    moved = nest_folder(top_id, top_name)
    grand_total += moved

    # Poi processa le sottocartelle dirette che hanno file flat
    subs = list_children(top_id, folders_only=True)
    for sub in subs:
        sub_children = list_children(sub["id"])
        sub_flat = [c for c in sub_children if c["mimeType"] != "application/vnd.google-apps.folder"]
        if len(sub_flat) >= MIN_FLAT:
            print(f"  └─ {sub['name']} ({len(sub_flat)} flat)")
            moved = nest_folder(sub["id"], sub["name"])
            grand_total += moved

print(f"\n{'='*60}")
print(f"✅ Completato: {grand_total} file annidati in sottocartelle.")

# Struttura finale
print("\n📊 STRUTTURA FINALE:")
nmap = root_map()
for name in sorted(nmap.keys()):
    kids = list_children(nmap[name])
    flat = sum(1 for k in kids if k["mimeType"] != "application/vnd.google-apps.folder")
    subs = [k for k in kids if k["mimeType"] == "application/vnd.google-apps.folder"]
    print(f"  {name}: {flat} flat, {len(subs)} sotto")
    for s in sorted(subs, key=lambda x: x["name"]):
        s_kids = list_children(s["id"])
        s_flat = sum(1 for k in s_kids if k["mimeType"] != "application/vnd.google-apps.folder")
        s_subs = sum(1 for k in s_kids if k["mimeType"] == "application/vnd.google-apps.folder")
        print(f"    └─ {s['name']}: {s_flat} file, {s_subs} sotto")
