#!/usr/bin/env python3
"""
hotas_dashboard.py  v3 — Professional real-time HOTAS test dashboard
Thrustmaster HOTAS Warthog (USAF A-10C replica) — Linux

Tabs (press TAB or click):
  LIVE  — Axes with 2-D stick plot, D-pad hat indicators, button LEDs
  MAP   — Full button reference table with live press highlighting

Keys:
  TAB / M   switch tabs          F   toggle fullscreen
  ESC       quit
"""

import sys
import os
import json
import time
import threading

# ── dependency checks ─────────────────────────────────────────────────────────
try:
    import evdev
    from evdev import ecodes
except ImportError:
    print("\n[ERROR] evdev not installed.  Run: pip install evdev\n")
    sys.exit(1)

try:
    import pygame
    import pygame.gfxdraw
except ImportError:
    print("\n[ERROR] pygame not installed.  Run: pip install pygame\n")
    sys.exit(1)

from warthog_mappings import (
    STICK_BUTTON_MAP, STICK_AXIS_MAP, STICK_HAT_MAP,
    STICK_BUTTON_GROUPS,
    THROTTLE_BUTTON_MAP, THROTTLE_AXIS_MAP, THROTTLE_HAT_MAP,
    THROTTLE_BUTTON_GROUPS,
    STICK_NAME_PATTERNS, THROTTLE_NAME_PATTERNS,
)
from config.constants import (
    VENDOR_THRUSTMASTER, PID_WARTHOG_STICK, PID_WARTHOG_THROTTLE,
    TARGET_FPS, RECONNECT_INTERVAL,
)

# ── paths ─────────────────────────────────────────────────────────────────────
_BASE         = os.path.dirname(os.path.abspath(__file__))
STICK_JSON    = os.path.join(_BASE, "output", "warthog_stick_map.json")
THROTTLE_JSON = os.path.join(_BASE, "output", "warthog_throttle_map.json")

# ── window / layout ───────────────────────────────────────────────────────────
W, H      = 1600, 950
TAB_H     = 58
FOOT_H    = 32
COL_W     = W // 2
PAD       = 10

DEV_HDR_H = 40
AXES_H    = 152
HATS_H    = 152

CONTENT_TOP   = TAB_H + DEV_HDR_H + 4
AXES_BOTTOM   = CONTENT_TOP + AXES_H + 3
HATS_BOTTOM   = AXES_BOTTOM + HATS_H + 3
BTNS_BOTTOM   = H - FOOT_H - 2
BTNS_H        = BTNS_BOTTOM - HATS_BOTTOM

TAB_LIVE, TAB_MAP = 0, 1

# ── color palette — military cockpit instrument ──────────────────────────────
C_BG        = (  8,  11,  18)
C_BG2       = ( 12,  16,  24)
C_PANEL     = ( 16,  20,  30)
C_PANEL_HDR = ( 20,  26,  38)
C_BORDER    = ( 34,  42,  56)
C_BORDER_L  = ( 48,  56,  72)
C_TEXT      = (200, 210, 228)
C_DIM       = ( 78,  90, 110)
C_DIM2      = ( 56,  65,  82)
C_AMBER     = (228, 168,  24)
C_AMBER_M   = (180, 132,  18)
C_AMBER_D   = ( 60,  44,   8)
C_AMBER_VD  = ( 32,  26,  10)
C_GREEN     = ( 42, 210,  92)
C_GREEN2    = ( 28, 136,  58)
C_GREEN3    = ( 14,  64,  28)
C_GREEN_VD  = (  8,  36,  16)
C_RED       = (200,  48,  48)
C_RED_D     = ( 72,  20,  20)
C_BLUE      = ( 56, 138, 248)
C_BLUE_D    = ( 18,  44,  88)
C_TEAL      = ( 42, 188, 152)
C_TEAL_D    = ( 14,  66,  52)
C_DPAD_ON   = ( 42, 210,  92)
C_DPAD_OFF  = ( 28,  34,  48)
C_BTN_OFF   = ( 30,  36,  50)
C_BTN_RING  = ( 40,  48,  64)
C_WHITE     = (236, 242, 252)
C_ROW_ODD   = ( 16,  20,  30)
C_ROW_EVEN  = ( 20,  25,  36)
C_ROW_HIT   = ( 14,  52,  28)
C_TAB_BG    = ( 22,  28,  40)
C_HDR_BG    = ( 12,  16,  24)
C_HDR_LINE  = ( 48,  38,  10)


# ═════════════════════════════════════════════════════════════════════════════
# SharedState — thread-safe input state
# ═════════════════════════════════════════════════════════════════════════════
class SharedState:
    def __init__(self):
        self._lock           = threading.Lock()
        self.stick_axes      = {}
        self.throttle_axes   = {}
        self.stick_buttons   = {}
        self.throttle_buttons = {}
        self.stick_hats      = {}
        self.throttle_hats   = {}
        self.stick_ok        = False
        self.throttle_ok     = False
        self._s_ev = self._t_ev = 0
        self.s_eps = self.t_eps = 0
        self._stat_t = time.monotonic()

    def update_axis(self, dev, code, val):
        with self._lock:
            (self.stick_axes if dev == "stick" else self.throttle_axes)[code] = val

    def update_button(self, dev, code, pressed):
        with self._lock:
            if dev == "stick":
                self.stick_buttons[code] = pressed
                self._s_ev += 1
            else:
                self.throttle_buttons[code] = pressed
                self._t_ev += 1

    def update_hat_axis(self, dev, code, raw, hat_map):
        """Update hat state immediately per-axis (no pending/batching)."""
        with self._lock:
            hats = self.stick_hats if dev == "stick" else self.throttle_hats
            for key, hd in hat_map.items():
                if code == hd["code_x"]:
                    prev = hats.get(key, (0, 0))
                    hats[key] = (raw, prev[1])
                elif code == hd["code_y"]:
                    prev = hats.get(key, (0, 0))
                    hats[key] = (prev[0], raw)

    def set_ok(self, dev, val):
        with self._lock:
            if dev == "stick": self.stick_ok = val
            else:              self.throttle_ok = val

    def tick(self):
        now = time.monotonic(); dt = now - self._stat_t
        if dt >= 1.0:
            with self._lock:
                self.s_eps = int(self._s_ev / dt)
                self.t_eps = int(self._t_ev / dt)
                self._s_ev = self._t_ev = 0
            self._stat_t = now

    def snapshot(self):
        with self._lock:
            return dict(
                stick_axes=dict(self.stick_axes),
                throttle_axes=dict(self.throttle_axes),
                stick_buttons=dict(self.stick_buttons),
                throttle_buttons=dict(self.throttle_buttons),
                stick_hats=dict(self.stick_hats),
                throttle_hats=dict(self.throttle_hats),
                stick_ok=self.stick_ok,
                throttle_ok=self.throttle_ok,
                s_eps=self.s_eps,
                t_eps=self.t_eps,
            )


# ═════════════════════════════════════════════════════════════════════════════
# Axis normalisation
# ═════════════════════════════════════════════════════════════════════════════
def normalise(raw, mn, mx, bipolar):
    if mx == mn: return 0.0
    r = (raw - mn) / (mx - mn)
    return r * 2.0 - 1.0 if bipolar else r


# ═════════════════════════════════════════════════════════════════════════════
# Mapping / device helpers
# ═════════════════════════════════════════════════════════════════════════════
def _load_json(path):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return None

def build_axis_lookup(js, axis_map):
    lu = {}
    if js:
        for ax in js.get("axes", []):
            c = ax["code"]
            lu[c] = {"min": ax["min"], "max": ax["max"],
                     "bipolar": axis_map.get(c, {}).get("bipolar", True)}
    for c, info in axis_map.items():
        lu.setdefault(c, {"min": 0, "max": 65535, "bipolar": info["bipolar"]})
    return lu

def _name_ok(name, pats):
    n = (name or "").lower()
    return any(p.lower() in n for p in pats)

def auto_detect():
    sp = tp = None
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path); i = d.info
            if i.vendor == VENDOR_THRUSTMASTER:
                if i.product == PID_WARTHOG_STICK:    sp = path
                elif i.product == PID_WARTHOG_THROTTLE: tp = path
            elif _name_ok(d.name, STICK_NAME_PATTERNS):    sp = sp or path
            elif _name_ok(d.name, THROTTLE_NAME_PATTERNS): tp = tp or path
            d.close()
        except Exception: pass
    return sp, tp

def resolve_path(js, fallback):
    if js:
        c = js.get("device_path")
        if c and os.path.exists(c): return c
    return fallback


# ═════════════════════════════════════════════════════════════════════════════
# Input reader thread
# ═════════════════════════════════════════════════════════════════════════════
def input_reader(path, dev, axis_lu, hat_map, shared):
    while True:
        try:
            d = evdev.InputDevice(path); shared.set_ok(dev, True)
            for ev in d.read_loop():
                if ev.type == ecodes.EV_ABS:
                    is_hat = any(ev.code in (hd["code_x"], hd["code_y"])
                                 for hd in hat_map.values())
                    if is_hat:
                        shared.update_hat_axis(dev, ev.code, ev.value, hat_map)
                    else:
                        ax = axis_lu.get(ev.code)
                        if ax:
                            shared.update_axis(dev, ev.code,
                                normalise(ev.value, ax["min"], ax["max"], ax["bipolar"]))
                elif ev.type == ecodes.EV_KEY:
                    shared.update_button(dev, ev.code, bool(ev.value))
        except PermissionError:
            print(f"[{dev.upper()}] Permission denied — sudo usermod -aG input $USER")
            shared.set_ok(dev, False); time.sleep(RECONNECT_INTERVAL)
        except OSError:
            shared.set_ok(dev, False); time.sleep(RECONNECT_INTERVAL)


# ═════════════════════════════════════════════════════════════════════════════
# Drawing primitives
# ═════════════════════════════════════════════════════════════════════════════

def filled_rect(surf, color, rect, r=4):
    pygame.draw.rect(surf, color, rect, border_radius=r)

def outlined_rect(surf, fill, border, rect, r=4, bw=1):
    pygame.draw.rect(surf, fill,   rect, border_radius=r)
    pygame.draw.rect(surf, border, rect, width=bw, border_radius=r)

def h_separator(surf, y, x0=0, x1=W):
    pygame.draw.line(surf, C_BORDER, (x0, y), (x1, y), 1)

def v_separator(surf, x, y0=TAB_H, y1=None):
    if y1 is None: y1 = H - FOOT_H
    pygame.draw.line(surf, C_BORDER, (x, y0), (x, y1), 1)
    pygame.draw.line(surf, (24, 30, 42), (x + 1, y0), (x + 1, y1), 1)


def draw_panel(surf, rect, title, fonts, accent=C_AMBER):
    """Panel with dark fill, border, and a colored header strip."""
    # Main panel body
    outlined_rect(surf, C_PANEL, C_BORDER, rect, r=5, bw=1)
    # Header strip
    hdr = pygame.Rect(rect.x + 1, rect.y + 1, rect.width - 2, 24)
    filled_rect(surf, C_PANEL_HDR, hdr, r=4)
    # Accent line under header
    pygame.draw.line(surf, accent,
                     (rect.x + 6, rect.y + 25),
                     (rect.right - 6, rect.y + 25), 1)
    # Title text
    f = fonts["panel"]
    lbl = f.render(title, True, accent)
    surf.blit(lbl, (rect.x + PAD, rect.y + 5))


def draw_axis_bar(surf, fonts, x, y, avail_w, label, value, bipolar, lc, dc):
    f_lbl  = fonts["small"]
    f_val  = fonts["mono"]
    LBL_W  = 112
    VAL_W  = 64
    BAR_H  = 20
    BAR_W  = avail_w - LBL_W - VAL_W - 12

    bar_x  = x + LBL_W + 4
    bar_y  = y
    val_x  = bar_x + BAR_W + 8

    # Label
    lbl = f_lbl.render(label, True, C_DIM)
    surf.blit(lbl, (x, y + (BAR_H - lbl.get_height()) // 2))

    # Track background with inset effect
    track = pygame.Rect(bar_x, bar_y, BAR_W, BAR_H)
    filled_rect(surf, (10, 14, 22), track, r=3)
    pygame.draw.rect(surf, (22, 28, 40), track, width=1, border_radius=3)

    # Fill
    clamped = max(-1.0, min(1.0, value))
    if bipolar:
        mid = bar_x + BAR_W // 2
        fill_px = int(abs(clamped) * (BAR_W // 2))
        fill_x = mid if clamped >= 0 else mid - fill_px
        if fill_px > 1:
            # Dark fill
            filled_rect(surf, dc,
                pygame.Rect(fill_x, bar_y + 2, fill_px, BAR_H - 4), r=2)
            # Bright core
            core_h = max(1, BAR_H // 3)
            core_y = bar_y + (BAR_H - core_h) // 2
            filled_rect(surf, lc,
                pygame.Rect(fill_x, core_y, fill_px, core_h), r=1)
        # Center tick
        pygame.draw.line(surf, C_DIM2, (mid, bar_y + 3), (mid, bar_y + BAR_H - 3), 1)
        pygame.draw.line(surf, C_TEXT, (mid, bar_y + 5), (mid, bar_y + BAR_H - 5), 1)
    else:
        fill_px = int(clamped * BAR_W)
        if fill_px > 1:
            filled_rect(surf, dc,
                pygame.Rect(bar_x, bar_y + 2, fill_px, BAR_H - 4), r=2)
            core_h = max(1, BAR_H // 3)
            core_y = bar_y + (BAR_H - core_h) // 2
            filled_rect(surf, lc,
                pygame.Rect(bar_x, core_y, fill_px, core_h), r=1)

    # Position indicator
    if bipolar:
        dot_x = bar_x + BAR_W // 2 + int(clamped * (BAR_W // 2))
    else:
        dot_x = bar_x + int(clamped * BAR_W)
    dot_x = max(bar_x + 5, min(bar_x + BAR_W - 5, dot_x))
    dot_y = bar_y + BAR_H // 2

    pygame.draw.circle(surf, dc,       (dot_x, dot_y), 7)
    pygame.draw.circle(surf, lc,       (dot_x, dot_y), 5)
    pygame.draw.circle(surf, C_WHITE,  (dot_x, dot_y), 2)

    # Value text
    fmt = f"{value:+.2f}" if bipolar else f"{value:.2f}"
    v_lbl = f_val.render(fmt, True, C_TEXT)
    surf.blit(v_lbl, (val_x, y + (BAR_H - v_lbl.get_height()) // 2))


def draw_stick_2d(surf, x, y, size, sx, sy):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 6

    # Background
    bg_rect = pygame.Rect(x, y, size, size)
    filled_rect(surf, (8, 12, 20), bg_rect, r=5)
    pygame.draw.rect(surf, C_BORDER, bg_rect, width=1, border_radius=5)

    # Grid — subtle cross
    for i in range(1, 4):
        frac = i / 4
        alpha_clr = (22, 28, 38)
        # Horizontal
        gy = y + int(size * frac)
        pygame.draw.line(surf, alpha_clr, (x + 4, gy), (x + size - 4, gy), 1)
        # Vertical
        gx = x + int(size * frac)
        pygame.draw.line(surf, alpha_clr, (gx, y + 4), (gx, y + size - 4), 1)

    # Center cross (brighter)
    pygame.draw.line(surf, C_DIM2, (x + 4, cy), (x + size - 4, cy), 1)
    pygame.draw.line(surf, C_DIM2, (cx, y + 4), (cx, y + size - 4), 1)

    # Range circle
    pygame.draw.circle(surf, (20, 26, 36), (cx, cy), r, 1)

    # Dot position
    dx = cx + int(sx * r)
    dy = cy + int(sy * r)
    dx = max(x + 6, min(x + size - 6, dx))
    dy = max(y + 6, min(y + size - 6, dy))

    # Crosshair lines to dot
    pygame.draw.line(surf, (20, 56, 28), (dx, y + 4), (dx, dy - 12), 1)
    pygame.draw.line(surf, (20, 56, 28), (dx, dy + 12), (dx, y + size - 4), 1)
    pygame.draw.line(surf, (20, 56, 28), (x + 4, dy), (dx - 12, dy), 1)
    pygame.draw.line(surf, (20, 56, 28), (dx + 12, dy), (x + size - 4, dy), 1)

    # Glow rings
    pygame.draw.circle(surf, C_GREEN_VD, (dx, dy), 12)
    pygame.draw.circle(surf, C_GREEN3,   (dx, dy),  9)
    pygame.draw.circle(surf, C_GREEN2,   (dx, dy),  6)
    pygame.draw.circle(surf, C_GREEN,    (dx, dy),  4)
    pygame.draw.circle(surf, C_WHITE,    (dx, dy),  2)


def draw_dpad(surf, fonts, x, y, label, hx, hy,
              push_btn_code=None, buttons_state=None):
    SIZE  = 72
    ARM_W = SIZE // 4
    ARM_H = SIZE // 3 + 2
    cx, cy = x + SIZE // 2, y + SIZE // 2

    # Label above
    f = fonts["tiny"]
    lbl = f.render(label, True, C_AMBER_M)
    surf.blit(lbl, (x + SIZE // 2 - lbl.get_width() // 2, y - 15))

    # Background
    bg = pygame.Rect(x, y, SIZE, SIZE)
    filled_rect(surf, (10, 14, 22), bg, r=4)
    pygame.draw.rect(surf, C_BORDER, bg, width=1, border_radius=4)

    # D-pad arms
    arms = {
        "U": pygame.Rect(cx - ARM_W // 2, y + 4,           ARM_W, ARM_H),
        "D": pygame.Rect(cx - ARM_W // 2, cy + ARM_W // 2, ARM_W, ARM_H),
        "L": pygame.Rect(x + 4,           cy - ARM_W // 2, ARM_H, ARM_W),
        "R": pygame.Rect(cx + ARM_W // 2, cy - ARM_W // 2, ARM_H, ARM_W),
    }

    # Determine active directions (support diagonals)
    active_dirs = set()
    if hy == -1: active_dirs.add("U")
    if hy ==  1: active_dirs.add("D")
    if hx == -1: active_dirs.add("L")
    if hx ==  1: active_dirs.add("R")

    for d, rect in arms.items():
        if d in active_dirs:
            # Glow background
            glow = rect.inflate(4, 4)
            filled_rect(surf, C_GREEN_VD, glow, r=3)
            filled_rect(surf, C_DPAD_ON, rect, r=2)
            pygame.draw.rect(surf, C_GREEN, rect, width=1, border_radius=2)
        else:
            filled_rect(surf, C_DPAD_OFF, rect, r=2)
            pygame.draw.rect(surf, (36, 44, 58), rect, width=1, border_radius=2)

    # Centre push indicator
    push_active = (push_btn_code is not None and
                   buttons_state is not None and
                   buttons_state.get(push_btn_code, False))
    ctr_rect = pygame.Rect(cx - ARM_W // 2, cy - ARM_W // 2, ARM_W, ARM_W)
    if push_active:
        filled_rect(surf, C_AMBER, ctr_rect, r=2)
    else:
        filled_rect(surf, (22, 28, 40), ctr_rect, r=2)
    pygame.draw.rect(surf, C_BORDER, ctr_rect, width=1, border_radius=2)


def draw_button_led(surf, fonts, x, y, name, pressed):
    R = 9
    if pressed:
        # Multi-ring glow
        pygame.draw.circle(surf, C_GREEN_VD, (x, y), R + 6)
        pygame.draw.circle(surf, C_GREEN3,   (x, y), R + 3)
        pygame.draw.circle(surf, C_GREEN2,   (x, y), R + 1)
        pygame.draw.circle(surf, C_GREEN,    (x, y), R)
        pygame.draw.circle(surf, C_WHITE,    (x, y), 3)
    else:
        pygame.draw.circle(surf, C_BTN_OFF,  (x, y), R)
        pygame.draw.circle(surf, C_BTN_RING, (x, y), R, 1)

    f   = fonts["small"]
    lbl = f.render(name, True, C_GREEN if pressed else C_DIM)
    surf.blit(lbl, (x + R + 6, y - lbl.get_height() // 2))


def draw_status_pill(surf, fonts, x, y, label, ok):
    f = fonts["panel"]
    color = C_GREEN if ok else C_RED
    bg_color = C_GREEN_VD if ok else C_RED_D
    status_text = "ONLINE" if ok else "OFFLINE"

    # Status dot with glow
    pygame.draw.circle(surf, bg_color, (x + 7, y + 8), 7)
    pygame.draw.circle(surf, color,    (x + 7, y + 8), 4)
    if ok:
        pygame.draw.circle(surf, C_WHITE, (x + 7, y + 8), 2)

    # Device label
    dev_lbl = f.render(label, True, C_TEXT)
    surf.blit(dev_lbl, (x + 20, y + 8 - dev_lbl.get_height() // 2))

    # Status badge
    badge_x = x + 24 + dev_lbl.get_width() + 8
    sf = fonts["tiny_bold"]
    st = sf.render(status_text, True, color)
    badge_w = st.get_width() + 12
    badge_r = pygame.Rect(badge_x, y + 1, badge_w, 16)
    filled_rect(surf, bg_color, badge_r, r=3)
    pygame.draw.rect(surf, color, badge_r, width=1, border_radius=3)
    surf.blit(st, (badge_x + 6, y + 1 + (16 - st.get_height()) // 2))


# ═════════════════════════════════════════════════════════════════════════════
# LIVE tab — section renderers
# ═════════════════════════════════════════════════════════════════════════════

def render_axes(surf, fonts, rect, axes_state, axis_map, axis_lu,
                lc, dc, show_2d=False, sx=0.0, sy=0.0):
    draw_panel(surf, rect, "AXES", fonts)
    y0 = rect.y + 30
    PLOT_SIZE = 108

    if show_2d:
        draw_stick_2d(surf, rect.x + PAD, y0 + 6, PLOT_SIZE, sx, sy)
        bar_x   = rect.x + PAD + PLOT_SIZE + 14
        avail_w = rect.right - bar_x - PAD
    else:
        bar_x   = rect.x + PAD
        avail_w = rect.width - PAD * 2

    row_h = 28
    by    = y0 + 14
    for code, info in axis_map.items():
        if by + row_h > rect.bottom - 6: break
        val = axes_state.get(code, 0.0)
        draw_axis_bar(surf, fonts, bar_x, by, avail_w,
                      info["name"], val, info["bipolar"], lc, dc)
        by += row_h


def render_hats(surf, fonts, rect, title,
                hats_state, hat_map,
                buttons_state=None, hat_btn_groups=None, button_map=None):
    draw_panel(surf, rect, title, fonts)

    DPAD_SZ    = 72
    DPAD_TOTAL = DPAD_SZ + 24
    gap        = 16
    x0         = rect.x + PAD + 4
    y0         = rect.y + 28

    # ABS-reported hats
    for key, hd in hat_map.items():
        hx, hy = hats_state.get(key, (0, 0))
        draw_dpad(surf, fonts, x0, y0 + 16, hd["name"][:10], hx, hy)
        x0 += DPAD_TOTAL + gap

    # Button-reported 4-way hats (TMS / DMS / CMS)
    if hat_btn_groups and button_map and buttons_state is not None:
        for grp_key, grp_label in hat_btn_groups:
            grp = [(c, i) for c, i in button_map.items() if i["group"] == grp_key]
            if not grp: continue
            hx = hy = 0
            for code, info in grp:
                if buttons_state.get(code, False):
                    nm = info["name"]
                    if   nm.endswith("U"): hy = -1
                    elif nm.endswith("D"): hy =  1
                    elif nm.endswith("L"): hx = -1
                    elif nm.endswith("R"): hx =  1
            push_code = next((c for c, i in grp if i["name"] == "H4P"), None)
            if x0 + DPAD_TOTAL > rect.right: break
            draw_dpad(surf, fonts, x0, y0 + 16, grp_label, hx, hy,
                      push_btn_code=push_code, buttons_state=buttons_state)
            x0 += DPAD_TOTAL + gap


def render_buttons(surf, fonts, rect, title,
                   buttons_state, button_map, button_groups,
                   n_cols=4):
    draw_panel(surf, rect, title, fonts)

    col_w  = (rect.width - PAD * 2) // n_cols
    GRP_H  = 20
    BTN_H  = 24

    x0 = rect.x + PAD
    y0 = rect.y + 30
    cy = y0

    f_grp = fonts["tiny_bold"]

    for grp_key, grp_label in button_groups:
        grp_btns = sorted(
            [(c, i) for c, i in button_map.items() if i["group"] == grp_key],
            key=lambda b: b[1]["dx"])
        if not grp_btns: continue

        if cy + GRP_H > rect.bottom - 6: break

        # Group header — just text, no extra decoration
        lbl = f_grp.render(grp_label.upper(), True, C_AMBER_M)
        surf.blit(lbl, (x0, cy))
        # Subtle line
        line_x = x0 + lbl.get_width() + 6
        pygame.draw.line(surf, C_BORDER, (line_x, cy + lbl.get_height() // 2),
                         (rect.right - PAD, cy + lbl.get_height() // 2), 1)
        cy += GRP_H

        col = 0
        for code, info in grp_btns:
            if cy + BTN_H > rect.bottom - 6: break
            bx = x0 + col * col_w + 12
            by = cy + BTN_H // 2
            if bx + col_w > rect.right: break
            pressed = buttons_state.get(code, False)
            draw_button_led(surf, fonts, bx, by, info["name"], pressed)
            col += 1
            if col >= n_cols:
                col = 0
                cy += BTN_H
        if col > 0:
            cy += BTN_H
        cy += 4


def render_live_tab(surf, fonts, state, s_lu, t_lu):
    # ── left column — stick ────────────────────────────────────────────────
    hdr_r = pygame.Rect(4, TAB_H + 2, COL_W - 8, DEV_HDR_H)
    outlined_rect(surf, C_PANEL, C_BORDER, hdr_r, r=4)
    draw_status_pill(surf, fonts, hdr_r.x + PAD, hdr_r.y + 8,
                     "JOYSTICK", state["stick_ok"])

    ax_r = pygame.Rect(4, CONTENT_TOP,  COL_W - 8, AXES_H)
    ht_r = pygame.Rect(4, AXES_BOTTOM,  COL_W - 8, HATS_H)
    bt_r = pygame.Rect(4, HATS_BOTTOM,  COL_W - 8, BTNS_H)

    sx = state["stick_axes"].get(0, 0.0)
    sy = state["stick_axes"].get(1, 0.0)

    render_axes(surf, fonts, ax_r,
                state["stick_axes"], STICK_AXIS_MAP, s_lu,
                C_BLUE, C_BLUE_D,
                show_2d=True, sx=sx, sy=sy)

    render_hats(surf, fonts, ht_r, "HATS",
                state["stick_hats"], STICK_HAT_MAP,
                state["stick_buttons"],
                [("tms","TMS"), ("dms","DMS"), ("cms","CMS")],
                STICK_BUTTON_MAP)

    render_buttons(surf, fonts, bt_r, "BUTTONS",
                   state["stick_buttons"],
                   STICK_BUTTON_MAP, STICK_BUTTON_GROUPS, n_cols=4)

    # ── right column — throttle ────────────────────────────────────────────
    RX = COL_W + 4
    hdr_r2 = pygame.Rect(RX, TAB_H + 2, COL_W - 8, DEV_HDR_H)
    outlined_rect(surf, C_PANEL, C_BORDER, hdr_r2, r=4)
    draw_status_pill(surf, fonts, hdr_r2.x + PAD, hdr_r2.y + 8,
                     "THROTTLE", state["throttle_ok"])

    ax_r2 = pygame.Rect(RX, CONTENT_TOP, COL_W - 8, AXES_H)
    ht_r2 = pygame.Rect(RX, AXES_BOTTOM, COL_W - 8, HATS_H)
    bt_r2 = pygame.Rect(RX, HATS_BOTTOM, COL_W - 8, BTNS_H)

    render_axes(surf, fonts, ax_r2,
                state["throttle_axes"], THROTTLE_AXIS_MAP, t_lu,
                C_TEAL, C_TEAL_D,
                show_2d=False)

    render_hats(surf, fonts, ht_r2, "COOLIE SWITCH",
                state["throttle_hats"], THROTTLE_HAT_MAP)

    render_buttons(surf, fonts, bt_r2, "BUTTONS",
                   state["throttle_buttons"],
                   THROTTLE_BUTTON_MAP, THROTTLE_BUTTON_GROUPS, n_cols=5)

    # ── column divider ─────────────────────────────────────────────────────
    v_separator(surf, COL_W)


# ═════════════════════════════════════════════════════════════════════════════
# MAP tab — button reference table
# ═════════════════════════════════════════════════════════════════════════════

def render_table(surf, fonts, rect, title, button_map, buttons_state,
                 scroll_y=0):
    draw_panel(surf, rect, title, fonts)

    C1    = 32
    C2    = 52
    C3    = 68
    CREST = rect.width - C1 - C2 - C3 - PAD * 2 - 74
    C4    = CREST
    C5    = 74

    HDR_H  = 24
    ROW_H  = 22
    CLIP_Y = rect.y + 28
    CLIP_H = rect.height - 28

    f_hdr  = fonts["tiny_bold"]
    f_row  = fonts["tiny"]
    f_val  = fonts["mono"]

    # Column headers
    hx = rect.x + PAD
    hy = CLIP_Y
    cols = [
        (C1,  "DX"),
        (C2,  "CODE"),
        (C3,  "NAME"),
        (C4,  "DESCRIPTION"),
        (C5,  "STATE"),
    ]
    header_rect = pygame.Rect(rect.x + 1, hy, rect.width - 2, HDR_H)
    filled_rect(surf, C_PANEL_HDR, header_rect, r=0)
    pygame.draw.line(surf, C_BORDER,
                     (rect.x + 4, hy + HDR_H - 1),
                     (rect.right - 4, hy + HDR_H - 1), 1)

    hx2 = hx
    for cw, ch in cols:
        lbl = f_hdr.render(ch, True, C_AMBER_M)
        surf.blit(lbl, (hx2, hy + (HDR_H - lbl.get_height()) // 2))
        hx2 += cw

    # Clip region for rows
    clip = pygame.Rect(rect.x, CLIP_Y + HDR_H, rect.width, CLIP_H - HDR_H)
    surf.set_clip(clip)

    sorted_btns = sorted(button_map.items(), key=lambda kv: kv[1]["dx"])
    ry = CLIP_Y + HDR_H - scroll_y

    for idx, (code, info) in enumerate(sorted_btns):
        if ry + ROW_H < clip.top:
            ry += ROW_H; continue
        if ry >= clip.bottom: break

        pressed  = buttons_state.get(code, False)
        row_bg   = C_ROW_HIT if pressed else (C_ROW_ODD if idx % 2 else C_ROW_EVEN)
        pygame.draw.rect(surf, row_bg, pygame.Rect(rect.x, ry, rect.width, ROW_H))

        if pressed:
            # Left accent bar for pressed rows
            pygame.draw.rect(surf, C_GREEN,
                             pygame.Rect(rect.x + 1, ry, 3, ROW_H))

        fx = rect.x + PAD
        txt_color = C_GREEN if pressed else C_TEXT

        cells = [
            (C1, f_row, f"{info['dx']:>2}",     C_DIM),
            (C2, f_val, f"0x{code:03X}",        C_DIM),
            (C3, f_row, info["name"],            C_GREEN if pressed else C_AMBER),
            (C4, f_row, info["desc"],            txt_color),
            (C5, f_row, "PRESSED" if pressed else "",
                        C_GREEN if pressed else C_DIM),
        ]
        for cw, cf, ct, cc in cells:
            if not ct: fx += cw; continue
            t = cf.render(ct, True, cc)
            if t.get_width() > cw - 4:
                while ct and cf.render(ct + "...", True, cc).get_width() > cw - 4:
                    ct = ct[:-1]
                t = cf.render(ct + "...", True, cc)
            surf.blit(t, (fx, ry + (ROW_H - t.get_height()) // 2))
            fx += cw

        ry += ROW_H

    surf.set_clip(None)

    # Scrollbar
    all_rows  = len(button_map)
    total_h   = all_rows * ROW_H
    visible_h = CLIP_H - HDR_H
    if total_h > visible_h:
        bar_h = max(24, int(visible_h * visible_h / total_h))
        bar_y = CLIP_Y + HDR_H + int(scroll_y / (total_h - visible_h) *
                                      (visible_h - bar_h))
        track_r = pygame.Rect(rect.right - 6, CLIP_Y + HDR_H, 4, visible_h)
        filled_rect(surf, (16, 20, 30), track_r, r=2)
        bar_r = pygame.Rect(rect.right - 6, bar_y, 4, bar_h)
        filled_rect(surf, C_DIM2, bar_r, r=2)


def render_map_tab(surf, fonts, state, scroll_s, scroll_t):
    half = W // 2 - 4
    left_r  = pygame.Rect(4,       TAB_H + 2, half, H - FOOT_H - TAB_H - 4)
    right_r = pygame.Rect(half+8,  TAB_H + 2, half, H - FOOT_H - TAB_H - 4)

    render_table(surf, fonts, left_r,
                 "JOYSTICK  --  Button Reference",
                 STICK_BUTTON_MAP, state["stick_buttons"], scroll_s)

    render_table(surf, fonts, right_r,
                 "THROTTLE  --  Button Reference",
                 THROTTLE_BUTTON_MAP, state["throttle_buttons"], scroll_t)

    v_separator(surf, W // 2)


# ═════════════════════════════════════════════════════════════════════════════
# Header / Footer
# ═════════════════════════════════════════════════════════════════════════════

def render_header(surf, fonts, current_tab, fps, state):
    # Background
    pygame.draw.rect(surf, C_HDR_BG, pygame.Rect(0, 0, W, TAB_H))
    # Bottom border — amber accent line
    pygame.draw.line(surf, C_AMBER_D, (0, TAB_H - 2), (W, TAB_H - 2), 1)
    pygame.draw.line(surf, C_BORDER,  (0, TAB_H - 1), (W, TAB_H - 1), 1)

    # Title block
    f_title = fonts["title"]
    f_sub   = fonts["small"]

    t1 = f_title.render("HOTAS WARTHOG", True, C_AMBER)
    t2 = f_title.render("  A-10C", True, C_DIM)
    surf.blit(t1, (PAD * 2, 8))
    surf.blit(t2, (PAD * 2 + t1.get_width(), 8))

    # Subtitle
    sub = f_sub.render("Thrustmaster Input Test Utility", True, C_DIM2)
    surf.blit(sub, (PAD * 2, 30))

    # Tab buttons
    tabs = [(TAB_LIVE, "LIVE INPUT"), (TAB_MAP, "BUTTON MAP")]
    tx = W - 340
    tab_rects = []
    for tab_id, tab_lbl in tabs:
        active = tab_id == current_tab
        r = pygame.Rect(tx, 8, 148, 32)

        if active:
            filled_rect(surf, C_AMBER_VD, r, r=4)
            pygame.draw.rect(surf, C_AMBER, r, width=1, border_radius=4)
            # Active underline
            pygame.draw.line(surf, C_AMBER,
                             (r.x + 4, r.bottom + 2),
                             (r.right - 4, r.bottom + 2), 2)
        else:
            filled_rect(surf, C_TAB_BG, r, r=4)
            pygame.draw.rect(surf, C_BORDER, r, width=1, border_radius=4)

        f = fonts["panel"]
        txt_c = C_AMBER if active else C_DIM
        lbl = f.render(tab_lbl, True, txt_c)
        surf.blit(lbl, (r.centerx - lbl.get_width() // 2,
                        r.centery - lbl.get_height() // 2))
        tab_rects.append((r, tab_id))
        tx += 156

    # Status line
    f_s = fonts["tiny"]
    info = (f"FPS {fps:4.0f}"
            f"   Stick ev/s {state['s_eps']:3d}"
            f"   Throttle ev/s {state['t_eps']:3d}"
            f"   ESC quit  |  TAB switch")
    lbl = f_s.render(info, True, (44, 52, 68))
    surf.blit(lbl, (PAD * 2, TAB_H - lbl.get_height() - 5))

    return tab_rects


def render_footer(surf, fonts):
    foot_rect = pygame.Rect(0, H - FOOT_H, W, FOOT_H)
    pygame.draw.rect(surf, C_HDR_BG, foot_rect)
    pygame.draw.line(surf, C_BORDER, (0, H - FOOT_H), (W, H - FOOT_H), 1)

    f = fonts["tiny"]
    lbl = f.render(
        "Thrustmaster HOTAS Warthog   VID:044F   "
        "Stick PID:0402   Throttle PID:0404   "
        "github/HOTAS-WARTHOG-USAF-A10C-Interface", True, (38, 46, 62))
    surf.blit(lbl, (PAD + 4, H - FOOT_H + (FOOT_H - lbl.get_height()) // 2))

    # Right side — version tag
    ver = f.render("v3.0", True, C_DIM2)
    surf.blit(ver, (W - ver.get_width() - PAD - 4,
                    H - FOOT_H + (FOOT_H - ver.get_height()) // 2))


# ═════════════════════════════════════════════════════════════════════════════
# Font loader
# ═════════════════════════════════════════════════════════════════════════════

def load_fonts():
    def sf(names, size, bold=False):
        for n in names:
            try:
                return pygame.font.SysFont(n, size, bold=bold)
            except Exception:
                pass
        return pygame.font.SysFont("monospace", size, bold=bold)

    SANS = ["dejavusans", "ubuntu", "liberation sans", "arial", "freesans",
            "noto sans", "cantarell"]
    MONO = ["dejavusansmono", "ubuntumono", "liberationmono",
            "couriernew", "monospace", "noto mono"]

    return {
        "title":     sf(SANS, 22, bold=True),
        "panel":     sf(SANS, 13, bold=True),
        "bold":      sf(SANS, 13, bold=True),
        "small":     sf(SANS, 12),
        "tiny":      sf(SANS, 11),
        "tiny_bold": sf(SANS, 11, bold=True),
        "mono":      sf(MONO, 12),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    s_js = _load_json(STICK_JSON)
    t_js = _load_json(THROTTLE_JSON)
    if not s_js:
        print("[INFO] warthog_stick_map.json not found — using auto-detect")
    if not t_js:
        print("[INFO] warthog_throttle_map.json not found — using auto-detect")

    a_sp, a_tp    = auto_detect()
    stick_path    = resolve_path(s_js, a_sp)
    throttle_path = resolve_path(t_js, a_tp)

    if not stick_path and not throttle_path:
        print("\n[WARNING] No Warthog device found — running in demo mode.")
        print("  Plug in the HOTAS, then restart the dashboard.\n")

    s_lu = build_axis_lookup(s_js, STICK_AXIS_MAP)
    t_lu = build_axis_lookup(t_js, THROTTLE_AXIS_MAP)

    shared = SharedState()

    if stick_path:
        threading.Thread(target=input_reader,
                         args=(stick_path, "stick",
                               s_lu, STICK_HAT_MAP, shared),
                         daemon=True).start()
    if throttle_path:
        threading.Thread(target=input_reader,
                         args=(throttle_path, "throttle",
                               t_lu, THROTTLE_HAT_MAP, shared),
                         daemon=True).start()

    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("HOTAS Warthog  --  A-10C Input Test Utility")
    clock  = pygame.time.Clock()
    fonts  = load_fonts()

    fullscreen  = False
    current_tab = TAB_LIVE
    scroll_s = scroll_t = 0
    tab_rects: list = []

    ROW_H   = 22
    HDR_H   = 24 + 28
    VISIBLE = H - FOOT_H - TAB_H - 4 - HDR_H
    MAX_S   = max(0, len(STICK_BUTTON_MAP)    * ROW_H - VISIBLE)
    MAX_T   = max(0, len(THROTTLE_BUTTON_MAP) * ROW_H - VISIBLE)

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key in (pygame.K_TAB, pygame.K_m):
                    current_tab = TAB_MAP if current_tab == TAB_LIVE else TAB_LIVE
                elif ev.key == pygame.K_l:
                    current_tab = TAB_LIVE
                elif ev.key == pygame.K_f:
                    fullscreen = not fullscreen
                    flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
                    screen = pygame.display.set_mode((W, H), flags)

            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    for r, tid in tab_rects:
                        if r.collidepoint(ev.pos):
                            current_tab = tid
                elif ev.button == 4:
                    if current_tab == TAB_MAP:
                        mx = ev.pos[0]
                        if mx < W // 2: scroll_s = max(0, scroll_s - ROW_H * 3)
                        else:           scroll_t = max(0, scroll_t - ROW_H * 3)
                elif ev.button == 5:
                    if current_tab == TAB_MAP:
                        mx = ev.pos[0]
                        if mx < W // 2: scroll_s = min(MAX_S, scroll_s + ROW_H * 3)
                        else:           scroll_t = min(MAX_T, scroll_t + ROW_H * 3)

        shared.tick()
        state = shared.snapshot()

        screen.fill(C_BG)

        tab_rects = render_header(screen, fonts, current_tab,
                                  clock.get_fps(), state)

        if current_tab == TAB_LIVE:
            render_live_tab(screen, fonts, state, s_lu, t_lu)
        else:
            render_map_tab(screen, fonts, state, scroll_s, scroll_t)

        render_footer(screen, fonts)

        pygame.display.flip()
        clock.tick(TARGET_FPS)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
