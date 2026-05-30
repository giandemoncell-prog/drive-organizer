from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from drive_organizer.duplicate_finder import DuplicateGroup, DuplicatePlan


def _size_str(size: int | None) -> str:
    if size is None:
        return "—"
    if size < 1_000:
        return f"{size} B"
    if size < 1_000_000:
        return f"{size/1000:.1f} KB"
    return f"{size/1_000_000:.1f} MB"


def print_duplicate_preview(console: Console, plan: DuplicatePlan) -> None:
    if not plan.groups:
        console.print("[green]Nessun duplicato trovato.[/green]")
        return

    exact = [g for g in plan.groups if g.reason == "md5"]
    by_name = [g for g in plan.groups if g.reason == "nome"]

    console.print()
    console.print(f"[bold]Trovati {plan.total_groups} gruppi di duplicati[/bold] "
                  f"([cyan]{len(exact)}[/cyan] esatti, [yellow]{len(by_name)}[/yellow] per nome)")
    console.print()

    for g in plan.groups:
        reason_badge = "[cyan]IDENTICI[/cyan]" if g.reason == "md5" else "[yellow]STESSO NOME[/yellow]"
        excepted_badge = " [dim](mantenuti tutti)[/dim]" if g.excepted else ""

        table = Table(
            title=f"Gruppo #{g.group_id} — {reason_badge}{excepted_badge}",
            show_lines=True,
            title_justify="left",
        )
        table.add_column("", width=4)
        table.add_column("Nome file", no_wrap=False)
        table.add_column("Dimensione", justify="right", width=10)
        table.add_column("Modificato", width=12)
        table.add_column("Azione")

        for f in g.files:
            is_keep = (f.id == g.keep.id) if g.keep else False
            badge = "[green]✓ tieni[/green]" if is_keep else "[yellow]→ archivio[/yellow]"
            if g.excepted:
                badge = "[dim]tenuto[/dim]"
            row_style = "bold" if is_keep else ""
            table.add_row(
                "",
                Text(f.name, style=row_style),
                _size_str(f.size),
                f.modified_time.strftime("%Y-%m-%d") if f.modified_time else "—",
                badge,
            )

        console.print(table)

    console.print()
    active = plan.files_to_archive
    console.print(f"[bold]Riepilogo:[/bold]")
    console.print(f"  Gruppi totali:          [cyan]{plan.total_groups}[/cyan]")
    console.print(f"  File da archiviare:     [yellow]{len(active)}[/yellow]  (spostati in 99_Archivio/Duplicati)")
    console.print(f"  Eccezioni (tenuti tutti): [dim]{plan.excepted_count}[/dim]")
    console.print()


def ask_exceptions(console: Console, plan: DuplicatePlan) -> None:
    """Permette all'utente di marcare gruppi come eccezione (tieni tutti)."""
    if not plan.groups:
        return

    console.print("[bold]Vuoi marcare qualche gruppo come eccezione?[/bold]")
    console.print("[dim]Digita i numeri dei gruppi separati da virgola (es: 1,3) o premi Invio per continuare.[/dim]")
    console.print()

    try:
        raw = click.prompt("Gruppi da tenere tutti (Invio = nessuno)", default="")
    except click.Abort:
        return

    if not raw.strip():
        return

    group_ids = set()
    for token in raw.split(","):
        try:
            group_ids.add(int(token.strip()))
        except ValueError:
            pass

    for g in plan.groups:
        if g.group_id in group_ids:
            g.excepted = True
            g.to_archive = []
            console.print(f"  [green]Gruppo #{g.group_id} marcato come eccezione.[/green]")
