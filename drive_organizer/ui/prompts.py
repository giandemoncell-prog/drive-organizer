from __future__ import annotations

import click
from rich.console import Console


def confirm_apply(console: Console, n_moves: int, yes: bool = False) -> bool:
    console.print(f"[bold yellow]Stai per spostare {n_moves} file su Google Drive.[/bold yellow]")
    console.print("[dim]Puoi annullare in qualsiasi momento con Ctrl-C — ogni file spostato è registrato nel manifest di rollback.[/dim]")
    if yes:
        console.print("[dim]--yes: conferma automatica.[/dim]")
        return True
    return click.confirm("Applicare le modifiche?", default=False)


def select_rollback(console: Console, manifests: list) -> object | None:
    if not manifests:
        return None
    try:
        choice = click.prompt(
            "Scegli il numero del rollback da eseguire (0 per annullare)",
            type=int,
            default=0,
        )
        if choice == 0 or choice > len(manifests):
            return None
        return manifests[choice - 1]
    except (click.Abort, ValueError):
        return None
