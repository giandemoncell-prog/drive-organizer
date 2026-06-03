# Drive Management Pipeline — Algoritmo

Algoritmo completo di organizzazione automatica e continua per Google Drive
personale. Implementa detection incrementale, classificazione a due livelli
(deterministica + AI), content reading per file ambigui, cascade AI robusto,
confidence gating, rollback universale e deduplicazione.

Moduli (in `drive_organizer/pipeline/`):

| File | Responsabilità |
|------|----------------|
| `manager.py` | `DriveManager`: orchestrazione (scan / classify / execute / audit / maintenance) |
| `ai_classifier.py` | `AIClassifier`: cascade Ollama → DeepSeek → Gemini, content reading, scoring |
| `rollback.py` | `PipelineRollback`: manifest compatibili col rollback esistente, undo LIFO |
| `__init__.py` | package marker (vuoto) |

---

## 1. Struttura target (6 top-level)

```
01_📂Documenti_Personali   → 🪪Identità 🏥Salute 💼Lavoro 🚗Veicoli 📋Legale_Fiscale 📄CV_Formazione 🌍Estero_Visti
02_📂Casa_e_Immobili        → 🏠×4 immobili + 💡Bollette 🏛️IMU 🔨Lavori 📑Aste 📄Generali
03_📂Scuola_e_Didattica     → 📚Libro_IA 🎓DSA_BES 👨‍🏫Docente 📝Materiali 🏫Documentazione
04_📂Progetti_e_Social      → Sviluppo BachataVibes Automazioni_Social HorizonWorlds
05_📂Workflow_Backup        → (nessuna sottocartella, file flat ok)
99_📂Archivio               → 📸Foto 🎮VR 💌Messaggi 📋Vari
```

La taxonomy (top-level → sottocartelle) e le regole keyword di livello 1 vivono
in `manager.py` (`DEFAULT_TAXONOMY`, `DEFAULT_L1_RULES`) e sono override-abili
via costruttore — nessuna modifica al codice per estenderle.

---

## 2. Flusso end-to-end

```
                       ┌─────────────────────────────────────────────┐
                       │            DriveManager.maintenance()        │
                       └─────────────────────────────────────────────┘
                                          │
              ┌───────────────────────────┼────────────────────────────┐
              ▼                                                          │
    ┌──────────────────┐                                                │
    │   1. SCAN         │  scan_all_files() (mai download del contenuto) │
    │  incremental?     │                                                │
    └──────────────────┘                                                │
              │  file "non organizzati":                                 │
              │    (a) flat in root                                      │
              │    (b) flat in top-level CON sottocartelle               │
              │    (c) modificati dopo last_run (solo incrementale)      │
              ▼                                                          │
    ┌──────────────────┐                                                │
    │ 2a. CLASSIFY L1   │  DETERMINISTICO (keyword/extension matching)   │
    │  top-level (6)    │  score≥2 → conf 1.0 | =1 → 0.7 | 0 → 0.3       │
    └──────────────────┘                                                │
              │                                                          │
              ▼                                                          │
    ┌──────────────────┐                                                │
    │ 2b. CLASSIFY L2   │  AIClassifier (sottocartella entro la top)     │
    │  sottocartelle    │  cascade + content reading + scoring           │
    └──────────────────┘                                                │
              │                                                          │
              ▼                                                          │
    ┌──────────────────┐        confidence < 0.6                        │
    │ 3. CONFIDENCE     │ ───────────────────────────►  REVIEW QUEUE     │
    │    GATING         │                               (non spostati)   │
    └──────────────────┘                                                │
              │  confidence ≥ 0.6                                        │
              ▼                                                          │
    ┌──────────────────┐                                                │
    │ 4. EXECUTE        │  get_or_create_folder_path + move_file         │
    │  + manifest       │  ogni move → PipelineRollback.record_move()    │
    └──────────────────┘  (manifest atomico/incrementale su disco)       │
              │                                                          │
              ▼                                                          │
    ┌──────────────────┐                                                │
    │ 5. DEDUP          │  find_duplicates(): md5 + nome normalizzato    │
    │  (segnalazione)   │  → report.duplicates (MAI eliminati)           │
    └──────────────────┘                                                │
              │                                                          │
              ▼                                                          │
        salva last_run ───────────────────────────────────────────────┘
        (state JSON per il prossimo scan incrementale)
```

L'`audit(folder)` è un sotto-flusso indipendente: percorre ricorsivamente una
top-level, riclassifica i file in L2 e sposta SOLO quelli con alta confidence
(≥ max(soglia, 0.75)) che risultano nella sotto-cartella sbagliata.

---

## 3. Cascade AI (`AIClassifier`)

```
   richiesta batch (metadati: nome, ext, mime, size, data — MAI contenuto al cloud)
        │
        ▼
   ┌────────────────────────────┐   conf ≥ 0.75   ┌──────────────┐
   │ Ollama (locale, GPU)       │ ───────────────►│  ACCETTATO   │
   │ batch=12, parallelismo 2   │                 └──────────────┘
   └────────────────────────────┘
        │ conf < 0.75
        ▼
   ┌────────────────────────────┐
   │ CONTENT READING (opzionale)│  solo se nome ambiguo (tr.pdf, tav.pdf, S.U.)
   │ extract_text_preview 500ch │  e file text-like (pdf/doc/txt/gdoc)
   │ Ollama content-aware       │  ⚠ contenuto resta LOCALE (mai al cloud)
   └────────────────────────────┘
        │ conf < 0.6
        ▼
   ┌────────────────────────────┐   conf ≥ 0.6 (+0.10 se accordo con Ollama)
   │ DeepSeek (cloud, batch=30) │ ──────────────────────────────────────────►
   └────────────────────────────┘                          ACCETTATO
        │ conf < 0.6
        ▼
   ┌────────────────────────────┐
   │ Gemini (cloud, batch=30)   │  livello finale (quando la quota è disponibile)
   └────────────────────────────┘
        │
        ▼
   confidence scoring finale:
     • +0.10 bonus accordo tra provider (stesso target_path)
     • −0.15 penalità se nome ambiguo e NON risolto via contenuto
     • clamp [0.0, 1.0]
```

Note di robustezza (dai problemi emersi in produzione):

- **JSON vuoto da Ollama su risposte grandi**: i provider cloud usano un singolo
  prompt batch; Ollama lavora a batch piccoli (12) con parallelismo limitato (2)
  per restare sotto la soglia che faceva fallire il modello 14B.
- **Skip provider non raggiungibili**: `health_check()` è chiamato prima di ogni
  livello; se fallisce, il livello viene saltato senza timeout per-file.
- **Errori non bloccanti**: ogni eccezione di provider produce un risultato a
  confidence 0.0 invece di abortire il batch (`_safe_batch`).
- **Quota cloud**: tetto `max_cloud_calls` (default 200) per evitare costi runaway;
  oltre il tetto i file restano nella review-queue.

---

## 4. Confidence scoring e review-queue

| Confidence finale | Azione |
|-------------------|--------|
| ≥ 0.75 | accettato già da Ollama (nessun costo cloud) |
| ≥ 0.60 e < 0.75 | accettato dopo content reading / cloud |
| < 0.60 | **review-queue**: NON spostato, restituito al chiamante |

L'audit alza la soglia a `max(soglia, 0.75)`: corregge solo quando è molto sicuro,
per non "ballare" i file ad ogni run.

---

## 5. Rollback universale (`PipelineRollback`)

Ogni operazione (`execute`, `audit`, e per estensione gli script `nest_/rescue_/
audit_`) registra un `RollbackManifest` **identico** a quello prodotto da
`PlanExecutor`:

- stessa cartella `settings.rollback_dir`, stesso prefisso `rollback_*.json`;
- compatibile con `drive_organizer.rollback.RollbackManager` → compare nella
  stessa lista e si annulla dalla stessa UI dell'app;
- scrittura **atomica e incrementale** (`os.replace` del `.tmp`): un crash a metà
  run lascia comunque un manifest valido e ripristinabile;
- undo **LIFO** (ordine inverso), tollerante a file già spostati/eliminati.

API di undo:

```python
rb = PipelineRollback(client, strategy="pipeline-execute", user_email=email)
with rb:
    rb.move_and_record(file_id, name, from_parent, to_parent)
restored, failed = rb.undo()                    # questa run
PipelineRollback.undo_last(client)              # ultima run (qualunque)
PipelineRollback.undo_manifest_file(client, p)  # un manifest specifico
```

---

## 6. Manutenzione incrementale

`maintenance()` legge `pipeline_state.json` (`last_run`, UTC ISO-8601). Lo scan
incrementale considera solo i file con `modifiedTime > last_run` (oltre ai flat
sempre considerati). Al termine di un run riuscito `last_run` viene aggiornato.
`maintenance(full=True)` forza un rescan completo ignorando il timestamp.

Uso tipico (es. da scheduler / cron):

```python
from drive_organizer.auth.google_auth import get_drive_service
from drive_organizer.drive.client import DriveClient
from drive_organizer.ai.ollama_provider import OllamaProvider
from drive_organizer.ai.deepseek_provider import DeepSeekFlashProvider
from drive_organizer.ai.gemini_provider import GeminiFlashProvider
from drive_organizer.pipeline.ai_classifier import AIClassifier
from drive_organizer.pipeline.manager import DriveManager

svc = get_drive_service()
client = DriveClient(svc)
classifier = AIClassifier(
    ollama=OllamaProvider(),
    deepseek=DeepSeekFlashProvider(),
    gemini=GeminiFlashProvider(),
    drive_service=svc,        # abilita il content reading
)
mgr = DriveManager(client, classifier, user_email="giandemoncell@gmail.com")

report = mgr.maintenance(dry_run=True)   # anteprima
print(report.moved, report.review_queue, report.duplicates.total_groups)
report = mgr.maintenance(dry_run=False)  # applica
```

---

## 7. Deduplicazione

Riusa `drive_organizer.duplicate_finder.find_duplicates`:

- **duplicati esatti**: stesso `md5Checksum`;
- **duplicati per nome**: nome normalizzato (rimossi `(1)`, `- Copia`, `copy`…),
  con almeno un membro che "sembra" una copia.

La pipeline **segnala** i gruppi in `report.duplicates` (mai eliminazione
automatica): la risoluzione resta una scelta esplicita dell'utente, coerente con
la policy "i duplicati vanno in `99_Archivio/Duplicati`, mai cancellati".

---

## 8. Privacy

- Lo scan e la classificazione di livello 1/2 usano **solo metadati**.
- Il **contenuto** dei file viene letto **esclusivamente** per nomi ambigui e
  passato **solo a Ollama locale** (`content_extractor.extract_text_preview`,
  con cleanup immediato del temp). Non lascia mai la macchina verso DeepSeek/Gemini.

---

## 9. Testabilità

Tutte le classi accettano le dipendenze in iniezione (duck-typing):

- `DriveManager(client, classifier, taxonomy=..., l1_rules=..., state_path=tmp)`
  — `client` può essere un fake con `scan_all_files()/move_file()/
  get_or_create_folder_path()`.
- `AIClassifier(ollama=Fake(), deepseek=None, gemini=None)` — i provider sono
  qualunque oggetto con `classify_batch()` e `health_check()`.
- `PipelineRollback(client, ...)` — scrive su `settings.rollback_dir`; nei test
  puntare `state_path`/`rollback_dir` a una tmpdir.

Funzioni pure facilmente unit-testabili: `is_ambiguous_name`, `_match_subfolder`,
`request_from_file`, `DriveManager._classify_l1`, `AIClassifier.split_by_confidence`.
