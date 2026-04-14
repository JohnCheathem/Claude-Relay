# SpaceMouse in OpenGOAL — Session Notes

## Goal
Make a 3Dconnexion SpaceMouse (SpaceNavigator, 2-button knob version) work as
Jak's left analog stick in OpenGOAL Jak 1. Camera stays on mouse. Movement only.
Pressure sensitivity preserved. Settings UI to tune feel.

## Device
SpaceNavigator (2 buttons, knob only). VID 0x046D, PID 0xC626.
Axes: x=left/right, y=forward/back (these are the only two we use).
Ignore z (up/down lift) and all rotation axes.

## What was built
Three approaches researched and partially implemented:

### Option A — SDL Gamepad Mapping string (NOT YET TESTED)
Add a line to `game/assets/sdl_controller_db.txt` mapping SpaceNavigator as a gamepad.
OpenGOAL loads this file on startup via SDL_AddGamepadMappingsFromFile().
Zero C++ changes, zero installs. Just a text file edit.
**This was never tried — should be the first thing to test next session.**

### Option B — SpaceMouseDevice C++ class (designed, not built)
New device class in game/system/hid/devices/spacemouse.cpp
Opens via SDL_OpenJoystick() (bypasses gamepad gate).
Maps x/y axes to PadData LEFT_X/LEFT_Y.
Requires OpenGOAL recompile.

### Option C — Python bridge script (built, works in theory, user can't run it)
`scratch/jak_spacemouse_bridge.py` — CLI script
`scratch/jak_spacemouse_app.py` — tkinter GUI app
Uses pyspacemouse (raw HID) + vgamepad (ViGEmBus virtual Xbox360 controller).
Signal chain: deadzone → power curve → sensitivity → invert → PadData.
**Blocked: user's Python installation is broken (multiple conflicting versions,**
**py.exe itself returns "Python was not found"). Script is correct, env is broken.**

## Why Option C failed
- User has multiple Python versions installed, all conflicting
- `py` command in Downloads folder shadowing C:\Windows\py.exe
- Even C:\Windows\py.exe returns "Python was not found"
- Script itself is verified correct (tested on Linux, all classes instantiate OK)
- Fix: uninstall all Python, fresh install from python.org with "Add to PATH" checked

## Next session options
1. Try Option A first — SDL mapping string, no installs needed
2. C# WinForms exe (source in scratch/SpaceMouseBridge/) — needs .NET SDK
3. Fix Python env and run jak_spacemouse_app.py

## Signal processing (for any implementation)
- Deadzone: ignore input below threshold, rescale remainder to 0-1
- Curve: power function (exponent 1.4 default) for pressure sensitivity
- Sensitivity: flat multiplier
- Invert Y: SpaceNavigator Y is naturally inverted

## Settings defaults
deadzone: 0.08, sensitivity: 1.0, curve_exponent: 1.4,
invert_x: false, invert_y: true, poll_hz: 60,
button_0: X, button_1: B

## OpenGOAL input system key facts
- input_manager.cpp: refresh_device_list() skips non-gamepad devices (SDL_IsGamepad check)
- PadData: 4 analog axes (LEFT_X, LEFT_Y, RIGHT_X, RIGHT_Y), range 0-255, neutral=127
- SDL3 raw joystick API available and working, just not hooked up for non-gamepad devices
- sdl_controller_db.txt loaded at startup — Option A entry point
