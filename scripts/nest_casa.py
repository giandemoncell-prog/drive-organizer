"""
Organizza 02_📂Casa_e_Immobili per immobile + categoria.
Sottocartelle per proprietà note + categorie trasversali.
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

# Sottocartelle per immobile + categorie trasversali
SUBFOLDERS = [
    "🏠 Via_Nazionale_122",      # proprietà Cagliari - affitti
    "🏠 Sant'Antioco",           # proprietà Sant'Antioco (Via Bolzano 20)
    "🏠 Sarroch",                # proprietà Sarroch
    "🏠 Spettu_45",              # Condominio via Mons Efisio Spettu 45, Quartucciu
    "💡 Bollette_Utenze",        # A2A/Enel, Tiscali, Abbanoa, acqua, luce, gas
    "🏛️ IMU_e_Tasse",           # IMU, F24, accertamenti fiscali
    "🔨 Lavori_Ristrutturazione",# preventivi, danni, umidità, installazioni
    "📑 Aste_e_Vendite",         # aste immobiliari, avvisi vendita, vendite
    "📄 Documenti_Generali",     # condominio, varie non classificabili altrove
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
        if f["name"] == name: return f["id"]
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
                      "options": {"num_predict": 3000}}, timeout=180)
            r.raise_for_status()
            text = re.sub(r"<think>.*?</think>", "",
                r.json()["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except Exception as e:
            print(f" [ollama err: {e}]", end=""); time.sleep(2)
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
        except Exception as e:
            print(f" [ds err: {e}]", end=""); time.sleep(3)
    raise RuntimeError("AI fallita")

# Trova cartella
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
PARENT = nmap.get("02_📂Casa_e_Immobili") or nmap.get("05_📂Casa_e_Immobili")
if not PARENT:
    print("ERRORE: Casa_e_Immobili non trovata"); sys.exit(1)

files = [f for f in list_children(PARENT)
         if f["mimeType"] != "application/vnd.google-apps.folder"]
print(f"02_📂Casa_e_Immobili: {len(files)} file flat\n")

# Pre-crea sottocartelle
sub_ids = {name: get_or_create(name, PARENT) for name in SUBFOLDERS}
subs_text = "\n".join(f"- {s}" for s in SUBFOLDERS)

BATCH = 12
total = 0

for i in range(0, len(files), BATCH):
    batch = files[i:i+BATCH]
    n, tot_b = i // BATCH + 1, (len(files) - 1) // BATCH + 1
    file_list = "\n".join(f"- {f['name']}" for f in batch)

    prompt = f"""Sei un assistente per organizzare documenti immobiliari su Google Drive.
Cartella: "02_📂Casa_e_Immobili"

Sottocartelle per immobile/categoria (usane SOLO queste):
{subs_text}

Regole di classificazione:
- 🏠 Via_Nazionale_122: affitti, locazioni, RLI, canoni, inquilini, Via Nazionale
- 🏠 Sant'Antioco: documenti Sant'Antioco, Via Bolzano, APE Sant'Antioco
- 🏠 Sarroch: documenti Sarroch, lottizzazione, aree edificabili Sarroch
- 🏠 Spettu_45: Spettu, Quartucciu, condominio Spettu, danni bagno, umidità armadio climatizzatore
- 💡 Bollette_Utenze: A2A, Enel, Tiscali, Abbanoa, luce, gas, acqua, bollette generiche
- 🏛️ IMU_e_Tasse: IMU, F24, accertamenti IMU, controdeduzioni, delibera IMU
- 🔨 Lavori_Ristrutturazione: preventivi, danni, umidità misurazioni, installazioni, serratura, climatizzatore, infiltrazioni, facciata, portoncino
- 📑 Aste_e_Vendite: aste immobiliari, avvisi vendita, offerte, licitazioni, vendite terreni, donazioni
- 📄 Documenti_Generali: condominio quote, VENDITE E DONAZIONI generici, certificati idoneità, tutto il resto

File da classificare:
{file_list}

Rispondi SOLO con JSON array:
[{{"file":"nome_esatto","subfolder":"nome_sottocartella"}}, ...]"""

    print(f"  batch {n}/{tot_b} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r["subfolder"] for r in results if "subfolder" in r}
        moved = 0
        for f in batch:
            sub = name_map.get(f["name"])
            if sub and sub in sub_ids:
                move_file(f["id"], PARENT, sub_ids[sub])
                moved += 1; total += 1
            time.sleep(0.08)
        print(f"ok ({moved}/{len(batch)})")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ {total}/{len(files)} file organizzati per immobile.")

# Struttura finale
print("\nStruttura finale 02_📂Casa_e_Immobili:")
for f in sorted(list_children(PARENT, folders_only=True), key=lambda x: x["name"]):
    kids = list_children(f["id"])
    flat = sum(1 for k in kids if k["mimeType"] != "application/vnd.google-apps.folder")
    print(f"  📁 {f['name']}: {flat} file")
