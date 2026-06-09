"""
Organizza i file sparsi in 🌍 Estero_Visti nelle sottocartelle corrette.
Crea ✈️ Voli_Biglietti se mancante. Cestina i duplicati evidenti in Widline.
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

def find_folder(parent_id, name):
    escaped = name.replace("'", "\\'")
    r = svc.files().list(
        q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' "
          f"and name='{escaped}' and trashed=false",
        fields="files(id,name)", pageSize=10,
    ).execute()
    items = r.get("files", [])
    return items[0] if items else None

def get_or_create(parent_id, name):
    f = find_folder(parent_id, name)
    if f:
        return f["id"]
    fid = svc.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder",
              "parents": [parent_id]}, fields="id").execute()["id"]
    print(f"  📁+ Creata: {name}")
    return fid

def list_files_flat(folder_id):
    items, token = [], None
    while True:
        kw = dict(
            q=f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name,mimeType,size)", pageSize=200,
        )
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items

def move(fid, src, dst, label=""):
    svc.files().update(fileId=fid, addParents=dst, removeParents=src, fields="id").execute()
    print(f"  ↪ {label}")

def rename(fid, new_name):
    svc.files().update(fileId=fid, body={"name": new_name}, fields="id").execute()

def trash(fid, label):
    svc.files().update(fileId=fid, body={"trashed": True}, fields="id").execute()
    print(f"  🗑 {label}")

# ─── Setup ────────────────────────────────────────────────────────────────────
root = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in root.get("files", [])}
doc_id = nmap["01_📂Documenti_Personali"]

estero = find_folder(doc_id, "🌍 Estero_Visti")
eid = estero["id"]

# Sottocartelle (get or create)
sub = {
    "Appuntamenti": get_or_create(eid, "Appuntamenti"),
    "Gianluca":     get_or_create(eid, "Gianluca"),
    "Modulistica":  get_or_create(eid, "Modulistica"),
    "NIE_Permessi": get_or_create(eid, "NIE_Permessi"),
    "Ospitalita":   get_or_create(eid, "Ospitalità"),
    "Widline":      get_or_create(eid, "Widline"),
    "Voli":         get_or_create(eid, "✈️ Voli_Biglietti"),
}

print("\n" + "="*60)
print("ORGANIZZAZIONE file flat in 🌍 Estero_Visti")
print("="*60)

flat = list_files_flat(eid)
print(f"File da classificare: {len(flat)}\n")

# Mappa nome → (sottocartella, nuovo_nome_opzionale)
RULES = {
    "Appuntamento Visto.pdf":
        ("Appuntamenti", None),

    "Autocertificazione_Frequenza_Corsi_Italiano":
        ("NIE_Permessi", "Autocertificazione Frequenza Corsi Italiano.pdf"),

    "Biglietti Andata.pdf":
        ("Voli", None),
    "Biglietti Ritorno.pdf":
        ("Voli", None),
    "Biglietto elettronico NzM3MjAwNDIw.pdf":
        ("Voli", "Biglietto Elettronico Andata Feb 2026.pdf"),
    "Biglietto elettronico passeggero NzM3MjAwNDIw copia.pdf":
        ("Voli", "Biglietto Elettronico Passeggero Feb 2026.pdf"),

    "Deposito EB-HD0000016 UraHotels HODEIA 28-02-13-03.pdf":
        ("Ospitalita", "Deposito Hotel UraHotels HODEIA Feb-Mar 2026.pdf"),

    "dichiarazione di ospitalità.pdf":
        ("Ospitalita", "Dichiarazione di Ospitalità.pdf"),

    "Formulario_NIE_e_certificati_Stampabile.pdf":
        ("NIE_Permessi", "Formulario NIE e Certificati.pdf"),
    "Formulario_NIE_e_certificati_stampabile.pdf":
        ("NIE_Permessi", None),   # duplicato — verrà cestinato

    "Foto_Aereo.jpeg":
        ("Voli", "Foto Aereo.jpeg"),

    "NIE_Z4338994-A.pdf":
        ("NIE_Permessi", None),

    "Passaporto - Gianluca Demontis (2018-2028).pdf":
        ("Gianluca", "Passaporto Gianluca Demontis 2018-2028.pdf"),
    "Passaporto e Visto - Widline.pdf":
        ("Widline", "Passaporto e Visto Widline.pdf"),
    "Passaporto Widline Rigaud.pdf":
        ("Widline", None),

    "Permesso di Soggiorno I21550196.jpeg":
        ("NIE_Permessi", None),
    "PermessoProvvisorio.pdf":
        ("NIE_Permessi", "Permesso Soggiorno Provvisorio.pdf"),

    "Progetto_Estero.docx":
        ("Gianluca", "Progetto Estero.docx"),

    "Report Itinerario Cagliari-Gran Canaria-Siviglia Feb-Mar 2026":
        ("Voli", "Report Itinerario Cagliari-Gran Canaria-Siviglia Feb-Mar 2026"),
    "Report Ottimizzazione Voli e Prenotazioni Low-Cost":
        ("Voli", None),
    "Ricerca Voli Cagliari-Gran Canaria-Siviglia Stopover Feb-Mar 2026":
        ("Voli", None),

    "Ricevuta_Arcoiris.pdf":
        ("Ospitalita", "Ricevuta Arcoiris.pdf"),

    "Riserva EB-RH0000796 Gianluca Demontis 28-02-2026 13-03-2026 UraHotels HODEIA.pdf":
        ("Ospitalita", "Riserva Hotel UraHotels HODEIA Feb-Mar 2026.pdf"),

    "Visto_Estero.jpg":
        ("Gianluca", "Visto Estero.jpg"),
}

# Individua duplicati da cestinare (stesso contenuto, nomi simili)
TRASH = {"Formulario_NIE_e_certificati_stampabile.pdf"}  # duplicato lowercase

moved = renamed = trashed = 0
for f in flat:
    name = f["name"]
    if name in TRASH:
        trash(f["id"], name)
        trashed += 1
        continue
    rule = RULES.get(name)
    if not rule:
        print(f"  ⚠️ Nessuna regola per: {name}")
        continue
    dst_key, new_name = rule
    dst_id = sub[dst_key]
    if new_name and new_name != name:
        rename(f["id"], new_name)
        renamed += 1
        label = f"{name} → {new_name} [{dst_key}]"
    else:
        label = f"{name} [{dst_key}]"
    move(f["id"], eid, dst_id, label)
    moved += 1
    time.sleep(0.05)

print(f"\n{'='*60}")
print(f"✅ Spostati: {moved} | Rinominati: {renamed} | Cestinati: {trashed}")

# ─── Widline: rimuovi duplicati ───────────────────────────────────
print("\n" + "="*60)
print("WIDLINE — rimozione duplicati")
print("="*60)
widline_files = list_files_flat(sub["Widline"])
# Raggruppa per nome normalizzato
from collections import defaultdict
import re
groups = defaultdict(list)
for f in widline_files:
    key = re.sub(r"\s+", " ", re.sub(r"\.[^.]+$", "", f["name"])).strip().lower()
    groups[key].append(f)

for key, files in groups.items():
    if len(files) > 1:
        # Tieni il file con estensione .pdf se disponibile, altrimenti il più grande
        pdfs = [f for f in files if f["name"].lower().endswith(".pdf")]
        keep = pdfs[0] if pdfs else max(files, key=lambda x: int(x.get("size", 0)))
        for f in files:
            if f["id"] != keep["id"]:
                trash(f["id"], f["name"])
                trashed += 1

print(f"Totale cestinati (inclusi Widline): {trashed}")
