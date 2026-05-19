#!/bin/bash
# =============================================================
#  ANON SMART ENGINE v3.0 — Installer
#  https://github.com/square64/anon-smart-engine
# =============================================================

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/square64/anon-smart-engine/main"
REPO_ZIP="https://github.com/square64/anon-smart-engine/archive/refs/heads/main.zip"
INSTALL_DIR="/opt/anon-smart-engine"
BIN_PATH="/usr/local/bin/anon"
TORRC="/etc/tor/torrc"
MIN_PYTHON="3.10"

# =============================================================
# COLORS
# =============================================================
if [[ -t 1 ]]; then
  RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
  CYAN='\033[1;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; DIM=''; NC=''
fi

ok()      { echo -e "${GREEN}  ✔  ${BOLD}$1${NC}"; }
info()    { echo -e "${CYAN}  ◆  ${NC}$1"; }
warn()    { echo -e "${YELLOW}  ⚠  ${BOLD}$1${NC}"; }
err()     { echo -e "${RED}  ✖  ${BOLD}$1${NC}"; exit 1; }
divider() { echo -e "${DIM}  ─────────────────────────────────────────${NC}"; }
section() { echo -e "\n${BOLD}${CYAN}  $1${NC}"; divider; echo; }

# =============================================================
# BANNER
# =============================================================
banner() {
  clear
  echo -e "${CYAN}"
  cat << "EOF"
  █████╗ ███╗   ██╗ ██████╗ ███╗   ██╗
 ██╔══██╗████╗  ██║██╔═══██╗████╗  ██║
 ███████║██╔██╗ ██║██║   ██║██╔██╗ ██║
 ██╔══██║██║╚██╗██║██║   ██║██║╚██╗██║
 ██║  ██║██║ ╚████║╚██████╔╝██║ ╚████║
 ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═══╝
EOF
  echo -e "${NC}"
  echo -e "  ${BOLD}${GREEN}ANON SMART ENGINE${NC} ${DIM}v3.0 — Installer${NC}"
  echo -e "  ${DIM}github.com/square64/anon-smart-engine${NC}"
  divider
  echo
}

# =============================================================
# SYSTEM CHECKS
# =============================================================
check_root() {
  [[ "$EUID" -ne 0 ]] && err "This installer must be run as root: sudo bash install.sh"
  ok "Running as root"
}

check_os() {
  [[ "$(uname -s)" == "Linux" ]] || err "Linux only"
  # Detect distro
  if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
  elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
  elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
  else
    warn "Unknown package manager — you may need to install dependencies manually"
    PKG_MANAGER="unknown"
  fi
  ok "OS: Linux (${PKG_MANAGER})"
}

check_python() {
  local py=""
  for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
      local ver
      ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
      local major minor
      major=$(echo "$ver" | cut -d. -f1)
      minor=$(echo "$ver" | cut -d. -f2)
      if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
        py="$cmd"
        ok "Python $ver: $(command -v $cmd)"
        break
      fi
    fi
  done

  if [[ -z "$py" ]]; then
    info "Python ${MIN_PYTHON}+ not found — attempting install..."
    case "$PKG_MANAGER" in
      apt) apt-get install -y python3 python3-pip python3-venv >/dev/null 2>&1 ;;
      dnf) dnf install -y python3 python3-pip >/dev/null 2>&1 ;;
      *)   err "Please install Python ${MIN_PYTHON}+ manually" ;;
    esac
    py="python3"
  fi
  PYTHON="$py"
}

# =============================================================
# INSTALL SYSTEM DEPENDENCIES
# =============================================================
install_system_deps() {
  section "System Dependencies"

  local deps=(tor curl dnsutils iproute2 netcat-openbsd iptables python3-pip python3-venv unzip)

  case "$PKG_MANAGER" in
    apt)
      info "Updating apt cache..."
      apt-get update -qq
      for dep in "${deps[@]}"; do
        if dpkg -s "$dep" &>/dev/null 2>&1; then
          ok "  $dep (already installed)"
        else
          info "  Installing $dep..."
          apt-get install -y "$dep" >/dev/null 2>&1 && ok "  $dep" || warn "  $dep failed"
        fi
      done
      ;;
    dnf)
      local dnf_deps=(tor curl bind-utils iproute nmap-ncat iptables python3-pip unzip)
      dnf install -y "${dnf_deps[@]}" >/dev/null 2>&1
      ok "Dependencies installed (dnf)"
      ;;
    pacman)
      local pac_deps=(tor curl bind iproute2 openbsd-netcat iptables python-pip unzip)
      pacman -Sy --noconfirm "${pac_deps[@]}" >/dev/null 2>&1
      ok "Dependencies installed (pacman)"
      ;;
    *)
      warn "Skipping automatic dependency install"
      ;;
  esac
}

# =============================================================
# CONFIGURE TORRC
# =============================================================
configure_torrc() {
  section "Configuring Tor"

  local required=(
    "VirtualAddrNetworkIPv4 10.192.0.0/10"
    "AutomapHostsOnResolve 1"
    "TransPort 9040"
    "DNSPort 5353"
    "ControlPort 9051"
  )

  local backup="${TORRC}.bak.$(date +%s)"
  cp "$TORRC" "$backup" 2>/dev/null || true
  info "Backed up torrc to $backup"

  local changed=0
  for line in "${required[@]}"; do
    local key
    key=$(echo "$line" | awk '{print $1}')
    if grep -q "^${key}" "$TORRC" 2>/dev/null; then
      # Replace existing
      sed -i "s|^${key}.*|${line}|" "$TORRC"
    else
      echo "$line" >> "$TORRC"
      changed=1
    fi
    ok "  $line"
  done

  if [[ $changed -eq 1 ]]; then
    info "Restarting Tor to apply new config..."
    systemctl restart tor >/dev/null 2>&1 && ok "Tor restarted" || warn "Tor restart failed"
  else
    ok "torrc already configured"
  fi
}

# =============================================================
# INSTALL PYTHON APP
# =============================================================
install_app() {
  section "Installing ANON SMART ENGINE"

  # Download or copy
  if [[ -f "./anon.py" && -d "./core" ]]; then
    info "Installing from local source..."
    mkdir -p "$INSTALL_DIR"
    cp -r . "$INSTALL_DIR/"
    ok "Copied to $INSTALL_DIR"
  else
    info "Downloading from GitHub..."
    local tmp_zip
    tmp_zip=$(mktemp --suffix=.zip)
    curl -fsSL --max-time 30 "$REPO_ZIP" -o "$tmp_zip" || err "Download failed"

    mkdir -p "$INSTALL_DIR"
    local tmp_dir
    tmp_dir=$(mktemp -d)
    unzip -q "$tmp_zip" -d "$tmp_dir"
    cp -r "$tmp_dir"/anon-smart-engine-main/. "$INSTALL_DIR/"
    rm -rf "$tmp_zip" "$tmp_dir"
    ok "Downloaded and extracted to $INSTALL_DIR"
  fi

  # Virtual environment
  info "Creating Python virtual environment..."
  "$PYTHON" -m venv "$INSTALL_DIR/.venv" >/dev/null 2>&1
  ok "Virtualenv: $INSTALL_DIR/.venv"

  info "Installing Python dependencies..."
  "$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt" \
    && ok "Python packages installed" \
    || err "pip install failed — check network and try again"

  # Wrapper script (auto-escalates to root)
  cat > "$BIN_PATH" << EOF
#!/bin/bash
if [[ "\$EUID" -ne 0 ]]; then
  exec sudo "\$0" "\$@"
fi
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/anon.py" "\$@"
EOF
  chmod +x "$BIN_PATH"
  ok "Wrapper installed: $BIN_PATH"

  # sudoers: passwordless for the anon wrapper
  local sudoers_file="/etc/sudoers.d/anon-smart-engine"
  cat > "$sudoers_file" << EOF
# Allow all users to run anon without password
ALL ALL=(root) NOPASSWD: $BIN_PATH
EOF
  chmod 440 "$sudoers_file"
  ok "Sudoers rule added: $sudoers_file"
}

# =============================================================
# VERIFY
# =============================================================
verify() {
  section "Verification"
  if command -v anon &>/dev/null; then
    ok "'anon' command available in PATH"
  else
    warn "'anon' not found — try: export PATH=\$PATH:/usr/local/bin"
  fi

  if systemctl is-active --quiet tor 2>/dev/null; then
    ok "Tor service is running"
  else
    info "Tor is not running — start with: anon on"
  fi
}

# =============================================================
# UNINSTALL
# =============================================================
uninstall() {
  banner
  section "Uninstalling ANON SMART ENGINE"

  # Disable proxy first
  if command -v anon &>/dev/null; then
    info "Disabling transparent proxy..."
    anon proxy disable 2>/dev/null || true
  fi

  [[ -f "$BIN_PATH" ]]     && rm -f "$BIN_PATH"     && ok "Removed $BIN_PATH"
  [[ -d "$INSTALL_DIR" ]]  && rm -rf "$INSTALL_DIR"  && ok "Removed $INSTALL_DIR"

  echo
  ok "Uninstall complete"
}

# =============================================================
# SUMMARY
# =============================================================
summary() {
  echo
  divider
  echo -e "  ${BOLD}${GREEN}Installation complete!${NC}"
  divider
  echo
  echo -e "  ${BOLD}Quick start:${NC}"
  echo -e "  ${CYAN}anon on${NC}              ${DIM}# Start Tor + transparent proxy${NC}"
  echo -e "  ${CYAN}anon check${NC}           ${DIM}# Full diagnostics${NC}"
  echo -e "  ${CYAN}anon watch${NC}           ${DIM}# Continuous leak monitor${NC}"
  echo -e "  ${CYAN}anon watch --interval 60 --alert-only${NC}"
  echo -e "  ${CYAN}anon newid${NC}           ${DIM}# New Tor identity${NC}"
  echo -e "  ${CYAN}anon proxy status${NC}    ${DIM}# Check iptables rules${NC}"
  echo -e "  ${CYAN}anon check --json${NC}    ${DIM}# JSON output for scripting${NC}"
  echo
  divider
  echo -e "  ${DIM}Installed to: $INSTALL_DIR${NC}"
  echo -e "  ${DIM}Tor config:   $TORRC${NC}"
  echo
}

# =============================================================
# ENTRY POINT
# =============================================================
case "${1:-}" in
  --uninstall|-u) check_root; uninstall; exit 0 ;;
  --help|-h)
    echo "Usage: sudo bash install.sh [--uninstall]"
    exit 0
    ;;
esac

banner
check_root
check_os
check_python
install_system_deps
configure_torrc
install_app
verify
summary
