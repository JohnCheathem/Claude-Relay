# SpaceMouse → OpenGOAL Bridge

Run your 3Dconnexion SpaceMouse as Jak's left analog stick in OpenGOAL Jak 1.
No engine modifications required — the bridge creates a virtual Xbox360 controller
that OpenGOAL picks up natively.

## How it works

```
SpaceMouse (USB HID)
    ↓  pyspacemouse (raw HID read, no driver needed)
    ↓  signal processing (dead zone → curve → sensitivity)
    ↓  vgamepad (ViGEmBus virtual XInput controller)
    ↓
OpenGOAL sees a normal Xbox360 left stick
```

Your SpaceMouse's X axis (push left/right) becomes Jak's left-right movement.
Your SpaceMouse's Y axis (push forward/back) becomes Jak's forward/back movement.
Push pressure is preserved — gentle push = slow walk, full push = full run.
Z axis (up/down lift) and all rotation axes are ignored.

The 2 buttons on your SpaceNavigator are mapped to virtual gamepad buttons
(default: button 0 → X, button 1 → B). Change in settings.

## Requirements

- Python 3.8+
- `pip install pyspacemouse vgamepad`
- **Windows only for vgamepad**: during `pip install vgamepad`, the ViGEmBus
  driver installer will run automatically — accept it.
- **Linux**: Add a udev rule so Python can access the HID device without sudo:
  ```
  echo 'KERNEL=="hidraw*", SUBSYSTEM=="hidraw", MODE="0664", GROUP="plugdev"' \
    | sudo tee /etc/udev/rules.d/99-hidraw-permissions.rules
  sudo usermod -aG plugdev $USER
  # then log out and back in
  ```
  Note: vgamepad on Linux is experimental. You may need to use
  `uinput` or a different virtual gamepad method on Linux.

## Usage

### First time — tune your settings:
```
python jak_spacemouse_bridge.py --tune
```

### Run the bridge:
```
python jak_spacemouse_bridge.py
```

Open OpenGOAL, go to controller settings and make sure the virtual Xbox controller
is assigned to port 0. Camera stays on mouse. The SpaceMouse controls movement only.

### Reset settings to defaults:
```
python jak_spacemouse_bridge.py --reset
```

## Settings reference

Settings are stored in `jak_spacemouse_settings.json` next to the script.

| Setting | Default | Description |
|---|---|---|
| `deadzone` | 0.08 | Ignore input below this level. Raise to 0.12–0.15 if Jak drifts when you let go. |
| `sensitivity` | 1.0 | Multiplier on top of everything else. Lower if the device is twitchy. |
| `curve_exponent` | 1.4 | Response curve. 1.0=linear, 2.0=very precise at centre, 0.8=aggressive. |
| `invert_x` | false | Flip left/right. |
| `invert_y` | true | SpaceNavigator Y is naturally inverted — leave this true. |
| `poll_hz` | 60 | How often the bridge updates per second. |
| `button_0_mapping` | "X" | Left button → virtual gamepad button. |
| `button_1_mapping` | "B" | Right button → virtual gamepad button. |

## Tuning tips

**Jak walks slowly at max push:**
→ Lower `curve_exponent` (try 1.0 or 0.9)
→ Or increase `sensitivity` to 1.2

**Jak drifts when you let go:**
→ Raise `deadzone` (try 0.12–0.18)

**Too sensitive / hard to walk slowly:**
→ Raise `curve_exponent` (try 1.8–2.0)
→ This makes the centre zone very precise and reserves fast movement for full pushes

**Direction feels off:**
→ Toggle `invert_x` or `invert_y` in --tune

## OpenGOAL controller setup

1. Start the bridge first (`python jak_spacemouse_bridge.py`)
2. Launch OpenGOAL
3. In the settings menu, go to Controller → Port 0
4. The virtual Xbox360 controller should appear — assign it to Port 0
5. The left stick is now your SpaceMouse. Camera stays on mouse as usual.

If OpenGOAL was already open when you started the bridge, disconnect/reconnect
the virtual controller or restart OpenGOAL.
