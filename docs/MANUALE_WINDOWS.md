# Drive Organizer — Manuale Windows

**Sistema operativo:** Windows 10 / 11 (64-bit)  
**Versione app:** 1.0.0

---

## Indice

1. [Requisiti](#1-requisiti)
2. [Installazione rapida (EXE)](#2-installazione-rapida-exe)
3. [Installazione da sorgente (sviluppatori)](#3-installazione-da-sorgente-sviluppatori)
4. [Configurazione Google Cloud](#4-configurazione-google-cloud)
5. [Configurazione API AI (opzionale)](#5-configurazione-api-ai-opzionale)
6. [Primo avvio e autenticazione](#6-primo-avvio-e-autenticazione)
7. [Comandi disponibili](#7-comandi-disponibili)
8. [Strategie di organizzazione](#8-strategie-di-organizzazione)
9. [Rinomina file con AI](#9-rinomina-file-con-ai)
10. [Gestione duplicati](#10-gestione-duplicati)
11. [Rollback — annullare le modifiche](#11-rollback--annullare-le-modifiche)
12. [Gestione più account Google](#12-gestione-più-account-google)
13. [Come funziona l'AI](#13-come-funziona-lai)
14. [Privacy e sicurezza](#14-privacy-e-sicurezza)
15. [Risoluzione problemi](#15-risoluzione-problemi)
16. [Riferimento rapido comandi](#16-riferimento-rapido-comandi)

---

## 1. Requisiti

| Componente | Dettaglio |
|---|---|
| Windows 10 / 11 (64-bit) | versione EXE: nessun Python richiesto |
| Google Account | uno o più account Gmail / Workspace |
| `credentials.json` | scaricato una volta da Google Cloud Console |
| API key Anthropic **o** Gemini | opzionale — solo per strategie AI (`project`, `custom`) |
| Ollama | opzionale — solo per `rename` e classificazione locale |

> **Le strategie `type` e `date` funzionano senza AI, senza API key e senza internet** (eccetto la connessione Google Drive).

---

## 2. Installazione rapida (EXE)

### 2.1 Scarica e posiziona i file

1. Scarica `drive-organizer.exe` dalla [pagina Releases su GitHub](https://github.com/giandemoncell-prog/drive-organizer/releases)
2. Crea una cartella dedicata, es. `C:\DriveOrganizer\`
3. Copia `drive-organizer.exe` nella cartella
4. Copia `credentials.json` nella **stessa cartella** (vedi sezione 4)
5. *(Facoltativo)* Copia `.env.example`, rinominalo `.env` e inserisci le API key

La struttura cartella deve essere:
```
C:\DriveOrganizer\
├── drive-organizer.exe   ← eseguibile principale
├── credentials.json      ← credenziali Google Cloud (obbligatorio)
├── .env                  ← API key (opzionale)
└── taxonomy_custom.json  ← tassonomia personalizzata (opzionale)
```

### 2.2 Apri il terminale nella cartella

**Metodo 1 — Esplora file:**  
Apri la cartella → barra degli indirizzi → digita `cmd` → Invio

**Metodo 2 — PowerShell:**  
Apri la cartella → tasto Shift + clic destro nello spazio vuoto → "Apri finestra PowerShell qui"

**Metodo 3 — Windows Terminal (consigliato):**  
Installa [Windows Terminal](https://aka.ms/terminal) dal Microsoft Store per la migliore compatibilità Unicode.

### 2.3 Esegui il setup guidato

```
drive-organizer.exe setup
```

Il wizard guida in 5 passi: configurazione AI, percorso credenziali, verifica Google Drive.

---

## 3. Installazione da sorgente (sviluppatori)

### 3.1 Prerequisiti

- Python 3.11+ ([python.org](https://python.org)) — spunta **"Add Python to PATH"** durante l'installazione
- Git ([git-scm.com](https://git-scm.com))

### 3.2 Setup con script automatico

```batch
git clone https://github.com/giandemoncell-prog/drive-organizer.git
cd drive-organizer
install_dev.bat
```

`install_dev.bat` crea un ambiente virtuale `.venv`, installa tutte le dipendenze e copia `.env.example` → `.env`.

### 3.3 Setup manuale

```batch
git clone https://github.com/giandemoncell-prog/drive-organizer.git
cd drive-organizer
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python main.py setup
```

### 3.4 Avvio in ambiente di sviluppo

```batch
.venv\Scripts\activate
python main.py COMANDO
```

### 3.5 Build EXE Windows

```batch
build\build_windows.bat
```

Produce `dist_windows\drive-organizer.exe` (circa 60 MB, standalone).

### 3.6 Disinstallazione pacchetti

```batch
build\uninstall_packages.bat
```

---

## 4. Configurazione Google Cloud

> **Da fare una sola volta.** Le credenziali funzionano con qualsiasi account Google.

### 4.1 Crea un progetto

1. Vai su [console.cloud.google.com](https://console.cloud.google.com)
2. Menu a tendina progetto (in alto a sinistra) → **New Project**
3. Nome: `Drive Organizer` → **Create**

### 4.2 Abilita Google Drive API

1. Menu → **APIs & Services → Library**
2. Cerca `Google Drive API` → **Enable**

### 4.3 Schermata di consenso OAuth

1. Menu → **APIs & Services → OAuth consent screen**
2. **User Type: External** → **Create**
3. Compila i campi:
   - **App name:** `Drive Organizer`
   - **User support email:** la tua email
   - **Developer contact:** la tua email
4. **Save and Continue**
5. In **Scopes** → **Add or Remove Scopes** → cerca `drive` → seleziona `https://www.googleapis.com/auth/drive` → **Update**
6. In **Test users** → **Add Users** → aggiungi i tuoi account Gmail → **Save**
7. **Back to Dashboard**

### 4.4 Crea credenziali OAuth

1. Menu → **Credentials → + Create Credentials → OAuth 2.0 Client ID**
2. **Application type: Desktop app** → **Name:** `Drive Organizer CLI` → **Create**
3. **Download JSON** → rinomina in `credentials.json` → copia nella cartella dell'app

---

## 5. Configurazione API AI (opzionale)

Crea il file `.env` dalla copia del template:

```batch
:: Prompt dei comandi
copy .env.example .env

:: PowerShell
Copy-Item .env.example .env
```

Apri `.env` con Blocco Note e configura:

```env
# Scegli UN provider cloud (o lascia entrambi vuoti per usare solo Ollama)
ANTHROPIC_API_KEY=sk-ant-...    # claude.ai/settings → API Keys
GEMINI_API_KEY=AIza...          # aistudio.google.com → Get API Key

# Ollama (locale, gratuito, privato)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Controllo costi cloud
MAX_CLOUD_ESCALATIONS=200
```

### Installazione Ollama (per `rename` e classificazione locale)

1. Scarica [ollama.com/download](https://ollama.com/download) → installa
2. Apri un nuovo terminale:
   ```
   ollama pull qwen3:8b
   ollama serve
   ```
3. Lascia il terminale Ollama aperto mentre usi Drive Organizer

---

## 6. Primo avvio e autenticazione

### Autenticazione Google

```
drive-organizer.exe auth
```

Il browser si apre con la schermata OAuth di Google. Accedi con l'account da organizzare → autorizza → il token viene salvato in `tokens\{email}.json`.

> Se appare l'avviso **"Google non ha verificato questa app"**: clicca **Avanzate** → **Vai a Drive Organizer (non sicuro)** → Consenti. L'app è tua, le credenziali sono le tue — è normale per le app in modalità Testing.

### Verifica connessione

```
drive-organizer.exe status
```

Output atteso:
```
┌──────────────────────────┬────────────────────────────────────┐
│ Google Drive             │ Connesso — tua@email.com           │
│ Storage                  │ 6.14 GB / 15 GB                    │
│ Ollama                   │ qwen3:8b                           │
│ Haiku 4.5 / Gemini Flash │ Anthropic                          │
│ Opus 4.8 / Gemini Pro    │ Anthropic                          │
└──────────────────────────┴────────────────────────────────────┘
     File trovati: 16.634
```

---

## 7. Comandi disponibili

### `setup` — Wizard primo avvio

```
drive-organizer.exe setup
```

Configurazione guidata in 5 passi. Eseguire una volta per installazione.

---

### `auth` — Autenticazione Google

```
drive-organizer.exe auth
drive-organizer.exe auth -a lavoro@azienda.com
```

Apre il browser per il login. Il token è permanente e si rinnova automaticamente.

---

### `accounts` — Lista account

```
drive-organizer.exe accounts
```

Mostra tutti gli account con token attivo.

---

### `status` — Statistiche Drive

```
drive-organizer.exe status
drive-organizer.exe status -a lavoro@azienda.com
```

Mostra spazio usato, numero file per tipo e stato AI.

---

### `organize` — Organizza il Drive

```
drive-organizer.exe organize -s STRATEGIA [opzioni]
```

| Opzione | Breve | Descrizione |
|---|---|---|
| `--strategy` | `-s` | `type`, `date`, `project`, `custom` |
| `--apply` | — | Applica le modifiche (senza: solo preview) |
| `--account` | `-a` | Account Google specifico |
| `--taxonomy-file` | `-t` | JSON tassonomia pre-costruita |
| `--custom-prompt` | `-p` | Descrizione struttura libera (richiede API) |
| `--year-only` | — | Con `date`: organizza solo per anno |
| `--no-haiku` | — | Salta Haiku/Flash, vai diretto a Opus/Pro |

---

### `rename` — Rinomina con AI locale

```
drive-organizer.exe rename
drive-organizer.exe rename --apply
drive-organizer.exe rename --limit 50 --min-confidence 0.7
```

**Richiede Ollama in esecuzione.** Il contenuto dei file non viene mai inviato al cloud.

---

### `rename-rollback` — Annulla rinomina

```
drive-organizer.exe rename-rollback
```

---

### `duplicates` — Trova duplicati

```
drive-organizer.exe duplicates
drive-organizer.exe duplicates --apply
drive-organizer.exe duplicates --archive-folder "99_Archivio/Duplicati"
```

---

### `rollback` — Annulla organizzazione

```
drive-organizer.exe rollback
```

---

## 8. Strategie di organizzazione

### `type` — Per tipo (senza AI, offline)

```
drive-organizer.exe organize -s type
drive-organizer.exe organize -s type --apply
```

Crea cartelle: Documenti · Fogli · Presentazioni · PDF · Immagini · Video · Audio · Archivi · Codice · Testo · Altro

---

### `date` — Per data (senza AI, offline)

```
drive-organizer.exe organize -s date
drive-organizer.exe organize -s date --year-only --apply
```

Crea struttura `Anno\Mese` (es. `2024\Marzo`) o solo `Anno`.

---

### `project` — Per argomento (AI)

```
drive-organizer.exe organize -s project
drive-organizer.exe organize -s project --apply
```

Raggruppa semanticamente per progetto. Richiede Ollama o API key.

---

### `custom` — Struttura personalizzata

```
:: Con file JSON (nessuna AI)
drive-organizer.exe organize -s custom -t taxonomy_custom.json

:: Con descrizione libera (richiede API key)
drive-organizer.exe organize -s custom -p "Dividi per cliente: Acme, Beta, Gamma"
```

**Formato `taxonomy.json`:**
```json
{
  "01_Lavoro": "Contratti, fatture, corrispondenza professionale",
  "02_Foto": "Fotografie personali e di famiglia",
  "03_Progetti": "File di sviluppo software e creativi",
  "99_Archivio": "File vecchi o da conservare"
}
```

---

## 9. Rinomina file con AI

```
:: Preview (nessuna modifica)
drive-organizer.exe rename

:: Applica le rinomina
drive-organizer.exe rename --apply

:: Limita a 50 file, soglia confidenza 70%
drive-organizer.exe rename --limit 50 --min-confidence 0.7
```

**Requisito:** Ollama deve essere in esecuzione (`ollama serve`).

Il comando analizza il nome del file con Ollama (localmente) e propone un nome più descrittivo. Se Ollama è offline, il comando termina con un messaggio esplicativo — non invia nulla al cloud.

---

## 10. Gestione duplicati

```
:: Preview
drive-organizer.exe duplicates

:: Sposta i duplicati in archivio
drive-organizer.exe duplicates --apply

:: Cartella di archivio personalizzata
drive-organizer.exe duplicates --archive-folder "Archivio/Duplicati"
```

I duplicati vengono **spostati** (non eliminati). Puoi marcare gruppi come eccezioni durante la preview per tenerli tutti.

---

## 11. Rollback — annullare le modifiche

Ogni `organize --apply` e `duplicates --apply` crea un log in `logs\`. Il rollback usa questo log.

```
drive-organizer.exe rollback
```

Seleziona la sessione da annullare dalla lista interattiva. I file vengono riportati nelle posizioni originali.

Per annullare una rinomina:
```
drive-organizer.exe rename-rollback
```

> **Nota:** le cartelle create durante l'organizzazione non vengono eliminate — solo i file vengono riposizionati.

---

## 12. Gestione più account Google

```
:: Autentica account aggiuntivi
drive-organizer.exe auth -a lavoro@azienda.com

:: Lista account attivi
drive-organizer.exe accounts

:: Usa account specifico
drive-organizer.exe organize -s type -a lavoro@azienda.com
drive-organizer.exe status -a mario@gmail.com
```

Con un solo account viene selezionato automaticamente. Con più account, senza `-a` ti viene chiesto di scegliere.

---

## 13. Come funziona l'AI

```
File
 │
 ├─ Classificazione deterministica? → SÌ → fine (conf 1.0)
 │
 ├─ Ollama locale (gratuito, offline)
 │   └─ conf ≥ 0.75 → fine
 │   └─ conf < 0.75 → escalation
 │
 ├─ Haiku 4.5 o Gemini Flash (cloud, solo metadati)
 │   └─ conf ≥ 0.80 → fine
 │   └─ conf < 0.80 → escalation
 │
 └─ Opus 4.8 o Gemini Pro (cloud, solo metadati) → fine
```

- **Nessuna API key:** tutto va in Ollama; se offline, i file ambigui finiscono in `Altro`
- **Budget cap:** dopo 200 escalation cloud (configurabile), i rimanenti vanno in `Altro`
- **Cache:** estensioni già classificate non vengono riprocessate

---

## 14. Privacy e sicurezza

| Cosa | Dettaglio |
|---|---|
| **Contenuto file** | mai scaricato, mai inviato a nessuno |
| **Metadati cloud** | solo nome, tipo MIME, dimensione, data |
| **`rename`** | usa solo Ollama locale — nessun dato in rete |
| **`duplicates`** | confronto MD5 locale — nessun dato in rete |
| **Token Google** | salvati in `tokens\` sul tuo PC |
| **API key** | salvate in `.env` sul tuo PC |

Revoca permessi in qualsiasi momento: [myaccount.google.com/permissions](https://myaccount.google.com/permissions)

---

## 15. Risoluzione problemi

### `credentials.json non trovato`
Il file deve stare nella stessa cartella di `drive-organizer.exe`. Segui la sezione 4.

### `Errore 403: access_denied` durante il login
Il tuo account non è tra i Test Users. Vai su Google Cloud Console → OAuth consent screen → Test users → aggiungi la tua email.

### Il browser non si apre durante `auth`
Copia manualmente l'URL mostrato nel terminale e aprilo nel browser.

### `Ollama non raggiungibile`
```
ollama serve
ollama pull qwen3:8b
```
Lascia il terminale Ollama aperto.

### Nessuna API key — file finiscono tutti in `Altro`
Con strategie `project` e `custom`, senza AI tutto va in `Altro`. Aggiungi nel `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
oppure:
```
GEMINI_API_KEY=AIza...
```

### Caratteri strani nel terminale
Usa **Windows Terminal** (installa dal Microsoft Store). Oppure nel Prompt dei comandi: `chcp 65001`.

### Errore 429 — troppe richieste Drive API
L'app gestisce i retry automaticamente. Se persiste, aspetta qualche minuto.

### Errore `Access is denied` su file nella cartella
Lancia il Prompt dei comandi o PowerShell **come amministratore**, oppure sposta l'app in una cartella che non richiede privilegi elevati (es. `C:\Users\TuoNome\DriveOrganizer\`).

---

## 16. Riferimento rapido comandi

```batch
:: Setup iniziale
drive-organizer.exe setup
drive-organizer.exe auth
drive-organizer.exe status

:: Organizzazione — preview poi aggiungere --apply
drive-organizer.exe organize -s type
drive-organizer.exe organize -s date
drive-organizer.exe organize -s date --year-only
drive-organizer.exe organize -s project
drive-organizer.exe organize -s custom -t taxonomy_custom.json
drive-organizer.exe organize -s custom -p "struttura libera"
drive-organizer.exe organize -s type --apply

:: Rinomina (richiede Ollama)
drive-organizer.exe rename
drive-organizer.exe rename --apply
drive-organizer.exe rename-rollback

:: Duplicati
drive-organizer.exe duplicates
drive-organizer.exe duplicates --apply

:: Multi-account
drive-organizer.exe accounts
drive-organizer.exe auth -a altro@gmail.com
drive-organizer.exe organize -s type -a altro@gmail.com

:: Rollback
drive-organizer.exe rollback
```
