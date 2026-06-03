"""
Crea sottocartelle logiche in 00_📂Documenti_Personali
usando huihui_ai/qwen3-abliterated:14b-v2 (GPU).
Max 7 sottocartelle, classificazione semantica.
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
DS_URL       = "https://api.deepseek.com/v1/chat/completions"

SUBFOLDERS = [
    "🪪 Identità",        # CI, passaporto, CF, NIE, permessi soggiorno
    "🏥 Salute",          # referti, ricette, visite
    "💼 Lavoro",          # contratti, buste paga, assunzione, INPS
    "🚗 Veicoli",         # libretto, assicurazione, bollo, rottamazione
    "📋 Legale_Fiscale",  # procure, atti notarili, 730, dichiarazioni
    "📄 CV_Formazione",   # curriculum, laurea, certificati, EIPASS
    "🌍 Estero_Visti",    # NIE, permessi, visti, documenti spagnoli
]

def list_children(parent_id):
    items, token = [], None
    while True:
        kw = dict(q=f"'{parent_id}' in parents and trashed=false",
                  fields="files(id,name,mimeType)", pageSize=200)
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items

def get_or_create(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        existing = [f for f in list_children(parent_id)
                    if f["mimeType"] == "application/vnd.google-apps.folder" and f["name"] == name]
        if existing:
            cache[key] = existing[0]["id"]
        else:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
            print(f"    📁+ {name}")
            cache[key] = fid
    return cache[key]

def move_file(fid, from_p, to_p):
    if from_p == to_p:
        return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def call_ai(prompt):
    # Ollama first
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
            r = httpx.post(DS_URL,
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
        except Exception as e:
            time.sleep(3)
    raise RuntimeError("AI fallita")

# ─── main ────────────────────────────────────────────────────────────────────

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
PARENT = nmap.get("01_📂Documenti_Personali") or nmap.get("00_📂Documenti_Personali")
if not PARENT:
    print("ERRORE: 01_📂Documenti_Personali non trovata"); sys.exit(1)

files = [f for f in list_children(PARENT)
         if f["mimeType"] != "application/vnd.google-apps.folder"]
print(f"01_📂Documenti_Personali: {len(files)} file da classificare\n")

# Pre-crea sottocartelle
sub_ids = {}
for name in SUBFOLDERS:
    sub_ids[name] = get_or_create(name, PARENT)

subs_text = "\n".join(f"- {s}" for s in SUBFOLDERS)

BATCH = 12
total_moved = 0
for i in range(0, len(files), BATCH):
    batch = files[i:i+BATCH]
    file_list = "\n".join(f"- {f['name']}" for f in batch)
    prompt = f"""Sei un assistente per l'organizzazione di Google Drive.

Cartella: "01_📂Documenti_Personali"
Sottocartelle disponibili (usane SOLO queste):
{subs_text}

File da classificare:
{file_list}

Regole:
- Ogni file DEVE avere una sottocartella
- Usa SOLO i nomi esatti delle sottocartelle
- Rispondi SOLO con JSON array:
[{{"file":"nome_esatto","subfolder":"nome_sottocartella"}}, ...]"""

    n = i // BATCH + 1
    tot = (len(files) - 1) // BATCH + 1
    print(f"  batch {n}/{tot} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r["subfolder"] for r in results if "subfolder" in r}
        moved = 0
        for f in batch:
            sub_name = name_map.get(f["name"])
            if sub_name and sub_name in sub_ids:
                move_file(f["id"], PARENT, sub_ids[sub_name])
                moved += 1
                total_moved += 1
            time.sleep(0.08)
        print(f"ok ({moved}/{len(batch)})")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ {total_moved}/{len(files)} file organizzati in sottocartelle.")
