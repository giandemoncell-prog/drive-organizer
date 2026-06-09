"""
AUDIT + RENAME — pipeline completa:
1. Audit: verifica che ogni file sia nella sottocartella giusta dentro le 4 top-level
2. Rename: rinomina i file con nomi non leggibili usando DeepSeek

Cascade AI: Ollama (locale) → DeepSeek (cloud fallback)
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

TOP_FOLDERS = [
    "01_📂Documenti_Personali",
    "02_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social",
]

# ─── helpers ──────────────────────────────────────────────────────────────────

def list_children(pid, folders_only=False):
    q = f"'{pid}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        kw = dict(q=q, fields="files(id,name,mimeType,parents,size,modifiedTime,fileExtension,owners)",
                  pageSize=200)
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items

def get_all_files_recursive(folder_id, path="", folder_name=""):
    """Ritorna lista di (file_dict, parent_id, path_str)."""
    result = []
    children = list_children(folder_id)
    for c in children:
        if c["mimeType"] == "application/vnd.google-apps.folder":
            sub_path = f"{path}/{c['name']}" if path else c["name"]
            result.extend(get_all_files_recursive(c["id"], sub_path, c["name"]))
        else:
            result.append((c, folder_id, path))
    return result

def get_or_create_subfolder(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        existing = [f for f in list_children(parent_id, folders_only=True) if f["name"] == name]
        if existing:
            cache[key] = existing[0]["id"]
        else:
            fid = svc.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [parent_id]}, fields="id").execute()["id"]
            print(f"      📁+ {name}")
            cache[key] = fid
    return cache[key]

def move_file(fid, from_p, to_p):
    if from_p == to_p:
        return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def rename_file(fid, new_name):
    svc.files().update(fileId=fid, body={"name": new_name}, fields="id").execute()

def call_ai(prompt, expect_json=True):
    # Try Ollama local first
    try:
        r = httpx.post(OLLAMA_URL, headers={"Content-Type": "application/json"},
            json={"model": OLLAMA_MODEL, "temperature": 0.1,
                  "messages": [{"role": "user", "content": prompt}],
                  "options": {"num_predict": 3000}}, timeout=60)
        r.raise_for_status()
        text = re.sub(r"<think>.*?</think>", "",
                      r.json()["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json\n").strip()
        return json.loads(text) if expect_json else text
    except Exception:
        pass

    # DeepSeek fallback
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
            return json.loads(text) if expect_json else text
        except Exception as e:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError("AI fallita dopo tutti i tentativi")

# ─── pattern per nomi non leggibili ──────────────────────────────────────────

_RE_TIMESTAMP = re.compile(
    r"^(\d{8}[_\-T]\d{6}|\d{4}[_\-]\d{2}[_\-]\d{2}[T_\- ]\d{2}[:\-]\d{2}|\d{13}|\d{10})$"
)
_RE_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", re.I)
_RE_DIGITS_ONLY = re.compile(r"^[\d_\-\.]+$")
_RE_HASH = re.compile(r"^[0-9a-fA-F]{16,}$")
_RE_IMG = re.compile(r"^(IMG|DSC|DCIM|SCAN|VID|MOV|PXL|MVIMG)[\s_\-]\d+", re.I)
_RE_AUTO = re.compile(r"^(untitled|senza titolo|document|foglio|presentazione|copia di|copy of)"
                      r"(\s*[\(\[\-]\d+[\)\]]?)?$", re.I)
_RE_SHORT_CODE = re.compile(r"^[A-Z0-9]{6,20}$")
_RE_RETENTION = re.compile(r"^(retention_curves|baseline_28gg|post_schedule)", re.I)
_RE_WORKFLOW_N8N = re.compile(r"My workflow|workflow \d+", re.I)

def is_unreadable(name: str) -> bool:
    stem = re.sub(r"\.[^.]+$", "", name).strip()
    if _RE_RETENTION.match(stem):
        return False  # file automazione n8n — lasciare intatti
    if _RE_WORKFLOW_N8N.search(stem):
        return False
    if _RE_TIMESTAMP.match(stem):
        return True
    if _RE_UUID.search(stem):
        return True
    if _RE_DIGITS_ONLY.match(stem) and len(stem) > 5:
        return True
    if _RE_HASH.match(stem):
        return True
    if _RE_IMG.match(stem):
        return True
    if _RE_AUTO.match(stem):
        return True
    if _RE_SHORT_CODE.match(stem) and not any(c.islower() for c in stem):
        return True
    return False

def sanitize_name(name: str, ext: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if ext and not name.lower().endswith(f".{ext.lower()}"):
        name = f"{name}.{ext}"
    return name[:120]

# ═══════════════════════════════════════════════════════════════════
# FASE 1 — AUDIT POSIZIONI
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 65)
print("FASE 1 — AUDIT: verifica posizione file nelle sottocartelle")
print("=" * 65)

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

AUDIT_BATCH = 20
grand_audit_moved = 0

for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        print(f"\n[SKIP] {top_name} — non trovata")
        continue

    print(f"\n{'─'*60}")
    print(f"📂 {top_name}")

    direct_subs = {f["name"]: f["id"] for f in list_children(top_id, folders_only=True)}
    if not direct_subs:
        print(f"  Nessuna sottocartella — skip audit")
        continue

    subs_text = "\n".join(f"- {s}" for s in direct_subs.keys())
    all_files = get_all_files_recursive(top_id)
    print(f"  Sottocartelle: {len(direct_subs)}  |  File totali: {len(all_files)}")

    if not all_files:
        continue

    folder_moved = 0
    n_batches = (len(all_files) - 1) // AUDIT_BATCH + 1

    for i in range(0, len(all_files), AUDIT_BATCH):
        batch = all_files[i:i + AUDIT_BATCH]
        n = i // AUDIT_BATCH + 1

        file_list = "\n".join(
            f'- "{f["name"]}" (ora in: {path.split("/")[0] if "/" in path else path or "[root]"})'
            for f, _, path in batch
        )

        prompt = f"""Sei un assistente per organizzare Google Drive in italiano.
Cartella principale: "{top_name}"

Sottocartelle disponibili (usa SOLO queste, scrivi il nome ESATTO):
{subs_text}

Per ogni file indica la sottocartella corretta tra quelle elencate.
Se il file è già nella posizione giusta, ripeti il nome attuale.
NON spostare file di automazione (workflow, n8n, analytics, retention, baseline).

File con posizione attuale:
{file_list}

Rispondi SOLO con JSON (array):
[{{"file":"nome_esatto_del_file","subfolder":"nome_sottocartella"}}, ...]"""

        print(f"  [{n}/{n_batches}] batch {len(batch)} file…", end=" ", flush=True)
        try:
            results = call_ai(prompt)
            name_map = {r["file"]: r.get("subfolder") for r in results if isinstance(r, dict)}
            moved = 0
            for f_dict, parent_id, current_path in batch:
                dest_sub = name_map.get(f_dict["name"])
                if not dest_sub or dest_sub not in direct_subs:
                    continue
                dest_id = direct_subs[dest_sub]
                current_sub = current_path.split("/")[0] if "/" in current_path else current_path
                if current_sub == dest_sub:
                    continue
                try:
                    move_file(f_dict["id"], parent_id, dest_id)
                    print(f"\n    ↪ {f_dict['name'][:50]} → {dest_sub}", end="")
                    moved += 1
                    folder_moved += 1
                    grand_audit_moved += 1
                except Exception as e:
                    print(f"\n    [ERR move] {f_dict['name'][:40]}: {e}", end="")
                time.sleep(0.08)
            print(f"  ok ({moved} spostati)")
        except Exception as e:
            print(f"  ERR: {e}")
        time.sleep(0.4)

    print(f"  ✅ {folder_moved} file riposizionati in {top_name}")

print(f"\n✅ FASE 1 completata: {grand_audit_moved} file riposizionati in totale.")

# ═══════════════════════════════════════════════════════════════════
# FASE 2 — RENAME FILE CON NOMI NON LEGGIBILI
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 65)
print("FASE 2 — RENAME: file con nomi non significativi")
print("=" * 65)

RENAME_BATCH = 15
grand_renamed = 0
grand_skipped = 0

for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        continue

    print(f"\n{'─'*60}")
    print(f"📂 {top_name}")

    all_files = get_all_files_recursive(top_id)

    # Filtra solo i file con nomi non leggibili
    bad_files = [(f, pid, path) for f, pid, path in all_files if is_unreadable(f["name"])]
    print(f"  File totali: {len(all_files)}  |  Nomi da rinominare: {len(bad_files)}")

    if not bad_files:
        continue

    folder_renamed = 0
    n_batches = (len(bad_files) - 1) // RENAME_BATCH + 1

    for i in range(0, len(bad_files), RENAME_BATCH):
        batch = bad_files[i:i + RENAME_BATCH]
        n = i // RENAME_BATCH + 1

        file_descriptions = []
        for f, _, path in batch:
            ext = f.get("fileExtension", "")
            size = f.get("size", "?")
            modified = (f.get("modifiedTime", "") or "")[:10]
            mime = f.get("mimeType", "")
            # Deduce contesto dalla cartella
            context = path.replace("/", " > ") if path else top_name
            file_descriptions.append(
                f'- nome: "{f["name"]}" | estensione: {ext} | cartella: {context} | '
                f'dim: {size} byte | modificato: {modified}'
            )

        prompt = f"""Sei un assistente per rinominare file Google Drive in italiano.
Cartella principale: "{top_name}"

Per ogni file suggerisci un nome leggibile e descrittivo in italiano.
Regole:
- Mantieni la stessa estensione
- Usa solo lettere, numeri, spazi, trattini, underscore
- Max 80 caratteri (senza estensione)
- Il nome deve descrivere il contenuto basandoti su cartella e tipo file
- Se il file sembra una foto, usa formato: Foto_YYYY-MM-DD
- Se è un documento, descrivi l'argomento in base alla cartella
- NON includere l'estensione nel campo "new_name"

File da rinominare:
{chr(10).join(file_descriptions)}

Rispondi SOLO con JSON (array):
[{{"old_name":"nome_attuale_con_estensione","new_name":"nuovo_nome_senza_estensione","confidence":0.8}}, ...]"""

        print(f"  [{n}/{n_batches}] batch {len(batch)} file…", end=" ", flush=True)
        try:
            results = call_ai(prompt)
            name_map = {r["old_name"]: r for r in results if isinstance(r, dict) and r.get("confidence", 0) >= 0.6}

            renamed = 0
            for f_dict, parent_id, path in batch:
                match = name_map.get(f_dict["name"])
                if not match:
                    grand_skipped += 1
                    continue
                ext = f_dict.get("fileExtension", "")
                new_name = sanitize_name(match["new_name"], ext)
                if new_name == f_dict["name"] or not new_name.strip():
                    grand_skipped += 1
                    continue
                try:
                    rename_file(f_dict["id"], new_name)
                    print(f"\n    ✏ {f_dict['name'][:45]} → {new_name[:45]}", end="")
                    renamed += 1
                    folder_renamed += 1
                    grand_renamed += 1
                except Exception as e:
                    print(f"\n    [ERR rename] {f_dict['name'][:40]}: {e}", end="")
                time.sleep(0.1)
            print(f"  ok ({renamed} rinominati)")
        except Exception as e:
            print(f"  ERR: {e}")
        time.sleep(0.4)

    print(f"  ✅ {folder_renamed} file rinominati in {top_name}")

print(f"\n{'='*65}")
print(f"✅ COMPLETATO:")
print(f"   Fase 1 (audit):  {grand_audit_moved} file riposizionati")
print(f"   Fase 2 (rename): {grand_renamed} file rinominati, {grand_skipped} skip (conf. bassa)")
