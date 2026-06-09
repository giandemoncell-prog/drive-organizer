"""
Rinomina le foto in 02_Casa_e_Immobili/📸 Foto_2025.
Converte nomi tipo "25-05-2025_1226_2e82cf1b.jpg" in "Cantiere_PROPRIETA_YYYY-MM-DD_NNN.jpg".

Usage:
  python scripts/fix/rename_cantiere_photos.py             # dry-run (mostra rename)
  python scripts/fix/rename_cantiere_photos.py --apply     # applica
"""
import argparse, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

APPLY = "--apply" in sys.argv

# Nomi proprietà noti in 02_Casa
PROPERTY_KEYWORDS = {
    "spettu":       "Spettu_45",
    "nazionale":    "Spettu_45",
    "bolzano":      "Via_Bolzano_20",
    "sant'antioco": "Sant_Antioco",
    "antioco":      "Sant_Antioco",
    "sarroch":      "Sarroch",
}

def find_foto_folder():
    """Trova 02_Casa_e_Immobili e dentro cerca 📸 Foto_2025."""
    root = svc.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute().get("files", [])
    casa = next((f for f in root if f["name"] == "02_📂Casa_e_Immobili"), None)
    if not casa:
        sys.exit("❌ 02_📂Casa_e_Immobili non trovata")

    subs = svc.files().list(
        q=f"'{casa['id']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute().get("files", [])
    foto = next((f for f in subs if "Foto" in f["name"]), None)
    if not foto:
        sys.exit("❌ Cartella Foto_* non trovata in 02_Casa")
    return foto["id"], foto["name"]

def list_photos(folder_id):
    items, token = [], None
    while True:
        kw = dict(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name,mimeType,fileExtension,modifiedTime)",
            pageSize=200,
        )
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return [f for f in items if f["mimeType"].startswith("image/")]

def extract_date(name):
    """Estrae YYYY-MM-DD dal nome file. Priorità: mese italiano > DD-MM-YYYY > YYYY-MM-DD."""
    nl = name.lower()
    # 1. Mese italiano (alta affidabilità — no ambiguità con orari)
    MESI = {"gennaio":"01","febbraio":"02","marzo":"03","aprile":"04",
            "maggio":"05","giugno":"06","luglio":"07","agosto":"08",
            "settembre":"09","ottobre":"10","novembre":"11","dicembre":"12"}
    for it, num in MESI.items():
        if it in nl:
            y_m = re.search(r"(\d{4})", nl)
            d_m = re.search(r"(\d{1,2})[_\-\s]*" + it, nl)
            if y_m and d_m:
                return f"{y_m.group(1)}-{num}-{int(d_m.group(1)):02d}"
    # 2. DD-MM-YYYY (comune in foto italiane; il lookbehind evita match dentro YYYY)
    m = re.search(r"(?<!\d)(\d{1,2})[_\-\.](\d{2})[_\-\.](\d{4})(?!\d)", name)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12 and 2000 <= y <= 2030:
            return f"{y}-{mo:02d}-{d:02d}"
    # 3. YYYY-MM-DD (es. Foto_2025-04-10.jpg)
    m = re.search(r"(?<!\d)(\d{4})[_\-](\d{2})[_\-](\d{2})(?!\d)", name)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2000 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y}-{mo:02d}-{d:02d}"
    return None

def guess_property(name):
    nl = name.lower()
    for kw, prop in PROPERTY_KEYWORDS.items():
        if kw in nl:
            return prop
    return "Via_Bolzano_20"  # default: cantiere ristrutturazione

foto_id, foto_name = find_foto_folder()
photos = list_photos(foto_id)
print(f"📸 Cartella: {foto_name}  |  Foto trovate: {len(photos)}")
if not photos:
    sys.exit("Nessuna foto da rinominare.")

# Raggruppa per data per numerare progressivamente
from collections import defaultdict
by_date = defaultdict(list)
for p in photos:
    date = extract_date(p["name"]) or (p.get("modifiedTime") or "")[:10]
    by_date[date].append(p)

print(f"\n{'DRY-RUN' if not APPLY else 'APPLY'} — rename {len(photos)} foto:\n")
renamed = 0
for date in sorted(by_date.keys()):
    group = by_date[date]
    for i, photo in enumerate(group, 1):
        ext = photo.get("fileExtension", "jpg") or "jpg"
        prop = guess_property(photo["name"])
        new_name = f"{prop}_{date}_{i:02d}.{ext.lower()}"
        if new_name == photo["name"]:
            continue
        print(f"  ✏ {photo['name'][:55]:<55} → {new_name}")
        if APPLY:
            try:
                svc.files().update(fileId=photo["id"], body={"name": new_name}, fields="id").execute()
                renamed += 1
            except Exception as e:
                print(f"    [ERR] {e}")
        else:
            renamed += 1

if APPLY:
    print(f"\n✅ {renamed} foto rinominate.")
else:
    print(f"\nDry-run: {renamed} rename proposti. Aggiungi --apply per applicare.")
