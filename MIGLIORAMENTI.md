# Drive Organizer — Report di miglioramento

Analisi del repo `giandemoncell-prog/drive-organizer` (117 file Python, ~13k righe). Stato di partenza: **82 test passano**, architettura solida e ben separata (ai / auth / drive / strategies / ui). Sotto trovi quello che ho **già applicato e verificato** (patch allegata) e una lista **prioritizzata** di interventi successivi.

---

## 1. Modifiche già applicate (verificate: 82 test passano, ruff pulito)

File: `miglioramenti_drive_organizer.patch` — applicabile con `git apply miglioramenti_drive_organizer.patch` dalla root del repo.

### 🔴 Sicurezza — il punto più importante

Il web server si avviava con `app.run(host="0.0.0.0")` **e** con l'autenticazione disattivata di default (`web_auth_token` vuoto). In pratica chiunque sulla stessa rete Wi‑Fi/LAN poteva aprire l'interfaccia e **muovere/cancellare i file del tuo Google Drive** senza credenziali. Correzioni:

- **Bind su `127.0.0.1` di default** (solo macchina locale). Esposizione in rete possibile solo opt‑in con `WEB_HOST=0.0.0.0`, sensato solo se imposti anche `WEB_AUTH_TOKEN`. Aggiunte anche le env `WEB_HOST` / `WEB_PORT`.
- **Confronto del token a tempo costante** (`hmac.compare_digest`) al posto di `==`, per non esporre il token via timing.

### 🟠 Robustezza e coerenza

- **Versione allineata**: `pyproject.toml` era ancora a `1.0.0` mentre il tag è `v1.5.0` → portato a `1.5.0`.
- **`email` inutilizzata** rimossa dalla route di preview (`organize.py`), che faceva una chiamata API senza usarne il risultato.

### 🟡 Qualità del codice e tooling

- Aggiunto **`ruff.toml`** (linter) con regole sensate; `scripts/` (i 54 script one‑off) esclusi perché artefatti d'uso, non libreria.
- Pulizia automatica su ~40 file: import inutilizzati rimossi, import riordinati, semplificazioni sicure (`dict()`→`{}`, `enumerate`, ecc.). Nessun cambiamento di comportamento.
- Aggiunto **`.github/workflows/ci.yml`**: lint + test su Python 3.11 e 3.12 a ogni push/PR.
- `ruff` aggiunto agli extra `dev` in `pyproject.toml`.

> Nota: ho **volutamente evitato** la conversione `timezone.utc → datetime.UTC` (suggerita dal linter): `datetime.UTC` esiste solo da Python 3.11, mentre `timezone.utc` funziona ovunque ed è equivalente. Regola disattivata in `ruff.toml`.

---

## 2. Interventi raccomandati (non applicati — richiedono una tua decisione)

### P0 — Da verificare subito

**Contratto SDK Anthropic.** In `haiku_provider.py` / `opus_provider.py` la chiamata usa `output_config={"format": {"type": "json_schema", ...}}`. È un parametro recente/non standard: se non combacia con la versione di `anthropic` installata, **fallisce a runtime** (e l'intera cascade ricade su Ollama o sul fallback "Altro"). Va verificato con uno smoke test reale o un test che registri una risposta. È il singolo punto più fragile della pipeline AI.

### P1 — Costi e performance AI (tema che ti interessa)

- **Telemetria di costo.** Oggi non si misurano token né costo per provider. Aggiungere un log di `input/output tokens` e costo stimato per livello (Ollama/Haiku/Opus) renderebbe **dimostrabile** il risparmio della cascade — utile anche per la proposta commerciale.
- **Precisione della cache.** La chiave è `(estensione, fascia_dimensione, mime)`: due PDF non collegati ma di dimensione simile condividono la stessa classificazione. Si può aggiungere un token normalizzato del nome (primo termine significativo) per alzare la precisione **senza inviare contenuto** al cloud.
- **Versioning della cache.** `.drive_organizer_cache.json` non ha TTL né versione: se cambi tassonomia, le voci vecchie restano valide per sempre. Aggiungere alla chiave una `schema_version`/hash della strategia per invalidarla automaticamente.
- **Parallelismo cloud.** Le batch Haiku/Opus sono sequenziali con `sleep(0.25)`. Con un piccolo pool di worker + gestione esplicita del 429 (il retry con backoff esiste già) si riducono i tempi sui Drive grandi.

### P1 — Robustezza

- **`except Exception: pass` silenziosi** in `cache.py` (load/save) e altrove: almeno un `logger.debug(...)` per non perdere errori diagnostici.
- **Lock file senza liveness.** L'executor blocca con un file `.lock` che contiene il PID ma non verifica se il processo è vivo: dopo un crash serve cancellarlo a mano. Si può controllare se il PID è ancora attivo e ripulire il lock stantio.

### P2 — Test e tipi

- **Provider non testati.** Non ci sono test per Haiku/Opus/Gemini/Ollama né per le route web (oltre a `test_web`). Aggiungere test che mockano i client SDK blinderebbe il parsing JSON (collegato al rischio P0).
- **Type checking in CI.** Aggiungere `mypy` o `pyright` al workflow: il codice usa già type hints estesi, sfruttarli.

### P2 — Funzionalità

- **Resume su Drive grandi.** Persistenza del progresso per riprendere una run interrotta senza riclassificare tutto.
- **Rollback parziale.** "Annulla le ultime N operazioni" oltre al rollback completo già presente.
- **Gestione multi‑account.** Comando per elencare/cambiare account (i token separati esistono già).

### P2 — Documentazione e distribuzione

- **Fonte unica per la versione.** Leggere la versione da `pyproject.toml` in `__init__.py` per non avere più disallineamenti.
- **Nota di sicurezza nel README** sul binding del web server e sul token (vedi fix P0 sopra).
- **`CHANGELOG.md`** con lo storico delle versioni.

---

## Come applicare la patch

```bash
cd drive-organizer
git apply miglioramenti_drive_organizer.patch
pip install -e ".[dev]"
ruff check .      # deve passare
pytest -q         # 82 passed
```

Se preferisci, posso anche applicare uno qualsiasi degli interventi P0/P1 e consegnarti la patch relativa.
