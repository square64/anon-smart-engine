import subprocess
import sys
import pwd

from core.display import ok, info, warn, err, label, section, status_badge

TRANS_PORT = 9040
DNS_PORT   = 5353

BYPASS_NETS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "224.0.0.4",
    "240.0.0.0/4",
]


class ProxyManager:

    # ----------------------------------------------------------
    # ENABLE
    # ----------------------------------------------------------
    def enable(self):
        section("Enabling Transparent Proxy")

        tor_uid = self._get_tor_uid()

        if tor_uid is None:
            warn("Tor user not found (debian-tor/tor)")
            warn("UID filtering disabled (less secure)")

        info("Cleaning previous ANON rules...")
        self._clean_all_rules()

        info("Setting up NAT rules...")

        try:
            self._apply_rules(tor_uid)

            ok("Transparent proxy enabled")
            ok("All TCP traffic routed through Tor")
            ok("DNS redirected through Tor")

            label("Tor TransPort", f"[cyan]127.0.0.1:{TRANS_PORT}[/cyan]")
            label("Tor DNSPort",   f"[cyan]127.0.0.1:{DNS_PORT}[/cyan]")
            label("Status",        status_badge("protected"))

        except subprocess.CalledProcessError as e:
            err(f"iptables error: {e}")
            self._clean_all_rules()
            sys.exit(1)

    # ----------------------------------------------------------
    # RULE ENGINE
    # ----------------------------------------------------------
    def _apply_rules(self, tor_uid):

        cmds = []

        # 1. DNS redirect (MUST be first)
        cmds.append([
            "sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
            "-p", "udp", "--dport", "53",
            "-j", "REDIRECT", "--to-ports", str(DNS_PORT)
        ])

        # 2. LAN + local bypass
        for net in BYPASS_NETS:
            cmds.append([
                "sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
                "-d", net, "-j", "RETURN"
            ])

        # 3. Tor process bypass (safe)
        if tor_uid is not None:
            cmds.append([
                "sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
                "-m", "owner", "--uid-owner", str(tor_uid),
                "-j", "RETURN"
            ])

        # 4. MAIN TOR REDIRECT (critical)
        cmds.append([
            "sudo", "iptables", "-t", "nat", "-A", "OUTPUT",
            "-p", "tcp",
            "-j", "REDIRECT", "--to-ports", str(TRANS_PORT)
        ])

        # 5. Safety: block non-DNS UDP
        cmds.append([
            "sudo", "iptables", "-A", "OUTPUT",
            "-p", "udp", "--dport", "53", "-j", "ACCEPT"
        ])

        cmds.append([
            "sudo", "iptables", "-A", "OUTPUT",
            "-p", "udp", "-j", "DROP"
        ])

        for cmd in cmds:
            subprocess.run(cmd, check=True, capture_output=True)

    # ----------------------------------------------------------
    # CLEAN ALL RULES (IMPORTANT FIX)
    # ----------------------------------------------------------
    def _clean_all_rules(self):
        subprocess.run(["sudo", "iptables", "-t", "nat", "-F", "OUTPUT"], capture_output=True)
        subprocess.run(["sudo", "iptables", "-t", "nat", "-F"], capture_output=True)
        subprocess.run(["sudo", "iptables", "-F", "OUTPUT"], capture_output=True)
        subprocess.run(["sudo", "iptables", "-F"], capture_output=True)

    # ----------------------------------------------------------
    # TOR USER DETECTION
    # ----------------------------------------------------------
    def _get_tor_uid(self):
        for user in ["debian-tor", "tor"]:
            try:
                return pwd.getpwnam(user).pw_uid
            except KeyError:
                continue
        return None

    # ----------------------------------------------------------
    # STATUS CHECK (FIXED + RELIABLE)
    # ----------------------------------------------------------
    def is_active(self):
        result = subprocess.run(
            ["sudo", "iptables", "-t", "nat", "-S"],
            capture_output=True,
            text=True
        )

        rules = result.stdout

        return (
            f"--to-ports {TRANS_PORT}" in rules
            and "REDIRECT" in rules
        )
