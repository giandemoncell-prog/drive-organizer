from __future__ import annotations

from collections import defaultdict

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from drive_organizer.drive.models import DriveFile, OrganizationPlan


def build_before_summary(files: list[DriveFile], folder_map: dict[str, str]) -> Tree:
    tree = Tree("[bold]Drive attuale[/bold]")
    by_parent: dict[str, list[DriveFile]] = defaultdict(list)
    for f in files:
        parent_id = f.parents[0] if f.parents else "root"
        by_parent[parent_id].append(f)

    for shown, (parent_id, file_list) in enumerate(
        sorted(by_parent.items(), key=lambda x: -len(x[1])), start=1
    ):
        folder_name = folder_map.get(parent_id, f"[dim]{parent_id[:8]}…[/dim]")
        branch = tree.add(f"[cyan]{folder_name}[/cyan] ({len(file_list)} file)")
        for f in file_list[:3]:
            branch.add(f"[dim]{f.name}[/dim]")
        if len(file_list) > 3:
            branch.add(f"[dim]… e altri {len(file_list) - 3}[/dim]")
        if shown >= 10:
            remaining = len(by_parent) - shown
            if remaining > 0:
                tree.add(f"[dim]… e altre {remaining} cartelle[/dim]")
            break

    return tree


def build_after_summary(plan: OrganizationPlan) -> Tree:
    tree = Tree("[bold]Struttura proposta[/bold]")
    by_target: dict[str, list[str]] = defaultdict(list)
    for op in plan.moves:
        if not op.skipped:
            by_target[op.target_path].append(op.file_name)

    for target_path in sorted(by_target.keys()):
        file_names = by_target[target_path]
        parts = target_path.split("/")
        current = tree
        for part in parts:
            found = None
            for child in current.children:
                if hasattr(child, "label") and f"[green]{part}[/green]" in str(child.label):
                    found = child
                    break
            if found:
                current = found
            else:
                current = current.add(f"[green]{part}[/green]")

        for name in file_names[:3]:
            current.add(f"[dim]{name}[/dim]")
        if len(file_names) > 3:
            current.add(f"[dim]… e altri {len(file_names) - 3}[/dim]")

    return tree


def print_diff(console: Console, plan: OrganizationPlan, files: list[DriveFile], folder_map: dict[str, str]) -> None:
    active = [op for op in plan.moves if not op.skipped]
    skipped = [op for op in plan.moves if op.skipped]

    before = build_before_summary(files, folder_map)
    after = build_after_summary(plan)

    console.print()
    console.print(Columns([
        Panel(before, title="[bold yellow]PRIMA[/bold yellow]", border_style="yellow"),
        Panel(after, title="[bold green]DOPO[/bold green]", border_style="green"),
    ]))
    console.print()

    # Summary stats
    by_provider: dict[str, int] = defaultdict(int)
    for op in active:
        by_provider[op.provider] += 1

    console.print("[bold]Riepilogo piano:[/bold]")
    console.print(f"  File da spostare: [green]{len(active)}[/green]")
    console.print(f"  Cartelle da creare: [green]{len(plan.folders_to_create)}[/green]")
    if skipped:
        console.print(f"  File saltati: [yellow]{len(skipped)}[/yellow] (shortcut / non owned / non movibili)")
    if by_provider:
        provider_text = " | ".join(f"{p}: {n}" for p, n in sorted(by_provider.items()))
        console.print(f"  Classificati da: [dim]{provider_text}[/dim]")
    console.print()
