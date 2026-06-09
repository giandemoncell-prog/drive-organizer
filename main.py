from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import certifi
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from drive_organizer.logging_config import setup_logging

setup_logging()

console = Console(legacy_windows=False)

_ACCOUNT_OPTION = click.option(
    "--account", "-a",
    default=None,
    metavar="EMAIL",
    help="Account Google da usare (email). Se omesso: auto-selezione.",
)


def _check_credentials():
    from drive_organizer.config import settings
    if not Path(settings.credentials_path).exists():
        console.print(Panel(
            "[bold red]credentials.json non trovato.[/bold red]\n\n"
            "1. Vai su https://console.cloud.google.com\n"
            "2. Crea un progetto e abilita [bold]Google Drive API v3[/bold]\n"
            "3. Crea credenziali [bold]OAuth 2.0 > App desktop[/bold]\n"
            "4. Scarica il JSON e salvalo come [bold]credentials.json[/bold] in questa cartella",
            title="Setup richiesto",
            border_style="red",
        ))
        sys.exit(1)


def _build_cascade():
    from drive_organizer.ai.factory import build_cascade
    from drive_organizer.config import settings
    if not any([settings.anthropic_api_key, settings.gemini_api_key,
                settings.deepseek_api_key, settings.dashscope_api_key]):
        console.print(
            "[yellow]Avviso: nessuna API key cloud configurata.[/yellow]\n"
            "Solo Ollama locale verrà usato. Configura una chiave in [bold].env[/bold] per la cascade completa."
        )
    return build_cascade()


@click.group()
def cli():
    """Drive Organizer — riorganizza Google Drive con AI locale + cloud."""


@cli.command()
def setup():
    """Setup guidato per il primo avvio (wizard interattivo)."""
    from drive_organizer.wizard import run_setup
    run_setup()


@cli.command()
@_ACCOUNT_OPTION
def auth(account):
    """Autenticazione Google Drive (apre il browser)."""
    _check_credentials()
    from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
    console.print("Apertura browser per autenticazione Google…")
    try:
        svc = get_drive_service(account)
        email = get_authenticated_email(svc)
        console.print(f"[green]Autenticato come:[/green] {email}")
        console.print(f"[dim]Token salvato in tokens/{email}.json[/dim]")
    except Exception as e:
        console.print(f"[red]Errore autenticazione:[/red] {e}")
        sys.exit(1)


@cli.command()
def accounts():
    """Mostra gli account Google autenticati."""
    from drive_organizer.auth.google_auth import list_accounts
    accs = list_accounts()
    if not accs:
        console.print("[yellow]Nessun account autenticato. Esegui: python main.py auth[/yellow]")
        return
    table = Table(title="Account autenticati", show_lines=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Email")
    for i, email in enumerate(accs, 1):
        table.add_row(str(i), email)
    console.print(table)


@cli.command()
@_ACCOUNT_OPTION
def status(account):
    """Mostra statistiche Drive e stato componenti AI."""
    _check_credentials()
    from drive_organizer.ai.ollama_provider import OllamaProvider
    from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
    from drive_organizer.config import settings
    from drive_organizer.drive.client import DriveClient

    console.print("[bold]Connessione a Google Drive…[/bold]")
    try:
        svc = get_drive_service(account)
        email = get_authenticated_email(svc)
        client = DriveClient(svc)
        about = client.get_about()
    except Exception as e:
        console.print(f"[red]Errore Drive:[/red] {e}")
        sys.exit(1)

    quota = about.get("storageQuota", {})
    used = int(quota.get("usage", 0))
    limit = int(quota.get("limit", 0))
    used_gb = used / 1e9
    limit_gb = limit / 1e9 if limit else 0

    table = Table(title=f"Drive: {email}", show_lines=True)
    table.add_column("Componente", style="bold")
    table.add_column("Stato")

    table.add_row("Google Drive", f"[green]Connesso[/green] — {email}")
    table.add_row("Storage", f"{used_gb:.2f} GB / {limit_gb:.0f} GB" if limit_gb else f"{used_gb:.2f} GB")

    ollama = OllamaProvider()
    ollama_ok = ollama.health_check()
    table.add_row("Ollama", f"[green]{settings.ollama_model}[/green]" if ollama_ok else "[red]Non raggiungibile[/red]")

    api_ok = bool(settings.anthropic_api_key)
    gemini_ok = bool(settings.gemini_api_key)
    table.add_row("Haiku 4.5 / Gemini Flash",
        "[green]Anthropic[/green]" if api_ok else
        ("[green]Gemini[/green]" if gemini_ok else "[yellow]Nessuna API key[/yellow]"))
    table.add_row("Opus 4.8 / Gemini Pro",
        "[green]Anthropic[/green]" if api_ok else
        ("[green]Gemini[/green]" if gemini_ok else "[yellow]Nessuna API key[/yellow]"))

    console.print(table)

    console.print("\n[bold]Scansione file in corso…[/bold]")
    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        prog.add_task("Lettura metadati…")
        files, _folder_map = client.scan_all_files()

    from collections import Counter

    from drive_organizer.strategies.by_type import _MIME_MAP
    type_counts: Counter = Counter()
    for f in files:
        cat = _MIME_MAP.get(f.mime_type, "Altro")
        type_counts[cat] += 1

    stat_table = Table(title=f"File trovati: {len(files)}", show_lines=True)
    stat_table.add_column("Tipo")
    stat_table.add_column("Conteggio", justify="right")
    for cat, count in type_counts.most_common():
        stat_table.add_row(cat, str(count))
    console.print(stat_table)


@cli.command()
@_ACCOUNT_OPTION
@click.option(
    "--strategy", "-s",
    type=click.Choice(["type", "project", "date", "custom"]),
    default=None,
    help="Strategia di organizzazione",
)
@click.option("--custom-prompt", "-p", default=None, help="Descrizione struttura (per --strategy custom)")
@click.option("--taxonomy-file", "-t", default=None, help="JSON con tassonomia pre-costruita (bypassa Opus)")
@click.option("--taxonomy-preset", default=None, metavar="NOME",
              help="Template preset: lavoro, personale, scolastico_docente, ecc.")
@click.option("--apply", is_flag=True, default=False, help="Applica le modifiche (default: solo preview)")
@click.option("--yes", "-y", is_flag=True, default=False, help="Conferma automaticamente senza prompt interattivo")
@click.option("--ollama-model", default=None, help="Override modello Ollama")
@click.option("--no-haiku", is_flag=True, default=False, help="Salta Haiku, va diretto a Opus per l'escalation")
@click.option("--year-only", is_flag=True, default=False, help="Per --strategy date: solo Anno (senza Mese)")
@click.option("--incremental", is_flag=True, default=False, help="Scan incrementale (più veloce su Drive già scansionati)")
@click.option("--export", "export_path", default=None, metavar="FILE",
              help="Esporta il piano in FILE (.csv o .json) dopo il dry-run")
def organize(account, strategy, custom_prompt, taxonomy_file, taxonomy_preset, apply, yes, ollama_model, no_haiku, year_only, incremental, export_path):
    """Analizza Google Drive e propone (o applica) una riorganizzazione."""
    _check_credentials()

    if taxonomy_preset and not strategy:
        strategy = "custom"

    if not strategy:
        strategy = click.prompt(
            "Strategia",
            type=click.Choice(["type", "project", "date", "custom"]),
        )

    if taxonomy_preset and not taxonomy_file:
        preset_path = Path("taxonomies") / f"taxonomy_{taxonomy_preset}.json"
        if not preset_path.exists():
            available = sorted(
                p.stem[len("taxonomy_"):]
                for p in Path("taxonomies").glob("taxonomy_*.json")
            )
            console.print(f"[red]Preset '{taxonomy_preset}' non trovato.[/red]")
            if available:
                console.print(f"Disponibili: {', '.join(available)}")
            sys.exit(1)
        taxonomy_file = str(preset_path)

    if strategy == "custom" and not custom_prompt and not taxonomy_file:
        custom_prompt = click.prompt("Descrivi la struttura desiderata (IT/EN)")

    from drive_organizer.config import settings
    if ollama_model:
        settings.ollama_model = ollama_model

    from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
    from drive_organizer.drive.client import DriveClient
    from drive_organizer.planner import OrganizationPlanner
    from drive_organizer.ui.tree_diff import print_diff

    console.print("\n[bold]Connessione Google Drive…[/bold]")
    svc = get_drive_service(account)
    email = get_authenticated_email(svc)
    client = DriveClient(svc)
    console.print(f"[green]Connesso come:[/green] {email}")

    console.print("[bold]Scansione file (metadati only)…[/bold]")
    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as prog:
        t = prog.add_task("Lettura Drive…")
        if incremental:
            safe_email = email.replace("@", "_at_").replace(".", "_")
            state_path = Path(settings.rollback_dir) / f"scan_state_{safe_email}.json"
            files, folder_map = client.scan_incremental(state_path, prog, t)
        else:
            files, folder_map = client.scan_all_files(prog, t)
    console.print(f"[green]{len(files)} file trovati.[/green]")

    strat = _build_strategy(strategy, custom_prompt, no_haiku, taxonomy_file, year_only=year_only)

    console.print(f"\n[bold]Classificazione con strategia '{strategy}'…[/bold]")
    cascade = None
    if strat.requires_ai():
        cascade = _build_cascade()
        if no_haiku:
            cascade._haiku = cascade._opus
        ollama_ok = cascade._ollama.health_check()
        if not ollama_ok:
            console.print("[yellow]Avviso: Ollama non raggiungibile — i file ambigui verranno escalati a cloud.[/yellow]")

    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        t = prog.add_task("Classificazione…", total=len(files))
        planner = OrganizationPlanner(cascade=cascade)
        plan = planner.build_plan(files, strat, prog, t)

    print_diff(console, plan, files, folder_map)

    if export_path:
        from drive_organizer.exporter import export_plan
        try:
            export_plan(plan, Path(export_path), folder_map)
            console.print(f"[green]Piano esportato:[/green] {export_path}")
        except ValueError as e:
            console.print(f"[red]Export non riuscito:[/red] {e}")

    active = [op for op in plan.moves if not op.skipped]
    if not active:
        console.print("[green]Nessuna modifica necessaria. Drive già organizzato.[/green]")
        return

    if not apply:
        console.print("[bold yellow]Modalità preview (dry-run). Usa --apply per eseguire.[/bold yellow]")
        return

    from drive_organizer.ui.prompts import confirm_apply
    if not confirm_apply(console, len(active), yes=yes):
        console.print("[yellow]Operazione annullata.[/yellow]")
        return

    from drive_organizer.executor import PlanExecutor
    executor = PlanExecutor(client, email)
    manifest = executor.execute(plan)
    console.print(f"\n[green]Completato![/green] {len(manifest.entries)} file spostati.")
    console.print(f"[dim]Rollback disponibile: logs/rollback_{manifest.run_id[:8]}_*.json[/dim]")


@cli.command()
@_ACCOUNT_OPTION
@click.option("--apply", is_flag=True, default=False, help="Applica le rinomina (default: solo preview)")
@click.option("--yes", "-y", is_flag=True, default=False, help="Conferma automaticamente senza prompt interattivo")
@click.option("--limit", default=0, help="Analizza solo N file (0 = tutti)", type=int)
@click.option("--offset", default=0, help="Salta i primi N file (per elaborare in batch)", type=int)
@click.option("--min-confidence", default=0.65, help="Soglia confidenza minima (0.0-1.0)", type=float)
@click.option("--incremental", is_flag=True, default=False, help="Scan incrementale (più veloce su Drive già scansionati)")
def rename(account, apply, yes, limit, offset, min_confidence, incremental):
    """Rinomina i file usando Ollama (AI locale — contenuto mai al cloud)."""
    _check_credentials()

    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
    from drive_organizer.config import settings
    from drive_organizer.drive.client import DriveClient
    from drive_organizer.renamer import FileRenamer
    from drive_organizer.ui.rename_diff import print_rename_preview

    console.print("\n[bold]Connessione Google Drive…[/bold]")
    svc = get_drive_service(account)
    email = get_authenticated_email(svc)
    client = DriveClient(svc)
    console.print(f"[green]Connesso come:[/green] {email}")

    renamer = FileRenamer(svc, confidence_threshold=min_confidence)
    if not renamer.health_check():
        console.print(
            "[red]Ollama non raggiungibile.[/red]\n"
            "La rinomina usa solo Ollama locale per garantire la privacy.\n"
            "Avvia Ollama con: [cyan]ollama serve[/cyan]"
        )
        return

    console.print("[bold]Scansione file…[/bold]")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        t = prog.add_task("Lettura Drive…")
        if incremental:
            safe_email = email.replace("@", "_at_").replace(".", "_")
            state_path = Path(settings.rollback_dir) / f"scan_state_{safe_email}.json"
            files, _ = client.scan_incremental(state_path, prog, t)
        else:
            files, _ = client.scan_all_files(prog, t)

    movable = [f for f in files if not f.is_folder and not f.is_shortcut and f.owned_by_me]
    if offset > 0:
        movable = movable[offset:]
        console.print(f"[dim]Salti i primi {offset} file.[/dim]")
    if limit > 0:
        movable = movable[:limit]
        console.print(f"[dim]Analisi limitata a {limit} file (offset {offset}).[/dim]")
    console.print(f"[green]{len(movable)} file da analizzare.[/green]")

    console.print(f"\n[bold]Analisi nomi con Ollama ({renamer._model})…[/bold]")
    console.print("[dim]Il contenuto dei file rimane sul tuo dispositivo — non raggiunge mai il cloud.[/dim]\n")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("Analisi file…", total=len(movable))
        plan = renamer.build_plan(movable, prog, task)

    print_rename_preview(console, plan)

    active = [op for op in plan.operations if not op.skipped]
    if not active:
        return

    if not apply:
        console.print("[bold yellow]Modalità preview. Usa --apply per rinominare.[/bold yellow]")
        return

    if not yes and not click.confirm(f"Rinominare {len(active)} file?", default=False):
        console.print("[yellow]Annullato.[/yellow]")
        return

    from drive_organizer.rename_executor import RenameExecutor
    executor = RenameExecutor(client, email)
    manifest = executor.execute(plan)
    console.print(f"\n[green]Completato![/green] {len(manifest.entries)} file rinominati.")
    console.print(f"[dim]Rollback disponibile: logs/rename_{manifest.run_id[:8]}_*.json[/dim]")


@cli.command(name="rename-rollback")
@_ACCOUNT_OPTION
def rename_rollback(account):
    """Annulla una sessione di rinomina precedente."""
    _check_credentials()
    from rich.table import Table as RichTable

    from drive_organizer.auth.google_auth import get_drive_service
    from drive_organizer.drive.client import DriveClient
    from drive_organizer.rename_executor import RenameRollbackManager

    svc = get_drive_service(account)
    client = DriveClient(svc)
    mgr = RenameRollbackManager(client)
    manifests = mgr.list_available()

    if not manifests:
        console.print("[yellow]Nessun rollback rinomina disponibile.[/yellow]")
        return

    table = RichTable(title="Rollback rinomina disponibili", show_lines=True)
    table.add_column("#", style="bold")
    table.add_column("Run ID")
    table.add_column("Data")
    table.add_column("File rinominati")
    table.add_column("Account")
    for i, m in enumerate(manifests, 1):
        table.add_row(str(i), m.run_id[:8], m.started_at.strftime("%Y-%m-%d %H:%M"),
                      str(len(m.entries)), m.drive_user_email)
    console.print(table)

    try:
        choice = click.prompt("Scegli numero (0 per annullare)", type=int, default=0)
    except click.Abort:
        return
    if choice == 0 or choice > len(manifests):
        return

    chosen = manifests[choice - 1]
    if click.confirm(f"Ripristinare {len(chosen.entries)} nomi originali?", default=False):
        mgr.execute_rollback(chosen)


@cli.command()
@_ACCOUNT_OPTION
@click.option("--apply", is_flag=True, default=False, help="Sposta i duplicati in archivio (default: solo preview)")
@click.option("--archive-folder", default="99_Archivio/Duplicati", show_default=True,
              help="Cartella destinazione duplicati")
def duplicates(account, apply, archive_folder):
    """Trova e archivia file duplicati (stesso contenuto o stesso nome)."""
    _check_credentials()

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
    from drive_organizer.drive.client import DriveClient
    from drive_organizer.drive.models import MoveOperation, OrganizationPlan
    from drive_organizer.duplicate_finder import find_duplicates
    from drive_organizer.executor import PlanExecutor
    from drive_organizer.ui.duplicate_diff import ask_exceptions, print_duplicate_preview

    console.print("\n[bold]Connessione Google Drive…[/bold]")
    svc = get_drive_service(account)
    email = get_authenticated_email(svc)
    client = DriveClient(svc)
    console.print(f"[green]Connesso come:[/green] {email}")

    console.print("[bold]Scansione file…[/bold]")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        prog.add_task("Lettura Drive…")
        files, folder_map = client.scan_all_files()

    from drive_organizer.config import settings as _settings
    exclude_ids = {
        fid for fid, name in folder_map.items()
        if any(p in name for p in _settings.duplicate_exclude_folder_patterns)
    }
    excluded_count = sum(1 for f in files if any(p in f.parents for p in exclude_ids))
    if exclude_ids:
        console.print(f"[dim]Escluse {len(exclude_ids)} cartelle ({excluded_count} file) dai pattern configurati.[/dim]")

    console.print(f"[green]{len(files)} file trovati.[/green] Ricerca duplicati in corso…")
    plan = find_duplicates(files, exclude_folder_ids=exclude_ids)

    print_duplicate_preview(console, plan)

    if not plan.groups:
        return

    if not apply:
        if plan.files_to_archive:
            ask_exceptions(console, plan)
            # Ricalcola preview dopo eccezioni
            active = plan.files_to_archive
            if active:
                console.print(f"[bold yellow]Modalità preview. {len(active)} file verranno spostati in [cyan]{archive_folder}[/cyan].[/bold yellow]")
                console.print("Aggiungi [bold]--apply[/bold] per procedere.")
            else:
                console.print("[green]Tutti i gruppi marcati come eccezione. Nessuna modifica.[/green]")
        return

    # Chiedi eccezioni prima di applicare
    ask_exceptions(console, plan)
    files_to_archive = plan.files_to_archive

    if not files_to_archive:
        console.print("[green]Nessun file da archiviare dopo le eccezioni.[/green]")
        return

    if not click.confirm(
        f"Spostare {len(files_to_archive)} file duplicati in '{archive_folder}'?",
        default=False,
    ):
        console.print("[yellow]Annullato.[/yellow]")
        return

    # Costruisci un OrganizationPlan e usa PlanExecutor
    moves = []
    for f in files_to_archive:
        if not f.owned_by_me or not f.can_move:
            continue
        moves.append(MoveOperation(
            file_id=f.id,
            file_name=f.name,
            source_parents=list(f.parents),
            target_path=archive_folder,
            confidence=1.0,
            provider="deterministic",
        ))

    dup_plan = OrganizationPlan(
        strategy_name="duplicates",
        moves=moves,
        folders_to_create=[archive_folder],
        total_files=len(moves),
    )

    executor = PlanExecutor(client, email)
    manifest = executor.execute(dup_plan)
    console.print(f"\n[green]Completato![/green] {len(manifest.entries)} duplicati archiviati.")
    console.print(f"[dim]Rollback: logs/rollback_{manifest.run_id[:8]}_*.json[/dim]")


@cli.command()
@_ACCOUNT_OPTION
@click.option("--run-id", default=None, help="ID sessione da annullare (prefisso 8 char). Se omesso: interattivo.")
@click.option("--yes", "-y", is_flag=True, default=False, help="Conferma senza prompt.")
@click.option("--all", "rollback_all", is_flag=True, default=False, help="Annulla tutte le sessioni in ordine inverso.")
def rollback(account, run_id, yes, rollback_all):
    """Annulla una sessione di organizzazione precedente."""
    _check_credentials()
    from drive_organizer.auth.google_auth import get_drive_service
    from drive_organizer.drive.client import DriveClient
    from drive_organizer.rollback import RollbackManager
    from drive_organizer.ui.prompts import select_rollback

    svc = get_drive_service(account)
    client = DriveClient(svc)
    mgr = RollbackManager(client)

    manifests = mgr.print_table(console)
    if not manifests:
        return

    if rollback_all:
        for m in manifests:
            console.print(f"\n[bold]Rollback sessione {m.run_id[:8]} ({len(m.entries)} file)…[/bold]")
            mgr.execute_rollback(m)
        return

    if run_id:
        chosen = next((m for m in manifests if m.run_id.startswith(run_id)), None)
        if not chosen:
            console.print(f"[red]Sessione '{run_id}' non trovata.[/red]")
            return
    else:
        chosen = select_rollback(console, manifests)
        if not chosen:
            console.print("[yellow]Annullato.[/yellow]")
            return

    if not yes and not click.confirm(
        f"Ripristinare {len(chosen.entries)} file dalla sessione {chosen.run_id[:8]}?",
        default=False,
    ):
        console.print("[yellow]Annullato.[/yellow]")
        return

    mgr.execute_rollback(chosen)


def _build_strategy(name: str, custom_prompt: str | None, no_haiku: bool, taxonomy_file: str | None = None, year_only: bool = False):
    if name == "custom":
        import json

        from pydantic import ValidationError

        from drive_organizer.strategies.custom import CustomNLStrategy, Taxonomy
        if taxonomy_file:
            try:
                raw = json.loads(Path(taxonomy_file).read_text(encoding="utf-8"))
                validated = Taxonomy.model_validate(raw)
            except ValidationError as e:
                console.print(f"[red]Tassonomia non valida:[/red]\n{e}")
                sys.exit(1)
            taxonomy = validated.model_dump()
            console.print(f"[green]Tassonomia caricata da file:[/green] {', '.join(validated.folders)}")
        else:
            from drive_organizer.config import settings
            if settings.gemini_api_key and not settings.anthropic_api_key:
                from drive_organizer.ai.gemini_provider import GeminiProProvider
                parser = GeminiProProvider()
                console.print("[bold]Gemini Pro interpreta la struttura desiderata…[/bold]")
            else:
                from drive_organizer.ai.opus_provider import OpusProvider
                parser = OpusProvider()
                console.print("[bold]Opus 4.8 interpreta la struttura desiderata…[/bold]")
            raw = parser.parse_custom_taxonomy(custom_prompt or "")
            try:
                validated = Taxonomy.model_validate(raw)
                taxonomy = validated.model_dump()
            except ValidationError as e:
                console.print(f"[yellow]Avviso: tassonomia AI non valida ({e}), uso raw.[/yellow]")
                taxonomy = raw
            console.print(f"[green]Tassonomia:[/green] {', '.join(taxonomy.get('folders', []))}")
        return CustomNLStrategy(description=custom_prompt or "", taxonomy=taxonomy)

    from drive_organizer.strategies.factory import build as _build
    return _build(name, year_only=year_only)


@cli.command()
@click.option("--port", default=5001, show_default=True, help="Porta del server web")
def web(port):
    """Avvia la web UI locale nel browser."""
    import threading
    import webbrowser

    from web import app
    url = f"http://localhost:{port}"
    console.print(f"[bold]Drive Organizer Web UI[/bold] → [link={url}]{url}[/link]")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    cli()
