# HOTAS Warthog - USAF A-10C Interface Dashboard (Linux)

Real-time joystick test dashboard for the **Thrustmaster HOTAS Warthog** on Linux, built with Python, `evdev`, and `pygame`.

Monitors every button, axis, and hat switch on both the flight stick and throttle with live visual feedback at 60 FPS.

```
 STICK                              THROTTLE
 Stick X  [======|======]           Left Throttle   [==========>]
 Stick Y  [==|===========]          Right Throttle  [==========>]
                                    Friction        [=======>   ]
 Trigger  * TG1  * TG2
 TMS      * H2U  * H2R  * H2D      Engine  * EFLNORM  * EFRNORM
 DMS      * H3U  * H3R  * H3D      Autopilot  * APENG  * APPAT
```

---

## Features

- Live axis bars (bipolar and unipolar) with normalized values
- Button LED indicators (green = pressed, gray = released)
- 4-way hat switch directional indicators
- 2-D stick position plot
- Full button reference table with live highlighting (MAP tab)
- Auto-reconnect when devices are unplugged/replugged
- Supports stick-only, throttle-only, or both connected
- Desktop shortcut installer for one-click launch

---

## Hardware

| Component    | USB VID | USB PID | Linux Device Name                    |
|--------------|---------|---------|--------------------------------------|
| Flight Stick | `044F`  | `0402`  | Thrustmaster HOTAS Warthog Joystick  |
| Throttle     | `044F`  | `0404`  | Thrustmaster HOTAS Warthog Throttle  |

The Warthog presents as **two separate USB HID devices**. The dashboard works with only one connected -- the missing device shows as DISCONNECTED and auto-reconnects when plugged in.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/0xFelipeGD/HOTAS-WARTHOG---USAF-A-10C-Interface-Script.git
cd HOTAS-WARTHOG---USAF-A-10C-Interface-Script

# 2. Install system dependencies (Debian/Ubuntu)
sudo apt update
sudo apt install python3-pip python3-venv libsdl2-dev libsdl2-mixer-dev \
                 libsdl2-image-dev libsdl2-ttf-dev

# 3. Grant input device permissions
sudo usermod -aG input $USER
# Log out and back in, then verify:
groups | grep input

# 4. Create virtual environment and install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Scan your hardware (generates calibrated JSON mappings)
python3 scan_joystick.py

# 6. Launch the dashboard
python3 hotas_dashboard.py
```

---

## Installation (step by step)

### 1. System dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-venv libsdl2-dev libsdl2-mixer-dev \
                 libsdl2-image-dev libsdl2-ttf-dev
```

### 2. Input device permissions

By default only root can read raw input devices. Add your user to the `input` group:

```bash
sudo usermod -aG input $USER
```

**Log out and log back in** for the group change to take effect.
Verify with:

```bash
groups | grep input
```

### 3. Python virtual environment

```bash
cd HOTAS-WARTHOG---USAF-A-10C-Interface-Script
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Desktop shortcut (optional)

Creates a clickable launcher on your desktop and in the application menu:

```bash
bash install.sh
```

After installing, double-click **HOTAS-Warthog** on your desktop or find it in your app menu as **HOTAS Warthog Dashboard**.

---

## Usage

### Scan your hardware

```bash
python3 scan_joystick.py
```

This script:
- Lists every input device in `/dev/input/`
- Identifies the Warthog stick and throttle by USB vendor/product ID
- Prints axis ranges, button codes, and official A-10C control names
- Writes calibrated mappings to `output/warthog_stick_map.json` and `output/warthog_throttle_map.json`

If you skip this step, the dashboard falls back to default ranges from `config/default_mapping.json`.

### Launch the dashboard

```bash
python3 hotas_dashboard.py
```

Or use the one-click launcher (runs scan automatically):

```bash
bash launch.sh
```

### Keyboard controls

| Key       | Action              |
|-----------|---------------------|
| `TAB` / `M` | Switch tabs (LIVE / MAP) |
| `F`       | Toggle fullscreen   |
| `ESC`     | Quit                |

---

## Project Structure

```
HOTAS-WARTHOG---USAF-A-10C-Interface-Script/
├── hotas_dashboard.py         # Real-time visual dashboard (pygame)
├── scan_joystick.py           # Device scanner — generates JSON mappings
├── warthog_mappings.py        # Complete button/axis/hat name dictionaries
├── config/
│   ├── constants.py           # Colors, layout, USB IDs, timing constants
│   └── default_mapping.json   # Fallback axis ranges (no scan needed)
├── output/                    # Generated at runtime by scan_joystick.py
│   ├── warthog_stick_map.json
│   └── warthog_throttle_map.json
├── install.sh                 # Desktop shortcut installer
├── launch.sh                  # One-click launcher (scan + dashboard)
├── requirements.txt
└── README.md
```

---

## Warthog Button Reference

### Stick (VID:044F PID:0402)

| DX# | Code | Name | Description                      |
|-----|------|------|----------------------------------|
| 1   | 288  | TG1  | Primary Trigger -- 1st stage     |
| 2   | 289  | S2   | Weapon Release Button            |
| 3   | 290  | S3   | Nosewheel Steering / Depress     |
| 4   | 291  | S4   | Pinky Lever                      |
| 5   | 292  | S1   | Paddle Switch (index finger)     |
| 6   | 293  | TG2  | Secondary Trigger -- 2nd stage   |
| 7   | 294  | H2U  | TMS Up                           |
| 8   | 295  | H2R  | TMS Right                        |
| 9   | 296  | H2D  | TMS Down                         |
| 10  | 297  | H2L  | TMS Left                         |
| 11  | 298  | H3U  | DMS Up                           |
| 12  | 299  | H3R  | DMS Right                        |
| 13  | 300  | H3D  | DMS Down                         |
| 14  | 301  | H3L  | DMS Left                         |
| 15  | 302  | H4U  | CMS Up                           |
| 16  | 303  | H4R  | CMS Right                        |
| 17  | 704  | H4D  | CMS Down                         |
| 18  | 705  | H4L  | CMS Left                         |
| 19  | 706  | H4P  | CMS Press (push)                 |

**Axes:** ABS_X (Roll), ABS_Y (Pitch)
**Hat:** H1 Trim (ABS_HAT0X / ABS_HAT0Y)

### Throttle (VID:044F PID:0404)

| DX# | Code | Name     | Description                       |
|-----|------|----------|-----------------------------------|
| 1   | 288  | SC       | Slew Control Push                 |
| 2   | 289  | MSP      | Mic Switch Push                   |
| 3   | 290  | MSU      | Mic Switch Up                     |
| 4   | 291  | MSR      | Mic Switch Right                  |
| 5   | 292  | MSD      | Mic Switch Down                   |
| 6   | 293  | MSL      | Mic Switch Left                   |
| 7   | 294  | SPDF     | Speedbrake Forward                |
| 8   | 295  | SPDB     | Speedbrake Back                   |
| 9   | 296  | BSF      | Boat Switch Forward               |
| 10  | 297  | BSB      | Boat Switch Back                  |
| 11  | 298  | CHF      | China Hat Forward                 |
| 12  | 299  | CHB      | China Hat Back                    |
| 13  | 704  | PSF      | Pinky Switch Forward              |
| 14  | 705  | PSB      | Pinky Switch Back                 |
| 15  | 706  | LTB      | Left Throttle Button              |
| 16  | 707  | EFLNORM  | Engine Fuel Flow Left -- NORM     |
| 17  | 708  | EFRNORM  | Engine Fuel Flow Right -- NORM    |
| 18  | 709  | EOLMOTOR | Engine Oper Left -- MOTOR         |
| 19  | 710  | EORMOTOR | Engine Oper Right -- MOTOR        |
| 20  | 711  | APUON    | APU Start                         |
| 21  | 712  | LDGH     | Landing Gear Horn Silence         |
| 22  | 713  | FLAPU    | Flaps Up                          |
| 23  | 714  | FLAPD    | Flaps Down                        |
| 24  | 715  | EACON    | EAC On                            |
| 25  | 716  | RDRNRM   | Radar Altimeter NORM              |
| 26  | 717  | APENG    | Autopilot Engage/Disengage        |
| 27  | 718  | APPAT    | Autopilot Path                    |
| 28  | 719  | APALT    | Autopilot Alt Hold                |
| 29  | 720  | IDLERON  | Idle Detent Right -- ON           |
| 30  | 721  | IDLELON  | Idle Detent Left -- ON            |
| 31  | 722  | EOLIGN   | Engine Oper Left -- IGN/NORM      |
| 32  | 723  | EORIGN   | Engine Oper Right -- IGN/NORM     |

**Axes:** ABS_X (Slew X), ABS_Y (Slew Y), ABS_Z (Left Throttle), ABS_RZ (Right Throttle), ABS_THROTTLE (Friction)
**Hat:** CS Coolie Switch (ABS_HAT0X / ABS_HAT0Y)

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

# Full diagnostic:
python3 scan_joystick.py
```

### Dashboard shows DISCONNECTED

The input thread retries every 2 seconds. Plug the device in and wait -- the status badge turns green automatically.

### evdev button codes differ from the mapping

Firmware revisions may reorder button codes. Run `scan_joystick.py` first -- it detects the actual codes from your hardware and writes calibrated JSON that the dashboard uses.

### Low frame rate

- Close other GPU-intensive applications
- Verify SDL2 hardware acceleration:
  ```bash
  python3 -c "import pygame; pygame.init(); print(pygame.display.Info())"
  ```

---

## Requirements

- **OS:** Linux (Ubuntu 22.04+ / Debian 12+ or any distro with kernel 4.x+)
- **Python:** 3.10+
- **Hardware:** Thrustmaster HOTAS Warthog (stick and/or throttle)
- **Python packages:** `evdev`, `pygame` (see `requirements.txt`)

---

## License

This project is provided as-is for personal and educational use.
