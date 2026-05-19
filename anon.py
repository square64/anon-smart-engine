#!/usr/bin/env python3
"""
ANON SMART ENGINE v3.0
Tor Privacy Control Toolkit
https://github.com/square64/anon-smart-engine
"""
import sys
import os
import signal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import click
from rich.console import Console

from core.display import banner, divider
from core.tor import TorManager
from core.proxy import ProxyManager
from core.check import Checker
from core.watch import Watcher

console = Console()

def handle_interrupt(sig, frame):
    console.print("\n\n[yellow]  ⚠  Interrupted[/yellow]")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_interrupt)

# =============================================================
# CLI GROUP
# =============================================================
@click.group(invoke_without_command=True)
@click.option("--no-color", is_flag=True, envvar="NO_COLOR", help="Disable colored output")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, no_color, json_output):
    """ANON SMART ENGINE — Tor Privacy Control Toolkit"""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["no_color"] = no_color

    if no_color:
        os.environ["NO_COLOR"] = "1"

    if ctx.invoked_subcommand is None:
        banner()
        click.echo(ctx.get_help())


# =============================================================
# ON
# =============================================================
@cli.command()
@click.option("--no-proxy", is_flag=True, help="Skip iptables transparent proxy (SOCKS only)")
@click.pass_context
def on(ctx, no_proxy):
    """Start Tor and enable system-wide anonymous routing."""
    banner()
    tor = TorManager()
    proxy = ProxyManager()
    checker = Checker()

    tor.start()

    if not no_proxy:
        proxy.enable()
    else:
        console.print("[dim]  Skipping transparent proxy (--no-proxy)[/dim]")

    checker.verify_circuit(show_summary=True)


# =============================================================
# OFF
# =============================================================
@cli.command()
@click.pass_context
def off(ctx):
    """Stop Tor and restore normal network routing."""
    banner()
    tor = TorManager()
    proxy = ProxyManager()

    proxy.disable()
    tor.stop()

    checker = Checker()
    checker.show_direct_ip()


# =============================================================
# STATUS
# =============================================================
@cli.command()
@click.pass_context
def status(ctx):
    """Quick status overview."""
    banner()
    checker = Checker()
    checker.quick_status(json_output=ctx.obj.get("json", False))


# =============================================================
# CHECK
# =============================================================
@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON")
@click.pass_context
def check(ctx, json_output):
    """Run full diagnostics: IP · DNS · leak · proxy · routes."""
    banner()
    checker = Checker()
    checker.full_check(json_output=json_output or ctx.obj.get("json", False))


# =============================================================
# WATCH
# =============================================================
@cli.command()
@click.option("--interval", default=30, show_default=True, help="Check interval in seconds")
@click.option("--alert-only", is_flag=True, help="Only print when a leak is detected")
@click.pass_context
def watch(ctx, interval, alert_only):
    """Continuously monitor for leaks and Tor health."""
    banner()
    watcher = Watcher(interval=interval, alert_only=alert_only)
    watcher.start()


# =============================================================
# NEWID
# =============================================================
@cli.command()
@click.pass_context
def newid(ctx):
    """Request a new Tor identity (NEWNYM signal)."""
    banner()
    tor = TorManager()
    tor.new_identity()


# =============================================================
# PROXY
# =============================================================
@cli.group()
def proxy():
    """Manage iptables transparent proxy rules."""
    pass

@proxy.command("enable")
def proxy_enable():
    """Enable system-wide Tor transparent proxy."""
    banner()
    p = ProxyManager()
    p.enable()

@proxy.command("disable")
def proxy_disable():
    """Disable system-wide Tor transparent proxy."""
    banner()
    p = ProxyManager()
    p.disable()

@proxy.command("status")
def proxy_status():
    """Show current proxy/iptables state."""
    banner()
    p = ProxyManager()
    p.status()


# =============================================================
# ENTRY
# =============================================================
if __name__ == "__main__":
    cli(obj={})
