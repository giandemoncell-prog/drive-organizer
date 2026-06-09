"""
Organizza 05_Workflow_Backup in sottocartelle semantiche.
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

def get_or_create(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        existing = [f for f in list_children(parent_id, folders_only=True) if f["name"] == name]
        if existing:
            cache[key] = existing[0]["id"]
        else:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
            print(f"  📁+ {name}")
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
                      "options": {"num_predict": 1024}}, timeout=120)
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

# Trova cartella
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
wf_id = nmap.get("05_\U0001f4c2Workflow_Backup")
if not wf_id:
    print("ERRORE: 05_Workflow_Backup non trovata"); sys.exit(1)

files = [f for f in list_children(wf_id)
         if f["mimeType"] != "application/vnd.google-apps.folder"]
print(f"05_Workflow_Backup: {len(files)} file\n")
for f in files:
    print(f"  - {f['name']}")
print()

if not files:
    print("Nessun file da organizzare."); sys.exit(0)

# Chiedi all'AI le sottocartelle più adatte basandosi sui nomi dei file
file_list = "\n".join(f"- {f['name']}" for f in files)
prompt = f"""Sei un assistente per organizzare Google Drive.
Cartella: "05_Workflow_Backup" (contiene backup, workflow n8n, automazioni, configurazioni)

File presenti:
{file_list}

1. Proponi max 4 sottocartelle semantiche adatte a questi file (nomi brevi, max 25 car).
2. Assegna ogni file alla sottocartella corretta.

Rispondi SOLO con JSON:
{{
  "subfolders": ["nome1", "nome2", ...],
  "assignments": [{{"file":"nome_esatto","subfolder":"nome_cartella"}}, ...]
}}"""

print("Classifico con AI…", end=" ", flush=True)
try:
    result = call_ai(prompt)
    subfolders = result.get("subfolders", [])
    assignments = result.get("assignments", [])
    print(f"ok ({len(subfolders)} sottocartelle, {len(assignments)} assegnazioni)")
except Exception as e:
    print(f"ERR: {e}"); sys.exit(1)

print(f"\nSottocartelle proposte: {', '.join(subfolders)}")
sub_ids = {name: get_or_create(name, wf_id) for name in subfolders}
name_map = {a["file"]: a["subfolder"] for a in assignments if "subfolder" in a}

total = 0
for f in files:
    sub = name_map.get(f["name"])
    if sub and sub in sub_ids:
        move_file(f["id"], wf_id, sub_ids[sub])
        print(f"  ✓ {f['name']} → {sub}")
        total += 1
    time.sleep(0.08)

print(f"\n✅ {total}/{len(files)} file organizzati in 05_Workflow_Backup.")
