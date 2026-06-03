"""
Riorganizza 05_📂Casa_e_Immobili in una gerarchia logica:

PRIMA (16 subfolder flat):
  Via Nazionale 122, Pagamenti Vari, Fatture Acquisti,
  Sant'Antioco (Via Bolzano 20), Sarroch, IMU (x2), Preventivi Ristrutturazione,
  Inps, Affitti, A2A_Enel, Tiscali, Abbanoa, Condominio,
  Aste Immobiliari, Condominio via Mons Efisio Spettu 45

DOPO (struttura per macro-categoria):
  📍 Immobili/
      Via Nazionale 122/
      Sant'Antioco/
      Sarroch/
      Condominio Spettu 45/
  💡 Bollette/
      A2A_Enel/
      Tiscali/
      Abbanoa/
  🏛 Fiscale/
      IMU/        (fonde le 2 IMU duplicate)
      INPS/
  🔨 Lavori/
      Preventivi Ristrutturazione/
  🏦 Aste_Immobiliari/    (resta top-level)
  📄 Affitti/             (resta top-level)
  📦 Varie/               (Pagamenti Vari, Fatture Acquisti)
"""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

# ─── helpers ─────────────────────────────────────────────────────────────────

def find_folder(name, parent_id):
    r = svc.files().list(
        q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    for f in r.get("files", []):
        if f["name"] == name:
            return f["id"]
    return None


def create_folder(name, parent_id):
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]}
    fid = svc.files().create(body=meta, fields="id").execute()["id"]
    print(f"  📁+ {name}")
    return fid


def get_or_create(name, parent_id, cache={}):
    key = (name, parent_id)
    if key not in cache:
        fid = find_folder(name, parent_id)
        cache[key] = fid or create_folder(name, parent_id)
    return cache[key]


def move_folder(folder_id, from_parent, to_parent):
    if folder_id == to_parent or from_parent == to_parent:
        return
    svc.files().update(
        fileId=folder_id, addParents=to_parent, removeParents=from_parent,
        fields="id",
    ).execute()


def list_children(folder_id, folders_only=False):
    q = f"'{folder_id}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    r = svc.files().list(q=q, fields="files(id,name,mimeType)", pageSize=200).execute()
    return r.get("files", [])


def merge_into(src_id, dst_id, src_name, dst_name):
    """Sposta tutti i figli di src in dst, poi elimina src (se vuota)."""
    kids = list_children(src_id)
    for kid in kids:
        move_folder(kid["id"], src_id, dst_id)
        print(f"      ↳ {kid['name']} → {dst_name}")
        time.sleep(0.12)
    remaining = list_children(src_id)
    if not remaining:
        svc.files().delete(fileId=src_id).execute()
        print(f"  🗑  {src_name} eliminata (vuota)")


def rename_folder(folder_id, new_name):
    svc.files().update(fileId=folder_id, body={"name": new_name}, fields="id,name").execute()
    print(f"  ✏  → {new_name}")

# ─── main ─────────────────────────────────────────────────────────────────────

# Trova la cartella top
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}
CASA = nmap.get("05_📂Casa_e_Immobili")
if not CASA:
    print("ERRORE: 05_📂Casa_e_Immobili non trovata")
    sys.exit(1)

print(f"Cartella: 05_📂Casa_e_Immobili (id={CASA[:12]}…)\n")

# Leggi sottocartelle attuali
subs = {f["name"]: f["id"] for f in list_children(CASA, folders_only=True)}
print("Sottocartelle trovate:")
for n in subs:
    print(f"  - {n}")
print()

# ─── 1. Crea macro-cartelle ──────────────────────────────────────────────────
print("=== 1. Macro-categorie ===")
IMMOBILI = get_or_create("📍 Immobili",  CASA)
BOLLETTE  = get_or_create("💡 Bollette",  CASA)
FISCALE   = get_or_create("🏛 Fiscale",   CASA)
LAVORI    = get_or_create("🔨 Lavori",    CASA)
VARIE     = get_or_create("📦 Varie",     CASA)

# ─── 2. Sposta immobili ──────────────────────────────────────────────────────
print("\n=== 2. Immobili ===")
for old_name, new_name in [
    ("Via Nazionale 122",               "Via Nazionale 122"),
    ("Sant'Antioco (Via Bolzano 20)",    "Sant'Antioco"),
    ("Sarroch",                          "Sarroch"),
    ("Condominio via Mons Efisio Spettu 45", "Spettu 45"),
]:
    fid = subs.get(old_name)
    if not fid:
        print(f"  [skip] {old_name} non trovata")
        continue
    move_folder(fid, CASA, IMMOBILI)
    if old_name != new_name:
        rename_folder(fid, new_name)
    print(f"  📦 {old_name} → Immobili/{new_name}")
    time.sleep(0.15)

# ─── 3. Bollette ────────────────────────────────────────────────────────────
print("\n=== 3. Bollette ===")
for name in ["A2A_Enel", "Tiscali", "Abbanoa"]:
    fid = subs.get(name)
    if not fid:
        print(f"  [skip] {name}")
        continue
    move_folder(fid, CASA, BOLLETTE)
    print(f"  ⚡ {name} → Bollette/")
    time.sleep(0.15)

# ─── 4. Fiscale ─────────────────────────────────────────────────────────────
print("\n=== 4. Fiscale ===")

# Fonde le 2 cartelle IMU in una sola sotto Fiscale
imu_folders = [f for f in list_children(CASA, folders_only=True) if f["name"] == "IMU"]
# Anche quelle già spostate (poco fa non le abbiamo ancora mosse)
imu_folders += [f for f in list_children(CASA, folders_only=True) if f["name"] == "IMU"]
# Usa find per essere sicuro
all_subs_now = {f["name"]: [] for f in list_children(CASA, folders_only=True)}
for f in list_children(CASA, folders_only=True):
    all_subs_now.setdefault(f["name"], []).append(f["id"])

imu_ids = all_subs_now.get("IMU", [])
if len(imu_ids) >= 1:
    # Crea/trova IMU sotto Fiscale
    IMU_DEST = get_or_create("IMU", FISCALE)
    for i, imu_id in enumerate(imu_ids):
        if i == 0:
            # Prima: sposta dentro Fiscale/IMU i suoi figli, poi elimina
            merge_into(imu_id, IMU_DEST, "IMU", "Fiscale/IMU")
        else:
            merge_into(imu_id, IMU_DEST, f"IMU ({i})", "Fiscale/IMU")
        time.sleep(0.15)
    print(f"  🏛 IMU ({len(imu_ids)} cartelle) → Fiscale/IMU")

inps_id = subs.get("Inps")
if inps_id:
    move_folder(inps_id, CASA, FISCALE)
    rename_folder(inps_id, "INPS")
    print(f"  🏛 Inps → Fiscale/INPS")
    time.sleep(0.15)

# ─── 5. Lavori ──────────────────────────────────────────────────────────────
print("\n=== 5. Lavori ===")
prev_id = subs.get("Preventivi Ristrutturazione")
if prev_id:
    move_folder(prev_id, CASA, LAVORI)
    print(f"  🔨 Preventivi Ristrutturazione → Lavori/")
    time.sleep(0.15)

# ─── 6. Varie ───────────────────────────────────────────────────────────────
print("\n=== 6. Varie ===")
for name in ["Pagamenti Vari", "Fatture Acquisti", "Condominio"]:
    fid = subs.get(name)
    if not fid:
        print(f"  [skip] {name}")
        continue
    move_folder(fid, CASA, VARIE)
    print(f"  📦 {name} → Varie/")
    time.sleep(0.15)

# ─── Risultato ───────────────────────────────────────────────────────────────
print("\n=== STRUTTURA FINALE ===")
final = list_children(CASA, folders_only=True)
for f in sorted(final, key=lambda x: x["name"]):
    kids = list_children(f["id"], folders_only=True)
    print(f"  📁 {f['name']}" + (f" ({len(kids)} sotto)" if kids else ""))
    for k in kids:
        print(f"    └─ {k['name']}")
print("\n✅ Ristrutturazione completata.")
