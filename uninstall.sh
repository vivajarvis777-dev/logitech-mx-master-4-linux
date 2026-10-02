#!/usr/bin/env bash
# Uninstallation script for Logitech MX Master 4 Linux Daemon

set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
CONF_DIR="${HOME}/.config/mx4"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

echo "=== Uninstalling Logitech MX Master 4 Linux Daemon ==="

# Stop and disable systemd service
if systemctl --user is-active --quiet mx4-daemon.service 2>/dev/null; then
    echo "Stopping mx4-daemon.service..."
    systemctl --user stop mx4-daemon.service || true
fi

if systemctl --user is-enabled --quiet mx4-daemon.service 2>/dev/null; then
    echo "Disabling mx4-daemon.service..."
    systemctl --user disable mx4-daemon.service || true
fi

# Remove unit file
rm -f "${SYSTEMD_USER_DIR}/mx4-daemon.service"
systemctl --user daemon-reload || true

# Remove binaries
rm -f "${BIN_DIR}/mx4-daemon"
rm -f "${BIN_DIR}/mx4-screenshot-menu"

echo "Removed binaries from ${BIN_DIR}."

# Restore legacy autostart if backup exists
if [[ -f "${HOME}/.config/autostart/mx4-daemon.desktop.bak" ]]; then
    echo "Restoring legacy autostart file ~/.config/autostart/mx4-daemon.desktop..."
    mv "${HOME}/.config/autostart/mx4-daemon.desktop.bak" "${HOME}/.config/autostart/mx4-daemon.desktop"
fi

echo ""
echo "Note: Configuration directory ${CONF_DIR} was preserved."
echo "If you wish to purge it, run: rm -rf ${CONF_DIR}"
echo ""
echo "=== Uninstallation Complete ==="
