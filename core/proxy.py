"""
core/proxy.py — iptables transparent proxy management for ANON SMART ENGINE

Routes all TCP/UDP traffic through Tor using iptables NAT rules.
DNS is redirected to Tor's DNSPort (5353).
"""

import subprocess
import sys

from core.display import ok, info, warn, err, label, section, status_badge

# Tor transparent proxy port (must match torrc: TransPort 9040)
TRANS_PORT = 9040
DNS_PORT   = 5353

# IPs that bypass Tor (loopback, LAN, Tor itself)
BYPASS_NETS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "224.0.0.0/4",
    "240.0.0.0/4",
]

TORRC_REQUIRED = f"""
# Required in /etc/tor/torrc for transparent proxy:
VirtualAddrNetworkIPv4 10.192.0.0/10
AutomapHostsOnResolve 1
TransPort {TRANS_PORT}
DNSPort {DNS_PORT}
ControlPort 9051
"""


class ProxyManager:

    # ----------------------------------------------------------
    # ENABLE
    # ----------------------------------------------------------
    def enable(self):
        section("Enabling Transparent Proxy")

        if not self._check_torrc():
            warn("torrc may not be configured for transparent proxy")
            warn("Required settings:")
            for line in TORRC_REQUIRED.strip().splitlines():
                print(f"    {line}")
            print()
            info("Add these to /etc/tor/torrc and restart Tor, then run: anon proxy enable")
            return

        info("Flushing existing iptables rules...")
        self._flush()

        info("Setting up NAT rules...")
        try:
            self._apply_rules()
            ok("Transparent proxy enabled")
            ok("All TCP traffic routed through Tor")
            ok("DNS redirected through Tor (port 5353)")
            print()
            label("Tor TransPort", f"[cyan]127.0.0.1:{TRANS_PORT}[/cyan]")
            label("Tor DNSPort",   f"[cyan]127.0.0.1:{DNS_PORT}[/cyan]")
            label("Status",        status_badge("protected"))
        except subprocess.CalledProcessError as e:
            err(f"iptables rule failed: {e}")
            err("Try running with sudo or check iptables availability")
            self._flush()
            sys.exit(1)

    # ----------------------------------------------------------
    # DISABLE
    # ----------------------------------------------------------
    def disable(self):
        section("Disabling Transparent Proxy")
        info("Flushing Tor iptables rules...")
        self._flush()
        ok("iptables rules cleared")
        ok("Normal network routing restored")
        print()
        label("Status", status_badge("unprotected"))

    # ----------------------------------------------------------
    # STATUS
    # ----------------------------------------------------------
    def status(self):
        section("Proxy Status")
        result = subprocess.run(
            ["sudo", "iptables", "-t", "nat", "-L", "OUTPUT", "-n", "--line-numbers"],
            capture_output=True, text=True
        )
        if f"{TRANS_PORT}" in result.stdout:
            ok("Transparent proxy rules are active")
            label("TransPort", f"[cyan]{TRANS_PORT}[/cyan]")
            label("DNSPort",   f"[cyan]{DNS_PORT}[/cyan]")
            label("Status",    status_badge("protected"))
        else:
            warn("No transparent proxy rules found")
            label("Status", status_badge("unprotected"))

        print()
        info("Raw NAT OUTPUT chain:")
        print(result.stdout)

    # ----------------------------------------------------------
    # IPTABLES RULES
    # ----------------------------------------------------------
    def _apply_rules(self):
        cmds = []

        # --- NAT table ---
        # Redirect DNS to Tor DNSPort
        cmds.append(["sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
                      "-p", "udp", "--dport", "53",
                      "-j", "REDIRECT", "--to-ports", str(DNS_PORT)])

        # Bypass local/LAN addresses
        for net in BYPASS_NETS:
            cmds.append(["sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
                          "-d", net, "-j", "RETURN"])

        # Bypass Tor process itself (by UID — tor runs as debian-tor)
        cmds.append(["sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
                      "-m", "owner", "--uid-owner", "debian-tor", "-j", "RETURN"])

        # Redirect all remaining TCP to TransPort
        cmds.append(["sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
                      "-p", "tcp", "--syn",
                      "-j", "REDIRECT", "--to-ports", str(TRANS_PORT)])

        # --- FILTER table — block non-Tor UDP (except DNS already redirected) ---
        cmds.append(["sudo", "iptables", "-A", "OUTPUT",
                      "-m", "owner", "--uid-owner", "debian-tor", "-j", "ACCEPT"])
        cmds.append(["sudo", "iptables", "-A", "OUTPUT",
                      "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
        for net in BYPASS_NETS:
            cmds.append(["sudo", "iptables", "-A", "OUTPUT",
                          "-d", net, "-j", "ACCEPT"])
        cmds.append(["sudo", "iptables", "-A", "OUTPUT",
                      "-p", "udp", "-j", "DROP"])

        for cmd in cmds:
            subprocess.run(cmd, check=True, capture_output=True)

    def _flush(self):
        """Remove all Tor-related iptables rules (flush NAT OUTPUT + filter OUTPUT)."""
        subprocess.run(["sudo", "iptables", "-t", "nat", "-F", "OUTPUT"],
                       capture_output=True)
        subprocess.run(["sudo", "iptables", "-F", "OUTPUT"],
                       capture_output=True)

    def _check_torrc(self) -> bool:
        """Check if torrc contains required transparent proxy settings."""
        try:
            with open("/etc/tor/torrc") as f:
                content = f.read()
            return f"TransPort {TRANS_PORT}" in content and f"DNSPort {DNS_PORT}" in content
        except FileNotFoundError:
            return False

    def is_active(self) -> bool:
        """Return True if transparent proxy rules are currently applied."""
        result = subprocess.run(
            ["sudo", "iptables", "-t", "nat", "-L", "OUTPUT", "-n"],
            capture_output=True, text=True
        )
        return str(TRANS_PORT) in result.stdout
