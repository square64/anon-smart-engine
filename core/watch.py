"""
core/watch.py — Continuous leak monitor for ANON SMART ENGINE
"""

import time
import sys
import subprocess
from datetime import datetime

import requests
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from core.display import ok, warn, err, info, divider

console = Console()

SOCKS_PROXY   = "socks5h://127.0.0.1:9050"
TOR_CHECK_URL = "https://check.torproject.org/api/ip"
IP_CHECK_URL  = "https://api.ipify.org"
TIMEOUT       = 10


class Watcher:

    def __init__(self, interval: int = 30, alert_only: bool = False):
        self.interval   = interval
        self.alert_only = alert_only
        self._history   = []   # list of dicts
        self._run_count = 0

    # ----------------------------------------------------------
    # MAIN LOOP
    # ----------------------------------------------------------
    def start(self):
        console.print(
            f"  [cyan]◆[/cyan]  Watching for leaks every [bold]{self.interval}s[/bold]"
            "  [dim](Ctrl+C to stop)[/dim]"
        )
        if self.alert_only:
            console.print("  [dim]Alert-only mode: silent unless leak detected[/dim]")
        console.print()
        divider()
        console.print()

        try:
            while True:
                result = self._run_check()
                self._history.append(result)
                self._run_count += 1
                self._render(result)

                # Countdown
                for remaining in range(self.interval, 0, -1):
                    console.print(
                        f"\r  [dim]Next check in {remaining:2d}s...[/dim]",
                        end=""
                    )
                    time.sleep(1)
                console.print("\r" + " " * 40 + "\r", end="")

        except KeyboardInterrupt:
            console.print()
            console.print()
            self._render_session_summary()
            console.print()

    # ----------------------------------------------------------
    # SINGLE CHECK
    # ----------------------------------------------------------
    def _run_check(self) -> dict:
        ts = datetime.now().strftime("%H:%M:%S")
        result = {
            "time":        ts,
            "tor_active":  False,
            "direct_ip":   "unavailable",
            "tor_ip":      "unavailable",
            "is_tor":      False,
            "ip_leak":     False,
            "tor_dropped": False,
            "ok":          False,
        }

        # Tor service
        svc = subprocess.run(
            ["systemctl", "is-active", "tor"],
            capture_output=True, text=True
        )
        result["tor_active"] = svc.stdout.strip() == "active"

        # Direct IP
        try:
            r = requests.get(IP_CHECK_URL, timeout=TIMEOUT)
            result["direct_ip"] = r.text.strip()
        except Exception:
            pass

        # Tor IP + verification
        if result["tor_active"]:
            try:
                r = requests.get(
                    TOR_CHECK_URL,
                    proxies={"https": SOCKS_PROXY, "http": SOCKS_PROXY},
                    timeout=TIMEOUT
                )
                data = r.json()
                result["tor_ip"]  = data.get("IP", "unavailable")
                result["is_tor"]  = data.get("IsTor", False)
            except Exception:
                result["tor_dropped"] = True

        # Leak detection
        if result["direct_ip"] != "unavailable" and result["tor_ip"] != "unavailable":
            result["ip_leak"] = result["direct_ip"] == result["tor_ip"]

        result["ok"] = (
            result["tor_active"]
            and result["is_tor"]
            and not result["ip_leak"]
            and not result["tor_dropped"]
        )

        return result

    # ----------------------------------------------------------
    # RENDER SINGLE RESULT
    # ----------------------------------------------------------
    def _render(self, r: dict):
        ts = r["time"]
        prefix = f"  [dim]{ts}[/dim]"

        if r["ok"]:
            if not self.alert_only:
                console.print(
                    f"{prefix}  [green]✔[/green]  Protected  "
                    f"[dim]Exit: {r['tor_ip']}[/dim]"
                )
            return  # no alert needed

        # Something is wrong — always print regardless of alert_only
        if not r["tor_active"]:
            console.print(f"{prefix}  [bold red]✖[/bold red]  [red]Tor service DOWN[/red]")

        elif r["tor_dropped"]:
            console.print(f"{prefix}  [bold yellow]⚠[/bold yellow]  [yellow]Tor circuit dropped — reconnecting[/yellow]")

        elif r["ip_leak"]:
            console.print(
                f"{prefix}  [bold red]⚠ IP LEAK[/bold red]  "
                f"Direct and Tor IP match: [red]{r['direct_ip']}[/red]"
            )

        elif not r["is_tor"]:
            console.print(
                f"{prefix}  [bold yellow]⚠[/bold yellow]  "
                f"[yellow]Tor routing not confirmed  Exit: {r['tor_ip']}[/yellow]"
            )

    # ----------------------------------------------------------
    # SESSION SUMMARY
    # ----------------------------------------------------------
    def _render_session_summary(self):
        if not self._history:
            return

        total    = len(self._history)
        clean    = sum(1 for r in self._history if r["ok"])
        leaks    = sum(1 for r in self._history if r["ip_leak"])
        dropped  = sum(1 for r in self._history if r["tor_dropped"])
        tor_down = sum(1 for r in self._history if not r["tor_active"])

        table = Table(box=box.SIMPLE, show_header=False,
                      border_style="dim cyan", padding=(0, 2))
        table.add_column("Key",   style="dim", min_width=20)
        table.add_column("Value")

        table.add_row("Session checks",  str(total))
        table.add_row("Clean checks",    f"[green]{clean}[/green]")
        table.add_row("IP leaks",        f"[red]{leaks}[/red]" if leaks else f"[green]{leaks}[/green]")
        table.add_row("Circuit drops",   f"[yellow]{dropped}[/yellow]" if dropped else str(dropped))
        table.add_row("Tor down events", f"[red]{tor_down}[/red]" if tor_down else str(tor_down))
        table.add_row("Check interval",  f"{self.interval}s")

        overall = (
            "[bold green]CLEAN[/bold green]" if leaks == 0 and tor_down == 0
            else "[bold red]ISSUES DETECTED[/bold red]"
        )
        table.add_row("", "")
        table.add_row("Overall", overall)

        console.print(Panel(
            table,
            title="[bold magenta]WATCH SESSION SUMMARY[/bold magenta]",
            border_style="cyan dim",
            expand=False,
            padding=(1, 2)
        ))
