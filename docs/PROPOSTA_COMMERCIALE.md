# Drive Organizer — Proposta Commerciale

---

## Analisi del prodotto

**Drive Organizer** è un'app CLI Python che riorganizza Google Drive con AI cascade privacy-first. Ha tutte le caratteristiche di un prodotto vendibile:

- Risolve un problema reale (Drive disordinato, 16.000+ file caotici)
- Privacy differenziante (nessun contenuto esce dal PC — vantaggio competitivo forte)
- Funziona senza abbonamento mensile (no dipendenza da servizi terzi)
- Target ben definito: professionisti, freelance, docenti, PMI con Drive saturo

---

## Modello di monetizzazione consigliato

### Freemium + One-time Purchase

| Livello | Prezzo | Cosa include |
|---|---|---|
| **Community** (GitHub) | Gratuito | Sorgente, max 500 file/run, strategie `type` e `date` |
| **Pro** (EXE standalone) | €14,99 una tantum | Nessun limite file, tutte le strategie, EXE Windows, manuale PDF, 1 anno aggiornamenti |
| **Pro + Source** | €24,99 una tantum | Tutto Pro + sorgente completo, 3 anni aggiornamenti, supporto email |

**Piattaforma consigliata:** Gumroad o LemonSqueezy — pagamento unico, nessun abbonamento da gestire, download diretto del pacchetto ZIP.

**Alternativa:** Rilascio completamente gratuito (MIT) come portfolio personale — punta alla visibilità, consulenze e commissioni custom invece che alle vendite dirette.

---

## Miglioramenti prioritari per la vendibilità

### 1. Screenshot e GIF demo nel README (urgente)

Il README ha zero immagini del prodotto in azione. Un buyer non sa cosa aspettarsi.

**Da fare:**
- Registrare una GIF (15 sec) di `organize -s type` con Rich progress bar e tree diff
- Screenshot del terminale con `status` — mostra il prodotto funzionante
- Inserire nel README con caption descrittive

**Tool:** [Terminalizer](https://github.com/faressoft/terminalizer) o OBS → GIF con [Gifski](https://gif.ski/)

---

### 2. Pagina dedicata sul sito (alta priorità)

`gianlucademontis.xyz/drive-organizer/` — landing page con:
- Hero: titolo, tagline, CTA "Scarica gratis" + "Acquista Pro"
- Sezione "Il problema" → "La soluzione"
- 3 feature block con animazioni CSS
- Tabella prezzi
- FAQ (OAuth, privacy, rollback)
- Social proof (stelle GitHub, numero file organizzati)

---

### 3. Changelog visibile (prerequisito per vendite)

Un buyer guarda il changelog prima di acquistare. Senza cronologia visibile, il prodotto sembra abbandonato.

**Creare `CHANGELOG.md`:**
```
## [1.0.0] — 2026-05-30
### Aggiunto
- Strategie organize: type, date, project, custom
- AI cascade 3 livelli: Ollama → Haiku/Gemini Flash → Opus/Gemini Pro
- Rollback completo con log JSON
- Duplicati: ricerca per hash MD5
- Rinomina con Ollama locale (privacy garantita)
- EXE standalone Windows (59 MB)
- Multi-account Google
- Manuali per Windows, macOS, Linux, ChromeOS
```

---

### 4. GitHub Release formale

Aggiungere una Release v1.0.0 con:
- Tag `v1.0.0`
- Allegati: `DriveOrganizer_v1.0.0_Windows.zip`, `DriveOrganizer_v1.0.0_macOS.zip`, `DriveOrganizer_v1.0.0_Linux.tar.gz`
- Release notes con la lista feature
- Questo attiva il badge `releases` su GitHub e i download contano

---

### 5. Social proof e lancio

**GitHub:**
- Aggiungere `CONTRIBUTING.md` (segnala che accetti contributi)
- Aggiungere `SECURITY.md` (responsabilità, nessun dato esce)
- Abilitare GitHub Discussions per FAQ pubbliche
- Richiedere stelline a conoscenti per superare la soglia psicologica di 10 ★

**Product Hunt:**
- Pubblicare in un martedì/mercoledì mattina (UTC)
- Categoria: Developer Tools + Productivity
- Headline: "Organize 16,000+ Google Drive files in minutes — AI-powered, privacy-first"
- Media: GIF demo + 3 screenshot

**Reddit:**
- r/Python — "I built a CLI to organize Google Drive with a 3-tier AI cascade"
- r/selfhosted — angolo privacy (Ollama locale)
- r/digitalnomad / r/productivity — angolo "riordina il tuo Drive"

---

### 6. Licenza per la versione commerciale

**Opzione A — Mantieni MIT per tutto:**  
Sorgente gratuito, guadagni solo dalla distribuzione dell'EXE e dal supporto. Più visibilità, meno entrate dirette.

**Opzione B — MIT per sorgente + licenza commerciale per EXE:**  
Sorgente libero su GitHub, EXE venduto su Gumroad. Chi vuole compilarlo può farlo, ma la maggior parte degli utenti compra l'EXE pronto.

**Opzione C — Business Source License (BSL 1.1):**  
Sorgente disponibile ma uso commerciale vietato per 4 anni. Dopo 4 anni diventa MIT. Permette vendite senza che competitor rivendano il prodotto.

**Raccomandazione:** Opzione B. Mantiene lo spirito open-source, protegge il prodotto distribuito.

---

## Feature roadmap per versioni future

### v1.1 — Miglioramenti UX (1-2 mesi)

- [ ] **Progress persistente**: salva l'avanzamento di una run lunga, riprende da dove si era fermata
- [ ] **Filtri per organize**: `--exclude "*.tmp" --max-size 100MB`
- [ ] **Dry-run HTML report**: genera un report HTML navigabile prima di applicare
- [ ] **Config file**: `drive-organizer.yaml` per salvare preferenze (account, soglie, tassonomia)

### v1.2 — Automazione (2-4 mesi)

- [ ] **Pianificazione automatica**: `drive-organizer schedule --every week --strategy type`
- [ ] **Notifiche Telegram/email**: avviso quando l'organizzazione è completa
- [ ] **Webhook post-organize**: integrazione con n8n, Make, Zapier
- [ ] **Export CSV**: esporta la lista file con classificazione proposta

### v2.0 — Distribuzione avanzata (6+ mesi)

- [ ] **Installer Windows firmato** (Code Signing Certificate ~€80/anno) — rimuove l'avviso SmartScreen
- [ ] **GUI minimale** (Tkinter o web locale): selezione strategia con click, preview grafica ad albero
- [ ] **Chrome Extension**: organizza direttamente da Google Drive nel browser
- [ ] **App macOS firmata** (Apple Developer Program €99/anno) — rimuove il blocco Gatekeeper

---

## Analisi competitor

| Prodotto | Prezzo | Pro | Contro |
|---|---|---|---|
| **DriveSort** (web) | gratuito | semplice | nessuna AI, solo rinomina |
| **Filestack** | SaaS $/mese | ricco | contenuto va al cloud, no privacy |
| **Google Drive nativo** | gratuito | integrato | nessuna organizzazione automatica |
| **Drive Organizer** | €14,99 | AI privata, rollback, multi-account | CLI (no GUI) |

**Vantaggio competitivo unico:** nessun competitor offre AI cascade + garanzia privacy strutturale (contenuto mai scaricato).

---

## Grafiche create

| File | Uso |
|---|---|
| `assets/icon.svg` | Icona app vettoriale — convertire in .ico/.png per installer |
| `assets/social-card.svg` | Preview social (1200×630) — caricare come GitHub Social Preview |
| `assets/banner.svg` | Banner README (1200×280) — già incluso nel README |

### Come impostare il GitHub Social Preview

1. Vai su [github.com/giandemoncell-prog/drive-organizer/settings](https://github.com/giandemoncell-prog/drive-organizer/settings)
2. Scorri fino a **"Social preview"**
3. Converti `assets/social-card.svg` in PNG 1200×630 (usa Inkscape, Figma, o browser → Print → Save as PDF → converti)
4. Carica il PNG

### Come convertire icon.svg in .ico

```bash
# Con Inkscape (cross-platform)
inkscape assets/icon.svg --export-filename=assets/icon_256.png --export-width=256

# Con ImageMagick
convert assets/icon_256.png -define icon:auto-resize=256,128,64,48,32,16 assets/icon.ico
```

---

## Pricing per Gumroad/LemonSqueezy

**Prodotto:** Drive Organizer Pro  
**Prezzo:** €14,99 (o $15.99 per mercato internazionale)  
**Cosa include:**
- `DriveOrganizer_v1.0.0_Windows.zip` (exe + manuale + taxonomy + .env.example)
- `DriveOrganizer_v1.0.0_macOS.zip`
- `DriveOrganizer_v1.0.0_Linux.tar.gz`
- `MANUALE_WINDOWS.pdf`, `MANUALE_MACOS.pdf`, `MANUALE_LINUX.pdf`
- Accesso a tutti gli aggiornamenti v1.x

**Descrizione prodotto (IT):**
> Stanchi di trovare file a caso nel vostro Google Drive? Drive Organizer analizza 16.000+ file in pochi minuti e propone una struttura ordinata — voi decidete se applicarla. L'AI lavora in locale con Ollama: il contenuto dei file non esce mai dal vostro computer. In anteprima potete verificare ogni singolo spostamento prima di confermare. Se cambiate idea, il rollback ripristina tutto in un click.

**Descrizione prodotto (EN):**
> Tired of a chaotic Google Drive? Drive Organizer scans 16,000+ files and proposes a clean structure — you review every move before it applies. AI runs locally via Ollama: your file content never leaves your computer. One command to organize, one command to undo everything.
