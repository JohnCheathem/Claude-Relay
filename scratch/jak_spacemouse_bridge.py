#!/usr/bin/env python3
"""
SpaceMouse → OpenGOAL Bridge
Reads your 3Dconnexion SpaceMouse (left-right / forward-back pan axes only)
and emits them as a virtual Xbox360 left joystick so OpenGOAL sees it as
a real controller's left thumb stick.

Axis mapping (SpaceNavigator raw):
  state.x  = left/right pan   →  virtual left_joystick X
  state.y  = forward/back pan →  virtual left_joystick Y  (inverted)
  state.z / rotation axes     →  ignored

Settings are saved to jak_spacemouse_settings.json next to this script.

Requirements:
  pip install pyspacemouse vgamepad

On Windows: vgamepad install will prompt to install ViGEmBus driver — required.
On Linux:   Add udev rule for hidraw access (see README).
"""

import json
import math
import os
import sys
import time
import threading
import signal

try:
    import pyspacemouse
except ImportError:
    print("[ERROR] pyspacemouse not installed. Run: pip install pyspacemouse")
    sys.exit(1)

try:
    import vgamepad as vg
except ImportError:
    print("[ERROR] vgamepad not installed. Run: pip install vgamepad")
    sys.exit(1)

# ── Settings ──────────────────────────────────────────────────────────────────

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jak_spacemouse_settings.json")

DEFAULT_SETTINGS = {
    # Dead zone: ignore input below this magnitude (0.0–1.0)
    # SpaceMouse rests at 0 but drifts slightly — raise this if Jak walks on his own
    "deadzone": 0.08,

    # Sensitivity multiplier applied AFTER dead zone (1.0 = full range uses full stick)
    # Lower = less responsive at high push, good if the device feels twitchy
    "sensitivity": 1.0,

    # Exponent for the response curve.
    # 1.0 = linear (same as a normal joystick)
    # 2.0 = quadratic (slow near centre, fast at edges — good for precise walking)
    # 0.5 = sqrt (very fast near centre, tapers off — aggressive feel)
    "curve_exponent": 1.4,

    # Invert X axis (true = pushing right moves Jak left)
    "invert_x": False,

    # Invert Y axis — SpaceNavigator Y is forward = negative, so this is True by default
    "invert_y": True,

    # Poll rate in Hz — how often we read the SpaceMouse and update the virtual pad
    # 60 matches the game's frame rate. Higher = more responsive, more CPU.
    "poll_hz": 60,

    # Map the two physical buttons on the SpaceNavigator to virtual gamepad buttons
    # Valid values: "A", "B", "X", "Y", "LB", "RB", "START", "BACK", "LS", "RS", null
    "button_0_mapping": "X",
    "button_1_mapping": "B",
}

BUTTON_MAP = {
    "A":     vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B":     vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X":     vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y":     vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "LB":    vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RB":    vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "BACK":  vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "LS":    vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "RS":    vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            # Merge with defaults so new keys always exist
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except Exception as e:
            print(f"[WARN] Could not load settings ({e}), using defaults.")
    return dict(DEFAULT_SETTINGS)


def save_settings(s):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)
    print(f"[INFO] Settings saved to {SETTINGS_FILE}")


# ── Signal processing ─────────────────────────────────────────────────────────

def apply_deadzone(value, deadzone):
    """Rescale value so the dead zone region maps cleanly to 0."""
    if abs(value) < deadzone:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    rescaled = (abs(value) - deadzone) / (1.0 - deadzone)
    return sign * min(rescaled, 1.0)


def apply_curve(value, exponent):
    """Power curve: preserves sign, applies exponent to magnitude."""
    if value == 0.0:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) ** exponent)


def process_axis(raw, settings, invert_key):
    """Full signal chain: deadzone → curve → sensitivity → invert → clamp."""
    v = apply_deadzone(raw, settings["deadzone"])
    v = apply_curve(v, settings["curve_exponent"])
    v = v * settings["sensitivity"]
    if settings[invert_key]:
        v = -v
    return max(-1.0, min(1.0, v))


# ── Main bridge loop ──────────────────────────────────────────────────────────

class SpaceMouseBridge:
    def __init__(self, settings):
        self.settings = settings
        self.running = False
        self._prev_buttons = [0, 0]
        self.gamepad = None
        self.device = None

    def start(self):
        print("[INFO] Connecting to SpaceMouse...")
        try:
            self.device = pyspacemouse.open()
            if not self.device:
                raise RuntimeError("No SpaceMouse found.")
        except Exception as e:
            print(f"[ERROR] Could not open SpaceMouse: {e}")
            print("        Make sure the device is plugged in and drivers/hidraw access are set up.")
            return False

        print("[INFO] Creating virtual Xbox360 gamepad...")
        try:
            self.gamepad = vg.VX360Gamepad()
            # Wake the virtual device up with a quick button tap
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
            self.gamepad.update()
            time.sleep(0.05)
            self.gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
            self.gamepad.update()
        except Exception as e:
            print(f"[ERROR] Could not create virtual gamepad: {e}")
            print("        On Windows: make sure ViGEmBus driver is installed (runs automatically with vgamepad install).")
            return False

        print("[INFO] Bridge active. SpaceMouse → OpenGOAL left stick.")
        print("       Press Ctrl+C to stop.\n")
        self._print_settings()
        self.running = True
        return True

    def _print_settings(self):
        s = self.settings
        print(f"  Deadzone:     {s['deadzone']:.2f}")
        print(f"  Sensitivity:  {s['sensitivity']:.2f}")
        print(f"  Curve exp:    {s['curve_exponent']:.2f}")
        print(f"  Invert X:     {s['invert_x']}")
        print(f"  Invert Y:     {s['invert_y']}")
        print(f"  Poll rate:    {s['poll_hz']} Hz")
        print(f"  Button 0 →    {s['button_0_mapping'] or 'none'}")
        print(f"  Button 1 →    {s['button_1_mapping'] or 'none'}")
        print()

    def run(self):
        if not self.start():
            return

        period = 1.0 / self.settings["poll_hz"]

        try:
            while self.running:
                t0 = time.perf_counter()

                state = self.device.read()
                if state is None:
                    time.sleep(period)
                    continue

                # ── Axes ──
                # SpaceNavigator: state.x = left/right, state.y = forward/back (raw -1..1)
                x = process_axis(state.x, self.settings, "invert_x")
                y = process_axis(state.y, self.settings, "invert_y")

                self.gamepad.left_joystick_float(x_value_float=x, y_value_float=y)

                # ── Buttons ──
                btns = state.buttons if len(state.buttons) >= 2 else [0, 0]
                for i, (mapping_key, prev) in enumerate(
                    zip(["button_0_mapping", "button_1_mapping"], self._prev_buttons)
                ):
                    mapping = self.settings[mapping_key]
                    if mapping is None or mapping not in BUTTON_MAP:
                        continue
                    vg_btn = BUTTON_MAP[mapping]
                    curr = btns[i] if i < len(btns) else 0
                    if curr and not prev:
                        self.gamepad.press_button(vg_btn)
                    elif not curr and prev:
                        self.gamepad.release_button(vg_btn)
                self._prev_buttons = list(btns[:2]) if len(btns) >= 2 else [0, 0]

                self.gamepad.update()

                # Optional live readout — uncomment for debugging
                # print(f"\r  raw x={state.x:+.3f} y={state.y:+.3f}  →  virt x={x:+.3f} y={y:+.3f}   ", end="")

                # Maintain poll rate
                elapsed = time.perf_counter() - t0
                sleep = period - elapsed
                if sleep > 0:
                    time.sleep(sleep)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        self.running = False
        print("\n[INFO] Shutting down bridge.")
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
        if self.gamepad:
            try:
                self.gamepad.left_joystick_float(0.0, 0.0)
                self.gamepad.update()
            except Exception:
                pass
        print("[INFO] Done.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def print_help():
    print("""
jak_spacemouse_bridge.py — SpaceMouse left-stick bridge for OpenGOAL

Usage:
  python jak_spacemouse_bridge.py             Run the bridge
  python jak_spacemouse_bridge.py --tune      Interactive tuning mode
  python jak_spacemouse_bridge.py --reset     Reset settings to defaults

Settings file: jak_spacemouse_settings.json (same folder as this script)
""")


def interactive_tune(settings):
    """Simple interactive tuner — lets you tweak each value and see the effect live."""
    print("\n=== Interactive Tune Mode ===")
    print("Change settings one at a time. Press Enter to keep current value.\n")

    fields = [
        ("deadzone",        "Dead zone (0.0–0.3, default 0.08): "),
        ("sensitivity",     "Sensitivity (0.1–2.0, default 1.0): "),
        ("curve_exponent",  "Curve exponent (0.5=aggressive, 1.0=linear, 2.0=precise, default 1.4): "),
        ("invert_x",        "Invert X? (y/n, default n): "),
        ("invert_y",        "Invert Y? (y/n, default y): "),
        ("poll_hz",         "Poll rate Hz (30–120, default 60): "),
        ("button_0_mapping","Button LEFT → [A/B/X/Y/LB/RB/START/BACK/LS/RS/none]: "),
        ("button_1_mapping","Button RIGHT → [A/B/X/Y/LB/RB/START/BACK/LS/RS/none]: "),
    ]

    bool_fields = {"invert_x", "invert_y"}
    int_fields  = {"poll_hz"}
    float_fields = {"deadzone", "sensitivity", "curve_exponent"}

    for key, prompt in fields:
        current = settings[key]
        raw = input(f"{prompt}[{current}] ").strip()
        if not raw:
            continue
        try:
            if key in bool_fields:
                settings[key] = raw.lower() in ("y", "yes", "true", "1")
            elif key in int_fields:
                settings[key] = int(raw)
            elif key in float_fields:
                settings[key] = float(raw)
            else:
                # button mapping
                val = raw.upper() if raw.lower() != "none" else None
                if val is None or val in BUTTON_MAP:
                    settings[key] = val
                else:
                    print(f"  [WARN] Unknown button '{raw}', keeping {current}")
        except ValueError:
            print(f"  [WARN] Invalid value '{raw}', keeping {current}")

    save_settings(settings)
    return settings


def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        return

    settings = load_settings()

    if "--reset" in args:
        settings = dict(DEFAULT_SETTINGS)
        save_settings(settings)
        print("[INFO] Settings reset to defaults.")
        return

    if "--tune" in args:
        settings = interactive_tune(settings)
        print("[INFO] Settings updated. Run without --tune to start the bridge.")
        return

    bridge = SpaceMouseBridge(settings)
    bridge.run()


if __name__ == "__main__":
    main()
