# Drive Organizer — Manuale Utente

**Drive Organizer** è un'app che riorganizza automaticamente Google Drive creando una struttura di cartelle leggibile e logica, usando intelligenza artificiale locale e cloud per classificare i file.

> **Manuali specifici per sistema operativo:**
> - [Manuale Windows](docs/MANUALE_WINDOWS.md) — EXE standalone, PowerShell, Inno Setup installer
> - [Manuale macOS](docs/MANUALE_MACOS.md) — binario precompilato, Gatekeeper, Homebrew
> - [Manuale Linux / Chrome OS](docs/MANUALE_LINUX.md) — install.sh, PATH, Crostini, alias

---

## Indice

1. [Requisiti](#1-requisiti)
2. [Installazione](#2-installazione)
3. [Configurazione Google Cloud](#3-configurazione-google-cloud)
4. [Configurazione dell'app](#4-configurazione-dellapp)
5. [Primo avvio](#5-primo-avvio)
6. [Comandi disponibili](#6-comandi-disponibili)
7. [Strategie di organizzazione](#7-strategie-di-organizzazione)
8. [Gestione di più account](#8-gestione-di-più-account)
9. [Rollback — annullare le modifiche](#9-rollback--annullare-le-modifiche)
10. [Come funziona l'AI](#10-come-funziona-lai)
11. [Privacy e sicurezza](#11-privacy-e-sicurezza)
12. [Risoluzione problemi](#12-risoluzione-problemi)

---

## 1. Requisiti

### Versione EXE (per utenti non tecnici)

| Componente | Note |
|---|---|
| Windows 10 / 11 (64-bit) | Nessun Python richiesto |
| Google Account | uno o più account |
| `credentials.json` | scaricato da Google Cloud Console (una volta sola) |
| Anthropic **oppure** Gemini API key | solo per strategie AI (`project`, `custom`) — opzionale |
| Ollama | solo per `rename` e AI locale — opzionale |

### Versione da sorgente (per sviluppatori)

| Componente | Versione minima |
|---|---|
| Python | 3.11+ |
| pip | qualsiasi |

> **Nota:** Le strategie `type` e `date` funzionano senza AI, senza API key e senza Ollama.

---

## 2. Installazione

### Versione EXE — Nessun Python richiesto

1. Copia `drive-organizer.exe` in una cartella a tua scelta (es. `C:\DriveOrganizer\`)
2. Copia `credentials.json` nella **stessa cartella**
3. *(Facoltativo)* Copia `.env.example`, rinominalo `.env` e inserisci le API key
4. Apri il **Prompt dei comandi** o **PowerShell** in quella cartella
5. Digita il primo comando:

```
drive-organizer.exe setup
```

Il wizard guida in 5 passi: provider AI, Google Cloud, credenziali OAuth, login Drive.

**Collegamento sul desktop:** se usi la cartella `D:\DRIVE_ORGANIZER`, è già presente un collegamento *Drive Organizer* sul desktop con l'icona personalizzata. Doppio clic per aprire PowerShell direttamente nella cartella dell'app.

---

### Versione da sorgente (sviluppatori)

```bash
cd D:\DRIVE_ORGANIZER
pip install -r requirements.txt
python main.py setup
```

**Disinstallazione pacchetti:**
```bash
build\uninstall_packages.bat
```

---

## 3. Configurazione Google Cloud

Questo passaggio va fatto **una volta sola**. Le credenziali ottenute funzionano con qualsiasi account Google.

### 3.1 Crea un progetto Google Cloud

1. Vai su [console.cloud.google.com](https://console.cloud.google.com)
2. In alto a sinistra: menu a tendina progetto → **New Project**
3. Nome: `Drive Organizer` → **Create**

### 3.2 Abilita Google Drive API

1. Menu → **APIs & Services → Library**
2. Cerca `Google Drive API` → clicca → **Enable**

### 3.3 Configura la schermata di consenso OAuth

1. Menu → **APIs & Services → OAuth consent screen**
2. **User Type: External** → **Create**
3. Compila i campi obbligatori:
   - **App name:** `Drive Organizer`
   - **User support email:** la tua email
   - **Developer contact information:** la tua email
4. **Save and Continue**
5. Nella sezione **Scopes**: clicca **Add or Remove Scopes**
   - Cerca `drive` → seleziona `https://www.googleapis.com/auth/drive`
   - **Update** → **Save and Continue**
6. Nella sezione **Test users**: clicca **Add Users**
   - Aggiungi gli indirizzi Gmail degli account che vuoi usare
   - **Save and Continue**
7. **Back to Dashboard**

> In modalità "Testing" solo gli utenti che aggiungi qui possono autenticarsi. Puoi aggiungere fino a 100 account. Per uso personale o professionale la modalità Testing è sufficiente.

### 3.4 Crea le credenziali OAuth

1. Menu → **APIs & Services → Credentials**
2. **+ Create Credentials → OAuth 2.0 Client ID**
3. **Application type: Desktop app**
4. **Name:** `Drive Organizer CLI` → **Create**
5. Nella finestra che appare: **Download JSON**
6. Rinomina il file scaricato in `credentials.json`
7. Salvalo nella stessa cartella dell'eseguibile

---

## 4. Configurazione dell'app

Crea il file `.env` copiando il template:

```bash
# Windows (Prompt dei comandi)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Apri `.env` con Blocco Note e imposta i valori:

```env
# Provider AI cloud (scegli uno dei due, o lascia vuoti per usare solo Ollama)
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# Ollama — modifica solo se usi un modello diverso da qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Soglie di confidenza AI (non modificare se non sai cosa fanno)
OLLAMA_CONFIDENCE_THRESHOLD=0.75
HAIKU_CONFIDENCE_THRESHOLD=0.80

# Massimo file inviati ai modelli cloud per run (controllo costi)
MAX_CLOUD_ESCALATIONS=200
```

Per le strategie `type` e `date` puoi lasciare tutte le chiavi vuote.

---

## 5. Primo avvio

### Autenticazione

```
drive-organizer.exe auth
```

Il browser si apre automaticamente con la schermata di login Google. Accedi con l'account che vuoi organizzare. Dopo aver autorizzato, il token viene salvato in `tokens/{tua-email}.json` e non dovrai ripetere il login.

Se il browser non si apre automaticamente, copia l'URL mostrato nel terminale e incollalo manualmente.

### Verifica connessione

```
drive-organizer.exe status
```

Mostra:
- Account connesso e spazio Drive usato
- Stato Ollama (raggiungibile / non raggiungibile)
- Stato API key (Anthropic o Gemini)
- Conteggio file per tipo

---

## 6. Comandi disponibili

### `setup` — Wizard primo avvio

```
drive-organizer.exe setup
```

Guida interattiva in 5 passi. Da eseguire una sola volta per ogni installazione.

---

### `auth` — Autenticazione

```
drive-organizer.exe auth
drive-organizer.exe auth --account mario@gmail.com
```

Apre il browser per autenticarsi. Il token viene rinnovato automaticamente.

---

### `accounts` — Lista account autenticati

```
drive-organizer.exe accounts
```

Mostra tutti gli account con token salvato.

---

### `status` — Statistiche Drive

```
drive-organizer.exe status
drive-organizer.exe status --account mario@gmail.com
```

Mostra spazio usato, numero di file per tipo e stato AI.

---

### `organize` — Organizza il Drive

```
drive-organizer.exe organize [opzioni]
```

| Opzione | Breve | Descrizione |
|---|---|---|
| `--strategy` | `-s` | Strategia: `type`, `date`, `project`, `custom` |
| `--apply` | — | Esegue le modifiche (senza: solo preview) |
| `--account` | `-a` | Account Google da usare |
| `--custom-prompt` | `-p` | Descrizione struttura (con `--strategy custom`) |
| `--taxonomy-file` | `-t` | File JSON tassonomia pre-costruita (offline, senza AI) |
| `--no-haiku` | — | Salta Haiku/Gemini Flash, va diretto a Opus/Gemini Pro |
| `--year-only` | — | Per `date`: organizza solo per anno, senza mese |
| `--ollama-model` | — | Override modello Ollama per questa run |

**Senza `--apply`** mostra solo un'anteprima (dry-run). Nessun file viene spostato.

---

### `rename` — Rinomina file con AI locale

```
drive-organizer.exe rename
drive-organizer.exe rename --apply
drive-organizer.exe rename --limit 50 --min-confidence 0.7
```

Analizza i nomi dei file con Ollama e propone nomi più descrittivi. Il contenuto dei file non viene mai scaricato né inviato al cloud — solo il nome, il tipo e la dimensione vengono elaborati localmente.

| Opzione | Descrizione |
|---|---|
| `--apply` | Applica le rinomina (senza: solo preview) |
| `--limit N` | Analizza solo i primi N file |
| `--min-confidence` | Soglia minima confidenza (default 0.65) |

> **Requisito:** Ollama in esecuzione con `ollama serve`.

---

### `rename-rollback` — Annulla rinomina

```
drive-organizer.exe rename-rollback
```

Mostra la lista delle sessioni di rinomina e permette di ripristinare i nomi originali.

---

### `duplicates` — Trova e archivia duplicati

```
drive-organizer.exe duplicates
drive-organizer.exe duplicates --apply
drive-organizer.exe duplicates --archive-folder "99_Archivio/Duplicati"
```

Trova file duplicati per contenuto identico (md5) e per nome simile (es. "file (1)", "Copia di file"). I duplicati vengono spostati in archivio, non eliminati.

| Opzione | Descrizione |
|---|---|
| `--apply` | Sposta i duplicati in archivio |
| `--archive-folder` | Cartella destinazione (default: `99_Archivio/Duplicati`) |

Durante la preview puoi marcare gruppi come **eccezioni** per tenerli tutti.

---

### `rollback` — Annulla organizzazione

```
drive-organizer.exe rollback
```

Riporta i file nelle posizioni originali dopo un `organize --apply`.

---

## 7. Strategie di organizzazione

### `type` — Per tipo di file (senza AI)

```
drive-organizer.exe organize -s type
drive-organizer.exe organize -s type --apply
```

| Cartella | Contiene |
|---|---|
| Documenti | .doc, .docx, Google Docs, .md |
| Fogli | .xls, .xlsx, Google Sheets, .csv |
| Presentazioni | .ppt, .pptx, Google Slides |
| PDF | .pdf |
| Immagini | .jpg, .png, .gif, .webp, .heic… |
| Video | .mp4, .mov, .avi, .mkv… |
| Audio | .mp3, .wav, .flac, .aac… |
| Archivi | .zip, .rar, .tar, .7z… |
| Codice | .py, .js, .ts, .java, .go, .sql… |
| Testo | .txt |
| Altro | tutto il resto |

---

### `date` — Per data di modifica (senza AI)

```
drive-organizer.exe organize -s date
drive-organizer.exe organize -s date --year-only
drive-organizer.exe organize -s date --apply
```

Crea cartelle `Anno/Mese` (es. `2024/Marzo`) o solo `Anno` con `--year-only`.

---

### `project` — Per progetto/argomento (AI)

```
drive-organizer.exe organize -s project
drive-organizer.exe organize -s project --apply
```

Raggruppa semanticamente i file per progetto. Cartelle predefinite:

`Lavoro` · `Personale` · `Finanza` · `Viaggi` · `Foto` · `Video` · `Sviluppo` · `Clienti` · `Fatture` · `Contratti` · `Formazione` · `Altro`

> Richiede Ollama attivo oppure una API key nel `.env`.

---

### `custom` — Struttura personalizzata (AI)

```
# Descrizione inline
drive-organizer.exe organize -s custom -p "Dividi per cliente: Acme, Beta, Gamma. Fatture separate."

# Con file tassonomia JSON (nessuna AI necessaria)
drive-organizer.exe organize -s custom -t taxonomy_custom.json
```

Con `-t taxonomy.json` classifica i file usando un file di tassonomia pre-costruito: nessuna API key necessaria, funziona offline.

> Con `-p` richiede ANTHROPIC_API_KEY o GEMINI_API_KEY.

---

## 8. Gestione di più account

```
# Autentica più account
drive-organizer.exe auth
drive-organizer.exe auth --account lavoro@azienda.com

# Vedi account attivi
drive-organizer.exe accounts

# Usa un account specifico
drive-organizer.exe organize -s type --account lavoro@azienda.com
drive-organizer.exe status --account mario@gmail.com
```

Se c'è un solo account viene selezionato automaticamente. Con più account, senza `--account` ti chiede di scegliere.

---

## 9. Rollback — annullare le modifiche

Ogni `organize --apply` o `duplicates --apply` crea automaticamente un file di rollback in `logs/`.

```
drive-organizer.exe rollback
```

Vedrai una tabella con le sessioni disponibili:

```
┌───┬──────────┬───────────┬─────────────────────┬────────────┐
│ # │ Run ID   │ Strategia │ Data                │ File mossi │
├───┼──────────┼───────────┼─────────────────────┼────────────┤
│ 1 │ a3f2b1c8 │ type      │ 2025-06-01 14:32    │ 247        │
│ 2 │ 7d9e4a12 │ project   │ 2025-05-28 09:15    │ 83         │
└───┴──────────┴───────────┴─────────────────────┴────────────┘
```

Scegli il numero della sessione da annullare.

> Le cartelle create durante l'organizzazione **non vengono eliminate** dal rollback — solo i file vengono riportati nelle posizioni originali.

Per annullare una rinomina:
```
drive-organizer.exe rename-rollback
```

---

## 10. Come funziona l'AI

### Cascade a tre livelli

Quando una strategia richiede AI (`project`, `custom`), ogni file passa attraverso una catena di modelli. Sale al livello successivo solo se la confidenza è troppo bassa:

```
File
 │
 ├─ Classificazione deterministica?
 │   └─ Sì → confidenza 1.0 (fine)
 │
 ├─ Ollama locale (gratuito, privato)
 │   └─ confidenza ≥ 0.75 → fine
 │   └─ confidenza < 0.75 → escalation
 │
 ├─ Claude Haiku 4.5  oppure  Gemini 2.0 Flash  (cloud, solo metadati)
 │   └─ se concorda con Ollama: +10% confidenza
 │   └─ confidenza ≥ 0.80 → fine
 │   └─ confidenza < 0.80 → escalation
 │
 └─ Claude Opus 4.8  oppure  Gemini 2.5 Pro  (cloud, solo metadati)
     └─ risposta finale
```

Il provider cloud dipende dalla API key configurata nel `.env`:
- `ANTHROPIC_API_KEY` → usa Claude Haiku 4.5 e Claude Opus 4.8
- `GEMINI_API_KEY` → usa Gemini 2.0 Flash e Gemini 2.5 Pro
- Nessuna chiave → solo Ollama; se Ollama è offline, tutti i file vanno in `Altro`

**Cache:** file con la stessa estensione e tipo MIME usano il risultato già calcolato — evita chiamate duplicate.

**Budget cap:** dopo 200 file inviati al cloud (configurabile con `MAX_CLOUD_ESCALATIONS`), i rimanenti vanno in `Altro` senza ulteriori chiamate.

### Controllo costi

La maggior parte dei file viene classificata da Ollama (gratuito). Solo i file ambigui raggiungono il cloud. Per un Drive con 1000 file tipici, meno del 20% raggiunge Haiku/Gemini Flash.

Per ridurre ulteriormente i costi:
- Usa `--no-haiku` per saltare il livello intermedio
- Riduci `MAX_CLOUD_ESCALATIONS` nel `.env`
- Usa strategie deterministiche (`type`, `date`) per grandi volumi

---

## 11. Privacy e sicurezza

### Cosa viene inviato al cloud

I modelli cloud (Haiku, Opus, Gemini) ricevono **solo metadati**:
- Nome del file
- Tipo MIME / estensione
- Dimensione in byte
- Data dell'ultima modifica

Il **contenuto** dei file non viene mai scaricato né inviato. Questa è una garanzia strutturale dell'architettura.

La funzione `rename` usa **solo Ollama locale**: nessun dato raggiunge il cloud in nessun caso.

### Cosa resta locale

- Contenuto di tutti i file (mai scaricato)
- Token di autenticazione Google (`tokens/`)
- Manifest di rollback (`logs/`)
- API key (`/env`)

### Permessi Google Drive

L'app richiede `https://www.googleapis.com/auth/drive` per spostare i file. Non accede a Gmail, Calendar o altri servizi Google.

Puoi revocare i permessi in qualsiasi momento da [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

---

## 12. Risoluzione problemi

### `credentials.json non trovato`

Il file `credentials.json` deve trovarsi nella stessa cartella dell'eseguibile. Segui la sezione [3. Configurazione Google Cloud](#3-configurazione-google-cloud).

### `Errore 403: access_denied` durante il login Google

Il tuo account non è nella lista degli utenti di test. Vai su Google Cloud Console → **APIs & Services → OAuth consent screen** → **Test users** → aggiungi la tua email → Salva. Poi riprova `auth`.

### Il browser non si apre durante `auth`

Copia l'URL che appare nel terminale e aprilo manualmente nel browser.

### `Ollama non raggiungibile`

Avvia Ollama:
```
ollama serve
```
E verifica che il modello sia scaricato:
```
ollama pull qwen3:8b
```
Le strategie `type` e `date` funzionano anche senza Ollama.

### Nessuna API key configurata

Senza API key le strategie `project` e `custom` classificano tutto in `Altro`. Aggiungi nel `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
oppure:
```
GEMINI_API_KEY=AIza...
```

### Errore 429 (troppe richieste) durante l'organizzazione

Drive API ha limiti di frequenza. L'app gestisce automaticamente i retry. Se l'errore persiste, aspetta qualche minuto e riprova.

### Il rollback non ha ripristinato tutti i file

Alcuni file potrebbero essere stati spostati o eliminati manualmente dopo l'organizzazione. Il rollback salta i file che non trova e riporta quanti ne ha ripristinati.

### Caratteri strani o errore Unicode nel terminale Windows

Usa **Windows Terminal** invece del Prompt dei comandi classico: supporta Unicode nativamente.

### Come verificare prima di applicare

Esegui sempre senza `--apply` prima:
```
drive-organizer.exe organize -s type
```
Leggi il pannello DOPO e conferma che la struttura proposta sia quella desiderata. Solo allora aggiungi `--apply`.

---

## Riferimento rapido comandi

```
# Setup iniziale
drive-organizer.exe setup                                   — wizard primo avvio
drive-organizer.exe auth                                    — login Google
drive-organizer.exe status                                  — statistiche Drive

# Organizzazione (preview → poi --apply per eseguire)
drive-organizer.exe organize -s type                        — per tipo file
drive-organizer.exe organize -s date                        — per data (Anno/Mese)
drive-organizer.exe organize -s date --year-only            — per anno
drive-organizer.exe organize -s project                     — per argomento (AI)
drive-organizer.exe organize -s custom -t taxonomy.json     — tassonomia da file
drive-organizer.exe organize -s custom -p "descrizione"     — struttura libera (AI)
drive-organizer.exe organize -s type --apply                — applica

# Rinomina (richiede Ollama)
drive-organizer.exe rename                                  — preview rinomina
drive-organizer.exe rename --apply                          — applica
drive-organizer.exe rename-rollback                         — annulla rinomina

# Duplicati
drive-organizer.exe duplicates                              — trova duplicati
drive-organizer.exe duplicates --apply                      — archivia duplicati

# Multi-account
drive-organizer.exe accounts                                — lista account
drive-organizer.exe auth --account altro@gmail.com          — nuovo account
drive-organizer.exe organize -s type -a altro@gmail.com

# Rollback
drive-organizer.exe rollback                                — annulla organizzazione
```
