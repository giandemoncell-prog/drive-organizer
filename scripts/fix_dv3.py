"""Sposta i file rimanenti in Documenti_Vari."""
import sys, os, certifi, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service
from googleapiclient.errors import HttpError

svc = get_drive_service()

def list_subs(pid):
    r = svc.files().list(
        q=f"'{pid}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}

def load_files(pid):
    items, token = {}, None
    while True:
        kw = dict(q=f"'{pid}' in parents and trashed=false",
                  fields="files(id,name,mimeType)", pageSize=200)
        if token: kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        for f in r.get("files", []):
            if f["mimeType"] != "application/vnd.google-apps.folder":
                items[f["name"]] = f["id"]
        token = r.get("nextPageToken")
        if not token: break
    return items

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

top01 = nmap["01_📂Documenti_Personali"]
top02 = nmap["02_📂Casa_e_Immobili"]
top03 = nmap["03_📂Scuola_e_Didattica"]
top04 = nmap["04_📂Progetti_e_Social"]

subs01 = list_subs(top01); subs02 = list_subs(top02)
subs03 = list_subs(top03); subs04 = list_subs(top04)

dv_id          = subs01["📋 Documenti_Vari"]
veicoli_id     = subs01["🚗 Veicoli"]
cv_id          = subs01["📄 CV_Formazione"]
estero_id      = subs01["🌍 Estero_Visti"]
legale_id      = subs01["📋 Legale_Fiscale"]
legale_subs    = list_subs(legale_id)
polizze_id     = legale_subs["🛡️ Polizze"]
pratiche_id    = legale_subs["⚖️ Pratiche_Legali"]

ristruttura_id = subs02["🔨 Lavori_Ristrutturazione"]
aste_id        = subs02["📑 Aste_e_Vendite"]
documenti_casa = subs02["📄 Documenti_Generali"]

materiali_id    = subs03["📝 Materiali_Didattici"]
pratiche_doc_id = subs03["👨‍🏫 Pratiche_Docente"]

sviluppo_id  = subs04["00_📂Sviluppo_e_Software"]
bvm_id       = subs04["01_📂BachataVibes"]
horizon_id   = subs04.get("🎮 HorizonWorlds_VR")

print("Caricamento file da Documenti_Vari…")
dv_files = load_files(dv_id)
print(f"  {len(dv_files)} file presenti\n")

def move(fid, to_id, name):
    svc.files().update(fileId=fid, addParents=to_id, removeParents=dv_id, fields="id").execute()
    print(f"  ✓ {name}")

MOVES = [
    # Veicoli
    (veicoli_id, [
        "Carta di circolazione Yaris.pdf",
        "atto di vendita Toyota Yaris.pdf",
        "radiazione dal pra opel corsa bp109rt.pdf",
    ]),
    # CV / Formazione
    (cv_id, [
        "libretto esami universitÃ .pdf",
        "esami universitari.txt",
    ]),
    # Polizze
    (polizze_id, [
        "ATR-PRP617406968.pdf",
    ]),
    # Pratiche legali
    (pratiche_id, [
        "Messaggi Angelo Pisu",
        "Tentativo di prenotazione 2024-12-23 08.19.52.png",
        "Tentativo di prenotazione 2024-12-23 08.22.24.png",
        "Lotteria degli scontrini.png",
    ]),
    # Casa – lavori
    (ristruttura_id, [
        "Fattura per demolizione.pdf",
        "quote condominiali 2024.pdf",
        "2023_Immagine_Scansionata.pdf",
    ]),
    # Casa – aste (foto maggio 2025 rimanenti)
    (aste_id, [
        "Foto_2025-04-10.jpg",
        "Foto_2025-05-25_123248.jpg",
        "WhatsApp Video 2024-07-16 at 22.23.39.mp4",
        "Documento_Vario_2025-01-15.pdf",
        "Documento_Vario_2025-09-17.pdf",
    ]),
    # Casa – documenti generali
    (documenti_casa, [
        "Set informativo.pdf",
        "Coldiretti.png",
    ]),
    # Scuola – materiali didattici
    (materiali_id, [
        "01 Analisi dei prodotti multimediali.pdf",
        "Costruisci la tua orchestra LD.pdf",
        "Creazione di un labirinto.pdf",
        "Educazione stradale e comportamenti corretti.pdf",
        "Fuga dalla gabbia.pdf",
        "GEOMETRIA CON SCRATCH.pdf",
        "I luoghi della storia. Tour virtuale interattivo con informazioni storiche e culturali sul territorio.pdf",
        "I poligoni con Scratch 1Â°B LD.pdf",
        "I.A. Sistema muscolare-arti superiori. Fondamentali individuali della pallavolo.pdf",
        "Il Robot disegnatore e pittore (Makeblock Ultimate 2.0).pdf",
        "Il mito.pdf",
        "L'evoluzione umana.pdf",
        "La Miniera tra speranza e disperazione.pdf",
        "La matematica nella natura.pdf",
        "Laboratorio verde.pdf",
        "Lo scambio economico.pdf",
        "OrtoLab.pdf",
        "PD-M5S Robot.pdf",
        "Pensiero computazionale LD.pdf",
        "Progetto Dungeon.pdf",
        "Proiezione Robot.pdf",
        "Proiezione e Robotica.pdf",
        "REALIZZIAMO IL NOSTRO GREEN-LAB ALL'ARIA APERTA.pdf",
        "Robot Vs Man.pdf",
        "SisteMBot.pdf",
        "Sommergibili, segreti e computer.pdf",
        "Tour interno al computer.pdf",
        "Tutorial di geometria 3D.pdf",
        "Viaggio nello spazio sonoro.pdf",
        "polycoding.pdf",
        "robotica e coding sulla luna.pdf",
        "Chiesa di San Michele.pdf",
    ]),
    # Scuola – pratiche docente
    (pratiche_doc_id, [
        "Test di autovalutazione per il tirocinio indiretto (25 ore)",
    ]),
    # Sviluppo e Software
    (sviluppo_id, [
        "Il Ribelle del Giua di Cagliari.pdf",
        "email metaverso.txt",
        "profilo ICC per PC.pdf",
        "profilo ICC.pdf",
        "profilo colore ICC.pdf",
        "Profilo ICC Pigiu Car sas.pdf",
        "Profilo ICC.pdf",
    ]),
]

# Horizon Worlds
if horizon_id:
    MOVES.append((horizon_id, [
        "02 Motion_V71_8_2022.pdf",
        "PlayerManagement-Identification.pdf",
    ]))

total_moved = 0
for dest_id, filenames in MOVES:
    for fname in filenames:
        fid = dv_files.get(fname)
        if not fid:
            continue
        try:
            move(fid, dest_id, fname)
            total_moved += 1
            del dv_files[fname]
        except HttpError as e:
            print(f"  [ERR] {fname}: {e}")
        time.sleep(0.1)

print(f"\n✅ Spostati: {total_moved}")
if dv_files:
    print(f"  File ancora presenti ({len(dv_files)}):")
    for n in sorted(dv_files.keys()):
        print(f"    - {n}")
