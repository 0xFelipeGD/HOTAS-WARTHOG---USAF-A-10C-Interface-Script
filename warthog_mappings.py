# =============================================================================
# warthog_mappings.py
#
# Complete button / axis / hat mapping for the Thrustmaster HOTAS Warthog.
# Source: Thrustmaster TARGET Software manual + Linux HID enumeration order.
#
# Both scan_joystick.py and hotas_dashboard.py import from this module.
# The stick and throttle present as TWO separate USB devices; they share the
# same evdev button-code numbers (both start at BTN_TRIGGER = 288), so they
# must always be namespaced separately.
# =============================================================================

from config.constants import (
    VENDOR_THRUSTMASTER,
    PID_WARTHOG_STICK,
    PID_WARTHOG_THROTTLE,
)

# ---------------------------------------------------------------------------
# USB identification helpers
# ---------------------------------------------------------------------------
VENDOR_ID         = VENDOR_THRUSTMASTER
STICK_PRODUCT_ID  = PID_WARTHOG_STICK
THROTTLE_PRODUCT_ID = PID_WARTHOG_THROTTLE

# Device name substrings as reported by the HID driver (covers minor typos)
STICK_NAME_PATTERNS    = ["Warthog Joystick", "Warthog Joy"]
THROTTLE_NAME_PATTERNS = ["Warthog Throttle"]

# ---------------------------------------------------------------------------
# STICK — Button mapping
# evdev code → { name, desc, group, dx }
#
# Linux HID driver enumerates buttons in DirectInput (DX) order.
# Codes BTN_TRIGGER(288)…BTN_BASE6(299) then BTN_TRIGGER_HAPPY1(704)…(710)
# ---------------------------------------------------------------------------
STICK_BUTTON_MAP = {
    # --- Trigger / paddle -----------------------------------------------
    288: {"name": "TG1",  "desc": "Primary Trigger — 1st stage",    "group": "trigger", "dx": 1},
    289: {"name": "S2",   "desc": "Weapon Release Button",           "group": "buttons", "dx": 2},
    290: {"name": "S3",   "desc": "Nosewheel Steering / Depress",    "group": "buttons", "dx": 3},
    291: {"name": "S4",   "desc": "Pinky Lever",                     "group": "buttons", "dx": 4},
    292: {"name": "S1",   "desc": "Paddle Switch (index finger)",    "group": "buttons", "dx": 5},
    293: {"name": "TG2",  "desc": "Secondary Trigger — 2nd stage",   "group": "trigger", "dx": 6},
    # --- TMS — Target Management Switch (4-way) -------------------------
    294: {"name": "H2U",  "desc": "TMS Up",                          "group": "tms",     "dx": 7},
    295: {"name": "H2R",  "desc": "TMS Right",                       "group": "tms",     "dx": 8},
    296: {"name": "H2D",  "desc": "TMS Down",                        "group": "tms",     "dx": 9},
    297: {"name": "H2L",  "desc": "TMS Left",                        "group": "tms",     "dx": 10},
    # --- DMS — Data Management Switch (4-way) ---------------------------
    298: {"name": "H3U",  "desc": "DMS Up",                          "group": "dms",     "dx": 11},
    299: {"name": "H3R",  "desc": "DMS Right",                       "group": "dms",     "dx": 12},
    300: {"name": "H3D",  "desc": "DMS Down",                        "group": "dms",     "dx": 13},
    301: {"name": "H3L",  "desc": "DMS Left",                        "group": "dms",     "dx": 14},
    # --- CMS — Countermeasure Management Switch (4-way + push) ----------
    302: {"name": "H4U",  "desc": "CMS Up",                          "group": "cms",     "dx": 15},
    303: {"name": "H4R",  "desc": "CMS Right",                       "group": "cms",     "dx": 16},
    704: {"name": "H4D",  "desc": "CMS Down",                        "group": "cms",     "dx": 17},
    705: {"name": "H4L",  "desc": "CMS Left",                        "group": "cms",     "dx": 18},
    706: {"name": "H4P",  "desc": "CMS Press (push)",                "group": "cms",     "dx": 19},
}

# ---------------------------------------------------------------------------
# STICK — Axis mapping
# evdev ABS code → { name, desc, bipolar }
# bipolar=True  → range maps to  -1.0 … +1.0
# bipolar=False → range maps to   0.0 …  1.0
# ---------------------------------------------------------------------------
STICK_AXIS_MAP = {
    0x00: {"name": "Stick X",  "desc": "Roll  (left ← → right)",   "bipolar": True},
    0x01: {"name": "Stick Y",  "desc": "Pitch (fwd  ↑ ↓ back)",    "bipolar": True},
}

# ---------------------------------------------------------------------------
# STICK — Hat mapping
# H1 is reported as two ABS axes, not as button events.
# ---------------------------------------------------------------------------
STICK_HAT_MAP = {
    "H1": {
        "name":     "H1 — Trim Hat",
        "code_x":   0x10,   # ABS_HAT0X
        "code_y":   0x11,   # ABS_HAT0Y
        "desc":     "Trim / Castle hat (top of stick)",
    },
}

# Group display order for the stick button panel
STICK_BUTTON_GROUPS = [
    ("trigger", "Trigger"),
    ("buttons", "Stick Buttons"),
    ("tms",     "TMS (Target Mgmt)"),
    ("dms",     "DMS (Data Mgmt)"),
    ("cms",     "CMS (Countermeasure)"),
]

# ---------------------------------------------------------------------------
# THROTTLE — Button mapping
# Same evdev code range as the stick — completely separate device namespace.
# ---------------------------------------------------------------------------
THROTTLE_BUTTON_MAP = {
    # --- Slew Control -----------------------------------------------------
    288: {"name": "SC",       "desc": "Slew Control Push",                "group": "slew",      "dx": 1},
    # --- Mic Switch (5-way) ----------------------------------------------
    289: {"name": "MSP",      "desc": "Mic Switch Push",                  "group": "mic",       "dx": 2},
    290: {"name": "MSU",      "desc": "Mic Switch Up",                    "group": "mic",       "dx": 3},
    291: {"name": "MSR",      "desc": "Mic Switch Right",                 "group": "mic",       "dx": 4},
    292: {"name": "MSD",      "desc": "Mic Switch Down",                  "group": "mic",       "dx": 5},
    293: {"name": "MSL",      "desc": "Mic Switch Left",                  "group": "mic",       "dx": 6},
    # --- Speedbrake -------------------------------------------------------
    294: {"name": "SPDF",     "desc": "Speedbrake Forward",               "group": "speedbrake","dx": 7},
    295: {"name": "SPDB",     "desc": "Speedbrake Back",                  "group": "speedbrake","dx": 8},
    # --- Boat Switch ------------------------------------------------------
    296: {"name": "BSF",      "desc": "Boat Switch Forward",              "group": "boat",      "dx": 9},
    297: {"name": "BSB",      "desc": "Boat Switch Back",                 "group": "boat",      "dx": 10},
    # --- China Hat --------------------------------------------------------
    298: {"name": "CHF",      "desc": "China Hat Forward",                "group": "china",     "dx": 11},
    299: {"name": "CHB",      "desc": "China Hat Back",                   "group": "china",     "dx": 12},
    # --- Pinky Switch -----------------------------------------------------
    704: {"name": "PSF",      "desc": "Pinky Switch Forward",             "group": "pinky",     "dx": 13},
    705: {"name": "PSB",      "desc": "Pinky Switch Back",                "group": "pinky",     "dx": 14},
    # --- Left Throttle Button ---------------------------------------------
    706: {"name": "LTB",      "desc": "Left Throttle Button",             "group": "thr_btn",   "dx": 15},
    # --- Engine / Fuel Flow -----------------------------------------------
    707: {"name": "EFLNORM",  "desc": "Eng Fuel Flow LEFT — NORM",        "group": "engine",    "dx": 16},
    708: {"name": "EFRNORM",  "desc": "Eng Fuel Flow RIGHT — NORM",       "group": "engine",    "dx": 17},
    709: {"name": "EOLMOTOR", "desc": "Eng Oper LEFT — MOTOR",            "group": "engine",    "dx": 18},
    710: {"name": "EORMOTOR", "desc": "Eng Oper RIGHT — MOTOR",           "group": "engine",    "dx": 19},
    # --- APU / Gear / Flaps -----------------------------------------------
    711: {"name": "APUON",    "desc": "APU Start",                        "group": "systems",   "dx": 20},
    712: {"name": "LDGH",     "desc": "Landing Gear Horn Silence",        "group": "systems",   "dx": 21},
    713: {"name": "FLAPU",    "desc": "Flaps Up",                         "group": "systems",   "dx": 22},
    714: {"name": "FLAPD",    "desc": "Flaps Down",                       "group": "systems",   "dx": 23},
    # --- Autopilot / EAC --------------------------------------------------
    715: {"name": "EACON",    "desc": "EAC On",                           "group": "autopilot", "dx": 24},
    716: {"name": "RDRNRM",   "desc": "Radar Altimeter NORM",             "group": "autopilot", "dx": 25},
    717: {"name": "APENG",    "desc": "Autopilot Engage / Disengage",     "group": "autopilot", "dx": 26},
    718: {"name": "APPAT",    "desc": "Autopilot Path",                   "group": "autopilot", "dx": 27},
    719: {"name": "APALT",    "desc": "Autopilot Alt Hold",               "group": "autopilot", "dx": 28},
    # --- Idle detents -----------------------------------------------------
    720: {"name": "IDLERON",  "desc": "Idle Detent RIGHT — ON",           "group": "idle",      "dx": 29},
    721: {"name": "IDLELON",  "desc": "Idle Detent LEFT — ON",            "group": "idle",      "dx": 30},
    # --- Engine ignition --------------------------------------------------
    722: {"name": "EOLIGN",   "desc": "Eng Oper LEFT — IGN / NORM",       "group": "engine",    "dx": 31},
    723: {"name": "EORIGN",   "desc": "Eng Oper RIGHT — IGN / NORM",      "group": "engine",    "dx": 32},
}

# ---------------------------------------------------------------------------
# THROTTLE — Axis mapping
# ---------------------------------------------------------------------------
THROTTLE_AXIS_MAP = {
    0x00: {"name": "Slew X",         "desc": "Slew Control X (left/right)", "bipolar": True},
    0x01: {"name": "Slew Y",         "desc": "Slew Control Y (fwd/back)",   "bipolar": True},
    0x02: {"name": "Left Throttle",  "desc": "Left Engine Throttle",        "bipolar": False},
    0x05: {"name": "Right Throttle", "desc": "Right Engine Throttle",       "bipolar": False},
    0x06: {"name": "Friction",       "desc": "Friction Adjustment Lever",   "bipolar": False},
}

# ---------------------------------------------------------------------------
# THROTTLE — Hat mapping
# ---------------------------------------------------------------------------
THROTTLE_HAT_MAP = {
    "CS": {
        "name":   "CS — Coolie Switch",
        "code_x": 0x10,   # ABS_HAT0X
        "code_y": 0x11,   # ABS_HAT0Y
        "desc":   "Coolie Switch (4-way hat on throttle)",
    },
}

# Group display order for the throttle button panel
THROTTLE_BUTTON_GROUPS = [
    ("slew",       "Slew"),
    ("mic",        "Mic Switch"),
    ("speedbrake", "Speedbrake"),
    ("boat",       "Boat Switch"),
    ("china",      "China Hat"),
    ("pinky",      "Pinky Switch"),
    ("thr_btn",    "Throttle Btn"),
    ("engine",     "Engine / Fuel"),
    ("systems",    "APU / Gear / Flaps"),
    ("autopilot",  "Autopilot / EAC"),
    ("idle",       "Idle Detents"),
]
