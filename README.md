<div align="center">

```
  █████╗ ███╗   ██╗ ██████╗ ███╗   ██╗
 ██╔══██╗████╗  ██║██╔═══██╗████╗  ██║
 ███████║██╔██╗ ██║██║   ██║██╔██╗ ██║
 ██╔══██║██║╚██╗██║██║   ██║██║╚██╗██║
 ██║  ██║██║ ╚████║╚██████╔╝██║ ╚████║
 ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═══╝
```

# ANON SMART ENGINE

**System-wide Tor anonymity toolkit with transparent proxy, DNS leak detection and continuous monitoring.**

![Platform](https://img.shields.io/badge/platform-linux-green?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)
![Tor](https://img.shields.io/badge/privacy-tor-purple?style=flat-square)
![Status](https://img.shields.io/badge/status-active-success?style=flat-square)
![Version](https://img.shields.io/badge/version-v3.0.0-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)

</div>

---

## Overview

ANON SMART ENGINE is a Python-based CLI toolkit that goes beyond simple Tor control. It routes **all system traffic** through Tor using `iptables` transparent proxy rules, verifies the circuit against torproject.org, detects IP and DNS leaks in real time, and can continuously monitor your anonymity in the background.

Designed for both security researchers and privacy-conscious users — it handles the hard parts (torrc configuration, iptables rules, DNS redirection) automatically.

---

## How It Works

```
Your traffic
     │
     ▼
iptables NAT (OUTPUT chain)
     │  bypasses: loopback, LAN, Tor process itself
     ▼
Tor TransPort :9040  ──►  Tor network  ──►  Exit node  ──►  Internet
     │
DNS queries ──► Tor DNSPort :5353  (no DNS leak)
```

**Without** the transparent proxy, only apps explicitly configured for SOCKS5 use Tor.  
**With** it, every TCP connection and DNS query is forced through Tor at the kernel level.

---

## Requirements

| Requirement | Version |
|---|---|
| Linux | Ubuntu 20.04+ / Debian 11+ / Arch |
| Python | 3.10+ |
| Tor | any recent version |
| iptables | kernel module must be available |
| Root | required for iptables and Tor service control |

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/square64/anon-smart-engine/main/install.sh -o install.sh
sudo bash install.sh
```

The installer will:
- Install system dependencies (`tor`, `curl`, `dnsutils`, `iptables`, etc.)
- Configure `/etc/tor/torrc` with `TransPort`, `DNSPort`, `ControlPort`
- Create a Python virtualenv at `/opt/anon-smart-engine/.venv`
- Install Python packages (`click`, `rich`, `requests`, `PySocks`)
- Add `anon` to `/usr/local/bin`
- Add a passwordless sudoers rule so `anon` works without `sudo` prefix

**Uninstall:**
```bash
sudo bash install.sh --uninstall
```

---

## Usage

```bash
anon on                          # Start Tor + enable transparent proxy
anon off                         # Stop Tor + restore normal routing
anon status                      # Quick status overview
anon check                       # Full diagnostics
anon check --json                # JSON output (for scripting/pipelines)
anon watch                       # Continuous leak monitor (30s interval)
anon watch --interval 60         # Custom interval
anon watch --alert-only          # Silent unless leak detected
anon newid                       # Request new Tor identity (NEWNYM)
anon proxy enable                # Enable iptables rules only
anon proxy disable               # Disable iptables rules only
anon proxy status                # Show current proxy state
```

---

## Features

| Feature | Description |
|---|---|
| **Transparent Proxy** | Routes all TCP via `iptables` NAT — no per-app SOCKS config needed |
| **DNS Leak Prevention** | Redirects DNS queries to Tor's `DNSPort` at kernel level |
| **Circuit Verification** | Confirms routing via `check.torproject.org` after every `anon on` |
| **IP Leak Detection** | Compares direct IP vs Tor exit IP — flags if they match |
| **DNS Leak Detection** | Tests DNS resolution through Tor DNS port vs system resolver |
| **Watch Mode** | Continuous monitoring with session summary on exit |
| **New Identity** | Sends `NEWNYM` via Tor control port for a fresh exit node |
| **JSON Output** | `--json` flag on any command for pipeline integration |
| **Auto torrc Config** | Installer sets up all required Tor options automatically |
| **Rich Terminal UI** | Spinner, panels, tables — readable at a glance |

---

## `anon watch` Output

```
  ◆  Watching for leaks every 30s  (Ctrl+C to stop)

  10:42:01  ✔  Protected  Exit: x.x.x.x
  10:42:31  ✔  Protected  Exit: x.x.x.x
  10:43:01  ⚠  IP LEAK — Direct and Tor IP match: y.y.y.y
  10:43:31  ✔  Protected  Exit: z.z.z.z

╭─────────── WATCH SESSION SUMMARY ────────────╮
│   Session checks      4                      │
│   Clean checks        3                      │
│   IP leaks            1                      │
│   Circuit drops       0                      │
│   Tor down events     0                      │
│                                              │
│   Overall             ISSUES DETECTED        │
╰──────────────────────────────────────────────╯
```

---

## Project Structure

```
anon-smart-engine/
├── anon.py              # CLI entry point (Click)
├── core/
│   ├── display.py       # Rich UI helpers
│   ├── tor.py           # Tor service management
│   ├── proxy.py         # iptables transparent proxy
│   ├── check.py         # IP/DNS/leak diagnostics
│   └── watch.py         # Continuous monitor
├── requirements.txt
├── install.sh
└── README.md
```

---

## torrc Reference

The installer configures these automatically. For reference:

```
VirtualAddrNetworkIPv4 10.192.0.0/10
AutomapHostsOnResolve 1
TransPort 9040
DNSPort 5353
ControlPort 9051
```

---

## Roadmap

- [ ] `anon rotate` — auto `newid` on a schedule
- [ ] `~/.anon/config` — user config file (custom ports, interval, log path)
- [ ] Telegram alert integration for `watch` mode
- [ ] IPv6 leak detection
- [ ] Country-based exit node selection (`ExitNodes {us}` helper)
- [ ] TUI dashboard (`textual`)

---

## Security Notes

- This tool requires root — review the source before running with `sudo`
- `anon proxy disable` / `anon off` fully restores your original routing
- The installer backs up your `/etc/tor/torrc` before modifying it
- `ControlPort 9051` is localhost-only; not exposed to the network

---

## Disclaimer

> Intended for **educational purposes and authorized security testing only**.  
> Do not use on systems or networks without **explicit written permission**.  
> The authors accept no responsibility for misuse.

---

## Contributing

1. Fork the repository
2. Create your branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m 'Add your feature'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for details.

---

<div align="center">

If this project helps you, consider giving it a ⭐

</div>
