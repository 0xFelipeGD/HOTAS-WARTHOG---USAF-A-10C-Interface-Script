#!/usr/bin/env bash
# =============================================================================
# install.sh — Install HOTAS Warthog Dashboard as a desktop application
#
# Creates:
#   • ~/Desktop/HOTAS-Warthog.desktop     (double-click to launch)
#   • ~/.local/share/applications/hotas-warthog.desktop  (app menu entry)
#
# Usage:  bash install.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
LAUNCHER="$SCRIPT_DIR/launch.sh"
DESKTOP_DST="$HOME/Desktop/HOTAS-Warthog.desktop"
APPS_DST="$HOME/.local/share/applications/hotas-warthog.desktop"

# Make launcher executable
chmod +x "$LAUNCHER"

# ── write .desktop content ────────────────────────────────────────────────────
write_desktop() {
    cat > "$1" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=HOTAS Warthog Dashboard
GenericName=Joystick Dashboard
Comment=Real-time USAF A-10C HOTAS Warthog interface — Thrustmaster
Exec=$LAUNCHER
Terminal=false
Categories=Utility;HardwareSettings;Game;
Keywords=joystick;HOTAS;warthog;A-10C;thrustmaster;flight;
StartupNotify=true
EOF
    chmod +x "$1"
}

# ── Desktop shortcut ──────────────────────────────────────────────────────────
mkdir -p "$HOME/Desktop"
write_desktop "$DESKTOP_DST"

# Mark as trusted on GNOME so the launcher icon is clickable
if command -v gio &>/dev/null; then
    gio set "$DESKTOP_DST" metadata::trusted true 2>/dev/null || true
fi

# ── Application menu entry ────────────────────────────────────────────────────
mkdir -p "$HOME/.local/share/applications"
write_desktop "$APPS_DST"

# Refresh desktop database if available
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo ""
echo "  [OK] Desktop shortcut:  $DESKTOP_DST"
echo "  [OK] App menu entry:    $APPS_DST"
echo ""
echo "  Double-click 'HOTAS-Warthog' on your Desktop to launch!"
echo "  Or find it in your application menu as 'HOTAS Warthog Dashboard'."
echo ""
echo "  NOTE: Make sure you are in the 'input' group for device access:"
echo "        sudo usermod -aG input \$USER   (then log out and back in)"
echo ""
