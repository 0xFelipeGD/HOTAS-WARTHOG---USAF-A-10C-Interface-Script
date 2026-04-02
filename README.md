# HOTAS Warthog — USAF A-10C Interface Dashboard (Linux)

Real-time joystick dashboard for the **Thrustmaster HOTAS Warthog** on Linux,
built with Python, `evdev`, and `pygame`.

---

## Hardware Support

| Component | USB VID | USB PID | Linux device name |
|-----------|---------|---------|-------------------|
| Flight Stick | `044F` | `0402` | Thrustmaster HOTAS Warthog Joystick |
| Throttle     | `044F` | `0404` | Thrustmaster HOTAS Warthog Throttle |

The Warthog presents as **two separate USB HID devices** on Linux.
Both must be plugged in for full coverage; the dashboard works with only
one connected (the other shows DISCONNECTED in red).

---

## Prerequisites

- Ubuntu 22.04+ / Debian 12+ (any Linux with kernel 4.x+)
- Python 3.10+
- HOTAS Warthog connected via USB

---

## Installation

### 1. System dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-venv libsdl2-dev libsdl2-mixer-dev \
                 libsdl2-image-dev libsdl2-ttf-dev
```

### 2. Input device permissions

By default only root can read raw input devices.
Add your user to the `input` group:

```bash
sudo usermod -aG input $USER
```

**Log out and log back in** for the group change to take effect.
Verify with: `groups | grep input`

### 3. Python virtual environment + dependencies

```bash
cd /path/to/HOTAS-WARTHOG---USAF-A-10C-Interface-Script
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

### Step 1 — Scan your hardware (recommended first run)

```bash
python3 scan_joystick.py
```

This script:
- Lists every input device in `/dev/input/`
- Identifies the Warthog stick and throttle by USB vendor/product ID
- Prints axis ranges, button codes, and official A-10C names
- Writes `output/warthog_stick_map.json` and `output/warthog_throttle_map.json`

The dashboard uses these JSON files for calibrated axis ranges.
If you skip this step the dashboard falls back to auto-detection with
default 0–65535 ranges from `config/default_mapping.json`.

### Step 2 — Launch the dashboard

```bash
python3 hotas_dashboard.py
```

Press **ESC** or close the window to exit.

---

## Project Structure

```
HOTAS-WARTHOG---USAF-A-10C-Interface-Script/
├── config/
│   ├── __init__.py
│   ├── constants.py           # Colors, layout, USB IDs, timing constants
│   └── default_mapping.json   # Fallback axis ranges (no scan needed)
├── output/                    # Created at runtime by scan_joystick.py
│   ├── warthog_stick_map.json
│   └── warthog_throttle_map.json
├── warthog_mappings.py        # Complete button/axis name dictionaries
├── scan_joystick.py           # Script 1 — device scanner
├── hotas_dashboard.py         # Script 2 — real-time visual dashboard
├── requirements.txt
└── README.md
```

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  HOTAS Warthog A-10C Dashboard                                  │
│  Stick: CONNECTED                    Throttle: CONNECTED        │
├──────────────────────────────┬──────────────────────────────────┤
│  STICK — AXES                │  THROTTLE — AXES                 │
│  Stick X  [══════|══════]    │  Left Throttle   [══════════>]   │
│  Stick Y  [══|═══════════]   │  Right Throttle  [══════════>]   │
│                              │  Slew X          [═══|══════]    │
├──────────────────────────────│  Slew Y          [══════|═══]    │
│  STICK — HATS                │  Friction        [═══════>  ]    │
│  H1(Trim) TMS  DMS  CMS     ├──────────────────────────────────┤
│  [↑←→↓]  [↑]  [←] [push]   │  THROTTLE — HATS                 │
├──────────────────────────────│  CS (Coolie Switch)  [↑←→↓]     │
│  STICK — BUTTONS             ├──────────────────────────────────┤
│  Trigger  ● TG1  ● TG2      │  THROTTLE — BUTTONS              │
│  Buttons  ● S1  ● S2  ...   │  Slew ● SC   Mic ● MSP ● MSU ... │
│  TMS  ● H2U ● H2R ...       │  Engine ● EFLNORM ● EFRNORM ...  │
│  DMS  ● H3U ● H3R ...       │  Autopilot ● APENG ● APPAT ...   │
│  CMS  ● H4U ● H4R ● H4P ... │                                  │
├──────────────────────────────┴──────────────────────────────────┤
│  FPS: 60.0  |  Stick ev/s:  342  |  Throttle ev/s:  18  |  ESC │
└─────────────────────────────────────────────────────────────────┘
```

- **Axes**: horizontal bar with normalised value (−1.0 … +1.0 for bipolar,
  0.0 … 1.0 for throttles/friction)
- **Buttons**: green LED = pressed, gray = released
- **Hats**: 4-arrow indicator, active direction highlighted in green

---

## Warthog Button Reference

### Stick (VID:044F PID:0402)

| DX# | evdev code | Official name | Description |
|-----|-----------|--------------|-------------|
| 1 | 288 | TG1 | Primary Trigger — 1st stage |
| 2 | 289 | S2  | Weapon Release Button |
| 3 | 290 | S3  | Nosewheel Steering / Depress |
| 4 | 291 | S4  | Pinky Lever |
| 5 | 292 | S1  | Paddle Switch |
| 6 | 293 | TG2 | Secondary Trigger — 2nd stage |
| 7 | 294 | H2U | TMS Up |
| 8 | 295 | H2R | TMS Right |
| 9 | 296 | H2D | TMS Down |
| 10 | 297 | H2L | TMS Left |
| 11 | 298 | H3U | DMS Up |
| 12 | 299 | H3R | DMS Right |
| 13 | 704 | H3D | DMS Down |
| 14 | 705 | H3L | DMS Left |
| 15 | 706 | H4U | CMS Up |
| 16 | 707 | H4R | CMS Right |
| 17 | 708 | H4D | CMS Down |
| 18 | 709 | H4L | CMS Left |
| 19 | 710 | H4P | CMS Press |

**Stick Axes:** ABS_X (Roll), ABS_Y (Pitch)
**Stick Hat:** H1 Trim (ABS_HAT0X / ABS_HAT0Y)

### Throttle (VID:044F PID:0404)

| DX# | evdev code | Official name | Description |
|-----|-----------|--------------|-------------|
| 1  | 288 | SC       | Slew Control Push |
| 2  | 289 | MSP      | Mic Switch Push |
| 3  | 290 | MSU      | Mic Switch Up |
| 4  | 291 | MSR      | Mic Switch Right |
| 5  | 292 | MSD      | Mic Switch Down |
| 6  | 293 | MSL      | Mic Switch Left |
| 7  | 294 | SPDF     | Speedbrake Forward |
| 8  | 295 | SPDB     | Speedbrake Back |
| 9  | 296 | BSF      | Boat Switch Forward |
| 10 | 297 | BSB      | Boat Switch Back |
| 11 | 298 | CHF      | China Hat Forward |
| 12 | 299 | CHB      | China Hat Back |
| 13 | 704 | PSF      | Pinky Switch Forward |
| 14 | 705 | PSB      | Pinky Switch Back |
| 15 | 706 | LTB      | Left Throttle Button |
| 16 | 707 | EFLNORM  | Engine Fuel Flow Left — NORM |
| 17 | 708 | EFRNORM  | Engine Fuel Flow Right — NORM |
| 18 | 709 | EOLMOTOR | Engine Oper Left — MOTOR |
| 19 | 710 | EORMOTOR | Engine Oper Right — MOTOR |
| 20 | 711 | APUON    | APU Start |
| 21 | 712 | LDGH     | Landing Gear Horn Silence |
| 22 | 713 | FLAPU    | Flaps Up |
| 23 | 714 | FLAPD    | Flaps Down |
| 24 | 715 | EACON    | EAC On |
| 25 | 716 | RDRNRM   | Radar Altimeter NORM |
| 26 | 717 | APENG    | Autopilot Engage/Disengage |
| 27 | 718 | APPAT    | Autopilot Path |
| 28 | 719 | APALT    | Autopilot Alt Hold |
| 29 | 720 | IDLERON  | Idle Detent Right — ON |
| 30 | 721 | IDLELON  | Idle Detent Left — ON |
| 31 | 722 | EOLIGN   | Engine Oper Left — IGN/NORM |
| 32 | 723 | EORIGN   | Engine Oper Right — IGN/NORM |

**Throttle Axes:** ABS_X (Slew X), ABS_Y (Slew Y), ABS_Z (Left Throttle),
ABS_RZ (Right Throttle), ABS_THROTTLE (Friction)
**Throttle Hat:** CS Coolie Switch (ABS_HAT0X / ABS_HAT0Y)

---

## Troubleshooting

### "Permission denied" when reading `/dev/input/eventX`
```bash
sudo usermod -aG input $USER
# Log out and back in, then verify:
groups | grep input
```

### Device not detected
```bash
# Check USB connection:
lsusb | grep -i 044f

# Check Linux input devices:
cat /proc/bus/input/devices | grep -i warthog

# Run scanner for full diagnostic:
python3 scan_joystick.py
```

### Dashboard shows DISCONNECTED
The input thread retries every 2 seconds. Plug the device in and wait —
the status badge turns green automatically.

### Low frame rate
- Close other GPU-intensive applications.
- Ensure `pygame` was installed with SDL2 hardware acceleration:
  `python3 -c "import pygame; pygame.init(); print(pygame.display.Info())"`

### evdev code numbers differ from the mapping
Firmware revisions occasionally reorder button codes. Run `scan_joystick.py`
first — it detects the actual codes from your hardware and writes the
calibrated JSON that the dashboard uses.

---

## Architecture Notes (for AI / developers)

### Why evdev instead of `pygame.joystick`?
`pygame.joystick` abstracts away USB vendor/product IDs, raw event codes,
and device capabilities — all of which are needed for accurate named mapping.
`evdev` reads `/dev/input/eventX` directly and exposes everything.

### Why pygame for rendering?
`pygame` runs a deterministic game loop at 60 Hz. `tkinter`'s `after()`
callback is unreliable at high refresh rates and not suited for real-time
visualisation.

### Thread model
- **Main thread**: pygame render loop only — never touches evdev.
- **Input threads**: one daemon thread per device, each runs
  `evdev.InputDevice.read_loop()` which blocks efficiently until an event
  arrives.
- **SharedState**: a `threading.Lock`-protected dict. The render thread
  calls `snapshot()` which returns a shallow copy, so the lock is held only
  during the copy — never during the full draw cycle.

### Two devices, same button codes
Both the stick and throttle start their button enumeration at
`BTN_TRIGGER = 288`. They are kept in separate namespaces inside
`SharedState` (`stick_buttons` vs `throttle_buttons`) to avoid collisions.

### Axis normalisation
Raw evdev values are integers in `[min, max]` (typically 0–65535).
`normalise_axis()` maps them to `[-1.0, 1.0]` (bipolar axes: X, Y, Slew)
or `[0.0, 1.0]` (unipolar: throttles, friction).

### Reconnection
If a device disconnects mid-session the input thread catches `OSError`,
sets `connected=False` in SharedState (triggering a red badge in the
dashboard), and retries `evdev.InputDevice(path)` every 2 seconds.
