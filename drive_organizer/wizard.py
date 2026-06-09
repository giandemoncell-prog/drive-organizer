from __future__ import annotations

import shutil
import sys
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule

console = Console(legacy_windows=False)
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _banner():
    console.print(Panel.fit(
        "[bold cyan]Drive Organizer[/bold cyan]\n"
        "[dim]Riorganizza Google Drive con intelligenza artificiale[/dim]",
        border_style="cyan",
    ))
    console.print()


def _step(n: int, total: int, text: str):
    console.print(Rule(f"[bold cyan]Passo {n} di {total} — {text}[/bold cyan]", style="cyan"))
    console.print()


def _ok(msg: str):
    console.print(f"  [green]✓[/green] {msg}")


def _info(msg: str):
    console.print(f"  [dim]{msg}[/dim]")


def run_setup() -> bool:
    """Wizard interattivo primo avvio. Returns True se completato."""
    _banner()

    console.print("[bold]Benvenuto in Drive Organizer![/bold]")
    console.print()
    console.print("Questo wizard ti guida nella configurazione iniziale.")
    console.print("Ci vorranno circa [bold]5-10 minuti[/bold] per completare tutti i passi.")
    console.print()

    if not Confirm.ask("Iniziare la configurazione?", default=True):
        console.print("[yellow]Puoi riprendere in qualsiasi momento rieseguendo l'app.[/yellow]")
        return False

    console.print()

    # ── Passo 1: Anthropic API key ─────────────────────────────────────────
    _step(1, 5, "Chiave API Anthropic (opzionale)")

    console.print("La chiave API Anthropic abilita le strategie AI avanzate:")
    console.print("  • [cyan]project[/cyan] — raggruppa per argomento/progetto")
    console.print("  • [cyan]custom[/cyan]  — struttura personalizzata a parole tue")
    console.print()
    console.print("[bold]Senza chiave[/bold] funzionano comunque le strategie gratuite:")
    console.print("  • [cyan]type[/cyan] — organizza per tipo di file (Immagini, PDF, Video…)")
    console.print("  • [cyan]date[/cyan] — organizza per anno/mese di modifica")
    console.print()
    _info("Puoi ottenere una chiave gratuita su console.anthropic.com")
    console.print()

    console.print("[bold]Scegli il provider AI che preferisci:[/bold]")
    console.print("  [cyan]1[/cyan] — Anthropic (Claude Haiku + Opus) — console.anthropic.com")
    console.print("  [cyan]2[/cyan] — Google Gemini (Flash + Pro)     — aistudio.google.com")
    console.print("  [cyan]0[/cyan] — Nessuno per ora (solo strategie gratuite)")
    console.print()
    provider_choice = Prompt.ask("Scelta", choices=["0", "1", "2"], default="0")

    anthropic_key = ""
    gemini_key = ""

    if provider_choice == "1":
        existing = _load_existing_key("ANTHROPIC_API_KEY")
        if existing:
            console.print(f"[green]Chiave Anthropic già presente:[/green] {existing[:16]}…")
            if Confirm.ask("Vuoi cambiarla?", default=False):
                anthropic_key = Prompt.ask("Chiave API Anthropic", default="", password=True)
            else:
                anthropic_key = existing
        else:
            _info("Ottieni una chiave su console.anthropic.com")
            anthropic_key = Prompt.ask("Chiave API Anthropic", password=True)
        _ok("Chiave Anthropic salvata." if anthropic_key else "Saltato.")

    elif provider_choice == "2":
        existing = _load_existing_key("GEMINI_API_KEY")
        if existing:
            console.print(f"[green]Chiave Gemini già presente:[/green] {existing[:16]}…")
            if Confirm.ask("Vuoi cambiarla?", default=False):
                gemini_key = Prompt.ask("Chiave API Gemini", default="", password=True)
            else:
                gemini_key = existing
        else:
            _info("Ottieni una chiave gratuita su aistudio.google.com")
            gemini_key = Prompt.ask("Chiave API Gemini", password=True)
        _ok("Chiave Gemini salvata." if gemini_key else "Saltato.")

    else:
        _ok("Saltato — userai le strategie gratuite.")

    _write_env(anthropic_key, gemini_key)
    console.print()

    # ── Passo 2: Google Cloud — Crea progetto ──────────────────────────────
    _step(2, 5, "Crea il tuo progetto su Google Cloud")

    console.print("Ogni utente crea il proprio progetto Google Cloud gratuito.")
    console.print("Questo è necessario per autorizzare l'accesso al tuo Drive.")
    console.print()
    console.print("[bold]Istruzioni:[/bold]")
    console.print("  1. Si aprirà Google Cloud Console nel browser")
    console.print("  2. Accedi con il tuo account Google")
    console.print("  3. Clicca [bold]\"Nuovo progetto\"[/bold]")
    console.print("  4. Nome: [cyan]Drive Organizer[/cyan] → Crea")
    console.print("  5. Torna qui quando hai creato il progetto")
    console.print()

    if Confirm.ask("Aprire Google Cloud Console nel browser?", default=True):
        webbrowser.open("https://console.cloud.google.com/projectcreate")
        console.print("[dim]Browser aperto. Crea il progetto e torna qui.[/dim]")

    Prompt.ask("\nPremi Invio quando hai creato il progetto", default="")
    _ok("Progetto creato.")
    console.print()

    # ── Passo 3: Abilita Drive API + crea credenziali ──────────────────────
    _step(3, 5, "Abilita Drive API e crea credenziali OAuth")

    console.print("[bold]Parte A — Abilita Google Drive API:[/bold]")
    console.print("  1. Si aprirà la pagina Google Drive API")
    console.print("  2. Clicca [bold]\"Abilita\"[/bold]")
    console.print()

    if Confirm.ask("Aprire la pagina Drive API?", default=True):
        webbrowser.open("https://console.cloud.google.com/apis/library/drive.googleapis.com")

    Prompt.ask("\nPremi Invio dopo aver abilitato Drive API", default="")
    _ok("Drive API abilitata.")
    console.print()

    console.print("[bold]Parte B — Configura la schermata di consenso OAuth:[/bold]")
    console.print("  1. Si aprirà Google Auth Platform")
    console.print("  2. Clicca [bold]\"Inizia\"[/bold] o [bold]\"Configura\"[/bold]")
    console.print("  3. Nome app: [cyan]Drive Organizer[/cyan]")
    console.print("  4. Email supporto: la tua email")
    console.print("  5. Tipo utente: [bold]Esterno[/bold]")
    console.print("  6. Ambiti: aggiungi [cyan]https://www.googleapis.com/auth/drive[/cyan]")
    console.print("  7. Utenti di test: aggiungi la tua email Gmail")
    console.print()

    if Confirm.ask("Aprire la configurazione OAuth?", default=True):
        webbrowser.open("https://console.cloud.google.com/auth/overview")

    Prompt.ask("\nPremi Invio dopo aver configurato la schermata di consenso", default="")
    _ok("Schermata di consenso configurata.")
    console.print()

    console.print("[bold]Parte C — Crea le credenziali OAuth:[/bold]")
    console.print("  1. Si aprirà la pagina Credenziali")
    console.print("  2. Clicca [bold]\"+ Crea credenziali\"[/bold] → [bold]\"ID client OAuth\"[/bold]")
    console.print("  3. Tipo applicazione: [bold]App desktop[/bold]")
    console.print("  4. Nome: [cyan]Drive Organizer CLI[/cyan] → Crea")
    console.print("  5. Clicca [bold]\"Scarica JSON\"[/bold]")
    console.print("  6. Salva il file — ti verrà chiesto il percorso nel passo successivo")
    console.print()

    if Confirm.ask("Aprire la pagina Credenziali?", default=True):
        webbrowser.open("https://console.cloud.google.com/apis/credentials")

    Prompt.ask("\nPremi Invio dopo aver scaricato il file JSON delle credenziali", default="")
    console.print()

    # ── Passo 4: Posiziona credentials.json ───────────────────────────────
    _step(4, 5, "Configura il file delle credenziali")

    app_dir = _get_app_dir()
    creds_dest = app_dir / "credentials.json"

    console.print("Il file scaricato da Google va rinominato [bold]credentials.json[/bold]")
    console.print(f"e copiato in: [cyan]{app_dir}[/cyan]")
    console.print()

    # Prova a trovarlo automaticamente nella cartella Download
    found = _find_credentials_in_downloads()
    if found:
        console.print(f"[green]File trovato automaticamente:[/green] {found}")
        if Confirm.ask("Usare questo file?", default=True):
            shutil.copy(found, creds_dest)
            _ok(f"credentials.json copiato in {app_dir}")
        else:
            found = None

    if not found:
        while True:
            path_str = Prompt.ask("Inserisci il percorso completo del file JSON scaricato")
            path = Path(path_str.strip().strip('"'))
            if path.exists() and path.suffix == ".json":
                shutil.copy(path, creds_dest)
                _ok(f"credentials.json copiato in {app_dir}")
                break
            else:
                console.print(f"[red]File non trovato:[/red] {path}")
                if not Confirm.ask("Riprovare?", default=True):
                    console.print("[yellow]Puoi copiare manualmente il file e rieseguire il setup.[/yellow]")
                    return False

    console.print()

    # ── Passo 5: Login Google + verifica ──────────────────────────────────
    _step(5, 5, "Login Google Drive")

    console.print("Ora autorizziamo l'accesso al tuo Google Drive.")
    console.print("Si aprirà il browser con la schermata di login Google.")
    console.print()

    if not Confirm.ask("Aprire il browser per il login?", default=True):
        console.print("[yellow]Puoi autenticarti in seguito con: drive-organizer auth[/yellow]")
        return False

    try:
        from drive_organizer.auth.google_auth import get_authenticated_email, get_drive_service
        from drive_organizer.drive.client import DriveClient
        console.print("[dim]Apertura browser…[/dim]")
        svc = get_drive_service()
        email = get_authenticated_email(svc)
        _ok(f"Connesso come: [bold]{email}[/bold]")

        client = DriveClient(svc)
        about = client.get_about()
        quota = about.get("storageQuota", {})
        used_gb = int(quota.get("usage", 0)) / 1e9
        limit_gb = int(quota.get("limit", 0)) / 1e9 if quota.get("limit") else 0
        storage = f"{used_gb:.1f} GB / {limit_gb:.0f} GB" if limit_gb else f"{used_gb:.1f} GB"
        _ok(f"Drive connesso — storage: {storage}")
    except Exception as e:
        console.print(f"[red]Errore:[/red] {e}")
        console.print("[dim]Riprova con: drive-organizer auth[/dim]")
        return False

    console.print()

    # ── Completato ─────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold green]Drive Organizer configurato![/bold green]\n\n"
        f"Account: [cyan]{email}[/cyan]\n\n"
        "Puoi ora organizzare il tuo Drive:\n\n"
        "  [cyan]drive-organizer organize --strategy type[/cyan]\n"
        "  [dim]Preview gratuita — organizza per tipo di file[/dim]\n\n"
        "  [cyan]drive-organizer organize --strategy type --apply[/cyan]\n"
        "  [dim]Applica le modifiche (rollback sempre disponibile)[/dim]\n\n"
        "  [cyan]drive-organizer organize --strategy project[/cyan]\n"
        "  [dim]Raggruppa per argomento con AI (richiede chiave Anthropic)[/dim]",
        border_style="green",
        title="[bold]Pronto[/bold]",
    ))
    return True


def _get_app_dir() -> Path:
    """Cartella dati app — stessa dell'eseguibile o working directory."""
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(".").resolve()


def _find_credentials_in_downloads() -> Path | None:
    """Cerca un file client_secret_*.json nella cartella Download."""
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return None
    candidates = sorted(downloads.glob("client_secret_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_existing_key(var: str) -> str:
    for env_path in [_get_app_dir() / ".env", Path(".env")]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{var}="):
                    val = line.split("=", 1)[1].strip()
                    return val if val else ""
    return ""


def _write_env(anthropic_key: str = "", gemini_key: str = ""):
    env_path = _get_app_dir() / ".env"
    if not env_path.exists():
        env_path = Path(".env")

    updates = {
        "ANTHROPIC_API_KEY": anthropic_key,
        "GEMINI_API_KEY": gemini_key,
    }

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        found_keys: set[str] = set()
        for line in lines:
            updated = False
            for key, val in updates.items():
                if line.startswith(f"{key}="):
                    new_lines.append(f"{key}={val}")
                    found_keys.add(key)
                    updated = True
                    break
            if not updated:
                new_lines.append(line)
        for key, val in updates.items():
            if key not in found_keys:
                new_lines.insert(0, f"{key}={val}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(
            f"ANTHROPIC_API_KEY={anthropic_key}\n"
            f"GEMINI_API_KEY={gemini_key}\n"
            "OLLAMA_BASE_URL=http://localhost:11434\n"
            "OLLAMA_MODEL=qwen3:8b\n"
            "OLLAMA_CONFIDENCE_THRESHOLD=0.75\n"
            "HAIKU_CONFIDENCE_THRESHOLD=0.80\n"
            "MAX_CLOUD_ESCALATIONS=200\n"
            "CREDENTIALS_PATH=credentials.json\n"
            "TOKENS_DIR=tokens\n"
            "ROLLBACK_DIR=logs\n",
            encoding="utf-8",
        )
