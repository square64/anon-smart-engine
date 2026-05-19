"""
core/tor.py — Tor service management for ANON SMART ENGINE
"""

import subprocess
import time
import sys

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.display import ok, info, warn, err, label, section, status_badge

console = Console()

TOR_CHECK_URL  = "https://check.torproject.org/api/ip"
SOCKS_PROXY    = "socks5h://127.0.0.1:9050"
CIRCUIT_TIMEOUT = 45
CONTROL_PORT   = 9051
REQUEST_TIMEOUT = 12


class TorManager:

    # ----------------------------------------------------------
    # SERVICE CONTROL
    # ----------------------------------------------------------
    def start(self):
        section("Starting Tor")

        if self._is_active():
            warn("Tor is already running")
            self._show_exit_ip()
            return

        info("Starting Tor service...")
        result = subprocess.run(
            ["sudo", "systemctl", "start", "tor"],
            capture_output=True
        )
        if result.returncode != 0:
            err("Failed to start Tor service")
            console.print(f"  [dim]{result.stderr.decode().strip()}[/dim]")
            sys.exit(1)

        ok("Tor service started")
        self._wait_for_circuit()

    def stop(self):
        section("Stopping Tor")

        if not self._is_active():
            warn("Tor is not running")
            return

        info("Stopping Tor service...")
        subprocess.run(["sudo", "systemctl", "stop", "tor"], capture_output=True)
        time.sleep(1)

        if not self._is_active():
            ok("Tor stopped")
        else:
            err("Failed to stop Tor — try: sudo systemctl stop tor")

    # ----------------------------------------------------------
    # CIRCUIT WAIT
    # ----------------------------------------------------------
    def _wait_for_circuit(self):
        console.print()
        with Progress(
            SpinnerColumn(spinner_name="dots", style="cyan"),
            TextColumn("[dim]{task.description}[/dim]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Establishing Tor circuit...", total=CIRCUIT_TIMEOUT)

            for elapsed in range(CIRCUIT_TIMEOUT):
                progress.update(task, advance=1,
                                description=f"Establishing Tor circuit... {elapsed+1}/{CIRCUIT_TIMEOUT}s")
                try:
                    resp = requests.get(
                        TOR_CHECK_URL,
                        proxies={"https": SOCKS_PROXY, "http": SOCKS_PROXY},
                        timeout=REQUEST_TIMEOUT
                    )
                    data = resp.json()
                    if data.get("IsTor"):
                        exit_ip = data.get("IP", "unknown")
                        console.print()
                        ok("Tor circuit established")
                        console.print()
                        label("Exit IP",    f"[cyan]{exit_ip}[/cyan]")
                        label("Status",     status_badge("protected"))
                        console.print()
                        return
                except Exception:
                    pass
                time.sleep(1)

        console.print()
        warn(f"Circuit not confirmed within {CIRCUIT_TIMEOUT}s")
        warn("Tor may still be bootstrapping — try: anon check")

    # ----------------------------------------------------------
    # NEW IDENTITY
    # ----------------------------------------------------------
    def new_identity(self):
        section("New Tor Identity")

        if not self._is_active():
            err("Tor is not running — start it first: anon on")
            sys.exit(1)

        info("Sending NEWNYM signal to Tor control port...")
        try:
            import socket
            with socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=5) as s:
                s.sendall(b'AUTHENTICATE ""\r\nSIGNAL NEWNYM\r\nQUIT\r\n')
                response = s.recv(256).decode()
                if "250" in response:
                    ok("NEWNYM signal accepted")
                else:
                    warn(f"Unexpected response: {response.strip()}")
        except ConnectionRefusedError:
            warn("Control port 9051 not accessible")
            warn("Add 'ControlPort 9051' to /etc/tor/torrc and restart Tor")
            return
        except Exception as e:
            err(f"Failed to send NEWNYM: {e}")
            return

        info("Waiting for new circuit...")
        time.sleep(5)
        self._show_exit_ip()

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------
    def _is_active(self) -> bool:
        result = subprocess.run(
            ["systemctl", "is-active", "tor"],
            capture_output=True, text=True
        )
        return result.stdout.strip() == "active"

    def is_active(self) -> bool:
        return self._is_active()

    def _show_exit_ip(self):
        info("Fetching current exit IP...")
        try:
            resp = requests.get(
                TOR_CHECK_URL,
                proxies={"https": SOCKS_PROXY, "http": SOCKS_PROXY},
                timeout=REQUEST_TIMEOUT
            )
            data = resp.json()
            if data.get("IsTor"):
                label("Exit IP",  f"[cyan]{data.get('IP', 'unknown')}[/cyan]")
                label("Status",   status_badge("protected"))
            else:
                label("Exit IP",  f"[yellow]{data.get('IP', 'unknown')}[/yellow]")
                label("Status",   status_badge("uncertain"))
        except Exception:
            warn("Could not reach Tor check endpoint")

    def get_exit_ip(self) -> dict:
        """Return dict with IP and IsTor fields, or empty dict on failure."""
        try:
            resp = requests.get(
                TOR_CHECK_URL,
                proxies={"https": SOCKS_PROXY, "http": SOCKS_PROXY},
                timeout=REQUEST_TIMEOUT
            )
            return resp.json()
        except Exception:
            return {}

    def get_direct_ip(self) -> str:
        try:
            resp = requests.get("https://api.ipify.org", timeout=REQUEST_TIMEOUT)
            return resp.text.strip()
        except Exception:
            return "unavailable"
