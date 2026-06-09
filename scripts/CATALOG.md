# Scripts — Catalogo

Struttura: `scripts/<gruppo>/<script>`

| File | Percorso | Funzione |
|------|----------|----------|
| `smoke_test_parallel_scan.py` | `inspect/` | Smoke test scan parallelo su Drive reale |
| `folder_stats.py` | `inspect/` | Statistiche cartelle top-level (file + sottocartelle) |
| `list_folders.py` | `inspect/` | Lista cartelle root con indicazione ownership |
| `list_bollette_lavori.py` | `inspect/` | Lista file in Bollette_Utenze e Lavori_Ristrutturazione |
| `list_documenti_vari.py` | `inspect/` | Lista file in Documenti_Vari |
| `check_cv_formazione.py` | `inspect/` | Lista file in CV_Formazione |
| `scan_archivio.py` | `inspect/` | Lista file flat in 99_Archivio |
| `count_old_folders.py` | `inspect/` | Conta contenuto delle vecchie cartelle pre-riorganizzazione |
| `map_old_subfolders.py` | `inspect/` | Mostra piano merge vecchie cartelle → nuove (solo stampa) |
| `audit_all.py` | `audit/` | Audit ciclico tutte le cartelle top-level via AI (verifica posizione file) |
| `audit_and_rename.py` | `audit/` | Pipeline completa: audit posizioni + rename file non leggibili |
| `audit_casa_immobili.py` | `audit/` | Audit specifico 02_Casa_e_Immobili (sposta fuori i file errati) |
| `fix_cv_formazione.py` | `fix/` | Sposta file non pertinenti fuori da CV_Formazione |
| `fix_documenti_vari.py` | `fix/` | Sposta file da Documenti_Vari nelle cartelle corrette (v1) |
| `fix_documenti_vari2.py` | `fix/` | Sposta file da Documenti_Vari (v2 — bulk load, evita apostrofi) |
| `fix_dv3.py` | `fix/` | Sposta file rimanenti in Documenti_Vari (v3) |
| `fix_bollette_lavori_by_property.py` | `fix/` | Organizza Bollette e Lavori per immobile con AI |
| `fix_dup_archivio.py` | `fix/` | Merge due cartelle 99_Archivio duplicate in una sola |
| `nest_documenti.py` | `nest/` | Crea sottocartelle in 01_Documenti_Personali via AI |
| `nest_documenti2.py` | `nest/` | Nesting documenti v2 (con content preview per file ambigui) |
| `nest_legale_fiscale.py` | `nest/` | Suddivide Legale_Fiscale in Pratiche/Fisco/Contratti/Polizze |
| `nest_casa.py` | `nest/` | Nesta 02_Casa_e_Immobili per immobile + categoria |
| `nest_scuola.py` | `nest/` | Nesta 03_Scuola_e_Didattica in KDP/DSA/Docente/Materiali |
| `nest_veicoli.py` | `nest/` | Nesta Veicoli in Panda/Assicurazioni/Manutenzione/Acquisto |
| `nest_progetti_social.py` | `nest/` | Nesta 04_Progetti_e_Social nelle sottocartelle esistenti |
| `nest_workflow.py` | `nest/` | Nesta 05_Workflow_Backup con AI (propone sottocartelle) |
| `nest_archivio.py` | `nest/` | Nesta 99_Archivio: smista file tra sottocartelle interne ed esterni |
| `nested_organizer.py` | `nest/` | Organizer generico: classifica file flat in tutte le cartelle |
| `full_drive_organize.py` | `nest/` | Pipeline completa: rinumerazione top-level + nesting AI |
| `merge_old_folders.py` | `restructure/` | Merge cartelle vecchie in nuove + emoji + colori Drive |
| `restructure_casa.py` | `restructure/` | Ristruttura 05_Casa_e_Immobili in macro-categorie |
| `restructure_scuola_viaggi.py` | `restructure/` | Ristruttura Scuola (consolida 23 micro) e Viaggi/Hobby |
| `flatten_archivio.py` | `restructure/` | Riporta 99_Archivio flat (undo nesting, conserva sottocartelle originali) |
| `rescue_archivio.py` | `restructure/` | Sposta intero contenuto di 99_Archivio nelle cartelle giuste |
| `renumber.py` | `restructure/` | Rinumerazione cartelle top-level (02→01, 05→02 ecc.) |
| `swap_00_02.py` | `restructure/` | One-off: swap prefissi 00↔02 tra Documenti e Sviluppo |
| `swap_folders.py` | `restructure/` | One-off: swap prefissi 00↔04 tra Workflow e Documenti |
| `move_into_viaggi.py` | `restructure/` | Sposta 03_Automazioni dentro 04_Progetti_e_Social |
| `move_py_files.py` | `restructure/` | Sposta tutti i *.py da 01_Documenti a 00_Sviluppo |
| `trash_batch1_folders.py` | `cleanup/` | Cestina batch 1 cartelle root obsolete (Video, Viaggi, Sviluppo, Personale) |
| `trash_batch2.py` | `cleanup/` | Cestina batch 2 cartelle root obsolete (Lavoro, Foto, Formazione, Finanza) |
| `trash_batch3_folders.py` | `cleanup/` | Cestina batch 3 cartelle root obsolete (Fatture, Contratti, Clienti, Altro) |
| `trash_batch4_residual.py` | `cleanup/` | Cestina batch 4 cartelle residuali (PDF, Fogli, Documenti, Gemini Gems) |
| `empty_trash.py` | `cleanup/` | Svuota cestino Google Drive |
| `cleanup_empty_subfolders.py` | `cleanup/` | Elimina ricorsivamente tutte le sottocartelle vuote |
| `configure.py` | `setup/` | Configuratore interattivo .env (chiavi API, soglie) |
| `rename_all_batches.ps1` | `setup/` | Script PowerShell per eseguire rename a batch progressivi |
| `install-chromebook.sh` | `setup/` | Installazione Drive Organizer su Chromebook (Linux) |
| `install-linux.sh` | `setup/` | Installazione Drive Organizer su Linux generico |
| `uninstall-chromebook.sh` | `setup/` | Disinstallazione da Chromebook |
| `uninstall-linux.sh` | `setup/` | Disinstallazione da Linux |
