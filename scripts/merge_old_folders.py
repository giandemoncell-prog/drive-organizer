"""
Merge old manual folders into AI-organized structure.
- Rinomina le cartelle AI aggiungendo l'emoji 📂
- Sposta le sottocartelle vecchie nelle nuove
- Applica colori distinti a ogni cartella
- Elimina le shell vuote
"""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

# Rinomina: vecchio nome AI → nuovo nome con 📂
RENAME_AI = {
    "00_Workflow_Backup":    "00_📂Workflow_Backup",
    "01_BachataVibes":       "01_📂BachataVibes",
    "02_Sviluppo_e_Software":"02_📂Sviluppo_e_Software",
    "03_Automazioni_Social": "03_📂Automazioni_Social",
    "04_Documenti_Personali":"04_📂Documenti_Personali",
    "05_Casa_e_Immobili":    "05_📂Casa_e_Immobili",
    "06_Scuola_e_Didattica": "06_📂Scuola_e_Didattica",
    "07_Viaggi_e_Hobby":     "07_📂Viaggi_e_Hobby",
    "99_Archivio":           "99_📂Archivio",
}

# Colori per ogni cartella finale (Google Drive hex palette)
COLORS = {
    "00_📂Workflow_Backup":     "#B0B0B0",  # grigio
    "01_📂BachataVibes":        "#D50000",  # rosso vivace
    "02_📂Sviluppo_e_Software": "#1565C0",  # blu scuro
    "03_📂Automazioni_Social":  "#0097A7",  # teal
    "04_📂Documenti_Personali": "#E65100",  # arancione
    "05_📂Casa_e_Immobili":     "#4E342E",  # marrone
    "06_📂Scuola_e_Didattica":  "#6A1B9A",  # viola
    "07_📂Viaggi_e_Hobby":      "#2E7D32",  # verde
    "99_📂Archivio":            "#757575",  # grigio scuro
}

# Merge: vecchia cartella manuale → nuova cartella AI (dopo rinomina)
MERGE_MAP = {
    "01_📂Immobili":          "05_📂Casa_e_Immobili",
    "02_📂Spese e Bollette":  "05_📂Casa_e_Immobili",
    "03_📂Veicoli ":          "04_📂Documenti_Personali",
    "04_📂Personale ":        "04_📂Documenti_Personali",
    "05_📂Lavoro":            "04_📂Documenti_Personali",
    "06_📂Progetti e Hobby":  "07_📂Viaggi_e_Hobby",
    "07_📂Viaggio Canarie":   "07_📂Viaggi_e_Hobby",
    "10_📂Software":          "02_📂Sviluppo_e_Software",
    "99_📂Archivio":          "99_📂Archivio",
}
# Eccezioni: sottocartella specifica va in target diverso
SPECIAL = {
    "Bachata Vibes Music": "01_📂BachataVibes",
    "ADS Canali Social":   "03_📂Automazioni_Social",
}

DELETE_EMPTY = [
    "08_📂Libro_IA", "09_📂SerenaInfissi", "2026-05-09",
    "Colab Notebooks", "DriveOrganizer_Chromebook",
]


def root_folders():
    r = svc.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}


def children(folder_id):
    r = svc.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id,name,mimeType)", pageSize=200,
    ).execute()
    return r.get("files", [])


def move_item(item_id, from_parent, to_parent):
    svc.files().update(
        fileId=item_id, addParents=to_parent, removeParents=from_parent,
        fields="id",
    ).execute()


def rename_folder(folder_id, new_name):
    svc.files().update(fileId=folder_id, body={"name": new_name}, fields="id,name").execute()


def set_color(folder_id, color_hex):
    svc.files().update(fileId=folder_id, body={"folderColorRgb": color_hex}, fields="id").execute()


def delete_folder(folder_id, name):
    svc.files().delete(fileId=folder_id).execute()
    print(f"  🗑  {name}")


# ─── STEP 1: Rinomina cartelle AI ───────────────────────────────────────────
print("=== 1. RINOMINA CARTELLE AI ===\n")
nmap = root_folders()
renamed = 0
for old, new in RENAME_AI.items():
    fid = nmap.get(old)
    if not fid:
        print(f"  [SKIP] {old} — già rinominata o non trovata")
        continue
    rename_folder(fid, new)
    print(f"  ✏  {old} → {new}")
    renamed += 1
    time.sleep(0.15)
print(f"\nRinominate: {renamed}")

# ─── STEP 2: Applica colori ──────────────────────────────────────────────────
print("\n=== 2. COLORI CARTELLE ===\n")
nmap = root_folders()
for folder_name, color in COLORS.items():
    fid = nmap.get(folder_name)
    if not fid:
        print(f"  [SKIP] {folder_name}")
        continue
    set_color(fid, color)
    print(f"  🎨 {folder_name} → {color}")
    time.sleep(0.15)

# ─── STEP 3: Merge vecchie → nuove ───────────────────────────────────────────
print("\n=== 3. MERGE SOTTOCARTELLE ===\n")
nmap = root_folders()
moved = 0
for old_name, default_target in MERGE_MAP.items():
    old_id = nmap.get(old_name)
    if not old_id:
        print(f"  [SKIP] {old_name} — non trovata")
        continue
    kids = children(old_id)
    if not kids:
        print(f"  [EMPTY] {old_name}")
        continue
    print(f"  {old_name} →")
    for item in kids:
        target = SPECIAL.get(item["name"], default_target)
        tid = nmap.get(target)
        if not tid:
            print(f"    [ERR] target '{target}' non trovata")
            continue
        try:
            move_item(item["id"], old_id, tid)
            k = "📁" if item["mimeType"] == "application/vnd.google-apps.folder" else "📄"
            print(f"    {k} {item['name']} → {target}")
            moved += 1
        except HttpError as e:
            print(f"    [ERR] {item['name']}: {e}")
        time.sleep(0.15)
print(f"\nSpostate: {moved}")

# ─── STEP 4: Elimina shell vuote ─────────────────────────────────────────────
print("\n=== 4. ELIMINAZIONE CARTELLE VUOTE ===\n")
nmap = root_folders()
deleted = 0
to_del = list(MERGE_MAP.keys()) + DELETE_EMPTY
for name in to_del:
    fid = nmap.get(name)
    if not fid:
        continue
    kids = children(fid)
    if kids:
        print(f"  [SKIP] {name} — ancora {len(kids)} elementi")
        continue
    try:
        delete_folder(fid, name)
        deleted += 1
    except HttpError as e:
        print(f"  [ERR] {name}: {e}")
    time.sleep(0.15)
print(f"\nEliminate: {deleted}")
print(f"\n✅ Fatto: {renamed} rinominate, {moved} spostate, {deleted} eliminate.")
