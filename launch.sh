#!/usr/bin/env bash
# =============================================================================
# launch.sh — HOTAS Warthog Dashboard single-click launcher
#
# What it does:
#   1. Navigates to the script's own directory (works from any working dir)
#   2. Activates the Python virtual environment (venv/) if it exists
#   3. Silently runs scan_joystick.py to refresh device paths / JSON mappings
#   4. Launches hotas_dashboard.py
#
# To create a desktop shortcut run:  bash install.sh
# =============================================================================

set -euo pipefail

# ── find this script's directory even when called via symlink ─────────────────
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR"

# ── select python interpreter ─────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python3"
else
    PYTHON="$(command -v python3 || echo python)"
fi

# ── silently rescan device to update output/*.json ───────────────────────────
"$PYTHON" "$SCRIPT_DIR/scan_joystick.py" --quiet 2>/dev/null || true

# ── launch the dashboard ──────────────────────────────────────────────────────
exec "$PYTHON" "$SCRIPT_DIR/hotas_dashboard.py"
