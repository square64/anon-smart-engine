"""
core/check.py — IP, DNS, leak and route diagnostics for ANON SMART ENGINE
"""

import subprocess
import socket
import json
import sys

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

from core.display import (
    ok, info, warn, err, label, section, divider,
    status_badge, summary_panel
)

console = Console()

SOCKS_PROXY     = "socks5h://127.0.0.1:9050"
TOR_CHECK_URL   = "https://check.torproject.org/api/ip"
IP_CHECK_URL    = "https://api.ipify.org"
DNS_LEAK_HOSTS  = ["github.com", "google.com", "cloudflare.com"]
TOR_DNS_PORT    = 5353
REQUEST_TIMEOUT = 12


class Checker:

    # ----------------------------------------------------------
    # QUICK STATUS
    # ----------------------------------------------------------
    def quick_status(self, json_output: bool = False):
        section("Quick Status")

        tor_active  = self._tor_is_active()
        direct_ip   = self._get_direct_ip()
        tor_data    = self._get_tor_data() if tor_active else {}
        tor_ip      = tor_data.get("IP", "unavailable")
        is_tor      = tor_data.get("IsTor", False)

        if json_output:
            print(json.dumps({
                "tor_active": tor_active,
                "direct_ip": direct_ip,
                "tor_ip": tor_ip,
                "is_tor": is_tor,
            }, indent=2))
            return

        label("Tor Service",  status_badge("active" if tor_active else "inactive"))
        label("Direct IP",    f"[yellow]{direct_ip}[/yellow]")
        if tor_active:
            label("Exit IP",  f"[cyan]{tor_ip}[/cyan]")
            label("Verified", f"[green]✔ torproject.org[/green]" if is_tor else "[red]✖ not confirmed[/red]")
            label("Status",   status_badge("protected" if is_tor else "uncertain"))
        else:
            label("Status",   status_badge("unprotected"))
        console.print()

 
    
    # VERIFY CIRCUIT (called after anon on)
    # ----------------------------------------------------------
    def verify_circuit(self, show_summary: bool = False):
        section("Circuit Verification")
        tor_data = self._get_tor_data()

        if tor_data.get("IsTor"):
            ok("Tor routing confirmed by torproject.org")
            label("Exit IP", f"[cyan]{tor_data.get('IP', 'unknown')}[/cyan]")
        else:
            warn("Tor routing NOT confirmed")
            warn("Traffic may not be going through Tor")

        if show_summary:
            proxy_status = self._check_proxy()
            self._render_summary(tor_data, proxy=proxy_status)


    # ----------------------------------------------------------
    # FULL CHECK
    # ----------------------------------------------------------
    def full_check(self, json_output: bool = False):
        section("Full Diagnostics")
        results = {}

        with Progress(
            SpinnerColumn(spinner_name="dots", style="cyan"),
            TextColumn("[dim]{task.description}[/dim]"),
            console=console, transient=True
        ) as progress:
            t = progress.add_task("Running diagnostics...", total=None)

            # --- Tor service ---
            progress.update(t, description="Checking Tor service...")
            results["tor_active"] = self._tor_is_active()

            # --- IPs ---
            progress.update(t, description="Resolving IPs...")
            results["direct_ip"] = self._get_direct_ip()
            results["tor_data"]  = self._get_tor_data() if results["tor_active"] else {}

            # --- DNS ---
            progress.update(t, description="Testing DNS...")
            results["dns"] = self._check_dns()

            # --- Leak ---
            progress.update(t, description="Checking for leaks...")
            results["ip_leak"] = self._check_ip_leak(
                results["direct_ip"],
                results["tor_data"].get("IP", "")
            )

            # --- Proxy ---
            progress.update(t, description="Checking iptables proxy...")
            results["proxy_active"] = self._check_proxy()

            # --- Routes ---
            progress.update(t, description="Reading routes...")
            results["routes"] = self._get_routes()

        if json_output:
            print(json.dumps(results, indent=2))
            return

        self._render_full(results)

    # ----------------------------------------------------------
    # SHOW DIRECT IP (after anon off)
    # ----------------------------------------------------------
    def show_direct_ip(self):
        ip = self._get_direct_ip()
        console.print()
        label("Direct IP", f"[yellow]{ip}[/yellow]")
        label("Status",    status_badge("unprotected"))
        console.print()

    # ----------------------------------------------------------
    # RENDER FULL RESULTS
    # ----------------------------------------------------------
    def _render_full(self, r: dict):
        tor_data   = r.get("tor_data", {})
        direct_ip  = r.get("direct_ip", "unavailable")
        tor_ip     = tor_data.get("IP", "unavailable")
        is_tor     = tor_data.get("IsTor", False)
        dns        = r.get("dns", {})
        ip_leak    = r.get("ip_leak", True)
        proxy      = r.get("proxy_active", False)
        routes     = r.get("routes", [])

        # --- Tor Service ---
        info("Tor Service")
        label("  systemd",
              status_badge("active" if r["tor_active"] else "inactive"))
        console.print()

        # --- IP ---
        info("IP Analysis")
        label("  Direct IP",  f"[yellow]{direct_ip}[/yellow]")
        label("  Tor Exit IP", f"[cyan]{tor_ip}[/cyan]")
        label("  Verified",
              "[green]✔ torproject.org[/green]" if is_tor else "[red]✖ not confirmed[/red]")
        console.print()

        # --- Leak ---
        info("IP Leak Check")
        if ip_leak:
            err("IP LEAK — direct and Tor IP match")
        else:
            ok("No IP leak detected")
        console.print()

        # --- DNS ---
        info("DNS Leak Check")
        if dns.get("tor_dns_ok"):
            ok("DNS resolving via Tor")
        else:
            warn("Tor DNS port not responding")
        for host, result in dns.get("results", {}).items():
            label(f"  {host}", f"[cyan]{result}[/cyan]" if result else "[dim]no response[/dim]")
        if dns.get("leak_detected"):
            err("DNS leak detected — queries not going through Tor")
        elif dns.get("tor_dns_ok"):
            ok("No DNS leak detected")
        console.print()

        # --- Transparent Proxy ---
        info("Transparent Proxy (iptables)")
        if proxy:
            ok("iptables rules active — system-wide Tor routing")
        else:
            warn("No iptables rules — only explicit SOCKS proxy apps are protected")
        console.print()

        # --- Routes ---
        info("Active Routes")
        for route in routes[:5]:
            console.print(f"  [dim]{route}[/dim]")
        console.print()

        # --- Summary ---
        self._render_summary(tor_data, ip_leak=ip_leak,
                             dns_leak=dns.get("leak_detected", False),
                             proxy=proxy)

    # ----------------------------------------------------------
    # SUMMARY PANEL
    # ----------------------------------------------------------
    def _render_summary(self, tor_data: dict, ip_leak: bool = False,
                        dns_leak: bool = False, proxy: bool = False):
        is_tor = tor_data.get("IsTor", False)
        lines = []

        if is_tor:
            lines.append(("[green]✔[/green]", "Tor routing confirmed"))
        else:
            lines.append(("[red]✖[/red]", "Tor routing NOT confirmed"))

        if not ip_leak:
            lines.append(("[green]✔[/green]", "No IP leak"))
        else:
            lines.append(("[red]✖[/red]", "IP leak detected"))

        if not dns_leak:
            lines.append(("[green]✔[/green]", "No DNS leak"))
        else:
            lines.append(("[red]✖[/red]", "DNS leak detected"))

        if proxy:
            lines.append(("[green]✔[/green]", "Transparent proxy active"))
        else:
            lines.append(("[yellow]⚠[/yellow]", "Transparent proxy inactive"))

        # Overall status
        lines.append(("", ""))
        if is_tor and not ip_leak and not dns_leak:
            lines.append(("", "[bold green]STATUS: PROTECTED[/bold green]"))
        elif is_tor:
            lines.append(("", "[bold yellow]STATUS: UNCERTAIN[/bold yellow]"))
        else:
            lines.append(("", "[bold red]STATUS: UNPROTECTED[/bold red]"))

        summary_panel(lines)

    # ----------------------------------------------------------
    # INTERNAL CHECKS
    # ----------------------------------------------------------
    def _tor_is_active(self) -> bool:
        result = subprocess.run(
            ["systemctl", "is-active", "tor"],
            capture_output=True, text=True
        )
        return result.stdout.strip() == "active"

    def _get_direct_ip(self) -> str:
        try:
            r = requests.get(IP_CHECK_URL, timeout=REQUEST_TIMEOUT)
            return r.text.strip()
        except Exception:
            return "unavailable"

    def _get_tor_data(self) -> dict:
        try:
            r = requests.get(
                TOR_CHECK_URL,
                proxies={"https": SOCKS_PROXY, "http": SOCKS_PROXY},
                timeout=REQUEST_TIMEOUT
            )
            return r.json()
        except Exception:
            return {}

    def _check_ip_leak(self, direct_ip: str, tor_ip: str) -> bool:
        if not direct_ip or not tor_ip:
            return False  # can't determine
        return direct_ip == tor_ip

    def _check_dns(self) -> dict:
        results = {}
        tor_dns_ok = False
        leak_detected = False

        for host in DNS_LEAK_HOSTS:
            try:
                resolver = socket.getaddrinfo.__module__
                # Query Tor DNS port
                result = subprocess.run(
                    ["dig", f"@127.0.0.1", "-p", str(TOR_DNS_PORT),
                     host, "+short", "+time=5"],
                    capture_output=True, text=True, timeout=8
                )
                ip = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
                if ip:
                    results[host] = ip
                    tor_dns_ok = True
                else:
                    results[host] = ""
            except (subprocess.TimeoutExpired, FileNotFoundError):
                results[host] = ""

        # Leak: compare with direct DNS
        if tor_dns_ok:
            for host in DNS_LEAK_HOSTS:
                try:
                    direct = subprocess.run(
                        ["dig", host, "+short", "+time=3"],
                        capture_output=True, text=True, timeout=5
                    )
                    direct_ip = direct.stdout.strip().splitlines()[0] if direct.stdout.strip() else ""
                    tor_ip = results.get(host, "")
                    # If both resolve but to the same server AND Tor DNS isn't working, flag it
                    if direct_ip and not tor_ip:
                        leak_detected = True
                except Exception:
                    pass

        return {
            "tor_dns_ok": tor_dns_ok,
            "results": results,
            "leak_detected": leak_detected,
        }

        def _check_proxy(self):
        try:
            
            res = subprocess.run(["sudo", "iptables", "-t", "nat", "-L", "OUTPUT", "-n"], capture_output=True, text=True)
            return "redir ports 9040" in res.stdout
        except: 
            return False


    def _get_routes(self) -> list:
        result = subprocess.run(
            ["ip", "route"], capture_output=True, text=True
        )
        return result.stdout.strip().splitlines()
