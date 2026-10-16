#!/usr/bin/env bash
# ==============================================================================
# Setup Passwordless Sudo for Shadowsocks TUN Mode
# ==============================================================================
# This script creates a secure sudoers drop-in file allowing the current user
# to run /usr/bin/sslocal and /usr/bin/ip without entering a sudo password.
# Run with:
#     sudo bash scripts/setup_sudoers.sh
# ==============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "[!] This script must be run as root (e.g. sudo bash $0)"
    exit 1
fi

TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
SSLOCAL_BIN="$(which sslocal || echo '/usr/bin/sslocal')"
IP_BIN="$(which ip || echo '/usr/bin/ip')"
IP6TABLES_BIN="$(which ip6tables || echo '/usr/bin/ip6tables')"
SYSCTL_BIN="$(which sysctl || echo '/usr/bin/sysctl')"
SUDOERS_FILE="/etc/sudoers.d/shadowsocks-tun"

echo "[*] Configuring passwordless sudo for user: $TARGET_USER"
echo "[*] sslocal binary:   $SSLOCAL_BIN"
echo "[*] ip binary:        $IP_BIN"
echo "[*] ip6tables binary: $IP6TABLES_BIN"
echo "[*] sysctl binary:    $SYSCTL_BIN"

cat <<EOF > "$SUDOERS_FILE"
# Allow $TARGET_USER to manage Shadowsocks TUN adapter, routing, and IPv6 leak protection without password
$TARGET_USER ALL=(ALL) NOPASSWD: $SSLOCAL_BIN, $IP_BIN, $IP6TABLES_BIN, $SYSCTL_BIN
EOF

chmod 0440 "$SUDOERS_FILE"

# Validate syntax with visudo
if visudo -c -f "$SUDOERS_FILE"; then
    echo "[✓] Successfully installed and verified $SUDOERS_FILE"
    echo "[✓] User '$TARGET_USER' can now toggle TUN mode in the TUI without entering a sudo password!"
else
    echo "[!] Sudoers syntax check failed! Removing file to prevent issues."
    rm -f "$SUDOERS_FILE"
    exit 1
fi
