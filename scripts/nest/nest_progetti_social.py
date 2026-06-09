"""Classifica i file flat in 04_📂Progetti_e_Social nelle sottocartelle esistenti."""
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

def list_children(parent_id, folders_only=False):
    q = f"'{parent_id}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        kw = dict(q=q, fields="files(id,name,mimeType)", pageSize=200)
        if token: kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token: break
    return items

def move_file(fid, from_p, to_p):
    if from_p == to_p: return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def call_ai(prompt):
    for _ in range(2):
        try:
            r = httpx.post(OLLAMA_URL, headers={"Content-Type": "application/json"},
                json={"model": OLLAMA_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.1, "options": {"num_predict": 2048}},
                timeout=120)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except Exception as e:
            time.sleep(1)
    # DeepSeek fallback
    for _ in range(3):
        try:
            r = httpx.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                         "Content-Type": "application/json"},
                json={"model": "deepseek-chat",
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.1}, timeout=90)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except Exception: time.sleep(3)
    raise RuntimeError("AI fallita")

# Trova la cartella
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
PARENT = nmap.get("04_📂Progetti_e_Social") or nmap.get("07_📂Viaggi_e_Hobby")
if not PARENT:
    print("ERRORE: 04_📂Progetti_e_Social non trovata"); sys.exit(1)

children = list_children(PARENT)
flat_files = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]
subfolders = {c["name"]: c["id"] for c in children if c["mimeType"] == "application/vnd.google-apps.folder"}

print(f"04_📂Progetti_e_Social: {len(flat_files)} file flat")
print(f"Sottocartelle: {', '.join(subfolders.keys())}\n")

if not flat_files:
    print("Nessun file flat. Fine."); sys.exit(0)

subs_text = "\n".join(f"- {s}" for s in subfolders.keys())
BATCH = 12
total_moved = 0

for i in range(0, len(flat_files), BATCH):
    batch = flat_files[i:i+BATCH]
    file_list = "\n".join(f"- {f['name']}" for f in batch)
    n = i // BATCH + 1
    tot = (len(flat_files) - 1) // BATCH + 1
    prompt = f"""Cartella: "04_📂Progetti_e_Social"
Sottocartelle disponibili:
{subs_text}

File da classificare:
{file_list}

Assegna ogni file alla sottocartella più adatta.
Rispondi SOLO con JSON: [{{"file":"nome","subfolder":"nome_sottocartella"}}, ...]"""

    print(f"  batch {n}/{tot} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r["subfolder"] for r in results if "subfolder" in r}
        moved = 0
        for f in batch:
            sub = name_map.get(f["name"])
            if sub and sub in subfolders:
                move_file(f["id"], PARENT, subfolders[sub])
                moved += 1; total_moved += 1
            time.sleep(0.08)
        print(f"ok ({moved}/{len(batch)})")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ {total_moved}/{len(flat_files)} file → sottocartelle.")
