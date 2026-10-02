#!/usr/bin/env bash
# Installation script for Logitech MX Master 4 Linux Daemon

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
CONF_DIR="${HOME}/.config/mx4"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

echo "=== Installing Logitech MX Master 4 Linux Daemon ==="

# 1. Check prerequisites
echo "[1/5] Checking dependencies..."
MISSING_PKGS=()
for cmd in python3 wmctrl xinput; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        MISSING_PKGS+=("$cmd")
    fi
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo "Warning: Recommended tools are missing: ${MISSING_PKGS[*]}"
    echo "On Debian/Ubuntu/Mint, install them with:"
    echo "  sudo apt install wmctrl xinput"
    echo ""
fi

# 2. Create destination directories
echo "[2/5] Creating directories..."
mkdir -p "${BIN_DIR}" "${CONF_DIR}" "${SYSTEMD_USER_DIR}"

# 3. Copy binaries and helpers
echo "[3/5] Installing executable scripts to ${BIN_DIR}..."
cp "${SCRIPT_DIR}/mx4_daemon.py" "${BIN_DIR}/mx4-daemon"
chmod +x "${BIN_DIR}/mx4-daemon"

cp "${SCRIPT_DIR}/scripts/screenshot-menu.sh" "${BIN_DIR}/mx4-screenshot-menu"
chmod +x "${BIN_DIR}/mx4-screenshot-menu"

# 4. Install default configuration if not present
echo "[4/5] Setting up configuration in ${CONF_DIR}..."
if [[ ! -f "${CONF_DIR}/config.ini" ]]; then
    cp "${SCRIPT_DIR}/config.ini.example" "${CONF_DIR}/config.ini"
    echo "  Created ${CONF_DIR}/config.ini"
else
    echo "  Configuration ${CONF_DIR}/config.ini already exists. Leaving intact."
fi

# 5. Setup systemd user service
echo "[5/5] Configuring systemd user service..."
cp "${SCRIPT_DIR}/systemd/mx4-daemon.service" "${SYSTEMD_USER_DIR}/mx4-daemon.service"

# Disable legacy autostart desktop file if found to avoid dual daemon instances
if [[ -f "${HOME}/.config/autostart/mx4-daemon.desktop" ]]; then
    echo "  Disabling legacy autostart file ~/.config/autostart/mx4-daemon.desktop..."
    mv "${HOME}/.config/autostart/mx4-daemon.desktop" "${HOME}/.config/autostart/mx4-daemon.desktop.bak"
fi

systemctl --user daemon-reload
systemctl --user enable --now mx4-daemon.service

echo ""
echo "=== Installation Complete! ==="
echo "Service status:"
systemctl --user status mx4-daemon.service --no-pager || true
echo ""
echo "Optional: If you need non-root permission for hidraw, install the udev rule:"
echo "  sudo cp \"${SCRIPT_DIR}/udev/99-logitech-mx4.rules\" /etc/udev/rules.d/"
echo "  sudo udevadm control --reload-rules && sudo udevadm trigger"
echo ""
echo "To test haptic feedback manually, run:"
echo "  ${BIN_DIR}/mx4-daemon --test-haptic 2"
