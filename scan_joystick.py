#!/usr/bin/env python3
# =============================================================================
# scan_joystick.py
#
# Step 1 — System Scanner for the Thrustmaster HOTAS Warthog on Linux.
#
# Usage:
#   python3 scan_joystick.py
#
# What it does:
#   1. Lists every input device found in /dev/input/ via evdev
#   2. Also cross-references /proc/bus/input/devices for context
#   3. Identifies the Warthog stick (VID:044F PID:0402) and
#      throttle (VID:044F PID:0404) by vendor/product ID
#   4. For each found device prints: path, name, axes (with ranges),
#      buttons (with evdev names and official A-10C names)
#   5. Writes JSON mapping files to output/ for use by hotas_dashboard.py
#
# Permissions:
#   If you get "Permission denied" errors run:
#     sudo usermod -aG input $USER
#   then log out and log back in.
# =============================================================================

import sys
import os
import json
import datetime

# ---------------------------------------------------------------------------
# Dependency check — give a clear message before a cryptic ImportError
# ---------------------------------------------------------------------------
try:
    import evdev
    from evdev import ecodes
except ImportError:
    print("\n[ERROR] The 'evdev' library is not installed.")
    print("  Install it with:  pip install evdev")
    print("  Or inside a venv: pip install -r requirements.txt\n")
    sys.exit(1)

# Local modules
from warthog_mappings import (
    VENDOR_ID,
    STICK_PRODUCT_ID,
    THROTTLE_PRODUCT_ID,
    STICK_NAME_PATTERNS,
    THROTTLE_NAME_PATTERNS,
    STICK_BUTTON_MAP,
    STICK_AXIS_MAP,
    STICK_HAT_MAP,
    THROTTLE_BUTTON_MAP,
    THROTTLE_AXIS_MAP,
    THROTTLE_HAT_MAP,
)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(width: int = 60) -> str:
    return "─" * width


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _name_matches(device_name: str, patterns: list) -> bool:
    """Case-insensitive substring match against any pattern in the list."""
    dn = device_name.lower()
    return any(p.lower() in dn for p in patterns)


# ---------------------------------------------------------------------------
# Read /proc/bus/input/devices  (informational cross-reference only)
# ---------------------------------------------------------------------------

def read_proc_devices() -> list[dict]:
    """Parse /proc/bus/input/devices into a list of dicts."""
    entries = []
    try:
        with open("/proc/bus/input/devices") as fh:
            current: dict = {}
            for line in fh:
                line = line.strip()
                if not line:
                    if current:
                        entries.append(current)
                        current = {}
                    continue
                if line.startswith("I:"):
                    # Bus=0003 Vendor=044f Product=0402 Version=0111
                    parts = dict(p.split("=") for p in line[2:].strip().split())
                    current["vendor"]  = parts.get("Vendor", "????").lower()
                    current["product"] = parts.get("Product", "????").lower()
                    current["bus"]     = parts.get("Bus", "??")
                elif line.startswith("N: Name="):
                    current["name"] = line.split("Name=", 1)[1].strip('"')
                elif line.startswith("H: Handlers="):
                    handlers = line.split("Handlers=", 1)[1].strip().split()
                    events = [h for h in handlers if h.startswith("event")]
                    current["event_handlers"] = events
            if current:
                entries.append(current)
    except PermissionError:
        print("[WARN] Cannot read /proc/bus/input/devices — skipping cross-reference.")
    except FileNotFoundError:
        print("[WARN] /proc/bus/input/devices not found.")
    return entries


# ---------------------------------------------------------------------------
# Enumerate all /dev/input/ devices via evdev
# ---------------------------------------------------------------------------

def enumerate_all_devices() -> list:
    """
    Return a list of evdev.InputDevice objects for all readable event nodes.
    Skips nodes we cannot open (PermissionError) but reports them.
    """
    devices = []
    permission_errors = []

    for path in evdev.list_devices():
        try:
            devices.append(evdev.InputDevice(path))
        except PermissionError:
            permission_errors.append(path)
        except Exception as exc:
            print(f"[WARN] Could not open {path}: {exc}")

    if permission_errors:
        print(f"\n[WARN] Permission denied on {len(permission_errors)} device(s):")
        for p in permission_errors:
            print(f"       {p}")
        print("  Fix: sudo usermod -aG input $USER  then log out and back in.\n")

    return devices


# ---------------------------------------------------------------------------
# Identify Warthog components
# ---------------------------------------------------------------------------

def find_warthog_devices(devices: list) -> tuple:
    """
    Returns (stick_device, throttle_device) — either may be None if not found.
    Primary match: USB vendor/product ID.
    Fallback match: device name substring.
    """
    stick    = None
    throttle = None

    for dev in devices:
        info = dev.info  # InputDeviceInfo(bustype, vendor, product, version)

        # Primary: VID / PID match
        if info.vendor == VENDOR_ID:
            if info.product == STICK_PRODUCT_ID:
                stick = dev
                continue
            if info.product == THROTTLE_PRODUCT_ID:
                throttle = dev
                continue

        # Fallback: name match (e.g., some firmwares report slightly different IDs)
        name = dev.name or ""
        if stick is None and _name_matches(name, STICK_NAME_PATTERNS):
            stick = dev
        elif throttle is None and _name_matches(name, THROTTLE_NAME_PATTERNS):
            throttle = dev

    return stick, throttle


# ---------------------------------------------------------------------------
# Build per-device capability report + JSON mapping
# ---------------------------------------------------------------------------

def build_mapping(device, device_type: str,
                  button_map: dict, axis_map: dict, hat_map: dict) -> dict:
    """
    Extract capabilities from an evdev InputDevice and cross-reference with
    the official warthog_mappings dictionaries to produce a serialisable dict.
    """
    caps = device.capabilities(verbose=True, absinfo=True)

    # ---- Axes ---------------------------------------------------------------
    axes = []
    hats_found = {}

    abs_events = caps.get(("EV_ABS", ecodes.EV_ABS), [])
    for (code_name, code_int), abs_info in abs_events:
        official = axis_map.get(code_int)
        # Check if this is a hat axis
        hat_entry = None
        for hat_key, hat_def in hat_map.items():
            if code_int in (hat_def["code_x"], hat_def["code_y"]):
                hat_entry = (hat_key, hat_def)
                break

        entry = {
            "code":          code_int,
            "evdev_name":    code_name,
            "official_name": official["name"] if official else code_name,
            "description":   official["desc"] if official else "",
            "bipolar":       official["bipolar"] if official else True,
            "min":           abs_info.min,
            "max":           abs_info.max,
            "fuzz":          abs_info.fuzz,
            "flat":          abs_info.flat,
            "resolution":    abs_info.resolution,
            "is_hat":        hat_entry is not None,
        }
        axes.append(entry)

        if hat_entry:
            hat_key, hat_def = hat_entry
            if hat_key not in hats_found:
                hats_found[hat_key] = {
                    "key":        hat_key,
                    "name":       hat_def["name"],
                    "description":hat_def.get("desc", ""),
                    "code_x":     hat_def["code_x"],
                    "code_y":     hat_def["code_y"],
                }

    # ---- Buttons ------------------------------------------------------------
    buttons = []
    key_events = caps.get(("EV_KEY", ecodes.EV_KEY), [])
    for item in key_events:
        # evdev returns (name_or_aliases, code_int) — name may be str, list, or tuple
        if isinstance(item, (list, tuple)) and len(item) == 2:
            code_name, code_int = item
            # Flatten aliases: list or tuple → take first element
            if isinstance(code_name, (list, tuple)):
                code_name = code_name[0]
            # Ensure it's a plain string
            if not isinstance(code_name, str):
                code_name = str(code_name)
        else:
            continue

        official = button_map.get(code_int)
        entry = {
            "code":          code_int,
            "evdev_name":    code_name,
            "official_name": official["name"]  if official else f"BTN_{code_int}",
            "description":   official["desc"]  if official else "Unknown",
            "group":         official["group"] if official else "unknown",
            "dx_number":     official["dx"]    if official else 0,
        }
        buttons.append(entry)

    # Sort buttons by code for deterministic output
    buttons.sort(key=lambda b: b["code"])
    axes.sort(key=lambda a: a["code"])

    return {
        "device_type":  device_type,
        "device_path":  device.path,
        "device_name":  device.name,
        "vid":          f"{device.info.vendor:04X}",
        "pid":          f"{device.info.product:04X}",
        "scan_timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "axes":    axes,
        "buttons": buttons,
        "hats":    list(hats_found.values()),
    }


# ---------------------------------------------------------------------------
# Pretty-print a device report to the terminal
# ---------------------------------------------------------------------------

def print_device_report(mapping: dict) -> None:
    dev_type = mapping["device_type"].upper()
    _section(f"WARTHOG {dev_type}  —  {mapping['device_name']}")
    print(f"  Path : {mapping['device_path']}")
    print(f"  VID  : {mapping['vid']}   PID : {mapping['pid']}")
    print(f"  Scan : {mapping['scan_timestamp']}")

    # Axes
    print(f"\n  AXES ({len(mapping['axes'])} found):")
    print(f"  {'Code':>5}  {'evdev name':<16}  {'Official name':<18}  {'min':>6}  {'max':>6}  {'fuzz':>4}  {'flat':>4}  Bipolar")
    print(f"  {_bar(80)}")
    for ax in mapping["axes"]:
        print(
            f"  {ax['code']:>5}  {ax['evdev_name']:<16}  {ax['official_name']:<18}  "
            f"{ax['min']:>6}  {ax['max']:>6}  {ax['fuzz']:>4}  {ax['flat']:>4}  "
            f"{'yes' if ax['bipolar'] else 'no'}"
        )

    # Hats
    if mapping["hats"]:
        print(f"\n  HATS ({len(mapping['hats'])} found):")
        for h in mapping["hats"]:
            print(f"    {h['key']} — {h['name']}  (X code={h['code_x']}, Y code={h['code_y']})")

    # Buttons
    print(f"\n  BUTTONS ({len(mapping['buttons'])} found):")
    print(f"  {'Code':>5}  {'DX':>3}  {'evdev name':<28}  {'Official':>10}  Description")
    print(f"  {_bar(80)}")
    for btn in mapping["buttons"]:
        print(
            f"  {btn['code']:>5}  {btn['dx_number']:>3}  {btn['evdev_name']:<28}  "
            f"{btn['official_name']:>10}  {btn['description']}"
        )


# ---------------------------------------------------------------------------
# Print all detected (non-Warthog) devices for diagnostic purposes
# ---------------------------------------------------------------------------

def print_all_devices(devices: list) -> None:
    _section("ALL DETECTED INPUT DEVICES")
    if not devices:
        print("  No readable input devices found.")
        return
    for dev in devices:
        vid = f"{dev.info.vendor:04X}"
        pid = f"{dev.info.product:04X}"
        print(f"  {dev.path:<24}  VID:{vid}  PID:{pid}  {dev.name}")


# ---------------------------------------------------------------------------
# Write JSON mapping to output/
# ---------------------------------------------------------------------------

def write_mapping(mapping: dict) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"warthog_{mapping['device_type']}_map.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w") as fh:
        json.dump(mapping, fh, indent=2)
    return filepath


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="HOTAS Warthog device scanner")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="Suppress terminal output (only write JSON files)")
    args = ap.parse_args()

    if args.quiet:
        sys.stdout = open(os.devnull, "w")

    print("\n" + "=" * 60)
    print("  HOTAS WARTHOG — Linux Device Scanner")
    print("  Thrustmaster A-10C Joystick Interface")
    print("=" * 60)
    print(f"  Python  : {sys.version.split()[0]}")
    try:
        from importlib.metadata import version as _pkg_version
        evdev_ver = _pkg_version("evdev")
    except Exception:
        evdev_ver = "unknown"
    print(f"  evdev   : {evdev_ver}")
    print(f"  Kernel  : {os.uname().release}")

    # Step 1: enumerate everything
    all_devices = enumerate_all_devices()
    print_all_devices(all_devices)

    if not all_devices:
        print("\n[ERROR] No input devices could be read.")
        print("  Make sure you are in the 'input' group:")
        print("    sudo usermod -aG input $USER")
        print("  Then log out and log back in.\n")
        return 2

    # Step 2: find Warthog components
    stick, throttle = find_warthog_devices(all_devices)

    if stick is None and throttle is None:
        print("\n[ERROR] No Thrustmaster HOTAS Warthog device found.")
        print("  Expected:  VID 044F  +  PID 0402 (stick) or 0404 (throttle)")
        print("  Check USB connection:  lsusb | grep -i 044f")
        print("  Check input devices:   cat /proc/bus/input/devices | grep -i warthog")
        return 3

    if stick is None:
        print("\n[WARN] Warthog STICK not detected (throttle found).")
    if throttle is None:
        print("\n[WARN] Warthog THROTTLE not detected (stick found).")

    # Step 3: build mappings, print reports, save JSON
    saved_files = []

    if stick is not None:
        stick_map = build_mapping(
            stick, "stick",
            STICK_BUTTON_MAP, STICK_AXIS_MAP, STICK_HAT_MAP,
        )
        print_device_report(stick_map)
        path = write_mapping(stick_map)
        saved_files.append(path)
        print(f"\n  [OK] Stick mapping saved → {path}")

    if throttle is not None:
        throttle_map = build_mapping(
            throttle, "throttle",
            THROTTLE_BUTTON_MAP, THROTTLE_AXIS_MAP, THROTTLE_HAT_MAP,
        )
        print_device_report(throttle_map)
        path = write_mapping(throttle_map)
        saved_files.append(path)
        print(f"\n  [OK] Throttle mapping saved → {path}")

    _section("SCAN COMPLETE")
    print("  The following files were written for use by hotas_dashboard.py:")
    for f in saved_files:
        print(f"    {f}")
    print()
    print("  Next step:  python3 hotas_dashboard.py")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
