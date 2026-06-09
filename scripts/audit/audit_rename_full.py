"""
FULL PASS — verifica nome E posizione di TUTTI i file nelle 4 cartelle.
A differenza di audit_and_rename.py, non filtra per is_unreadable():
chiede all'AI di valutare ogni file e suggerire nome+cartella migliori.

Usage:
  python scripts/audit/audit_rename_full.py          # dry-run
  python scripts/audit/audit_rename_full.py --apply  # applica
"""
import json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

import httpx
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.config import settings

APPLY  = "--apply" in sys.argv
# --folder "01_..." limita a una sola cartella (per run paralleli)
_folder_arg = next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--folder" and i+1 < len(sys.argv)), None)

svc   = get_drive_service()

OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "huihui_ai/qwen3-abliterated:14b-v2"

ALL_TOP_FOLDERS = [
    "01_📂Documenti_Personali",
    "02_📂Casa_e_Immobili",
    "03_📂Scuola_e_Didattica",
    "04_📂Progetti_e_Social",
]
TOP_FOLDERS = [_folder_arg] if _folder_arg else ALL_TOP_FOLDERS

BATCH = 15  # file per chiamata AI

# ─── Drive helpers ────────────────────────────────────────────────────────────

def list_children(pid, folders_only=False):
    q = f"'{pid}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        kw = dict(q=q, pageSize=200,
                  fields="files(id,name,mimeType,size,modifiedTime,fileExtension,owners)")
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items

def scan_recursive(folder_id, path=""):
    rows = []
    for item in list_children(folder_id):
        p = f"{path}/{item['name']}" if path else item["name"]
        if item["mimeType"] == "application/vnd.google-apps.folder":
            rows.extend(scan_recursive(item["id"], p))
        else:
            rows.append((item, folder_id, path))
    return rows

def get_direct_subs(folder_id):
    return {f["name"]: f["id"] for f in list_children(folder_id, folders_only=True)}

def move_file(fid, from_p, to_p):
    if from_p == to_p:
        return
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

def rename_file(fid, new_name):
    svc.files().update(fileId=fid, body={"name": new_name}, fields="id").execute()

def sanitize(name, ext):
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if ext and not name.lower().endswith(f".{ext.lower()}"):
        name = f"{name}.{ext}"
    return name[:120]

# ─── AI helper ────────────────────────────────────────────────────────────────

def call_ai(prompt):
    # Ollama first
    try:
        r = httpx.post(OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            json={"model": OLLAMA_MODEL, "temperature": 0.1,
                  "messages": [{"role": "user", "content": prompt}],
                  "options": {"num_predict": 4000}},
            timeout=90)
        r.raise_for_status()
        text = re.sub(r"<think>.*?</think>", "",
                      r.json()["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
        if "```" in text:
            text = re.split(r"```(?:json)?", text)[1].strip().rstrip("`").strip()
        return json.loads(text)
    except Exception:
        pass
    # DeepSeek fallback
    for attempt in range(4):
        try:
            r = httpx.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                         "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=90)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if "```" in text:
                text = re.split(r"```(?:json)?", text)[1].strip().rstrip("`").strip()
            return json.loads(text)
        except Exception:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError("AI fallita")

# ─── Skip patterns (file da non toccare mai) ──────────────────────────────────

_SKIP = re.compile(
    r"(retention_curves|baseline_28gg|post_schedule|my workflow|workflow \d+|"
    r"undefined\.json|analytics_snapshot|trackers_snapshot)",
    re.I
)

def should_skip(name):
    return bool(_SKIP.search(name))

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n{'='*65}")
print(f"FULL PASS — {'DRY-RUN' if not APPLY else 'APPLY'}")
print(f"Valuta nome + posizione di TUTTI i file nelle 4 cartelle")
print(f"{'='*65}\n")

root = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in root.get("files", [])}

grand_renamed = grand_moved = grand_skipped = 0

for top_name in TOP_FOLDERS:
    top_id = nmap.get(top_name)
    if not top_id:
        print(f"[SKIP] {top_name} — non trovata\n")
        continue

    print(f"{'─'*65}")
    print(f"📂 {top_name}")

    direct_subs = get_direct_subs(top_id)
    subs_text   = "\n".join(f"- {s}" for s in direct_subs)
    all_files   = [(f, pid, path) for f, pid, path in scan_recursive(top_id)
                   if not should_skip(f["name"])]

    print(f"  Sottocartelle: {len(direct_subs)}  |  File da verificare: {len(all_files)}")
    if not all_files:
        continue

    n_batches = (len(all_files) - 1) // BATCH + 1
    folder_renamed = folder_moved = 0

    for i in range(0, len(all_files), BATCH):
        batch = all_files[i:i + BATCH]
        n = i // BATCH + 1

        file_descriptions = []
        for f, _, path in batch:
            ext      = f.get("fileExtension", "") or ""
            size     = f.get("size", "?")
            modified = (f.get("modifiedTime") or "")[:10]
            ctx      = path.replace("/", " > ") if path else top_name
            curr_sub = path.split("/")[0] if "/" in path else path or "[root]"
            file_descriptions.append(
                f'- nome: "{f["name"]}" | cartella attuale: {curr_sub} | '
                f'estensione: {ext} | dim: {size}B | modificato: {modified} | contesto: {ctx}'
            )

        prompt = f"""Sei un assistente per organizzare Google Drive in italiano.
Cartella principale: "{top_name}"

Sottocartelle disponibili (usa SOLO queste):
{subs_text}

Per ogni file valuta:
1. Il nome attuale è descrittivo e chiaro? Se no, proponi un nome migliore in italiano.
   - Mantieni la stessa estensione (NON includerla nel campo new_name)
   - Max 80 caratteri, usa lettere/numeri/spazi/trattini/underscore
   - Se il nome è già buono, restituisci null per new_name
2. La sottocartella attuale è quella giusta? Se no, indica quella corretta.
   - Usa SOLO i nomi esatti delle sottocartelle elencate sopra
   - Se la posizione è già corretta, ripeti il nome attuale

NON toccare file di automazione (n8n, analytics, workflow, retention).

File:
{chr(10).join(file_descriptions)}

Rispondi SOLO con JSON array:
[{{"file":"nome_attuale_con_estensione","new_name":"nuovo_nome_senza_ext_o_null","subfolder":"nome_sottocartella","rename_confidence":0.9,"move_confidence":0.9}}, ...]"""

        print(f"  [{n}/{n_batches}] batch {len(batch)} file…", end=" ", flush=True)
        try:
            results = call_ai(prompt)
            res_map = {r["file"]: r for r in results if isinstance(r, dict)}

            batch_renamed = batch_moved = 0
            for f_dict, parent_id, current_path in batch:
                res = res_map.get(f_dict["name"])
                if not res:
                    grand_skipped += 1
                    continue

                # ── RENAME ──
                new_name_stem = res.get("new_name")
                if new_name_stem and new_name_stem not in (None, "null", "") \
                        and res.get("rename_confidence", 0) >= 0.7:
                    ext = f_dict.get("fileExtension", "") or ""
                    new_name = sanitize(new_name_stem, ext)
                    # Salta renames che aggiungono solo "_2" al nome originale
                    old_stem = re.sub(r"\.[^.]+$", "", f_dict["name"])
                    new_stem = re.sub(r"\.[^.]+$", "", new_name)
                    if new_stem == old_stem + "_2":
                        grand_skipped += 1
                        continue
                    if new_name and new_name != f_dict["name"]:
                        print(f"\n    ✏ {f_dict['name'][:48]} → {new_name[:48]}", end="")
                        if APPLY:
                            try:
                                rename_file(f_dict["id"], new_name)
                                f_dict["name"] = new_name  # aggiorna per move sotto
                            except Exception as e:
                                print(f" [ERR rename: {e}]", end="")
                        batch_renamed += 1
                        grand_renamed += 1

                # ── MOVE ──
                dest_sub = res.get("subfolder")
                if dest_sub and dest_sub in direct_subs \
                        and res.get("move_confidence", 0) >= 0.75:
                    curr_sub = current_path.split("/")[0] if "/" in current_path else current_path
                    if curr_sub != dest_sub:
                        print(f"\n    ↪ {f_dict['name'][:48]} → {dest_sub}", end="")
                        if APPLY:
                            try:
                                move_file(f_dict["id"], parent_id, direct_subs[dest_sub])
                            except Exception as e:
                                print(f" [ERR move: {e}]", end="")
                        batch_moved += 1
                        grand_moved += 1

                time.sleep(0.05)

            folder_renamed += batch_renamed
            folder_moved   += batch_moved
            print(f"  ok (rename: {batch_renamed}, move: {batch_moved})")
        except Exception as e:
            print(f"  ERR: {e}")
        time.sleep(0.3)

    print(f"  ✅ {folder_renamed} rename, {folder_moved} move in {top_name}\n")

print(f"{'='*65}")
print(f"✅ COMPLETATO ({'APPLY' if APPLY else 'DRY-RUN'}):")
print(f"   Rename: {grand_renamed}")
print(f"   Move:   {grand_moved}")
print(f"   Skip:   {grand_skipped}")
