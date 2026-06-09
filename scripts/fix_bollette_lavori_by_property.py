"""
Organizza Bollette_Utenze e Lavori_Ristrutturazione per immobile.
Crea sottocartelle per ogni proprietà, sposta i file, rinomina quelli generici.

Immobili noti:
  - Spettu_45       (Via Nazionale 122, condominio, umidità/climatizzatore)
  - Via_Bolzano_20  (appartamento in vendita/acquisto)
  - Sant_Antioco    (APE, SIRA, Via Nora)
  - Sarroch         (foglio 28)
  - Generale        (non classificabile)
"""
import sys, os, certifi, time, json, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings
from googleapiclient.errors import HttpError
import httpx

svc = get_drive_service()

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "huihui_ai/qwen3-abliterated:14b-v2"

PROPERTY_SUBS = [
    "🏠 Spettu_45",
    "🏠 Via_Bolzano_20",
    "🏠 Sant_Antioco",
    "🏠 Sarroch",
    "📋 Generale",
]

# ─── helpers ──────────────────────────────────────────────────────────────────

def list_files(pid):
    items, token = [], None
    while True:
        kw = dict(q=f"'{pid}' in parents and trashed=false and "
                    f"mimeType!='application/vnd.google-apps.folder'",
                  fields="files(id,name,mimeType,size,modifiedTime)", pageSize=200)
        if token: kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token: break
    return items

def get_or_create_sub(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        r = svc.files().list(
            q=f"'{parent_id}' in parents and name='{name}' and "
              f"mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id)", pageSize=5,
        ).execute()
        hits = r.get("files", [])
        if hits:
            cache[key] = hits[0]["id"]
        else:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
            print(f"  📁+ {name}")
            cache[key] = fid
    return cache[key]

def move_file(fid, from_p, to_p):
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def rename_file(fid, new_name):
    svc.files().update(fileId=fid, body={"name": new_name}, fields="id").execute()

def call_ai(prompt):
    try:
        r = httpx.post(OLLAMA_URL, headers={"Content-Type": "application/json"},
            json={"model": OLLAMA_MODEL, "temperature": 0.1,
                  "messages": [{"role": "user", "content": prompt}],
                  "options": {"num_predict": 2000}}, timeout=60)
        r.raise_for_status()
        text = re.sub(r"<think>.*?</think>", "",
                      r.json()["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json\n").strip()
        return json.loads(text)
    except Exception:
        pass
    for attempt in range(4):
        try:
            r = httpx.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                         "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]}, timeout=90)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json\n").strip()
            return json.loads(text)
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("AI fallita")

def sanitize(name, ext):
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if ext and not name.lower().endswith(f".{ext.lower()}"):
        name = f"{name}.{ext}"
    return name[:120]

# ─── Root map ─────────────────────────────────────────────────────────────────

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
top02 = nmap["02_📂Casa_e_Immobili"]

r2 = svc.files().list(
    q=f"'{top02}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
subs02 = {f["name"]: f["id"] for f in r2.get("files", [])}

TARGET_FOLDERS = {
    "💡 Bollette_Utenze": subs02.get("💡 Bollette_Utenze"),
    "🔨 Lavori_Ristrutturazione": subs02.get("🔨 Lavori_Ristrutturazione"),
}

# ─── Processa ogni cartella ───────────────────────────────────────────────────

PROPERTY_MAP = {
    "Spettu_45":      "🏠 Spettu_45",
    "Via_Bolzano_20": "🏠 Via_Bolzano_20",
    "Sant_Antioco":   "🏠 Sant_Antioco",
    "Sarroch":        "🏠 Sarroch",
    "Generale":       "📋 Generale",
}

grand_moved = 0
grand_renamed = 0

for folder_label, folder_id in TARGET_FOLDERS.items():
    if not folder_id:
        print(f"\n[SKIP] {folder_label} — non trovata")
        continue

    print(f"\n{'='*65}")
    print(f"📁 {folder_label}")
    print(f"{'='*65}")

    # Crea le sottocartelle per property
    sub_ids = {prop: get_or_create_sub(sub_name, folder_id)
               for prop, sub_name in PROPERTY_MAP.items()}

    files = list_files(folder_id)
    print(f"  File da organizzare: {len(files)}")

    if not files:
        continue

    BATCH = 15
    for i in range(0, len(files), BATCH):
        batch = files[i:i + BATCH]
        n = i // BATCH + 1
        n_batches = (len(files) - 1) // BATCH + 1

        file_lines = []
        for f in batch:
            ext = f.get("fileExtension", "") or ""
            size_kb = int(f.get("size", 0)) // 1024 if f.get("size") else 0
            modified = (f.get("modifiedTime", "") or "")[:10]
            file_lines.append(f'- "{f["name"]}" | ext:{ext} | {size_kb}KB | {modified}')

        prompt = f"""Sei un assistente per organizzare documenti immobiliari italiani.
Cartella: "{folder_label}"

Immobili noti del proprietario (Gianluca Demontis):
- Spettu_45: Via Nazionale 122 Spettu, condominio, problemi umidità/climatizzatore, scala Marchetti
- Via_Bolzano_20: appartamento in acquisto/ristrutturazione a Cagliari Via Bolzano 20
- Sant_Antioco: immobile a Sant'Antioco (APE F13PART11, Abbanoa, SIRA, Via Nora)
- Sarroch: terreno/immobile a Sarroch (foglio 28, Abbanoa Aex3l potrebbe essere qui)
- Generale: bollette/documenti non attribuibili a un immobile specifico

Per ogni file indica:
1. "property": uno di [Spettu_45, Via_Bolzano_20, Sant_Antioco, Sarroch, Generale]
2. "new_name": nome leggibile in italiano (senza estensione), oppure "" se il nome è già ottimale
3. "confidence": 0.0-1.0

File da classificare:
{chr(10).join(file_lines)}

Regole rename:
- Bollette: "Bolletta_[fornitore]_[immobile]_[YYYY-MM].pdf" es: "Bolletta_Enel_Spettu_45_2024-06.pdf"
- Foto danni/umidità: lascia il nome se descrive già il contenuto
- Se confidence < 0.6 usa "Generale"

Rispondi SOLO con JSON:
[{{"old_name":"nome_con_estensione","property":"Spettu_45","new_name":"nome_senza_ext","confidence":0.8}}]"""

        print(f"  [{n}/{n_batches}] batch {len(batch)}…", end=" ", flush=True)
        try:
            results = call_ai(prompt)
            moved_in_batch = 0
            renamed_in_batch = 0
            for f in batch:
                match = next((r for r in results if isinstance(r, dict) and r.get("old_name") == f["name"]), None)
                if not match:
                    # Fallback a Generale
                    dest = sub_ids["Generale"]
                    move_file(f["id"], folder_id, dest)
                    grand_moved += 1
                    moved_in_batch += 1
                    continue

                prop = match.get("property", "Generale")
                if prop not in sub_ids:
                    prop = "Generale"
                dest = sub_ids[prop]

                # Move
                move_file(f["id"], folder_id, dest)
                grand_moved += 1
                moved_in_batch += 1

                # Rename se suggerito e confidence sufficiente
                new_name_stem = match.get("new_name", "").strip()
                confidence = match.get("confidence", 0.0)
                ext = f.get("fileExtension", "") or ""
                if new_name_stem and confidence >= 0.7 and new_name_stem.lower() != re.sub(r"\.[^.]+$", "", f["name"]).lower():
                    full_new = sanitize(new_name_stem, ext)
                    if full_new and full_new != f["name"]:
                        try:
                            rename_file(f["id"], full_new)
                            print(f"\n    ✏ {f['name'][:40]} → {full_new[:40]}", end="")
                            grand_renamed += 1
                            renamed_in_batch += 1
                        except Exception:
                            pass

                time.sleep(0.1)
            print(f"  ok ({moved_in_batch} mossi, {renamed_in_batch} rinominati)")
        except Exception as e:
            print(f"  ERR: {e}")
        time.sleep(0.5)

    print(f"  ✅ {folder_label}: completata")

print(f"\n{'='*65}")
print(f"✅ COMPLETATO: {grand_moved} file organizzati per immobile, {grand_renamed} rinominati")
