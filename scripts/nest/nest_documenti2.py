"""Inserisce i file flat in 01_📂Documenti_Personali nelle sottocartelle esistenti."""
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

def move_file(fid, from_p, to_p):
    if from_p == to_p: return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def read_file_preview(fid, mime):
    """Legge i primi 500 caratteri di un file leggibile."""
    try:
        # Google Docs → export come testo
        if "google-apps.document" in mime:
            content = svc.files().export(fileId=fid, mimeType="text/plain").execute()
            return content.decode("utf-8", errors="replace")[:500]
        # Google Sheets → export CSV
        elif "google-apps.spreadsheet" in mime:
            content = svc.files().export(fileId=fid, mimeType="text/csv").execute()
            return content.decode("utf-8", errors="replace")[:500]
        # File di testo/HTML/XML
        elif any(t in mime for t in ["text/", "html", "xml", "json"]):
            content = svc.files().get_media(fileId=fid).execute()
            return content.decode("utf-8", errors="replace")[:500]
    except Exception:
        pass
    return ""

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

# Trova la cartella
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
PARENT = nmap.get("01_📂Documenti_Personali")
if not PARENT: print("ERRORE"); sys.exit(1)

children = list_children(PARENT)
flat_files = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]
subfolders = {c["name"]: c["id"] for c in children if c["mimeType"] == "application/vnd.google-apps.folder"}

# Nomi ambigui → leggo contenuto
AMBIGUOUS_PATTERNS = ["tr.", "tav.", "S. ", "G. ", "E. ", "order-", "Set ",
                      "526505", "15/01", "17/09", "carta_", "Coldiretti"]
def is_ambiguous(name):
    return any(p.lower() in name.lower() for p in AMBIGUOUS_PATTERNS) or len(name) < 8

previews = {}
for f in flat_files:
    if is_ambiguous(f["name"]):
        preview = read_file_preview(f["id"], f["mimeType"])
        if preview:
            previews[f["name"]] = preview[:300]
            print(f"  📖 Letto: {f['name']} → {preview[:80]}…")

print(f"01_📂Documenti_Personali: {len(flat_files)} file flat")
print(f"Sottocartelle: {', '.join(subfolders.keys())}\n")

if not flat_files:
    print("Nessun file flat."); sys.exit(0)

subs_text = "\n".join(f"- {s}" for s in subfolders.keys())
BATCH = 12
total = 0

for i in range(0, len(flat_files), BATCH):
    batch = flat_files[i:i+BATCH]
    n, tot_b = i//BATCH+1, (len(flat_files)-1)//BATCH+1
    file_list = "\n".join(
        f"- {f['name']}" + (f"\n  [contenuto: {previews[f['name']]}]" if f["name"] in previews else "")
        for f in batch
    )
    prompt = f"""Cartella: "01_📂Documenti_Personali"
Sottocartelle (usa SOLO queste):
{subs_text}

Regole:
- 🪪 Identità: CI, passaporto, CF, tessera sanitaria, NIE, SPID, codice fiscale
- 🏥 Salute: referti, ricette, prescrizioni occhiali, analisi, visite, vaccinazioni
- 💼 Lavoro: buste paga, contratti, assunzione, TFR, INPS, NoiPA, cedolini, sindacale
- 🚗 Veicoli: libretto, bollo, assicurazione auto, rottamazione, cessione, PRA, carta circolazione
- 📋 Legale_Fiscale: procure, 730, dichiarazioni, accertamenti, polizze, RLI, PEC
- 📄 CV_Formazione: curriculum, laurea, EIPASS, certificati, esami, titoli studio
- 🌍 Estero_Visti: visti, NIE, permesso soggiorno, documenti spagnoli, Widline

File:
{file_list}

Rispondi SOLO con JSON: [{{"file":"nome","subfolder":"nome_sottocartella"}}, ...]"""

    print(f"  batch {n}/{tot_b} ({len(batch)} file)…", end=" ", flush=True)
    try:
        results = call_ai(prompt)
        name_map = {r["file"]: r["subfolder"] for r in results if "subfolder" in r}
        moved = 0
        for f in batch:
            sub = name_map.get(f["name"])
            if sub and sub in subfolders:
                move_file(f["id"], PARENT, subfolders[sub])
                moved += 1; total += 1
            time.sleep(0.08)
        print(f"ok ({moved}/{len(batch)})")
    except Exception as e:
        print(f"ERR: {e}")
    time.sleep(0.5)

print(f"\n✅ {total}/{len(flat_files)} file organizzati.")
for f in sorted(list_children(PARENT, folders_only=True), key=lambda x: x["name"]):
    kids = list_children(f["id"])
    flat = sum(1 for k in kids if k["mimeType"] != "application/vnd.google-apps.folder")
    print(f"  📁 {f['name']}: {flat} file")
