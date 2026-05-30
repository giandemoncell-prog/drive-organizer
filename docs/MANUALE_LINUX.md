# Drive Organizer — Manuale Linux / Chrome OS

**Sistema operativo:** Ubuntu 20.04+, Debian 11+, Fedora 38+, Chrome OS (Crostini)  
**Versione app:** 1.0.0

---

## Indice

1. [Requisiti](#1-requisiti)
2. [Installazione rapida (binario precompilato)](#2-installazione-rapida-binario-precompilato)
3. [Installazione da sorgente (sviluppatori)](#3-installazione-da-sorgente-sviluppatori)
4. [Setup Chrome OS / Crostini](#4-setup-chrome-os--crostini)
5. [Configurazione Google Cloud](#5-configurazione-google-cloud)
6. [Configurazione API AI (opzionale)](#6-configurazione-api-ai-opzionale)
7. [Primo avvio e autenticazione](#7-primo-avvio-e-autenticazione)
8. [Comandi disponibili](#8-comandi-disponibili)
9. [Strategie di organizzazione](#9-strategie-di-organizzazione)
10. [Rinomina file con AI](#10-rinomina-file-con-ai)
11. [Gestione duplicati](#11-gestione-duplicati)
12. [Rollback — annullare le modifiche](#12-rollback--annullare-le-modifiche)
13. [Gestione più account Google](#13-gestione-più-account-google)
14. [Come funziona l'AI](#14-come-funziona-lai)
15. [Privacy e sicurezza](#15-privacy-e-sicurezza)
16. [Risoluzione problemi](#16-risoluzione-problemi)
17. [Riferimento rapido comandi](#17-riferimento-rapido-comandi)

---

## 1. Requisiti

| Componente | Dettaglio |
|---|---|
| Linux x86_64 o arm64 | Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch, ecc. |
| Google Account | uno o più account Gmail / Workspace |
| `credentials.json` | scaricato una volta da Google Cloud Console |
| API key Anthropic **o** Gemini | opzionale — solo per strategie AI (`project`, `custom`) |
| Ollama | opzionale — solo per `rename` e classificazione locale |

> **Le strategie `type` e `date` funzionano senza AI e senza API key.**

---

## 2. Installazione rapida (binario precompilato)

### 2.1 Scarica e installa

```bash
# Scarica il pacchetto
wget https://github.com/giandemoncell-prog/drive-organizer/releases/latest/download/DriveOrganizer_v1.0.0_Linux.tar.gz

# Estrai
tar -xzf DriveOrganizer_v1.0.0_Linux.tar.gz -C ~/DriveOrganizer/
cd ~/DriveOrganizer/

# Copia credentials.json nella cartella
# (vedi sezione 5 per ottenerlo)
cp /percorso/del/credentials.json .
```

### 2.2 Installa globalmente (consigliato)

```bash
cd ~/DriveOrganizer/
chmod +x install.sh
./install.sh
```

`install.sh` copia il binario in `~/.local/bin/` e aggiunge il PATH a `.bashrc` / `.zshrc`.

Riapri il terminale e il comando è disponibile ovunque:

```bash
drive-organizer setup
```

### 2.3 Usa senza installazione (esecuzione diretta)

```bash
chmod +x ~/DriveOrganizer/drive-organizer
~/DriveOrganizer/drive-organizer setup
# oppure dalla stessa cartella:
./drive-organizer setup
```

### 2.4 Disinstalla

```bash
~/DriveOrganizer/uninstall.sh
```

---

## 3. Installazione da sorgente (sviluppatori)

### 3.1 Prerequisiti

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y

# Fedora
sudo dnf install python3 python3-pip git -y

# Arch Linux
sudo pacman -S python python-pip git
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

### 3.4 Build binario Linux

```bash
bash build/build_linux.sh
```

Produce `dist_linux/drive-organizer` e `DriveOrganizer_v1.0.0_Linux.tar.gz`.

---

## 4. Setup Chrome OS / Crostini

Chrome OS include un ambiente Linux (Crostini) basato su Debian. Drive Organizer funziona nativamente.

### 4.1 Abilita l'ambiente Linux

1. Impostazioni ChromeOS → **Sviluppatori** → **Ambiente Linux (beta)** → **Attiva**
2. Segui la procedura guidata (scarica Debian, imposta dimensione disco)
3. Si apre automaticamente il Terminale Linux

### 4.2 Installa Drive Organizer in Crostini

Dal Terminale Linux di ChromeOS:

```bash
sudo apt update && sudo apt install wget -y

# Scarica Drive Organizer
wget https://github.com/giandemoncell-prog/drive-organizer/releases/latest/download/DriveOrganizer_v1.0.0_Linux.tar.gz
mkdir ~/DriveOrganizer && tar -xzf DriveOrganizer_v1.0.0_Linux.tar.gz -C ~/DriveOrganizer/
cd ~/DriveOrganizer && chmod +x install.sh && ./install.sh
```

### 4.3 credentials.json su ChromeOS

Il file `credentials.json` va scaricato dal browser ChromeOS (non Linux). Poi:

```bash
# Il browser ChromeOS scarica in ~/Scaricati
# Crostini può accedere a questa cartella in /mnt/chromeos/MyFiles/Downloads/
cp /mnt/chromeos/MyFiles/Downloads/credentials.json ~/DriveOrganizer/
```

### 4.4 Browser per OAuth su ChromeOS

Il comando `auth` tenta di aprire il browser. Su Crostini, se il browser non si apre automaticamente:

```bash
drive-organizer auth
# Copia l'URL mostrato
# Aprilo in Chrome ChromeOS (non nel Terminale Linux)
```

### 4.5 Ollama su ChromeOS

Ollama funziona in Crostini ma richiede più spazio disco:

```bash
# Imposta almeno 20 GB per il container Linux in Impostazioni
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
ollama serve &
```

---

## 5. Configurazione Google Cloud

> **Da fare una sola volta.** Le credenziali funzionano con qualsiasi account Google.

### 5.1 Crea un progetto

1. Vai su [console.cloud.google.com](https://console.cloud.google.com)
2. Menu a tendina progetto (in alto a sinistra) → **New Project**
3. Nome: `Drive Organizer` → **Create**

### 5.2 Abilita Google Drive API

1. Menu → **APIs & Services → Library**
2. Cerca `Google Drive API` → **Enable**

### 5.3 Schermata di consenso OAuth

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

### 5.4 Crea credenziali OAuth

1. Menu → **Credentials → + Create Credentials → OAuth 2.0 Client ID**
2. **Application type: Desktop app** → **Name:** `Drive Organizer CLI` → **Create**
3. **Download JSON** → rinomina in `credentials.json` → copia nella cartella dell'app

---

## 6. Configurazione API AI (opzionale)

```bash
cp .env.example .env
nano .env
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

### Installazione Ollama

```bash
# Installa Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Scarica il modello
ollama pull qwen3:8b

# Avvia il server (in background o terminale separato)
ollama serve &
# oppure come servizio systemd:
# sudo systemctl enable --now ollama
```

---

## 7. Primo avvio e autenticazione

### Autenticazione Google

```bash
drive-organizer auth
```

Il browser si apre con la schermata OAuth di Google. Accedi → autorizza → il token viene salvato in `~/.config/drive-organizer/tokens/{email}.json` (installazione globale) oppure `tokens/{email}.json` (cartella locale).

> Se appare **"Google non ha verificato questa app"**: clicca **Avanzate** → **Vai a Drive Organizer** → **Consenti**. Normale per le app in modalità Testing.

**Se il browser non si apre automaticamente:**
```bash
drive-organizer auth
# Copia l'URL mostrato e aprilo nel browser manualmente
```

Oppure forza l'apertura del browser:
```bash
BROWSER=xdg-open drive-organizer auth
```

### Verifica connessione

```bash
drive-organizer status
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

## 8. Comandi disponibili

Con installazione globale usa `drive-organizer COMANDO`.  
Senza installazione usa `./drive-organizer COMANDO` dalla cartella del binario.

### `setup` — Wizard primo avvio

```bash
drive-organizer setup
```

### `auth` — Autenticazione Google

```bash
drive-organizer auth
drive-organizer auth -a lavoro@azienda.com
```

### `accounts` — Lista account

```bash
drive-organizer accounts
```

### `status` — Statistiche Drive

```bash
drive-organizer status
drive-organizer status -a lavoro@azienda.com
```

### `organize` — Organizza il Drive

```bash
drive-organizer organize -s STRATEGIA [opzioni]
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
drive-organizer rename
drive-organizer rename --apply
drive-organizer rename --limit 50 --min-confidence 0.7
```

**Richiede Ollama in esecuzione** (`ollama serve`).

### `rename-rollback` / `rollback`

```bash
drive-organizer rename-rollback
drive-organizer rollback
```

### `duplicates` — Trova duplicati

```bash
drive-organizer duplicates
drive-organizer duplicates --apply
drive-organizer duplicates --archive-folder "99_Archivio/Duplicati"
```

---

## 9. Strategie di organizzazione

### `type` — Per tipo (senza AI)

```bash
drive-organizer organize -s type
drive-organizer organize -s type --apply
```

### `date` — Per data (senza AI)

```bash
drive-organizer organize -s date
drive-organizer organize -s date --year-only --apply
```

### `project` — Per argomento (AI)

```bash
drive-organizer organize -s project --apply
```

### `custom` — Struttura personalizzata

```bash
# Con file JSON (nessuna AI)
drive-organizer organize -s custom -t taxonomy_custom.json

# Con descrizione libera (richiede API key)
drive-organizer organize -s custom -p "Dividi per cliente: Acme, Beta, Gamma"
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

## 10. Rinomina file con AI

```bash
# Preview — nessuna modifica
drive-organizer rename

# Applica
drive-organizer rename --apply

# Limita a 50 file, soglia 70%
drive-organizer rename --limit 50 --min-confidence 0.7
```

**Richiede Ollama in esecuzione.** Il contenuto dei file non lascia mai il tuo computer.

---

## 11. Gestione duplicati

```bash
drive-organizer duplicates
drive-organizer duplicates --apply
```

I duplicati vengono spostati in archivio, non eliminati.

---

## 12. Rollback

```bash
drive-organizer rollback
drive-organizer rename-rollback
```

---

## 13. Gestione più account Google

```bash
drive-organizer auth -a lavoro@azienda.com
drive-organizer accounts
drive-organizer organize -s type -a lavoro@azienda.com
```

---

## 14. Come funziona l'AI

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

## 15. Privacy e sicurezza

| Cosa | Dettaglio |
|---|---|
| **Contenuto file** | mai scaricato, mai inviato |
| **Metadati cloud** | solo nome, tipo, dimensione, data |
| **`rename`** | solo Ollama locale |
| **`duplicates`** | confronto MD5 locale |
| **Token Google** | salvati in `tokens/` o `~/.config/drive-organizer/tokens/` |
| **API key** | salvate in `.env` |

---

## 16. Risoluzione problemi

### `bash: drive-organizer: command not found`

```bash
# Opzione 1: riapri il terminale dopo l'installazione (PATH aggiornato)
# Opzione 2: aggiungi manualmente al PATH
export PATH="$HOME/.local/bin:$PATH"
# Per renderlo permanente:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### `Permission denied: ./drive-organizer`

```bash
chmod +x ./drive-organizer
```

### `credentials.json non trovato`

Il file deve stare nella stessa cartella del binario (o nella directory di lavoro corrente).

### `Errore 403: access_denied`

Il tuo account non è tra i Test Users. Google Cloud Console → OAuth consent screen → Test users → aggiungi la tua email.

### Il browser non si apre durante `auth`

```bash
# Forza il browser predefinito
BROWSER=xdg-open drive-organizer auth
# oppure
BROWSER=firefox drive-organizer auth
```

### `Ollama non raggiungibile`

```bash
ollama serve &
ollama pull qwen3:8b
```

Verifica che sia in ascolto:
```bash
curl http://localhost:11434/api/tags
```

### Errore di certificato SSL su Crostini

```bash
sudo apt install ca-certificates -y
```

### Errore 429 — troppe richieste Drive API

L'app gestisce i retry automaticamente. Se persiste, aspetta qualche minuto.

### `libz.so.1: cannot open shared object file` o errori di dipendenze

Il binario PyInstaller include tutte le dipendenze Python ma può richiedere alcune librerie di sistema:

```bash
# Ubuntu / Debian
sudo apt install libz1 libssl3 -y

# Fedora
sudo dnf install zlib openssl -y
```

---

## 17. Riferimento rapido comandi

```bash
# Setup iniziale
drive-organizer setup
drive-organizer auth
drive-organizer status

# Organizzazione — prima preview, poi --apply
drive-organizer organize -s type
drive-organizer organize -s date
drive-organizer organize -s date --year-only
drive-organizer organize -s project
drive-organizer organize -s custom -t taxonomy_custom.json
drive-organizer organize -s custom -p "struttura libera"
drive-organizer organize -s type --apply

# Rinomina (richiede Ollama)
drive-organizer rename
drive-organizer rename --apply
drive-organizer rename-rollback

# Duplicati
drive-organizer duplicates
drive-organizer duplicates --apply

# Multi-account
drive-organizer accounts
drive-organizer auth -a altro@gmail.com
drive-organizer organize -s type -a altro@gmail.com

# Rollback
drive-organizer rollback
```

### Aggiornamento

```bash
# Scarica nuova versione
wget https://github.com/giandemoncell-prog/drive-organizer/releases/latest/download/DriveOrganizer_vNEW_Linux.tar.gz
tar -xzf DriveOrganizer_vNEW_Linux.tar.gz -C /tmp/drive-organizer-update/
cp /tmp/drive-organizer-update/drive-organizer ~/.local/bin/
```

### Alias utili (opzionale)

```bash
# Aggiungi a ~/.bashrc o ~/.zshrc
alias dro='drive-organizer'
alias dro-status='drive-organizer status'
alias dro-type='drive-organizer organize -s type'
alias dro-type-apply='drive-organizer organize -s type --apply'
alias dro-rollback='drive-organizer rollback'
```
