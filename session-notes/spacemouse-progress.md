# SpaceMouse in OpenGOAL — Session Notes

## Goal
Make a 3Dconnexion SpaceMouse work as a camera/movement controller in Jak 1 via OpenGOAL.

## Research Summary

### How OpenGOAL handles input (SDL3-based)
- Entry point: `game/system/hid/input_manager.cpp` / `input_manager.h`
- Devices: `game/system/hid/devices/` — `game_controller.*`, `keyboard.*`, `mouse.*`, `input_device.h`
- All devices write to `PadData` (4 analog axes: LEFT_X, LEFT_Y, RIGHT_X, RIGHT_Y + 16 buttons)
- GameController wraps `SDL_Gamepad` API (high-level)
- **Critical blocker:** `refresh_device_list()` explicitly calls `SDL_IsGamepad()` and SKIPs any device that returns false. SpaceMouse is NOT a gamepad — it has no SDL gamepad mapping. It will be silently skipped.

### How SpaceMouse exposes itself
- USB HID device: vendor 0x046D (Logitech/3Dconnexion) or 0x256F (3Dconnexion newer)
- 6 axes: TX, TY, TZ (translation), RX, RY, RZ (rotation)
- NOT a gamepad. SDL sees it as a raw joystick (`SDL_IsGamepad()` = false).
- On Windows: may or may not appear depending on whether 3DxWare driver is active
- On Linux: appears as `/dev/hidraw*`, needs udev rule or spacenavd

### The fix — two approaches

#### Option A: SDL Gamepad Mapping string (easiest, no C++ changes)
Add an entry to `game/assets/sdl_controller_db.txt` that maps SpaceMouse as a gamepad:
```
<guid>,3Dconnexion SpaceMouse,platform:Windows,a:b0,b:b1,leftx:a0,lefty:a1,rightx:a3,righty:a4,...
```
SDL's `SDL_AddGamepadMappingsFromFile()` is already called at startup. If this mapping exists,
`SDL_IsGamepad()` will return true for the SpaceMouse and it'll be treated as a standard controller.
Pros: zero C++ changes. Cons: axis mapping is limited to what gamepad layout allows (no twist axis).

#### Option B: SpaceMouseDevice class (proper, 6-DOF capable)
Create `game/system/hid/devices/spacemouse.h` and `.cpp`, analogous to `mouse.cpp`.
- Listen for `SDL_EVENT_JOYSTICK_ADDED` with device name containing "3Dconnexion" or matching VID
- Open with `SDL_OpenJoystick()` (NOT `SDL_OpenGamepad()`)
- Read 6 axes via `SDL_EVENT_JOYSTICK_AXIS_MOTION` / `SDL_GetJoystickAxis()`
- Map axes to PadData:
  - TX (left-right pan) → analog_data[LEFT_X]
  - TY (forward-back) → analog_data[LEFT_Y]  (player movement)
  - RX (tilt) → analog_data[RIGHT_X]         (camera)
  - RY (tilt) → analog_data[RIGHT_Y]         (camera)
  - TZ (up-down) and RZ (twist) → unmapped or bound to buttons/L2R2
- Register in `InputManager` alongside keyboard/mouse

#### Option C: SDL Virtual Joystick bridge (external process)
A small Python script reads SpaceMouse via hidapi/pyspacemouse and creates an SDL virtual joystick
that looks like a standard gamepad. OpenGOAL picks it up natively. No engine changes needed.
Most portable and doesn't require recompiling OpenGOAL.

## Recommended Approach
**Start with Option A** (gamepad mapping string) — test if SpaceMouse even shows up via SDL.
If that works → Option B is the clean long-term solution.
Option C is good for users who can't compile OpenGOAL.

## SpaceMouse VID/PID reference
| Device | VID | PID |
|--------|-----|-----|
| SpaceNavigator | 046d | c626 |
| SpaceMouse Compact | 256f | c635 |
| SpaceMouse Pro | 046d | c62b |
| SpaceMouse Enterprise | 256f | c633 |
| Universal Receiver | 256f | c652 |

## Axis layout (SDL raw joystick axis indices)
Typically: axis 0=TX, 1=TY, 2=TZ, 3=RX, 4=RY, 5=RZ
Range: SDL_GetJoystickAxis → -32768 to +32767 → needs remap to 0–255 for PadData (neutral=127)

## Files to modify (Option B)
- `game/system/hid/devices/spacemouse.h` — NEW
- `game/system/hid/devices/spacemouse.cpp` — NEW
- `game/system/hid/input_manager.h` — add SpaceMouseDevice member
- `game/system/hid/input_manager.cpp` — detect/open in refresh_device_list, poll in process_sdl_event
- `game/assets/sdl_controller_db.txt` — Option A mapping (no C++)

## Status
- [ ] Test Option A: add SDL mapping string, see if device appears
- [ ] If not: implement Option B SpaceMouseDevice
- [ ] Option C: Python bridge script

## Notes
- OpenGOAL uses SDL3 (not SDL2). `SDL_OpenJoystick` is available and works.
- InputManager constructor already calls `SDL_InitSubSystem(SDL_INIT_GAMEPAD)` — this also inits joystick subsystem, so joystick events will fire.
- `process_sdl_event()` already loops over all events — just need to handle `SDL_EVENT_JOYSTICK_AXIS_MOTION` for non-gamepad devices.
- `PadData::analog_data` is `std::array<int, 4>` internally (clamped to 0–255 when read). Neutral = 127.
- SpaceMouse axis scale: SDL gives -32768 to 32767. Map: `(val / 32767.0f * 127) + 127` clamped to [0,255].
