# Drive Organizer — Manuale macOS

**Sistema operativo:** macOS 12 Monterey o superiore (Apple Silicon e Intel)  
**Versione app:** 1.0.0

---

## Indice

1. [Requisiti](#1-requisiti)
2. [Installazione rapida (binario precompilato)](#2-installazione-rapida-binario-precompilato)
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
| macOS 12+ | Monterey, Ventura, Sonoma, Sequoia |
| Google Account | uno o più account Gmail / Workspace |
| `credentials.json` | scaricato una volta da Google Cloud Console |
| API key Anthropic **o** Gemini | opzionale — solo per strategie AI (`project`, `custom`) |
| Ollama | opzionale — solo per `rename` e classificazione locale |

> **Le strategie `type` e `date` funzionano senza AI, senza API key** (solo connessione Google Drive).

---

## 2. Installazione rapida (binario precompilato)

### 2.1 Scarica il pacchetto

1. Scarica `DriveOrganizer_v1.0.0_macOS.zip` dalla [pagina Releases](https://github.com/giandemoncell-prog/drive-organizer/releases)
2. Estrai lo ZIP — si crea la cartella `dist_mac/`
3. Sposta la cartella dove preferisci, es. `~/Applicazioni/DriveOrganizer/`

La struttura deve essere:
```
~/Applicazioni/DriveOrganizer/
├── drive-organizer             ← binario principale (eseguibile)
├── credentials.json            ← credenziali Google Cloud (obbligatorio)
├── .env                        ← API key (opzionale)
├── taxonomy_custom.json        ← tassonomia personalizzata (opzionale)
└── Avvia Drive Organizer.command  ← doppio clic per avvio rapido
```

### 2.2 Rendi eseguibile il binario

Apri il Terminale (Cmd+Spazio → digita "Terminale"):

```bash
cd ~/Applicazioni/DriveOrganizer
chmod +x drive-organizer
```

### 2.3 Prima esecuzione — sblocca Gatekeeper

La prima volta che esegui il binario, macOS mostra un avviso di sicurezza perché il file non è firmato con un certificato Apple Developer.

**Metodo consigliato:**
```bash
xattr -cr drive-organizer
./drive-organizer --help
```

**Metodo alternativo (Finder):**
- Clic destro su `drive-organizer` → **Apri** → conferma nella finestra di dialogo
- Poi potrai eseguirlo normalmente dal Terminale

**Metodo via Impostazioni:**
- Vai in **Impostazioni di Sistema → Privacy e Sicurezza**
- In fondo alla sezione Sicurezza: clicca **"Apri comunque"** accanto al nome dell'app

### 2.4 Doppio clic da Finder

Per avviare facilmente senza Terminale, usa `Avvia Drive Organizer.command`:
- Doppio clic sul file → si apre il Terminale con il setup guidato

---

## 3. Installazione da sorgente (sviluppatori)

### 3.1 Prerequisiti

```bash
# Installa Homebrew (se non presente)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.11+ e Git
brew install python@3.11 git
```

### 3.2 Clone e setup

```bash
git clone https://github.com/giandemoncell-prog/drive-organizer.git
cd drive-organizer

# Crea ambiente virtuale
python3 -m venv .venv
source .venv/bin/activate

# Installa dipendenze
python3 -m pip install -r requirements.txt

# Copia configurazione
cp .env.example .env
```

### 3.3 Avvio in sviluppo

```bash
source .venv/bin/activate
python3 main.py setup
```

### 3.4 Build binario macOS

```bash
bash build/build_mac.sh
```

Produce `dist_mac/drive-organizer` e un archivio `DriveOrganizer_v1.0.0_macOS.zip`.

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

```bash
cp .env.example .env
nano .env     # oppure: open -e .env
```

Configura nel `.env`:

```env
# Scegli UN provider cloud (o lascia vuoti per usare solo Ollama)
ANTHROPIC_API_KEY=sk-ant-...    # claude.ai/settings → API Keys
GEMINI_API_KEY=AIza...          # aistudio.google.com → Get API Key

# Ollama (locale, gratuito, privato)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Controllo costi cloud
MAX_CLOUD_ESCALATIONS=200
```

### Installazione Ollama (per `rename` e classificazione locale)

```bash
# Scarica da ollama.com oppure con Homebrew
brew install ollama

# Scarica il modello
ollama pull qwen3:8b

# Avvia il server (necessario prima di usare rename)
ollama serve
```

Lascia `ollama serve` in esecuzione in un Terminale separato mentre usi Drive Organizer.

---

## 6. Primo avvio e autenticazione

### Autenticazione Google

```bash
./drive-organizer auth
```

Il browser si apre con la schermata OAuth di Google. Accedi → autorizza → il token viene salvato in `tokens/{email}.json`.

> Se appare l'avviso **"Google non ha verificato questa app"**: clicca **Avanzate** → **Vai a Drive Organizer** → **Consenti**. È normale per le app in modalità Testing.

Se il browser non si apre automaticamente, copia l'URL dal Terminale e incollalo nel browser.

### Verifica connessione

```bash
./drive-organizer status
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

Tutti i comandi usano il prefisso `./drive-organizer` se esegui dalla cartella, oppure `drive-organizer` se installato globalmente.

### `setup` — Wizard primo avvio

```bash
./drive-organizer setup
```

### `auth` — Autenticazione Google

```bash
./drive-organizer auth
./drive-organizer auth -a lavoro@azienda.com
```

### `accounts` — Lista account

```bash
./drive-organizer accounts
```

### `status` — Statistiche Drive

```bash
./drive-organizer status
./drive-organizer status -a lavoro@azienda.com
```

### `organize` — Organizza il Drive

```bash
./drive-organizer organize -s STRATEGIA [opzioni]
```

| Opzione | Breve | Descrizione |
|---|---|---|
| `--strategy` | `-s` | `type`, `date`, `project`, `custom` |
| `--apply` | — | Applica le modifiche (senza: solo preview) |
| `--account` | `-a` | Account Google specifico |
| `--taxonomy-file` | `-t` | JSON tassonomia pre-costruita |
| `--custom-prompt` | `-p` | Descrizione struttura libera |
| `--year-only` | — | Con `date`: solo anno |
| `--no-haiku` | — | Salta Haiku/Flash, vai diretto a Opus/Pro |

### `rename` — Rinomina con AI locale

```bash
./drive-organizer rename
./drive-organizer rename --apply
./drive-organizer rename --limit 50 --min-confidence 0.7
```

### `rename-rollback` / `rollback`

```bash
./drive-organizer rename-rollback
./drive-organizer rollback
```

### `duplicates` — Trova duplicati

```bash
./drive-organizer duplicates
./drive-organizer duplicates --apply
```

---

## 8. Strategie di organizzazione

### `type` — Per tipo (senza AI)

```bash
./drive-organizer organize -s type
./drive-organizer organize -s type --apply
```

### `date` — Per data (senza AI)

```bash
./drive-organizer organize -s date
./drive-organizer organize -s date --year-only --apply
```

### `project` — Per argomento (AI)

```bash
./drive-organizer organize -s project --apply
```

### `custom` — Struttura personalizzata

```bash
# Con file JSON (nessuna AI necessaria)
./drive-organizer organize -s custom -t taxonomy_custom.json

# Con descrizione libera (richiede API key)
./drive-organizer organize -s custom -p "Dividi per cliente: Acme, Beta, Gamma"
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

```bash
# Preview — nessuna modifica
./drive-organizer rename

# Applica le rinomina
./drive-organizer rename --apply

# Limita a 50 file, soglia 70%
./drive-organizer rename --limit 50 --min-confidence 0.7
```

**Richiede Ollama in esecuzione** (`ollama serve` in un Terminale separato).

---

## 10. Gestione duplicati

```bash
./drive-organizer duplicates
./drive-organizer duplicates --apply
./drive-organizer duplicates --archive-folder "99_Archivio/Duplicati"
```

I duplicati vengono spostati in archivio, non eliminati.

---

## 11. Rollback

```bash
# Annulla organizzazione
./drive-organizer rollback

# Annulla rinomina
./drive-organizer rename-rollback
```

---

## 12. Gestione più account Google

```bash
./drive-organizer auth -a lavoro@azienda.com
./drive-organizer accounts
./drive-organizer organize -s type -a lavoro@azienda.com
```

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

I modelli cloud ricevono **solo** nome file, tipo MIME, dimensione, data — mai il contenuto.

---

## 14. Privacy e sicurezza

| Cosa | Dettaglio |
|---|---|
| **Contenuto file** | mai scaricato, mai inviato |
| **Metadati cloud** | solo nome, tipo, dimensione, data |
| **`rename`** | solo Ollama locale — nessun dato in rete |
| **`duplicates`** | confronto MD5 locale |
| **Token Google** | salvati in `tokens/` |
| **API key** | salvate in `.env` |

---

## 15. Risoluzione problemi

### `zsh: permission denied: ./drive-organizer`
```bash
chmod +x drive-organizer
```

### `"drive-organizer" non può essere aperto perché proviene da uno sviluppatore non identificato`
```bash
xattr -cr drive-organizer
./drive-organizer --help
```
Oppure: clic destro → Apri → Apri (nella finestra di dialogo).

### `credentials.json non trovato`
Il file deve stare nella stessa cartella del binario.

### `Errore 403: access_denied`
Il tuo account non è tra i Test Users. Google Cloud Console → OAuth consent screen → Test users → aggiungi la tua email.

### `Ollama non raggiungibile`
```bash
ollama serve
ollama pull qwen3:8b
```

### Errore 429 — troppe richieste
Drive API ha limiti di frequenza. L'app gestisce i retry automaticamente. Se persiste, aspetta qualche minuto.

### Il browser non si apre durante `auth`
macOS potrebbe bloccare l'apertura del browser da un processo non firmato. Copia l'URL dal Terminale e aprilo manualmente in Safari/Chrome.

---

## 16. Riferimento rapido comandi

```bash
# Setup iniziale
./drive-organizer setup
./drive-organizer auth
./drive-organizer status

# Organizzazione — prima preview, poi --apply
./drive-organizer organize -s type
./drive-organizer organize -s date
./drive-organizer organize -s date --year-only
./drive-organizer organize -s project
./drive-organizer organize -s custom -t taxonomy_custom.json
./drive-organizer organize -s custom -p "struttura libera"
./drive-organizer organize -s type --apply

# Rinomina (richiede Ollama)
./drive-organizer rename
./drive-organizer rename --apply
./drive-organizer rename-rollback

# Duplicati
./drive-organizer duplicates
./drive-organizer duplicates --apply

# Multi-account
./drive-organizer accounts
./drive-organizer auth -a altro@gmail.com
./drive-organizer organize -s type -a altro@gmail.com

# Rollback
./drive-organizer rollback
```

### Installazione globale (opzionale)

Per usare `drive-organizer` senza `./` da qualsiasi cartella:

```bash
sudo cp drive-organizer /usr/local/bin/
# Poi da qualsiasi percorso:
drive-organizer status
```
