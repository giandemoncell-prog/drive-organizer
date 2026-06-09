"""
Sposta da 01_📂Documenti_Personali/📋 Documenti_Vari i file
nelle cartelle corrette (anche in 02_, 03_, 04_).
"""
import sys, os, certifi, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

sys.path.insert(0, "D:/DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service
from googleapiclient.errors import HttpError

svc = get_drive_service()

# ─── helpers ──────────────────────────────────────────────────────────────────

def list_subs(pid):
    r = svc.files().list(
        q=f"'{pid}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}

def find_folder(pid, name):
    subs = list_subs(pid)
    if name in subs:
        return subs[name]
    raise FileNotFoundError(f"Cartella '{name}' non trovata in {pid}")

def find_file(pid, name):
    r = svc.files().list(
        q=f"'{pid}' in parents and name='{name}' and trashed=false",
        fields="files(id,name)", pageSize=5,
    ).execute()
    hits = r.get("files", [])
    return hits[0]["id"] if hits else None

def move(fid, from_p, to_p):
    svc.files().update(fileId=fid, addParents=to_p, removeParents=from_p, fields="id").execute()

# ─── Mappa cartelle root ──────────────────────────────────────────────────────

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute()
nmap = {f["name"]: f["id"] for f in r.get("files", [])}

top01 = nmap["01_📂Documenti_Personali"]
top02 = nmap["02_📂Casa_e_Immobili"]
top03 = nmap["03_📂Scuola_e_Didattica"]
top04 = nmap["04_📂Progetti_e_Social"]

subs01 = list_subs(top01)
subs02 = list_subs(top02)
subs03 = list_subs(top03)
subs04 = list_subs(top04)

dv_id        = subs01["📋 Documenti_Vari"]
identita_id  = subs01["🪪 Identità"]
veicoli_id   = subs01["🚗 Veicoli"]
estero_id    = subs01["🌍 Estero_Visti"]
legale_id    = subs01["📋 Legale_Fiscale"]
lavoro_id    = subs01.get("💼 Lavoro")

legale_subs  = list_subs(legale_id)
pratiche_id  = legale_subs["⚖️ Pratiche_Legali"]
polizze_id   = legale_subs["🛡️ Polizze"]
fisco_id     = legale_subs["🏦 Fisco_e_Tasse"]

ristruttura_id = subs02["🔨 Lavori_Ristrutturazione"]
aste_id        = subs02["📑 Aste_e_Vendite"]
documenti_casa = subs02["📄 Documenti_Generali"]
bollette_id    = subs02["💡 Bollette_Utenze"]
santantioco_id = subs02["🏠 Sant'Antioco"]

dsa_id         = subs03["🎓 DSA_BES"]
materiali_id   = subs03["📝 Materiali_Didattici"]
pratiche_doc_id= subs03["👨‍🏫 Pratiche_Docente"]
libro_id       = subs03["📚 Libro_IA_KDP"]

bvm_id         = subs04["01_📂BachataVibes"]
sviluppo_id    = subs04["00_📂Sviluppo_e_Software"]
horizon_id     = subs04.get("🎮 HorizonWorlds_VR")
automazioni_id = subs04.get("03_📂Automazioni_Social")

print(f"dv_id={dv_id}\n")

# ─── Piani di spostamento ────────────────────────────────────────────────────

MOVES = [

    # == IDENTITÀ ==
    (identita_id, "🪪 Identità", [
        "ts Demontis Gianluca 2031",
        "Puoi compilare questo formulario con i miei dati.pdf",
    ]),

    # == VEICOLI ==
    (veicoli_id, "🚗 Veicoli", [
        "Carta Verde.pdf",
        "BP109RT Cessazione dalla Circolazione.pdf",
    ]),

    # == ESTERO / VISTI ==
    (estero_id, "🌍 Estero_Visti", [
        "Permesso di Soggiorno I21550196.jpeg",
        "PermessoProvvisorio.pdf",
        "AUTOCERTIFICAZIONE Frequenza corsi di Italiano",
        "progetto estero.docx",
        "ricevuta arcoiris.pdf",
        "Sintesi della situazione attuale.docx.pdf",
    ]),

    # == PRATICHE LEGALI ==
    (pratiche_id, "⚖️ Pratiche_Legali", [
        "DENUNCIA-QUERELA PER FURTO DI IDENTITÀ E TENTATA FRODE AGGRAVATA",
        "Messaggi e chiamate truffa bbva",
        "Messaggi e chiamate truffa bbva.pdf",
        "Messaggi01.jpeg",
        "Messaggi02.jpeg",
        "Messaggi 03.jpeg",
        "Lista chiamate entrata e uscita.jpeg",
        "Accesso al conto tramite altro dispositivo.png",
        "bbva.pdf",
        "postacert.eml",
        "ricevuta.pdf",
        "Segnatura.xml",
        "daticert.xml",
        "Delibera_CC_5-2012_07_09.pdf",
        "MODCLI031R3 Accesso agli atti.pdf",
        "MODCLI031R3_ACCESSO AGLI ATTI_firmato.pdf",
    ]),

    # == FISCO E TASSE ==
    (fisco_id, "🏦 Fisco_e_Tasse", [
        "ricevuta pagamento.pdf",
        "istruzioni per il pagamento.pdf",
        "Modello 790-012.pdf",
        "ordine-2510001700.pdf",
    ]),

    # == CASA – LAVORI RISTRUTTURAZIONE ==
    (ristruttura_id, "🔨 Lavori_Ristrutturazione", [
        "Porta_Blindata_Tunisi_5-7-9_Foglio_Tecnico.pdf",
        "Preventivo_171_Gianluca_Demontis.pdf",
        "Preventivo_171_DEMONTIS_GIANLUCA.pdf",
        "Preventivo.pdf",
        "documentazione_fotografica_balcone.pdf",
        "Corridoio tecnico per impianti e pluviali.",
        "Elenco lavori da fare",
        "Rilievi Porte",
        "Fattura porta blindata.pdf",
        "Fattura-144_2025-DEMONTIS-GIANLUCA.pdf",
        "Fattura-142_2025-DEMONTIS-GIANLUCA.pdf",
        "Fattura-230-DEMONTIS GIANLUCA (1).pdf",
        "Fattura-230-DEMONTIS GIANLUCA.pdf",
        "Bonifico.pdf",
        "scontrino deumidificatore.pdf",
        "Dichiarazione Di Rispondenza - Impianto Elettrico - Demontis.pdf",
        "serratura installata.pdf",
        "Infiltrazioni.pdf",
        "Condominio_Saldo_2024.pdf",
        "Quote condominiali 2024 Acconto (1 semestre).pdf",
        "Quote condominiali 2024 Saldo.pdf",
        "LetteraSicurezzaLavoroDomestico.pdf",
        "Via Bolzano 20 Facciata-1.jpeg",
        "Via Bolzano 20 Facciata-2.jpeg",
        "Via Bolzano 20 Facciata-3.jpeg",
        "Misura umidità 30 agosto 2024 alle 191954.jpeg",
        "Misura di umidità 2024-08-30 alle 19.20.56.jpeg",
        "Misura di umidità 2024-08-30 alle 19.22.06.jpeg",
        "Misura di umidità 2024-08-30 alle 192253.jpeg",
        "Immagine WhatsApp 2024-09-02 alle 21.45.30.jpeg",
        "WhatsApp Image 2024-09-03 at 20.14.03.jpeg",
        "Umidità sopra l'armadio sotto il climatizzatore2024-09-03 at 20.13.48.jpeg",
        "Umidità sopra l'armadio sotto il climatizzatore2024-09-03 at 20.13.10.jpeg",
        "Umidità sopra l'armadio sotto il climatizzatore2024-09-03 at 20.12.55.jpeg",
        "Bagno adiacente Disimpegno 2024-08-26 at 14.41.01.jpeg",
        "Misura di umidità 2024-08-30 at 19.19.19.jpeg",
        "Misura di umidità 2024-08-30 at 19.19.12.jpeg",
        "Misura di umidità 2024-08-30 at 19.18.44.jpeg",
        "Misura di umidità 2024-08-30 at 19.18.31.jpeg",
        # Foto 30 giugno 2025 (visita immobile/lavori)
        "Foto_2025-06-30_1140.jpg",
        "Foto_2025-06-30_1137.jpg",
        "Foto_2025-05-25_1232.jpg",
        "30 giugno 2025 18.52.jpg",
        "Foto_2025-06-30_18.51.42.jpg",
        "Foto_2025-06-30_11.49.25.jpg",
        "30 giugno 2025 1146.jpg",
        "30 giugno 2025 114512.jpg",
        "30 giugno 2025 1142.jpg",
        "30 giugno 2025 113644.jpg",
    ]),

    # == CASA – ASTE E VENDITE ==
    (aste_id, "📑 Aste_e_Vendite", [
        "FatturaTerreno edificabile 2001.pdf",
        "2063033_c_planimetria.pdf",
        "2063034_c_perizia.pdf",
        "2063045_c_avviso_di_vendita.pdf",
        "Via E Pais.pdf",
        "Manuale_utente_Offerta_Telematica_vp1.1.pdf",
        "offerta (1).pdf",
        "offerta.pdf",
        "offertaintegrale.xml.p7m",
        "Spese Vendita Via Bolzano 20 e Terreno",
        # Foto visite immobili (maggio 2025)
        "PXL_10-04-2025_075009926.jpg",
        "Foto 05-04-2025 0835.jpg",
        "25_maggio_2025_12_22_56.jpg",
        "25-05-2025 1223 5f7c89f6.jpg",
        "25 maggio 2025 122554.jpg",
        "25-05-2025_12-26-25_18f61077.jpg",
        "25-05-2025_1226_2e82cf1b.jpg",
        "Foto 25-05-2025 1226.jpg",
        "25 Maggio 2025 12-26-34.jpg",
        "25-maggio-2025_12-26-36.jpg",
        "25 maggio 2025 122638 da93d0ad.jpg",
        "Foto_25_maggio_2025_12.29.47.jpg",
        "25-05-2025_12-32.jpg",
        "Foto_25-05-2025_12-32.jpg",
        "25-05-2025_12-32-48.jpg",
        "Foto_25-05-2025_12.32.jpg",
        "Foto_25-maggio-2025_1233.jpg",
        "Foto 25-maggio-2025 12.34.20 98d4e144.jpg",
        "Foto_25-05-2025_12-42-52.jpg",
        "Foto_25-maggio-2025_125130.jpg",
        "25-05-2025 130537 d0627914.jpg",
        "25 maggio 2025 130555.jpg",
        "25 maggio 2025 130608_9ea81008.jpg",
        "Foto_25-maggio-2025_13.09.jpg",
        "Foto Aereo.jpeg",
    ]),

    # == CASA – DOCUMENTI GENERALI ==
    (documenti_casa, "📄 Documenti_Generali (Casa)", [
        "IBAN PAGAMENTI CASA E TERRENO.txt",
        "INQUADRAMENTO ortografico.pdf",
        "planimetria con misure.pdf",
        "visura via Bolzano 20.pdf",
        "ADDEBITO RLI-01-03 16.40.41.png",
        "26139607_1_RLI12.pdf",
        "tav.pdf",
        "Prospetto_Affitti_Via_Nazionale",
        "VENDITE E DONAZIONI",
        "Indagine Imprese Edili Facciate Sant'Antioco",
    ]),

    # == CASA – BOLLETTE ==
    (bollette_id, "💡 Bollette_Utenze", [
        "Contatore1.jpeg",
        "Contatore2.jpeg",
        "Foto Punto Fornitura Senza Contatore.jpg",
        "a2a spa_11_2024.pdf",
    ]),

    # == CASA – SANT'ANTIOCO ==
    (santantioco_id, "🏠 Sant'Antioco", [
        "APE_SANT_ANTIOCO_F13PART11SUB1.pdf",
        "SIRA Parte 2 - Strumenti GPA.pdf",
        "Spese Via Nora Sant'Antioco",
    ]),

    # == SCUOLA – DSA/BES ==
    (dsa_id, "🎓 DSA_BES", [
        "Verifica finale PEI sez.11 (pag.11-12) LA27MP030111 (firmato)",
        "firme PEI 1D Marghinotti.pdf",
        "Intervista allo studente",
    ]),

    # == SCUOLA – MATERIALI DIDATTICI ==
    (materiali_id, "📝 Materiali_Didattici", [
        "Privacy e Sicurezza Dati.pdf",
        "03 Comunicare_collaborare_in_Rete.pdf",
        "02 Navigare_e_cercare_informazioni_sul_Web.pdf",
        "le donne nella preistoria.pdf",
        "EX15_Demontis_Gianluca.docx",
        "La Mesopotamia - La Terra tra i Due Fiumi",
    ]),

    # == SCUOLA – PRATICHE DOCENTE ==
    (pratiche_doc_id, "👨‍🏫 Pratiche_Docente", [
        "circ. n. 240 Richieste part time a.s.2026-2027.pdf",
        "all. circ. n. 240 Domanda_part-time o rientro a tempo pieno DOCENTI A.S. 2026-2027.docx",
        "modello-domanda-1 vecchio USP CAGLIARI.docx",
        "Come compilare la domanda.pdf",
        "Titoli di precedenza previsti dall'ar.pdf",
        "Richiesta nulla osta per partecipazione educatrice Dott.ssa Cuccu Rossella.pdf",
        "Richiesta nulla osta per partecipazione educatrice Dott.ssa Cuccu Rossella.docx",
        "verbale di restituzione Cts Cagliari.pdf",
        "Biglietti Ritorno.pdf",
        "Biglietti Andata.pdf",
    ]),

    # == SCUOLA – LIBRO KDP ==
    (libro_id, "📚 Libro_IA_KDP", [
        "07_lead_magnet.pdf",
    ]),

    # == PROGETTI – BACHATA VIBES ==
    (bvm_id, "01_📂BachataVibes", [
        "post_02_mambo_inferno.jpg",
        "post_04_te_fuiste.jpg",
        "reel_01_bailando_playa.mp4",
        "reel_02_mambo_inferno.mp4",
        "reel_03_brisa.mp4",
        "storia_01_entre_copas.mp4",
        "storia_02_entre_sombras.mp4",
        "storia_03_mambo_v2.mp4",
        "media.mp4",
    ]),

    # == PROGETTI – SVILUPPO E SOFTWARE ==
    (sviluppo_id, "00_📂Sviluppo_e_Software", [
        "manuale_linux_chrome_os.md",
        "flask-web.py",
        "Organizzatore Drive.desktop",
        "ISTRUZIONI_ACCESSO_REMOTO_WINDOWS_DA_CHROMEBOOK.txt",
        "index.html",
        ".env.example",
        "comandi-remoto.txt",
        "Office e Windows 10 Enterprise.txt",
        "Generazione Salsa per Radio Automatica",
        "Configurazione e Verifica Raspberry Pi 5",
        "Anno Zero - Cronache del Dopo.docx",
        "Anno Zero - Cronache del Dopo.pdf",
        "AnnoZero_Cronache_del_Dopo_V2.pdf",
        "Struttura del Romanzo (V.3 da rivedere)",
        "Struttura del Romanzo (V.2)",
        "Struttura del Romanzo (V.2).docx",
        "Romanzo distopico.docx",
        "Il fantasy.pdf",
        "Creazione_Video_per_Social_Media (1).mp4",
        "Creazione_Video_per_Social_Media.mp4",
    ]),
]

# Horizon Worlds (solo se la cartella esiste)
if horizon_id:
    MOVES.append((horizon_id, "🎮 HorizonWorlds_VR", [
        "EventoAggiornamento_22luglio2022.pdf",
        "Guida di Riferimento Spawning Asset_7_11_2022.pdf",
        "01 Eventi_V71_8_2022.pdf",
        "Variabili_V71_8_2022.pdf",
        "Riferimento Tecnico Prestazioni Giocatori 11-ago-2022.pdf",
    ]))

# ─── Esegui spostamenti ───────────────────────────────────────────────────────

total_moved = 0
total_not_found = 0

for dest_id, dest_label, filenames in MOVES:
    print(f"\n→ {dest_label} ({len(filenames)} file)")
    for fname in filenames:
        fid = find_file(dv_id, fname)
        if not fid:
            print(f"  [skip] {fname}")
            total_not_found += 1
            continue
        try:
            move(fid, dv_id, dest_id)
            print(f"  ✓ {fname}")
            total_moved += 1
        except HttpError as e:
            print(f"  [ERR] {fname}: {e}")
        time.sleep(0.1)

print(f"\n{'='*60}")
print(f"✅ Spostati: {total_moved} | Non trovati/già mossi: {total_not_found}")
