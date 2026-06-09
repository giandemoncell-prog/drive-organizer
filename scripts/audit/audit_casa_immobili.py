"""
Audit ricorsivo 02_📂Casa_e_Immobili:
- Legge TUTTI i file (inclusi nelle sottocartelle)
- Chiede all'AI se ogni file è nella cartella giusta
- Sposta i file mal collocati nella destinazione corretta
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

DESTINATIONS = [
    "02_📂Casa_e_Immobili",      # resta qui
    "01_📂Documenti_Personali",  # identità, salute, lavoro, veicoli
    "03_📂Scuola_e_Didattica",   # materiali didattici
    "04_📂Progetti_e_Social",    # tech, social, bachata
    "05_📂Workflow_Backup",      # n8n
    "99_📂Archivio",             # archivio generico
]

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
        except Exception: time.sleep(2)
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

# Trova cartelle top-level
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

CASA_ID = nmap.get("02_📂Casa_e_Immobili")
if not CASA_ID: print("ERRORE: Casa non trovata"); sys.exit(1)

print("Scansione ricorsiva 02_📂Casa_e_Immobili…")
all_files = get_all_files_recursive(CASA_ID)
print(f"Trovati {len(all_files)} file totali\n")

# Mostra riassunto per sottocartella
from collections import Counter
path_counts = Counter(path for _, _, path in all_files)
for path, count in sorted(path_counts.items()):
    print(f"  {path or '[root]'}: {count} file")

print()
dest_text = "\n".join(f"- {d}" for d in DESTINATIONS)
BATCH = 15
total_moved = 0

for i in range(0, len(all_files), BATCH):
    batch = all_files[i:i+BATCH]
    n, tot_b = i // BATCH + 1, (len(all_files) - 1) // BATCH + 1

    file_list = "\n".join(
        f"- \"{f['name']}\" (in: {path or 'root Casa'})"
        for f, _, path in batch
    )

    prompt = f"""Sei un assistente per organizzare Google Drive.

Stai analizzando file che si trovano dentro "02_📂Casa_e_Immobili" e le sue sottocartelle.
Per ogni file, indica se va bene dov'è o se deve andare in un'altra cartella principale.

Cartelle di destinazione disponibili:
{dest_text}

Criteri:
- 02_📂Casa_e_Immobili: documenti casa, immobili, bollette, IMU, affitti, lavori, aste, umidità, danni
- 01_📂Documenti_Personali: identità, salute, lavoro, veicoli, assicurazioni personali, CV, pratiche legali personali (NON immobiliari)
- 03_📂Scuola_e_Didattica: materiali scolastici, didattica, libri
- 04_📂Progetti_e_Social: sviluppo sw, bachata, social, automazioni
- 99_📂Archivio: file obsoleti, archivio storico

File da verificare:
{file_list}

Per ogni file: se è già nella cartella giusta scrivi "02_📂Casa_e_Immobili", altrimenti la destinazione corretta.
Rispondi SOLO con JSON: [{{"file":"nome_esatto","destination":"cartella"}}]"""

    print(f"  batch {n}/{tot_b} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r.get("destination") for r in results}
        moved = 0
        for f_dict, parent_id, _ in batch:
            dest = name_map.get(f_dict["name"])
            if dest and dest != "02_📂Casa_e_Immobili" and dest in nmap:
                move_file(f_dict["id"], parent_id, nmap[dest])
                print(f"\n    → {f_dict['name']} → {dest}", end="")
                moved += 1; total_moved += 1
            time.sleep(0.08)
        print(f"  ok ({moved} spostati)")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ Audit completato: {total_moved} file spostati fuori da Casa.")
