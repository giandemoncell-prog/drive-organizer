"""Sposta da CV_Formazione i documenti non pertinenti nelle cartelle giuste."""
import sys, os, certifi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service
from googleapiclient.errors import HttpError
import time

svc = get_drive_service()

def find_folder(parent_id, name):
    r = svc.files().list(
        q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' "
          f"and name='{name}' and trashed=false",
        fields="files(id,name)", pageSize=10,
    ).execute()
    hits = r.get("files", [])
    if hits:
        return hits[0]["id"]
    raise FileNotFoundError(f"Cartella '{name}' non trovata in {parent_id}")

def find_file(parent_id, name):
    r = svc.files().list(
        q=f"'{parent_id}' in parents and name='{name}' and trashed=false",
        fields="files(id,name)", pageSize=5,
    ).execute()
    hits = r.get("files", [])
    return hits[0]["id"] if hits else None

def move(fid, from_p, to_p):
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

# ─── Trova ID cartelle ────────────────────────────────────────────────────────
r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

top01 = nmap["01_📂Documenti_Personali"]
top02 = nmap["02_📂Casa_e_Immobili"]

cv_id       = find_folder(top01, "📄 CV_Formazione")
identita_id = find_folder(top01, "🪪 Identità")
veicoli_id  = find_folder(top01, "🚗 Veicoli")
legale_id   = find_folder(top01, "📋 Legale_Fiscale")
polizze_id  = find_folder(legale_id, "🛡️ Polizze")
casa_docs_id = find_folder(top02, "📄 Documenti_Generali")

print(f"cv_id={cv_id}")
print(f"identita_id={identita_id}")
print(f"veicoli_id={veicoli_id}")
print(f"polizze_id={polizze_id}")
print(f"casa_docs_id={casa_docs_id}\n")

# ─── Definizione spostamenti ──────────────────────────────────────────────────

MOVES = {
    identita_id: [
        "Certificato_Anagrafico.pdf",
        "Stato_di_Famiglia.pdf",
        "Certificato_di_Residenza.pdf",
    ],
    polizze_id: [
        "Certificato polizza PRP571193026 luglio 2023.pdf",
        "Certificato polizza PRP207163003 Marzo 2025.pdf",
        "Certificato polizza PRP207163003 mar 2025.pdf",
        "674-Certificato di Assicurazione.pdf",
        "Attestato di rischio2026.pdf",
        "Attestato di rischio.pdf",
        "865-Attestato_di_Rischio.pdf",
    ],
    veicoli_id: [
        "Certificato di Rottamazione BP109RT.pdf",
        "certificato di rottamazione Opel corsa bp109rt.pdf",
        "certificato di proprietà GR172LF.pdf",
    ],
    casa_docs_id: [
        "Notifica_SIRA-GPA__Pratica_N°_5951-426_2025_APE_-_Attestato_di_certificazione_energetica_degli_edifici_.pdf",
        "Certificato idoneità abitativa.pdf",
    ],
}

# ─── Esegui spostamenti ───────────────────────────────────────────────────────

DEST_NAMES = {
    identita_id: "🪪 Identità",
    polizze_id: "🛡️ Polizze",
    veicoli_id: "🚗 Veicoli",
    casa_docs_id: "📄 Documenti_Generali (Casa)",
}

total_moved = 0
for dest_id, filenames in MOVES.items():
    dest_name = DEST_NAMES[dest_id]
    print(f"\n→ {dest_name}")
    for fname in filenames:
        fid = find_file(cv_id, fname)
        if not fid:
            print(f"  [NOT FOUND] {fname}")
            continue
        try:
            move(fid, cv_id, dest_id)
            print(f"  ✓ {fname}")
            total_moved += 1
        except HttpError as e:
            print(f"  [ERR] {fname}: {e}")
        time.sleep(0.1)

print(f"\n✅ {total_moved} file spostati da CV_Formazione.")
