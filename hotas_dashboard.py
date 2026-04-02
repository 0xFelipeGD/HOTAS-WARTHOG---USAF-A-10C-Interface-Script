#!/usr/bin/env python3
# =============================================================================
# hotas_dashboard.py
#
# Step 2 — Real-time visual dashboard for the Thrustmaster HOTAS Warthog.
#
# Usage:
#   python3 hotas_dashboard.py
#
# Architecture:
#   • evdev  → input reading on daemon threads (one per USB device)
#   • pygame → 60 Hz render loop on the main thread
#   • SharedState → thread-safe snapshot between the two layers
#
# The dashboard works with or without the JSON files from scan_joystick.py.
# If the files exist they provide calibrated axis ranges; otherwise the script
# auto-detects the device using VID/PID and uses the default ranges from
# warthog_mappings.py.
#
# Permissions:
#   sudo usermod -aG input $USER   (then log out and back in)
# =============================================================================

import sys
import os
import json
import time
import threading

# ---------------------------------------------------------------------------
# Dependency checks — clear messages before cryptic ImportErrors
# ---------------------------------------------------------------------------
try:
    import evdev
    from evdev import ecodes
except ImportError:
    print("\n[ERROR] The 'evdev' library is not installed.")
    print("  Install: pip install evdev\n")
    sys.exit(1)

try:
    import pygame
except ImportError:
    print("\n[ERROR] The 'pygame' library is not installed.")
    print("  Install: pip install pygame\n")
    sys.exit(1)

# Local modules
from config.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    TARGET_FPS, RECONNECT_INTERVAL,
    COLOR_BG, COLOR_PANEL_BG, COLOR_TEXT, COLOR_TEXT_DIM,
    COLOR_TEXT_HEADER, COLOR_GREEN, COLOR_GREEN_DIM, COLOR_RED,
    COLOR_AMBER, COLOR_BLUE, COLOR_BLUE_TROT, COLOR_DARK_GRAY,
    COLOR_BORDER, COLOR_CENTER_LINE,
    AXIS_BAR_WIDTH, AXIS_BAR_HEIGHT, AXIS_LABEL_W,
    BUTTON_LED_RADIUS, BUTTON_LABEL_OFFSET, BUTTON_COL_W, BUTTON_ROW_H,
    HAT_BOX_SIZE, HAT_ARROW_LEN,
    SECTION_PAD, SECTION_GAP,
    VENDOR_THRUSTMASTER, PID_WARTHOG_STICK, PID_WARTHOG_THROTTLE,
)
from warthog_mappings import (
    STICK_BUTTON_MAP, STICK_AXIS_MAP, STICK_HAT_MAP,
    STICK_BUTTON_GROUPS,
    THROTTLE_BUTTON_MAP, THROTTLE_AXIS_MAP, THROTTLE_HAT_MAP,
    THROTTLE_BUTTON_GROUPS,
    STICK_NAME_PATTERNS, THROTTLE_NAME_PATTERNS,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STICK_JSON    = os.path.join(OUTPUT_DIR, "warthog_stick_map.json")
THROTTLE_JSON = os.path.join(OUTPUT_DIR, "warthog_throttle_map.json")


# =============================================================================
# SharedState — thread-safe state container
# =============================================================================

class SharedState:
    """
    Stores the latest values from both evdev input threads.
    The render thread calls snapshot() to get a point-in-time copy without
    holding the lock during the entire draw cycle.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Axes: {evdev_code: float}  (normalised to -1.0..1.0 or 0.0..1.0)
        self.stick_axes     = {}
        self.throttle_axes  = {}

        # Buttons: {evdev_code: bool}
        self.stick_buttons    = {}
        self.throttle_buttons = {}

        # Hats: {"H1": (hat_x_raw, hat_y_raw)} where raw is -1, 0, or 1
        self.stick_hats    = {}
        self.throttle_hats = {}

        # Pending hat axis updates (we receive X and Y separately)
        self._hat_pending_stick    = {}
        self._hat_pending_throttle = {}

        # Connection flags
        self.stick_connected    = False
        self.throttle_connected = False

        # Stats
        self.stick_events_sec    = 0
        self.throttle_events_sec = 0
        self._stick_event_count    = 0
        self._throttle_event_count = 0
        self._last_stat_time = time.monotonic()

    # ---- Axis ---------------------------------------------------------------

    def update_axis(self, device_type: str, code: int, norm_value: float) -> None:
        with self._lock:
            if device_type == "stick":
                self.stick_axes[code] = norm_value
            else:
                self.throttle_axes[code] = norm_value

    # ---- Button -------------------------------------------------------------

    def update_button(self, device_type: str, code: int, pressed: bool) -> None:
        with self._lock:
            if device_type == "stick":
                self.stick_buttons[code] = pressed
                self._stick_event_count += 1
            else:
                self.throttle_buttons[code] = pressed
                self._throttle_event_count += 1

    # ---- Hat (received as two separate EV_ABS events) ----------------------

    def update_hat_axis(self, device_type: str, code: int, raw: int,
                        hat_map: dict) -> None:
        """
        Accumulate X / Y hat axis events then resolve to (x, y) tuple.
        hat_map: the STICK_HAT_MAP or THROTTLE_HAT_MAP dict.
        """
        with self._lock:
            pending = (self._hat_pending_stick
                       if device_type == "stick"
                       else self._hat_pending_throttle)
            hats    = (self.stick_hats
                       if device_type == "stick"
                       else self.throttle_hats)

            for hat_key, hat_def in hat_map.items():
                if code == hat_def["code_x"]:
                    pending.setdefault(hat_key, [None, None])
                    pending[hat_key][0] = raw
                elif code == hat_def["code_y"]:
                    pending.setdefault(hat_key, [None, None])
                    pending[hat_key][1] = raw

                # Publish once both axes received
                if hat_key in pending:
                    x, y = pending[hat_key]
                    if x is not None and y is not None:
                        hats[hat_key] = (x, y)
                        pending[hat_key] = [None, None]

    # ---- Connection ---------------------------------------------------------

    def set_connected(self, device_type: str, value: bool) -> None:
        with self._lock:
            if device_type == "stick":
                self.stick_connected = value
            else:
                self.throttle_connected = value

    # ---- Stats tick (called once per second from main thread) ---------------

    def tick_stats(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_stat_time
        if elapsed >= 1.0:
            with self._lock:
                self.stick_events_sec    = int(self._stick_event_count    / elapsed)
                self.throttle_events_sec = int(self._throttle_event_count / elapsed)
                self._stick_event_count    = 0
                self._throttle_event_count = 0
            self._last_stat_time = now

    # ---- Snapshot (render thread uses this) ---------------------------------

    def snapshot(self) -> dict:
        """Return a shallow-copied, immutable snapshot — no lock held after return."""
        with self._lock:
            return {
                "stick_axes":         dict(self.stick_axes),
                "throttle_axes":      dict(self.throttle_axes),
                "stick_buttons":      dict(self.stick_buttons),
                "throttle_buttons":   dict(self.throttle_buttons),
                "stick_hats":         dict(self.stick_hats),
                "throttle_hats":      dict(self.throttle_hats),
                "stick_connected":    self.stick_connected,
                "throttle_connected": self.throttle_connected,
                "stick_events_sec":   self.stick_events_sec,
                "throttle_events_sec":self.throttle_events_sec,
            }


# =============================================================================
# Axis normalisation
# =============================================================================

def normalise_axis(raw: int, ax_min: int, ax_max: int, bipolar: bool) -> float:
    """
    Map a raw axis integer to a float.
    bipolar=True  → -1.0 … +1.0
    bipolar=False →  0.0 …  1.0
    """
    if ax_max == ax_min:
        return 0.0
    ratio = (raw - ax_min) / (ax_max - ax_min)   # 0.0 … 1.0
    return (ratio * 2.0 - 1.0) if bipolar else ratio


# =============================================================================
# Mapping loader — JSON or fallback
# =============================================================================

def _load_json(path: str) -> dict | None:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def build_axis_lookup(mapping_json: dict | None,
                      axis_map: dict) -> dict:
    """
    Returns {code: {min, max, bipolar}} for normalisation.
    Prefers data from scan_joystick.py JSON (calibrated hardware ranges),
    falls back to theoretical 0–65535 for unknown axes.
    """
    lookup = {}
    if mapping_json:
        for ax in mapping_json.get("axes", []):
            code    = ax["code"]
            bipolar = axis_map.get(code, {}).get("bipolar", True)
            lookup[code] = {"min": ax["min"], "max": ax["max"], "bipolar": bipolar}
    # Fill gaps from warthog_mappings (use 0–65535 as default range)
    for code, info in axis_map.items():
        if code not in lookup:
            lookup[code] = {"min": 0, "max": 65535, "bipolar": info["bipolar"]}
    return lookup


# =============================================================================
# Device detection
# =============================================================================

def _name_matches(name: str, patterns: list) -> bool:
    n = (name or "").lower()
    return any(p.lower() in n for p in patterns)


def auto_detect_warthog() -> tuple:
    """Returns (stick_path, throttle_path) — either may be None."""
    stick_path    = None
    throttle_path = None
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            info = dev.info
            if info.vendor == VENDOR_THRUSTMASTER:
                if info.product == PID_WARTHOG_STICK:
                    stick_path = path
                elif info.product == PID_WARTHOG_THROTTLE:
                    throttle_path = path
            elif _name_matches(dev.name, STICK_NAME_PATTERNS):
                stick_path = stick_path or path
            elif _name_matches(dev.name, THROTTLE_NAME_PATTERNS):
                throttle_path = throttle_path or path
            dev.close()
        except (PermissionError, OSError):
            pass
    return stick_path, throttle_path


def resolve_device_path(json_map: dict | None, fallback_path: str | None) -> str | None:
    """Use the path from the JSON mapping if valid, else use fallback."""
    if json_map:
        candidate = json_map.get("device_path")
        if candidate and os.path.exists(candidate):
            return candidate
    return fallback_path


# =============================================================================
# Input reader thread
# =============================================================================

def input_reader(device_path: str, device_type: str,
                 axis_lookup: dict, hat_map: dict,
                 shared: SharedState) -> None:
    """
    Daemon thread: opens the evdev device and runs an infinite read loop.
    On disconnect (OSError) it waits RECONNECT_INTERVAL and retries.
    """
    while True:
        try:
            dev = evdev.InputDevice(device_path)
            shared.set_connected(device_type, True)
            for event in dev.read_loop():
                if event.type == ecodes.EV_ABS:
                    code = event.code
                    # Check if it is a hat axis
                    is_hat = any(
                        code in (hd["code_x"], hd["code_y"])
                        for hd in hat_map.values()
                    )
                    if is_hat:
                        shared.update_hat_axis(device_type, code, event.value, hat_map)
                    else:
                        ax_info = axis_lookup.get(code)
                        if ax_info:
                            norm = normalise_axis(
                                event.value,
                                ax_info["min"],
                                ax_info["max"],
                                ax_info["bipolar"],
                            )
                            shared.update_axis(device_type, code, norm)
                elif event.type == ecodes.EV_KEY:
                    shared.update_button(device_type, event.code, bool(event.value))
        except PermissionError:
            print(f"[{device_type.upper()}] Permission denied on {device_path}.")
            print("  Fix: sudo usermod -aG input $USER  then log out and back in.")
            shared.set_connected(device_type, False)
            time.sleep(RECONNECT_INTERVAL)
        except OSError:
            shared.set_connected(device_type, False)
            time.sleep(RECONNECT_INTERVAL)


# =============================================================================
# Rendering helpers
# =============================================================================

def draw_panel(surf: pygame.Surface,
               rect: pygame.Rect,
               title: str,
               font_h: pygame.font.Font) -> None:
    """Draw a rounded-corner panel with a title bar."""
    pygame.draw.rect(surf, COLOR_PANEL_BG, rect, border_radius=6)
    pygame.draw.rect(surf, COLOR_BORDER,   rect, width=1, border_radius=6)
    lbl = font_h.render(title, True, COLOR_TEXT_HEADER)
    surf.blit(lbl, (rect.x + SECTION_PAD, rect.y + 4))


def draw_axis_bar(surf: pygame.Surface,
                  font: pygame.font.Font,
                  x: int, y: int,
                  label: str,
                  value: float,
                  bipolar: bool,
                  color: tuple) -> None:
    """
    Draw a horizontal progress bar representing one axis value.
    bipolar=True: bar fills from centre outward; value range -1.0..1.0
    bipolar=False: bar fills from left; value range 0.0..1.0
    """
    # Label
    lbl = font.render(label, True, COLOR_TEXT_DIM)
    surf.blit(lbl, (x, y))

    bx = x + AXIS_LABEL_W
    by = y
    bw = AXIS_BAR_WIDTH
    bh = AXIS_BAR_HEIGHT

    # Track background
    pygame.draw.rect(surf, COLOR_BORDER, (bx, by, bw, bh), border_radius=3)

    # Fill
    clamped = max(-1.0, min(1.0, value))
    if bipolar:
        mid = bx + bw // 2
        fill_w = int(abs(clamped) * (bw // 2))
        if clamped >= 0:
            fill_rect = pygame.Rect(mid, by + 1, fill_w, bh - 2)
        else:
            fill_rect = pygame.Rect(mid - fill_w, by + 1, fill_w, bh - 2)
    else:
        fill_w = int(clamped * bw)
        fill_rect = pygame.Rect(bx, by + 1, fill_w, bh - 2)

    if fill_rect.width > 0:
        pygame.draw.rect(surf, color, fill_rect, border_radius=2)

    # Center line (bipolar only)
    if bipolar:
        cx = bx + bw // 2
        pygame.draw.line(surf, COLOR_CENTER_LINE, (cx, by), (cx, by + bh))

    # Numeric value
    val_lbl = font.render(f"{value:+.2f}", True, COLOR_TEXT)
    surf.blit(val_lbl, (bx + bw + 6, by))


def draw_button_led(surf: pygame.Surface,
                    font: pygame.font.Font,
                    cx: int, cy: int,
                    label: str,
                    pressed: bool) -> None:
    """Draw a circular LED indicator with a label."""
    color  = COLOR_GREEN     if pressed else COLOR_DARK_GRAY
    border = COLOR_GREEN_DIM if pressed else COLOR_BORDER
    pygame.draw.circle(surf, color,  (cx, cy), BUTTON_LED_RADIUS)
    pygame.draw.circle(surf, border, (cx, cy), BUTTON_LED_RADIUS, 1)
    lbl = font.render(label, True, COLOR_TEXT if pressed else COLOR_TEXT_DIM)
    surf.blit(lbl, (cx + BUTTON_LED_RADIUS + BUTTON_LABEL_OFFSET, cy - lbl.get_height() // 2))


def draw_hat_indicator(surf: pygame.Surface,
                       font: pygame.font.Font,
                       x: int, y: int,
                       label: str,
                       hat_x: int, hat_y: int) -> None:
    """
    Draw a 4-arrow hat indicator.
    hat_x / hat_y: -1, 0, or 1.
    """
    cx = x + HAT_BOX_SIZE // 2
    cy = y + HAT_BOX_SIZE // 2 + 10
    sz = HAT_BOX_SIZE

    # Box
    pygame.draw.rect(surf, COLOR_PANEL_BG, (x, y + 10, sz, sz), border_radius=4)
    pygame.draw.rect(surf, COLOR_BORDER,   (x, y + 10, sz, sz), width=1, border_radius=4)

    # Label above
    lbl = font.render(label, True, COLOR_TEXT_HEADER)
    surf.blit(lbl, (x + sz // 2 - lbl.get_width() // 2, y - 2))

    al = HAT_ARROW_LEN
    directions = {
        "U": ((cx, cy), (cx, cy - al),      hat_y == -1),
        "D": ((cx, cy), (cx, cy + al),      hat_y ==  1),
        "L": ((cx, cy), (cx - al, cy),      hat_x == -1),
        "R": ((cx, cy), (cx + al, cy),      hat_x ==  1),
    }
    for _, (start, end, active) in directions.items():
        color = COLOR_GREEN if active else COLOR_TEXT_DIM
        pygame.draw.line(surf, color, start, end, 3 if active else 1)
        # Arrowhead dot
        pygame.draw.circle(surf, color, end, 3 if active else 2)

    # Centre dot — green when any direction active
    any_active = hat_x != 0 or hat_y != 0
    pygame.draw.circle(surf, COLOR_GREEN if any_active else COLOR_BORDER, (cx, cy), 4)


def draw_connection_badge(surf: pygame.Surface,
                          font: pygame.font.Font,
                          x: int, y: int,
                          label: str,
                          connected: bool) -> None:
    color = COLOR_GREEN if connected else COLOR_RED
    text  = f"{label}: {'CONNECTED' if connected else 'DISCONNECTED'}"
    lbl = font.render(text, True, color)
    surf.blit(lbl, (x, y))


# =============================================================================
# High-level section renderers
# =============================================================================

def render_axes_panel(surf: pygame.Surface,
                      font_h: pygame.font.Font,
                      font: pygame.font.Font,
                      rect: pygame.Rect,
                      title: str,
                      axes_state: dict,
                      axis_map: dict,
                      axis_lookup: dict,
                      color: tuple) -> None:
    draw_panel(surf, rect, title, font_h)
    row_h = AXIS_BAR_HEIGHT + 8
    y = rect.y + 26
    for code, info in axis_map.items():
        if y + row_h > rect.bottom - 4:
            break
        value = axes_state.get(code, 0.0)
        draw_axis_bar(
            surf, font,
            rect.x + SECTION_PAD, y,
            info["name"], value, info["bipolar"], color,
        )
        y += row_h


def render_buttons_panel(surf: pygame.Surface,
                         font_h: pygame.font.Font,
                         font: pygame.font.Font,
                         rect: pygame.Rect,
                         title: str,
                         buttons_state: dict,
                         button_map: dict,
                         button_groups: list) -> None:
    draw_panel(surf, rect, title, font_h)

    x0 = rect.x + SECTION_PAD
    y0 = rect.y + 26

    col = 0
    row = 0
    max_cols = max(1, (rect.width - 2 * SECTION_PAD) // BUTTON_COL_W)

    for group_key, group_label in button_groups:
        group_btns = [
            (code, info)
            for code, info in button_map.items()
            if info["group"] == group_key
        ]
        if not group_btns:
            continue

        # Group header — if we're mid-row start a new row
        if col != 0:
            row += 1
            col = 0

        # Draw group label
        glbl = font.render(group_label, True, COLOR_AMBER)
        gy = y0 + row * BUTTON_ROW_H
        if gy + BUTTON_ROW_H > rect.bottom - 4:
            break
        surf.blit(glbl, (x0, gy))
        row += 1
        col = 0

        for code, info in sorted(group_btns, key=lambda b: b[1]["dx"]):
            cx = x0 + col * BUTTON_COL_W + BUTTON_LED_RADIUS
            cy = y0 + row * BUTTON_ROW_H + BUTTON_LED_RADIUS
            if cy + BUTTON_LED_RADIUS > rect.bottom - 4:
                break
            pressed = buttons_state.get(code, False)
            draw_button_led(surf, font, cx, cy, info["name"], pressed)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        row += 1
        col = 0


def render_hats_panel(surf: pygame.Surface,
                      font_h: pygame.font.Font,
                      font: pygame.font.Font,
                      rect: pygame.Rect,
                      title: str,
                      hats_state: dict,
                      hat_map: dict,
                      # also include 4-way hat-button groups (TMS/DMS/CMS)
                      buttons_state: dict | None = None,
                      hat_button_groups: list | None = None,
                      button_map: dict | None = None) -> None:
    draw_panel(surf, rect, title, font_h)

    x = rect.x + SECTION_PAD
    y = rect.y + 26

    # ABS hat axes
    for hat_key, hat_def in hat_map.items():
        hx, hy = hats_state.get(hat_key, (0, 0))
        draw_hat_indicator(surf, font, x, y, hat_def["name"], hx, hy)
        x += HAT_BOX_SIZE + SECTION_GAP + 10
        if x + HAT_BOX_SIZE > rect.right:
            x = rect.x + SECTION_PAD
            y += HAT_BOX_SIZE + 20

    # Hat-button groups rendered as mini LED clusters
    if buttons_state and hat_button_groups and button_map:
        for group_key, group_label in hat_button_groups:
            group_btns = sorted(
                [(c, i) for c, i in button_map.items() if i["group"] == group_key],
                key=lambda b: b[1]["dx"],
            )
            if not group_btns:
                continue

            # Derive (x,y) from active button
            hat_x, hat_y = 0, 0
            for code, info in group_btns:
                if buttons_state.get(code, False):
                    nm = info["name"]
                    if nm.endswith("U"):
                        hat_y = -1
                    elif nm.endswith("D"):
                        hat_y =  1
                    elif nm.endswith("L"):
                        hat_x = -1
                    elif nm.endswith("R"):
                        hat_x =  1

            if x + HAT_BOX_SIZE > rect.right:
                x = rect.x + SECTION_PAD
                y += HAT_BOX_SIZE + 20

            draw_hat_indicator(surf, font, x, y, group_label, hat_x, hat_y)
            x += HAT_BOX_SIZE + SECTION_GAP + 10


# =============================================================================
# Startup helpers
# =============================================================================

def print_no_device_error() -> None:
    print("\n[ERROR] No Thrustmaster HOTAS Warthog device found.")
    print("  Check USB:     lsusb | grep -i 044f")
    print("  Check devices: cat /proc/bus/input/devices | grep -i warthog")
    print("  Check perms:   sudo usermod -aG input $USER  (then re-login)")
    print()


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    # ------------------------------------------------------------------
    # 1. Load JSON mappings from scan_joystick.py output (if available)
    # ------------------------------------------------------------------
    stick_json    = _load_json(STICK_JSON)
    throttle_json = _load_json(THROTTLE_JSON)

    if not stick_json:
        print("[INFO] output/warthog_stick_map.json not found — using auto-detect.")
    if not throttle_json:
        print("[INFO] output/warthog_throttle_map.json not found — using auto-detect.")

    # ------------------------------------------------------------------
    # 2. Resolve device paths
    # ------------------------------------------------------------------
    auto_stick, auto_throttle = auto_detect_warthog()

    stick_path    = resolve_device_path(stick_json,    auto_stick)
    throttle_path = resolve_device_path(throttle_json, auto_throttle)

    if stick_path is None and throttle_path is None:
        print_no_device_error()
        # We continue anyway so the user can see the dashboard in
        # "no-device" mode (all indicators grey / disconnected).

    # ------------------------------------------------------------------
    # 3. Build axis lookup tables (range info for normalisation)
    # ------------------------------------------------------------------
    stick_axis_lookup    = build_axis_lookup(stick_json,    STICK_AXIS_MAP)
    throttle_axis_lookup = build_axis_lookup(throttle_json, THROTTLE_AXIS_MAP)

    # ------------------------------------------------------------------
    # 4. Shared state
    # ------------------------------------------------------------------
    shared = SharedState()

    # ------------------------------------------------------------------
    # 5. Spawn input threads (daemon — die with main thread)
    # ------------------------------------------------------------------
    if stick_path:
        t_stick = threading.Thread(
            target=input_reader,
            args=(stick_path, "stick", stick_axis_lookup, STICK_HAT_MAP, shared),
            daemon=True,
        )
        t_stick.start()

    if throttle_path:
        t_throttle = threading.Thread(
            target=input_reader,
            args=(throttle_path, "throttle", throttle_axis_lookup, THROTTLE_HAT_MAP, shared),
            daemon=True,
        )
        t_throttle.start()

    # ------------------------------------------------------------------
    # 6. Pygame initialisation
    # ------------------------------------------------------------------
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock  = pygame.time.Clock()

    font_large  = pygame.font.SysFont("monospace", 20, bold=True)
    font_medium = pygame.font.SysFont("monospace", 14, bold=True)
    font_small  = pygame.font.SysFont("monospace", 12)

    # ------------------------------------------------------------------
    # 7. Layout constants (computed once)
    # ------------------------------------------------------------------
    H_HEADER  = 56
    H_FOOTER  = 30
    USABLE_H  = WINDOW_HEIGHT - H_HEADER - H_FOOTER
    COL_W     = WINDOW_WIDTH // 2 - SECTION_GAP

    # Row splits inside each column
    AXES_H    = 220
    HATS_H    = 150
    BTNS_H    = USABLE_H - AXES_H - HATS_H - SECTION_GAP * 2

    # Left column (stick)
    stick_axes_rect  = pygame.Rect(SECTION_GAP,  H_HEADER + SECTION_GAP,
                                    COL_W, AXES_H)
    stick_hats_rect  = pygame.Rect(SECTION_GAP,
                                    stick_axes_rect.bottom + SECTION_GAP,
                                    COL_W, HATS_H)
    stick_btns_rect  = pygame.Rect(SECTION_GAP,
                                    stick_hats_rect.bottom + SECTION_GAP,
                                    COL_W, BTNS_H)

    # Right column (throttle)
    rx = WINDOW_WIDTH // 2 + SECTION_GAP
    thr_axes_rect  = pygame.Rect(rx, H_HEADER + SECTION_GAP,
                                  COL_W, AXES_H)
    thr_hats_rect  = pygame.Rect(rx, thr_axes_rect.bottom + SECTION_GAP,
                                  COL_W, HATS_H)
    thr_btns_rect  = pygame.Rect(rx, thr_hats_rect.bottom + SECTION_GAP,
                                  COL_W, BTNS_H)

    # Hat button groups shown inside the hats panel
    STICK_HAT_BTN_GROUPS  = [("tms", "TMS"), ("dms", "DMS"), ("cms", "CMS")]
    THROTTLE_HAT_BTN_GROUPS = []   # throttle hat is ABS-only

    # ------------------------------------------------------------------
    # 8. Render loop
    # ------------------------------------------------------------------
    running = True
    stats_timer = time.monotonic()

    while running:
        # ---- Events ------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # ---- Stats -------------------------------------------------------
        shared.tick_stats()
        state = shared.snapshot()

        # ---- Clear -------------------------------------------------------
        screen.fill(COLOR_BG)

        # ---- Header ------------------------------------------------------
        title_lbl = font_large.render(WINDOW_TITLE, True, COLOR_TEXT)
        screen.blit(title_lbl, (SECTION_GAP, 10))

        draw_connection_badge(screen, font_medium,
                              SECTION_GAP, 34,
                              "Stick", state["stick_connected"])
        draw_connection_badge(screen, font_medium,
                              WINDOW_WIDTH // 2 + SECTION_GAP, 34,
                              "Throttle", state["throttle_connected"])

        # ---- Stick axes --------------------------------------------------
        render_axes_panel(
            screen, font_medium, font_small,
            stick_axes_rect, "STICK — AXES",
            state["stick_axes"], STICK_AXIS_MAP, stick_axis_lookup,
            COLOR_BLUE,
        )

        # ---- Stick hats (ABS hat + TMS/DMS/CMS button-hats) -------------
        render_hats_panel(
            screen, font_medium, font_small,
            stick_hats_rect, "STICK — HATS",
            state["stick_hats"], STICK_HAT_MAP,
            state["stick_buttons"], STICK_HAT_BTN_GROUPS, STICK_BUTTON_MAP,
        )

        # ---- Stick buttons -----------------------------------------------
        render_buttons_panel(
            screen, font_medium, font_small,
            stick_btns_rect, "STICK — BUTTONS",
            state["stick_buttons"], STICK_BUTTON_MAP, STICK_BUTTON_GROUPS,
        )

        # ---- Throttle axes -----------------------------------------------
        render_axes_panel(
            screen, font_medium, font_small,
            thr_axes_rect, "THROTTLE — AXES",
            state["throttle_axes"], THROTTLE_AXIS_MAP, throttle_axis_lookup,
            COLOR_BLUE_TROT,
        )

        # ---- Throttle hats -----------------------------------------------
        render_hats_panel(
            screen, font_medium, font_small,
            thr_hats_rect, "THROTTLE — HATS",
            state["throttle_hats"], THROTTLE_HAT_MAP,
        )

        # ---- Throttle buttons --------------------------------------------
        render_buttons_panel(
            screen, font_medium, font_small,
            thr_btns_rect, "THROTTLE — BUTTONS",
            state["throttle_buttons"], THROTTLE_BUTTON_MAP, THROTTLE_BUTTON_GROUPS,
        )

        # ---- Footer ------------------------------------------------------
        fps     = clock.get_fps()
        ev_lbl  = (f"  FPS: {fps:>5.1f}"
                   f"  |  Stick ev/s: {state['stick_events_sec']:>4}"
                   f"  |  Throttle ev/s: {state['throttle_events_sec']:>4}"
                   f"  |  ESC to quit")
        foot = font_small.render(ev_lbl, True, COLOR_TEXT_DIM)
        screen.blit(foot, (SECTION_GAP, WINDOW_HEIGHT - H_FOOTER + 6))

        # ---- Flip --------------------------------------------------------
        pygame.display.flip()
        clock.tick(TARGET_FPS)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
