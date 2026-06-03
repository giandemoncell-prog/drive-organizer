"""
Suddivide 📋 Legale_Fiscale in sottocartelle semantiche.
Sottocartelle proposte:
  ⚖️ Pratiche_Legali     — procure, atti, avvocati, cause
  🏦 Fisco_e_Tasse       — 730, F24, dichiarazioni redditi, ISEE
  📜 Contratti           — contratti locazione RLI, contratti lavoro
  🛡️ Polizze             — assicurazioni, polizze auto/vita
  📮 Corrispondenza      — PEC, raccomandate, accessi agli atti
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

SUBFOLDERS = [
    "⚖️ Pratiche_Legali",
    "🏦 Fisco_e_Tasse",
    "📜 Contratti",
    "🛡️ Polizze",
    "📮 Corrispondenza",
]

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

def find_folder(name, parent_id):
    for f in list_children(parent_id, folders_only=True):
        if f["name"] == name:
            return f["id"]
    return None

def get_or_create(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        fid = find_folder(name, parent_id)
        if not fid:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
            print(f"    📁+ {name}")
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

# Trova 📋 Legale_Fiscale dentro Documenti_Personali
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

# Supporta sia 01_ che 02_ (potrebbe essere rinumerata)
doc_id = nmap.get("01_📂Documenti_Personali") or nmap.get("02_📂Documenti_Personali")
if not doc_id:
    print("ERRORE: Documenti_Personali non trovata"); sys.exit(1)

legale_id = find_folder("📋 Legale_Fiscale", doc_id)
if not legale_id:
    print("ERRORE: 📋 Legale_Fiscale non trovata"); sys.exit(1)

files = [f for f in list_children(legale_id)
         if f["mimeType"] != "application/vnd.google-apps.folder"]
print(f"📋 Legale_Fiscale: {len(files)} file\n")

# Pre-crea sottocartelle
sub_ids = {name: get_or_create(name, legale_id) for name in SUBFOLDERS}
subs_text = "\n".join(f"- {s}" for s in SUBFOLDERS)

BATCH = 12
total = 0
for i in range(0, len(files), BATCH):
    batch = files[i:i+BATCH]
    file_list = "\n".join(f"- {f['name']}" for f in batch)
    n, tot = i // BATCH + 1, (len(files) - 1) // BATCH + 1
    prompt = f"""Cartella: "📋 Legale_Fiscale" (dentro Documenti_Personali)
Sottocartelle disponibili (usane SOLO queste):
{subs_text}

File da classificare:
{file_list}

Regole:
- ⚖️ Pratiche_Legali: procure, nomina avvocato, atti giudiziari, cause legali
- 🏦 Fisco_e_Tasse: 730, F24, ISEE, dichiarazioni, accertamenti IMU, INPS
- 📜 Contratti: RLI, contratti locazione, contratti lavoro, contratti attivazione
- 🛡️ Polizze: assicurazioni auto/vita/casa, certificati polizza, attestati rischio, Attestato di rischio.pdf
- 📮 Corrispondenza: PEC, accesso agli atti, raccomandate, notifiche, ricevute

Rispondi SOLO con JSON: [{{"file":"nome_esatto","subfolder":"nome_sottocartella"}}, ...]"""

    print(f"  batch {n}/{tot} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r["subfolder"] for r in results if "subfolder" in r}
        moved = 0
        for f in batch:
            sub = name_map.get(f["name"])
            if sub and sub in sub_ids:
                move_file(f["id"], legale_id, sub_ids[sub])
                moved += 1; total += 1
            time.sleep(0.08)
        print(f"ok ({moved}/{len(batch)})")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ {total}/{len(files)} file organizzati in 📋 Legale_Fiscale.")
