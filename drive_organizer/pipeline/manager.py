"""
DriveManager — orchestratore della pipeline di Drive Management.

Implementa l'algoritmo completo descritto in `PIPELINE_ALGORITHM.md`:

    scan → classify (L1 deterministico, L2 AI) → execute (con manifest rollback)
         → audit (correzione collocamenti) → maintenance (pipeline incrementale)

Concetti chiave:
  - **Livello 1 (top-level)**: 6 cartelle canoniche, classificazione DETERMINISTICA
    via keyword matching (taxonomy). Veloce, nessun costo AI.
  - **Livello 2 (sotto-cartelle)**: AI (`AIClassifier`) sceglie la sotto-cartella
    all'interno di una top-level, con confidence scoring.
  - **Detection**: un file è "non organizzato" se è flat in root, oppure flat in
    una top-level che possiede sotto-cartelle (quindi dovrebbe stare in una di
    esse), oppure se è stato modificato/aggiunto dopo l'ultimo run (incrementale).
  - **Confidence gating**: classificazioni sotto soglia finiscono in review-queue
    invece di essere spostate.
  - **Rollback universale**: ogni move passa per `PipelineRollback`, quindi è
    annullabile dalla stessa UI del resto dell'app.
  - **Deduplicazione**: riusa `drive_organizer.duplicate_finder` (md5 + nome).

Tutte le classi e i metodi sono importabili e testabili: `DriveManager` accetta
in iniezione il `DriveClient`, l'`AIClassifier` e (opzionale) la taxonomy, così
nei test si possono usare dei fake senza toccare la rete.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from drive_organizer.config import settings
from drive_organizer.drive.client import DriveClient
from drive_organizer.drive.models import DriveFile
from drive_organizer.duplicate_finder import DuplicatePlan, find_duplicates
from drive_organizer.pipeline.ai_classifier import AIClassifier
from drive_organizer.pipeline.rollback import PipelineRollback

_GFOLDER = "application/vnd.google-apps.folder"

# Le 6 top-level canoniche (struttura ottenuta in produzione). Le sottocartelle
# note guidano la fase L2; possono essere estese senza toccare il codice.
DEFAULT_TAXONOMY: dict[str, list[str]] = {
    "01_📂Documenti_Personali": [
        "🪪 Identità", "🏥 Salute", "💼 Lavoro", "🚗 Veicoli",
        "📋 Legale_Fiscale", "📄 CV_Formazione", "🌍 Estero_Visti",
    ],
    "02_📂Casa_e_Immobili": [
        "🏠 Via_Nazionale_122", "🏠 Sant'Antioco", "🏠 Sarroch", "🏠 Spettu_45",
        "💡 Bollette_Utenze", "🏛️ IMU_e_Tasse", "🔨 Lavori_Ristrutturazione",
        "📑 Aste_e_Vendite", "📄 Documenti_Generali",
    ],
    "03_📂Scuola_e_Didattica": [
        "📚 Libro_IA_KDP", "🎓 DSA_BES", "👨‍🏫 Pratiche_Docente",
        "📝 Materiali_Didattici", "🏫 Documentazione",
    ],
    "04_📂Progetti_e_Social": [
        "00_📂Sviluppo_e_Software", "01_📂BachataVibes",
        "03_📂Automazioni_Social", "HorizonWorlds",
    ],
    "05_📂Workflow_Backup": [],
    "99_📂Archivio": [
        "📸 Foto_2025", "🎮 HorizonWorlds_VR", "💌 Messaggi_Personali",
        "📋 Documenti_Vari",
    ],
}

# Keyword → top-level (livello 1 deterministico). Sottoinsieme curato a partire da
# taxonomy_emoji.json, mappato sulle 6 cartelle finali.
DEFAULT_L1_RULES: dict[str, list[str]] = {
    "01_📂Documenti_Personali": [
        "passaporto", "carta identità", "codice fiscale", "tessera sanitaria",
        "curriculum", "cv", "patente", "spid", "referto", "ricetta", "inps",
        "730", "redditi", "busta paga", "stipendio", "contratto lavoro",
        "permesso soggiorno", "nie", "visto", "denuncia", "querela",
    ],
    "02_📂Casa_e_Immobili": [
        "immobil", "appartamento", "affitto", "condominio", "catasto", "rogito",
        "planimetria", "visura", "locazione", "canone", "bolletta", "enel",
        "a2a", "tiscali", "abbanoa", "imu", "f24", "ristrutturazione", "asta",
        "sarroch", "quartucciu", "spettu", "sant'antioco", "via nazionale",
    ],
    "03_📂Scuola_e_Didattica": [
        "scuola", "docente", "alunno", "studente", "didattica", "lezione",
        "verifica", "pei", "pdp", "dsa", "bes", "sostegno", "ptof", "kdp",
        "manoscritto", "capitolo", "materiale didattico", "circolare",
    ],
    "04_📂Progetti_e_Social": [
        ".py", ".sh", ".bat", ".ts", ".js", "script", "deploy", "docker",
        "bachata", "vibes", "tiktok", "instagram", "facebook", "youtube",
        "social", "reel", "automazione", "horizonworlds", "workflow",
    ],
    "05_📂Workflow_Backup": [
        "n8n", "workflow_backup", "backup_workflow", "flows", "execution",
    ],
    "99_📂Archivio": [
        "vecchio", "obsoleto", "old", ".bak", ".log", ".eml", "duplicato",
    ],
}


@dataclass
class UnorganizedFile:
    """Un file candidato all'organizzazione, con il contesto di dove si trova."""
    file: DriveFile
    location: str          # "root" | "<top-level name>"
    parent_id: str
    reason: str            # perché è considerato non organizzato


@dataclass
class PlanItem:
    """Una decisione di spostamento (livello 1 o 2)."""
    file: DriveFile
    current_parent_id: str
    target_top: str                 # top-level di destinazione
    target_sub: str | None = None   # sotto-cartella (livello 2), o None
    confidence: float = 1.0
    provider: str = "deterministic"
    reasoning: str = ""

    @property
    def target_path(self) -> str:
        if self.target_sub:
            return f"{self.target_top}/{self.target_sub}"
        return self.target_top


@dataclass
class ExecutionReport:
    moved: int = 0
    skipped: int = 0
    failed: int = 0
    review_queue: list[PlanItem] = field(default_factory=list)
    manifest_path: str | None = None
    duplicates: DuplicatePlan | None = None


@dataclass
class AuditReport:
    folder: str
    checked: int = 0
    misplaced: list[PlanItem] = field(default_factory=list)
    corrected: int = 0
    manifest_path: str | None = None


class DriveManager:
    """Pipeline completa di Drive Management.

    Args:
        client:        DriveClient già autenticato.
        classifier:    AIClassifier per il livello 2 (sottocartelle).
        user_email:    email per i manifest di rollback.
        taxonomy:      mappa top-level → sottocartelle (default: DEFAULT_TAXONOMY).
        l1_rules:      keyword → top-level (default: DEFAULT_L1_RULES).
        confidence_threshold: sotto questa soglia i file vanno in review-queue.
        state_path:    file JSON con il timestamp dell'ultimo run (incrementale).
    """

    def __init__(
        self,
        client: DriveClient,
        classifier: AIClassifier,
        user_email: str = "",
        taxonomy: dict[str, list[str]] | None = None,
        l1_rules: dict[str, list[str]] | None = None,
        confidence_threshold: float = 0.6,
        state_path: str | Path | None = None,
    ) -> None:
        self._client = client
        self._classifier = classifier
        self._email = user_email
        self.taxonomy = taxonomy or DEFAULT_TAXONOMY
        self.l1_rules = l1_rules or DEFAULT_L1_RULES
        self.confidence_threshold = confidence_threshold
        self._state_path = Path(state_path or (Path(settings.rollback_dir) / "pipeline_state.json"))

        # Popolati durante scan().
        self._all_files: list[DriveFile] = []
        self._folder_map: dict[str, str] = {}      # folder_id → name
        self._name_to_id: dict[str, str] = {}       # top-level name → id
        self._top_has_subs: dict[str, bool] = {}    # top-level id → ha sottocartelle?
        self._loaded = False

    # ══════════════════════════════════════════════════════════════════════
    # 1. SCAN
    # ══════════════════════════════════════════════════════════════════════
    def scan(self, incremental: bool = True) -> list[UnorganizedFile]:
        """Identifica i file non organizzati.

        Non organizzato =
          (a) flat in root, oppure
          (b) flat in una top-level che ha sotto-cartelle (dovrebbe stare in una),
          (c) [incremental] modificato/aggiunto dopo l'ultimo run riuscito.

        Con `incremental=False` viene fatto uno scan completo (full rescan)."""
        self._load_tree()

        since = self._last_run_time() if incremental else None
        root_id = self._resolve_root_id()
        top_ids = set(self._name_to_id.values())

        unorg: list[UnorganizedFile] = []
        for f in self._all_files:
            parent = f.parents[0] if f.parents else "root"

            # (a) flat in root
            if parent in (root_id, "root") or not f.parents:
                if not f.is_folder:
                    if since and not self._is_newer(f, since):
                        continue
                    unorg.append(UnorganizedFile(f, "root", parent, "flat-in-root"))
                continue

            # (b) flat in top-level che possiede sottocartelle
            if parent in top_ids and self._top_has_subs.get(parent, False):
                if since and not self._is_newer(f, since):
                    continue
                top_name = self._folder_map.get(parent, "?")
                unorg.append(
                    UnorganizedFile(f, top_name, parent, "flat-in-top-with-subs")
                )
                continue

            # (c) incrementale: file nuovo/modificato ovunque → ricontrolla L2
            if since and self._is_newer(f, since) and parent in top_ids:
                top_name = self._folder_map.get(parent, "?")
                if self.taxonomy.get(top_name):
                    unorg.append(
                        UnorganizedFile(f, top_name, parent, "modified-since-last-run")
                    )

        return unorg

    # ══════════════════════════════════════════════════════════════════════
    # 2. CLASSIFY
    # ══════════════════════════════════════════════════════════════════════
    def classify(self, files: Iterable[UnorganizedFile], level: int = 1) -> list[PlanItem]:
        """Classifica i file al livello richiesto.

        level=1 → assegna la top-level con keyword matching DETERMINISTICO.
        level=2 → assegna la sotto-cartella con l'AIClassifier (confidence scoring).

        Il livello 2 va invocato dopo aver raggruppato i file per top-level
        (vedi `maintenance()` per l'uso combinato)."""
        items = list(files)
        if level == 1:
            return [self._classify_l1(uf) for uf in items]
        if level == 2:
            return self._classify_l2(items)
        raise ValueError(f"level deve essere 1 o 2, ricevuto {level!r}")

    def _classify_l1(self, uf: UnorganizedFile) -> PlanItem:
        name_l = uf.file.name.lower()
        ext = (uf.file.file_extension or "").lower()
        best_top = "99_📂Archivio"
        best_score = 0
        for top, keywords in self.l1_rules.items():
            score = 0
            for kw in keywords:
                if kw.startswith(".") and ext and ext == kw[1:]:
                    score += 2
                elif kw in name_l:
                    score += 1
            if score > best_score:
                best_score = score
                best_top = top
        confidence = 1.0 if best_score >= 2 else (0.7 if best_score == 1 else 0.3)
        return PlanItem(
            file=uf.file,
            current_parent_id=uf.parent_id,
            target_top=best_top,
            confidence=confidence,
            provider="deterministic",
            reasoning=f"L1 keyword score={best_score}",
        )

    def _classify_l2(self, items: list[UnorganizedFile]) -> list[PlanItem]:
        """Per ciascuna top-level, chiede all'AI la sotto-cartella migliore."""
        out: list[PlanItem] = []
        # Raggruppa per top-level (la location indica già dove sta il file).
        by_top: dict[str, list[UnorganizedFile]] = {}
        for uf in items:
            top = uf.location if uf.location in self.taxonomy else self._guess_top(uf)
            by_top.setdefault(top, []).append(uf)

        for top, group in by_top.items():
            subs = self.taxonomy.get(top, [])
            if not subs:
                # top-level senza sottocartelle: il file resta lì (livello 1).
                for uf in group:
                    out.append(PlanItem(
                        file=uf.file, current_parent_id=uf.parent_id,
                        target_top=top, confidence=1.0, provider="deterministic",
                        reasoning="top-level senza sottocartelle",
                    ))
                continue

            hint = (
                f"Classifica i file nella sotto-cartella corretta di '{top}'. "
                f"Usa SOLO una di queste cartelle."
            )
            drive_files = [uf.file for uf in group]
            results = self._classifier.classify(drive_files, hint, allowed_folders=subs)
            by_id = {r.file_id: r for r in results}
            for uf in group:
                res = by_id.get(uf.file.id)
                sub = _match_subfolder(res.target_path if res else "", subs)
                out.append(PlanItem(
                    file=uf.file,
                    current_parent_id=uf.parent_id,
                    target_top=top,
                    target_sub=sub,
                    confidence=res.confidence if res else 0.0,
                    provider=res.provider if res else "deterministic",
                    reasoning=res.reasoning if res else "no result",
                ))
        return out

    # ══════════════════════════════════════════════════════════════════════
    # 3. EXECUTE
    # ══════════════════════════════════════════════════════════════════════
    def execute(self, plan: list[PlanItem], dry_run: bool = False) -> ExecutionReport:
        """Esegue il piano spostando i file e registrando un manifest di rollback.

        I file con confidence < soglia finiscono in `report.review_queue` e NON
        vengono spostati. Con `dry_run=True` nulla viene scritto su Drive."""
        self._load_tree()
        report = ExecutionReport()

        confident: list[PlanItem] = []
        for item in plan:
            if item.confidence < self.confidence_threshold:
                report.review_queue.append(item)
            else:
                confident.append(item)

        if dry_run:
            report.skipped = len(plan)
            return report

        if not confident:
            return report

        rb = PipelineRollback(
            self._client, strategy="pipeline-execute", user_email=self._email
        )
        with rb:
            for item in confident:
                target_id = self._ensure_folder(item.target_path)
                if item.current_parent_id == target_id:
                    report.skipped += 1
                    continue
                ok = rb.move_and_record(
                    file_id=item.file.id,
                    file_name=item.file.name,
                    from_parent=item.current_parent_id,
                    to_parent=target_id,
                )
                if ok:
                    report.moved += 1
                else:
                    report.failed += 1
            report.manifest_path = str(rb.manifest_path)

        self._save_run_time()
        return report

    # ══════════════════════════════════════════════════════════════════════
    # 4. AUDIT
    # ══════════════════════════════════════════════════════════════════════
    def audit(self, folder: str, dry_run: bool = False) -> AuditReport:
        """Verifica ricorsivamente una top-level e corregge i collocamenti errati.

        Per ogni file dentro `folder` (e sue sottocartelle), riclassifica al
        livello 2 e, se l'AI indica con alta confidence una sotto-cartella diversa
        da quella attuale, lo sposta (registrando il rollback)."""
        self._load_tree()
        top_id = self._name_to_id.get(folder)
        report = AuditReport(folder=folder)
        if not top_id:
            return report

        subs = self.taxonomy.get(folder, [])
        sub_ids = {self._folder_map.get(cid): cid
                   for cid in self._children_folder_ids(top_id)}

        # Tutti i file (ricorsivi) sotto la top-level.
        descendant_files = self._descendant_files(top_id)
        report.checked = len(descendant_files)
        if not subs or not descendant_files:
            return report

        hint = f"Verifica la sotto-cartella corretta di '{folder}'. Usa SOLO queste."
        results = self._classifier.classify(descendant_files, hint, allowed_folders=subs)
        by_id = {r.file_id: r for r in results}

        misplaced: list[PlanItem] = []
        for f in descendant_files:
            res = by_id.get(f.id)
            if not res or res.confidence < max(self.confidence_threshold, 0.75):
                continue  # audit è conservativo: corregge solo con alta confidence
            want_sub = _match_subfolder(res.target_path, subs)
            if not want_sub:
                continue
            want_id = sub_ids.get(want_sub)
            current = f.parents[0] if f.parents else None
            if want_id and current and current != want_id:
                misplaced.append(PlanItem(
                    file=f, current_parent_id=current, target_top=folder,
                    target_sub=want_sub, confidence=res.confidence,
                    provider=res.provider, reasoning=res.reasoning,
                ))

        report.misplaced = misplaced
        if dry_run or not misplaced:
            return report

        rb = PipelineRollback(
            self._client, strategy=f"pipeline-audit:{folder}", user_email=self._email
        )
        with rb:
            for item in misplaced:
                target_id = self._ensure_folder(item.target_path)
                if rb.move_and_record(
                    item.file.id, item.file.name, item.current_parent_id, target_id
                ):
                    report.corrected += 1
            report.manifest_path = str(rb.manifest_path)
        return report

    # ══════════════════════════════════════════════════════════════════════
    # 5. MAINTENANCE (pipeline completa incrementale)
    # ══════════════════════════════════════════════════════════════════════
    def maintenance(self, dry_run: bool = False, full: bool = False) -> ExecutionReport:
        """Pipeline completa: scan incrementale → L1 → L2 → execute → dedup.

        Con `full=True` fa uno scan completo invece che incrementale.
        Restituisce un ExecutionReport con i conteggi e la review-queue."""
        self._load_tree()
        unorg = self.scan(incremental=not full)

        # Deduplicazione (segnalazione, mai eliminazione).
        dup_plan = find_duplicates(self._all_files)

        if not unorg:
            report = ExecutionReport(duplicates=dup_plan)
            if not dry_run:
                self._save_run_time()
            return report

        # Livello 1: assegna la top-level deterministicamente.
        l1 = self.classify(unorg, level=1)
        # I file flat-in-top restano nella loro top-level: forziamo la top corrente.
        l1_by_id = {}
        for uf, item in zip(unorg, l1):
            if uf.location in self.taxonomy:
                item.target_top = uf.location
            l1_by_id[uf.file.id] = item

        # Livello 2: per le top-level con sottocartelle, l'AI sceglie la sub.
        #   Costruiamo UnorganizedFile "virtuali" con la top assegnata in L1.
        for_l2: list[UnorganizedFile] = []
        passthrough: list[PlanItem] = []
        for uf in unorg:
            item = l1_by_id[uf.file.id]
            if self.taxonomy.get(item.target_top):
                for_l2.append(UnorganizedFile(
                    uf.file, item.target_top, uf.parent_id, uf.reason
                ))
            else:
                passthrough.append(item)  # nessuna sotto-cartella: resta in top

        l2 = self._classify_l2(for_l2) if for_l2 else []
        plan = passthrough + l2

        report = self.execute(plan, dry_run=dry_run)
        report.duplicates = dup_plan
        return report

    # ══════════════════════════════════════════════════════════════════════
    # Helpers Drive / stato
    # ══════════════════════════════════════════════════════════════════════
    def _load_tree(self) -> None:
        if self._loaded:
            return
        files, folder_map = self._client.scan_all_files()
        self._all_files = files
        self._folder_map = folder_map

        # top-level = cartelle figlie della root il cui nome è nella taxonomy.
        self._name_to_id = {}
        for fid, fname in folder_map.items():
            if fname in self.taxonomy:
                self._name_to_id[fname] = fid

        # quali top-level hanno effettivamente sottocartelle su Drive.
        self._top_has_subs = {}
        for top_name, top_id in self._name_to_id.items():
            has = any(self._folder_map.get(cid) for cid in self._children_folder_ids(top_id))
            self._top_has_subs[top_id] = bool(has) or bool(self.taxonomy.get(top_name))

        self._loaded = True

    def refresh(self) -> None:
        """Forza un nuovo scan al prossimo accesso (dopo modifiche su Drive)."""
        self._loaded = False
        self._client._folder_cache.clear()

    def _resolve_root_id(self) -> str:
        """ID della cartella root del My Drive.

        Le top-level canoniche sono figlie della root: il loro parent comune è il
        vero root id. Se non deducibile, ripiega su 'root' (alias accettato dalle
        API Drive)."""
        if self._name_to_id:
            parents = [
                f.parents[0]
                for f in self._all_files
                if f.is_folder and f.id in self._name_to_id.values() and f.parents
            ]
            if parents:
                # il parent più frequente delle top-level è la root.
                return max(set(parents), key=parents.count)
        return "root"

    def _children_folder_ids(self, parent_id: str) -> list[str]:
        return [
            f.id for f in self._all_files
            if f.is_folder and f.parents and f.parents[0] == parent_id
        ]

    def _descendant_files(self, root_id: str) -> list[DriveFile]:
        """Tutti i file (non-folder) discendenti di root_id, ricorsivamente."""
        children_of: dict[str, list[DriveFile]] = {}
        for f in self._all_files:
            p = f.parents[0] if f.parents else None
            if p:
                children_of.setdefault(p, []).append(f)
        out: list[DriveFile] = []
        stack = [root_id]
        seen: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for child in children_of.get(cur, []):
                if child.is_folder:
                    stack.append(child.id)
                else:
                    out.append(child)
        return out

    def _ensure_folder(self, path: str) -> str:
        """Crea/risolve la cartella (top/sub) e ritorna il suo id."""
        return self._client.get_or_create_folder_path(path, "root")

    def _guess_top(self, uf: UnorganizedFile) -> str:
        return self._classify_l1(uf).target_top

    # ── stato incrementale ────────────────────────────────────────────────
    def _last_run_time(self) -> datetime | None:
        if not self._state_path.exists():
            return None
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return datetime.fromisoformat(data["last_run"])
        except Exception:
            return None

    def _save_run_time(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_run": datetime.now(timezone.utc).isoformat()}
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._state_path)

    @staticmethod
    def _is_newer(f: DriveFile, since: datetime) -> bool:
        mt = f.modified_time
        if mt.tzinfo is None:
            mt = mt.replace(tzinfo=timezone.utc)
        s = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        return mt > s


def _match_subfolder(target_path: str, subs: list[str]) -> str | None:
    """Mappa la risposta libera dell'AI su una delle sottocartelle ammesse.

    Tollerante: prova match esatto, poi per ultimo segmento del path, poi per
    contenuto testuale ignorando emoji e maiuscole."""
    if not target_path:
        return None
    candidate = target_path.split("/")[-1].strip()

    # 1. match esatto
    if candidate in subs:
        return candidate

    # 2. confronto normalizzato (senza emoji, lowercase, no spazi/underscore)
    def norm(s: str) -> str:
        return "".join(c for c in s.lower() if c.isalnum())

    cnorm = norm(candidate)
    for sub in subs:
        if norm(sub) == cnorm:
            return sub
    # 3. substring
    for sub in subs:
        sn = norm(sub)
        if sn and (sn in cnorm or cnorm in sn):
            return sub
    return None
