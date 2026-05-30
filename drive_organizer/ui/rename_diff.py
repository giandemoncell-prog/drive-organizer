from __future__ import annotations

from collections import defaultdict

from rich.console import Console
from rich.table import Table

from drive_organizer.drive.models import RenamePlan


def print_rename_preview(console: Console, plan: RenamePlan) -> None:
    active = [op for op in plan.operations if not op.skipped]
    skipped = [op for op in plan.operations if op.skipped]

    if not active:
        console.print("[yellow]Nessuna rinomina necessaria o possibile.[/yellow]")
        return

    table = Table(
        title=f"Rinomina proposta — {len(active)} file",
        show_lines=True,
        highlight=True,
    )
    table.add_column("Nome attuale", style="yellow", no_wrap=False)
    table.add_column("Nuovo nome", style="green", no_wrap=False)
    table.add_column("Conf.", justify="right", style="dim", width=6)

    for op in active:
        conf_str = f"{op.confidence:.0%}"
        table.add_row(op.old_name, op.new_name, conf_str)

    console.print()
    console.print(table)
    console.print()
    console.print(f"[bold]Riepilogo:[/bold]")
    console.print(f"  File da rinominare: [green]{len(active)}[/green]")
    if skipped:
        console.print(f"  File saltati:       [yellow]{len(skipped)}[/yellow] (nome già ottimale, confidenza bassa o non rinominabili)")
    console.print()
