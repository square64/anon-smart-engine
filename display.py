"""
core/display.py — Visual output helpers for ANON SMART ENGINE
"""

import os
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

BANNER_ART = r"""
  █████╗ ███╗   ██╗ ██████╗ ███╗   ██╗
 ██╔══██╗████╗  ██║██╔═══██╗████╗  ██║
 ███████║██╔██╗ ██║██║   ██║██╔██╗ ██║
 ██╔══██║██║╚██╗██║██║   ██║██║╚██╗██║
 ██║  ██║██║ ╚████║╚██████╔╝██║ ╚████║
 ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═══╝"""


def banner():
    os.system("clear")
    console.print(BANNER_ART, style="cyan bold")
    console.print()
    console.print(
        "  [bold green]ANON SMART ENGINE[/bold green] "
        "[dim]v3.0[/dim]  [dim]│[/dim]  [dim]Tor Privacy Control Toolkit[/dim]"
    )
    console.print("  [dim]github.com/square64/anon-smart-engine[/dim]")
    divider()
    console.print()


def divider():
    console.print("  [dim cyan]─────────────────────────────────────────[/dim cyan]")


def section(title: str):
    console.print()
    console.print(f"  [bold magenta]{title}[/bold magenta]")
    console.print("  [dim cyan]─────────────────────────────────────────[/dim cyan]")
    console.print()


def ok(msg: str):
    console.print(f"  [bold green]✔[/bold green]  {msg}")


def info(msg: str):
    console.print(f"  [cyan]◆[/cyan]  {msg}")


def warn(msg: str):
    console.print(f"  [bold yellow]⚠[/bold yellow]  [bold]{msg}[/bold]")


def err(msg: str):
    console.print(f"  [bold red]✖[/bold red]  [bold]{msg}[/bold]")


def label(key: str, value: str):
    console.print(f"  [dim]{key:<22}[/dim] {value}")


def status_badge(state: str) -> str:
    """Return a colored status string."""
    states = {
        "protected":   "[bold green]● PROTECTED[/bold green]",
        "unprotected": "[bold red]● UNPROTECTED[/bold red]",
        "uncertain":   "[bold yellow]● UNCERTAIN[/bold yellow]",
        "active":      "[bold green]● active[/bold green]",
        "inactive":    "[bold red]● inactive[/bold red]",
        "leak":        "[bold red]⚠ LEAK DETECTED[/bold red]",
        "no_leak":     "[bold green]✔ No leak[/bold green]",
    }
    return states.get(state, f"[dim]{state}[/dim]")


def summary_panel(lines: list[tuple[str, str]], title: str = "SUMMARY"):
    """Render a rich Panel summary box."""
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("icon", style="", no_wrap=True)
    table.add_column("text")

    for icon, text in lines:
        table.add_row(icon, text)

    console.print()
    console.print(Panel(table, title=f"[bold magenta]{title}[/bold magenta]",
                        border_style="cyan dim", expand=False, padding=(1, 2)))
    console.print()


def result_table(rows: list[tuple[str, str]], title: str = ""):
    """Render a two-column result table."""
    table = Table(box=box.SIMPLE, show_header=False,
                  border_style="dim cyan", padding=(0, 1))
    table.add_column("Key", style="dim", min_width=22)
    table.add_column("Value")

    for key, value in rows:
        table.add_row(key, value)

    if title:
        console.print(f"\n  [bold]{title}[/bold]")
    console.print(table)
