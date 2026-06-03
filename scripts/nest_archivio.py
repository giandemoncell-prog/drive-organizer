"""
Organizza 99_📂Archivio:
- Sposta fuori i file che appartengono ad altre cartelle
- Crea sottocartelle semantiche per il resto
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

# Sottocartelle interne all'archivio
ARCHIVE_SUBS = [
    "📸 Foto_2025",              # foto con timestamp, WhatsApp images
    "🎮 HorizonWorlds_VR",       # guide e reference Horizon Worlds
    "💌 Messaggi_Personali",     # messaggi, screenshot conversazioni
    "📋 Documenti_Vari",         # file ambigui, non classificabili altrove
]

# Targets esterni (file che NON appartengono all'archivio)
EXTERNAL_TARGETS = [
    "03_📂Scuola_e_Didattica",   # materiali didattici robotica/coding
    "01_📂Documenti_Personali",  # CV, polizze, auto, salute
    "02_📂Casa_e_Immobili",      # danni bagno, foto casa
]

ALL_OPTIONS = ARCHIVE_SUBS + EXTERNAL_TARGETS

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

# Trova cartelle
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
ARCH = nmap.get("99_📂Archivio")
if not ARCH: print("ERRORE: 99_📂Archivio non trovata"); sys.exit(1)

files = [f for f in list_children(ARCH)
         if f["mimeType"] != "application/vnd.google-apps.folder"]
print(f"99_📂Archivio: {len(files)} file\n")

# Pre-crea sottocartelle interne
arch_sub_ids = {name: get_or_create(name, ARCH) for name in ARCHIVE_SUBS}

options_text = "\n".join(f"- {o}" for o in ALL_OPTIONS)

BATCH = 12
total_arch = 0
total_out  = 0

for i in range(0, len(files), BATCH):
    batch = files[i:i+BATCH]
    n, tot_b = i // BATCH + 1, (len(files) - 1) // BATCH + 1
    file_list = "\n".join(f"- {f['name']}" for f in batch)

    prompt = f"""Sei un assistente per organizzare Google Drive.
Cartella corrente: "99_📂Archivio" (fallback — contiene file eterogenei da smistare)

Opzioni di destinazione:
{options_text}

Regole:
- 📸 Foto_2025: foto con timestamp (20250525_*.jpg, 20250630_*.jpg, PXL_*.jpg, WhatsApp Image *.jpeg, Messaggi*.jpeg, Danni Bagno*.jpeg)
- 🎮 HorizonWorlds_VR: Horizon Worlds PDF, Events_V71, Motion_V71, Values_V71, Variables_V71, AssetSpawning, OnUpdateEvent, PlayerAchievements, PlayerManagement, Creation Limits, System Time
- 💌 Messaggi_Personali: S. U., G. C., E. Z., Messaggi01/02/03, email *.txt, Consigli di lavoro
- 📋 Documenti_Vari: tr.pdf, tav.pdf, file con nomi ambigui senza categoria chiara
- 03_📂Scuola_e_Didattica: materiali didattici (robotica, coding, mBot, Scratch, algoritmi, geometria, polycoding, IOT, DUDU, Laboratorio, OrtoLab, robot, Pensiero computazionale, A caccia di Isole, Accipitrum, Chiesa di San Michele, Geostoric, Progetto Dungeon, Proiezione, SisteMBot, Tour computer, Tutorial 3D, SOStenibilità, PD-M5S, PRESENTAZIONE Urbino, GEOMETRIA, Imparare coding, Il mito, Il paesaggio, esami universitari.txt)
- 01_📂Documenti_Personali: CV 2023/2024, polizze, certificati assicurazione, carta circolazione, certificato proprietà veicolo, codice autoradio, prescrizioni occhiali, permesso soggiorno Widline, caparra occhiali, modello occhiali, Carta Freccia, carta_232181654, Lotteria scontrini, order-*.pdf, Set informativo, certificato_*, 526505135250*, 15/01/2025.pdf, 17/09/2025.pdf, Europass_CV, Coldiretti
- 02_📂Casa_e_Immobili: foto danni bagno (già → 📸 Foto per ora)

File da classificare:
{file_list}

Rispondi SOLO con JSON array:
[{{"file":"nome_esatto","destination":"destinazione_esatta"}}, ...]"""

    print(f"  batch {n}/{tot_b} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r.get("destination") or r.get("subfolder") for r in results}
        moved_a = moved_o = 0
        for f in batch:
            dest = name_map.get(f["name"])
            if not dest: time.sleep(0.08); continue
            if dest in arch_sub_ids:
                move_file(f["id"], ARCH, arch_sub_ids[dest])
                moved_a += 1; total_arch += 1
            elif dest in nmap:
                move_file(f["id"], ARCH, nmap[dest])
                moved_o += 1; total_out += 1
            time.sleep(0.08)
        print(f"ok ({moved_a} arch, {moved_o} out)")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ Nell'archivio: {total_arch} | Spostati fuori: {total_out}")
print("\nStruttura finale 99_📂Archivio:")
for f in sorted(list_children(ARCH, folders_only=True), key=lambda x: x["name"]):
    kids = list_children(f["id"])
    flat = sum(1 for k in kids if k["mimeType"] != "application/vnd.google-apps.folder")
    print(f"  📁 {f['name']}: {flat} file")
remaining = [f for f in list_children(ARCH) if f["mimeType"] != "application/vnd.google-apps.folder"]
print(f"  [flat rimanenti: {len(remaining)}]")
