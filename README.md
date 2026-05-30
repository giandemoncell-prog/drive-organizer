# Drive Organizer

**Riorganizza Google Drive con AI locale + cloud — privacy-first, zero upload di contenuti.**

Uno strumento CLI Python che analizza i tuoi 16.000+ file, propone una struttura ordinata e la applica in un click. L'AI scala da Ollama locale (gratuita, offline) fino a Haiku/Opus o Gemini solo sui casi difficili — il contenuto dei file non raggiunge mai il cloud.

---

## Funzionalità

- **4 strategie di organizzazione** — per tipo, per data, per progetto, tassonomia custom JSON
- **Rinomina intelligente** — Ollama locale legge il contenuto, il cloud non lo vede mai
- **Trova duplicati** — 365+ gruppi in un Drive da 16 GB, con preview prima di agire
- **Cascade AI 3 livelli** — Ollama → Haiku 4.5 / Gemini Flash → Opus 4.8 / Gemini Pro
- **Rollback completo** — ogni operazione è annullabile da log JSON
- **Multi-account** — gestione token separati per più account Google
- **EXE standalone Windows** — nessuna dipendenza Python richiesta
- **Privacy totale** — solo metadati (nome, tipo, dimensione, data) raggiungono i provider cloud

---

## Documentazione

| Sistema operativo | Manuale |
|---|---|
| Windows 10/11 | [docs/MANUALE_WINDOWS.md](docs/MANUALE_WINDOWS.md) |
| macOS 12+ | [docs/MANUALE_MACOS.md](docs/MANUALE_MACOS.md) |
| Linux / Chrome OS | [docs/MANUALE_LINUX.md](docs/MANUALE_LINUX.md) |
| Riferimento generale | [MANUALE.md](MANUALE.md) |

---

## Quick Start

```bash
# 1. Clona e installa
git clone https://github.com/giandemoncell-prog/drive-organizer.git
cd drive-organizer
pip install -r requirements.txt

# 2. Aggiungi credentials.json (Google Cloud Console → OAuth Desktop App)
# 3. Setup guidato
python main.py setup

# 4. Autentica l'account Google
python main.py auth

# 5. Preview organizzazione per tipo (nessuna modifica applicata)
python main.py organize -s type
```

**Oppure scarica direttamente l'[EXE standalone Windows](dist/drive-organizer.exe) (59 MB, no Python richiesto).**

---

## Comandi

| Comando | Descrizione |
|---|---|
| `setup` | Wizard guidato — configura API key, Ollama, credenziali |
| `auth [-a email]` | Autenticazione OAuth Google Drive |
| `accounts` | Lista account autenticati |
| `status [-a email]` | Statistiche Drive + stato componenti AI |
| `organize -s type` | Organizza per tipo file (PDF, Video, Immagini…) |
| `organize -s date [--year-only]` | Organizza per anno/mese creazione |
| `organize -s project` | Organizza per progetto con AI |
| `organize -s custom -t taxonomy.json` | Tassonomia personalizzata da file JSON |
| `organize ... --apply` | Applica le modifiche (default: solo preview) |
| `rename [--limit N] [--min-confidence 0.65]` | Rinomina con Ollama locale |
| `rename-rollback` | Annulla ultima sessione rinomina |
| `duplicates [--apply]` | Trova duplicati e propone archiviazione |
| `rollback` | Annulla ultima organizzazione |

---

## Cascade AI

```
File → classify_without_ai()  →  conf = 1.0  →  done (deterministico)
                              ↓ None
       Ollama health_check()  →  skip se offline (nessun hang)
       Ollama locale          →  conf ≥ 0.75?  →  done
                              ↓
       Haiku 4.5 / Gemini Flash  →  conf ≥ 0.80?  →  done (+0.10 bonus accordo)
       (try/except: API error → break graceful)
                              ↓
       Opus 4.8 / Gemini Pro  →  risposta finale
       (budget cap MAX_CLOUD_ESCALATIONS=200 → fallback "Altro")
```

Usa **Gemini** se `GEMINI_API_KEY` presente e `ANTHROPIC_API_KEY` assente. Tutte le chiamate cloud ricevono solo metadati, mai il contenuto del file.

---

## Prerequisiti

1. **Python 3.11+**
2. **credentials.json** — [Google Cloud Console](https://console.cloud.google.com) → API & Servizi → OAuth 2.0 → App Desktop
3. **`.env`** — copia `.env.example` e compila le chiavi API (tutte opzionali)
4. **Ollama** (opzionale) — per `rename` e classificazione locale. `ollama serve` + `ollama pull qwen3:8b`

```
# .env — tutte le variabili sono opzionali
ANTHROPIC_API_KEY=       # lascia vuoto per usare solo Gemini o solo Ollama
GEMINI_API_KEY=          # alternativa a Anthropic
OLLAMA_MODEL=qwen3:8b    # qualsiasi modello Ollama installato
```

---

## Tassonomia personalizzata

Crea un file JSON con le cartelle che vuoi:

```json
{
  "01_Lavoro": "Documenti di lavoro, contratti, fatture",
  "02_Foto": "Fotografie e immagini personali",
  "03_Progetti": "Progetti software e creativi",
  "99_Archivio": "File vecchi e da archiviare"
}
```

```bash
python main.py organize -s custom -t mia_taxonomy.json
```

---

## Build EXE Windows

```bash
pip install pyinstaller
python -m PyInstaller drive_organizer.spec --clean --noconfirm
# Output: dist/drive-organizer.exe
```

---

## Privacy

Il progetto segue un principio fondamentale: **il contenuto dei file non lascia mai il tuo computer**.

- `organize` — invia solo nome file, tipo MIME, dimensione, data modifica
- `rename` — usa esclusivamente Ollama locale; se offline, il comando non parte
- `duplicates` — confronta hash MD5 localmente, nessun dato in rete

---

## Struttura

```
drive_organizer/
├── ai/          cascade.py, ollama/haiku/opus/gemini provider
├── auth/        OAuth Google
├── drive/       client API Drive, modelli dati
├── strategies/  by_type, by_date, by_project, custom
└── ui/          console Rich, diff ad albero, prompts
main.py          CLI Click
```

---

## Licenza

MIT — vedi [LICENSE](LICENSE)
