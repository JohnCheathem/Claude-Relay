# OpenGOAL Blender Addon — Session Progress

## Status: CAMERA ROTATION STILL BROKEN — need in-game diagnostics

## Active Branch: `feature/camera`

---

## The Situation (Honest)

We have spent 3+ hours across multiple sessions trying to fix camera rotation by reading
source code and doing math. Every attempt has been wrong. We are going in circles.

The fundamental problem: **we have never read back what the game actually produces.**
All math has been done blind. Without ground truth from the running game, we cannot solve this.

---

## What WORKS ✅
- Trigger volume fires correctly (walk in/out = camera switch/revert)
- Camera entity is found by name (`entity-by-name` works)
- Camera POSITION is correct
- Camera SWITCH happens (game enters cam-fixed state)

## What is BROKEN ❌
- Camera rotation/orientation is always wrong
- 6 distinct attempts, all failed

---

## Attempt History (all failed)

| # | Approach | Code | Result |
|---|---|---|---|
| 1 | Raw component remap | `qx=bl.x, qy=bl.z, qz=-bl.y, qw=bl.w` | Wrong direction |
| 2 | Remap + conjugate | negate xyz | Different wrong |
| 3 | Pre-multiply flip_y | `q = flip_y @ q` | Wrong |
| 4 | Post-multiply flip_y | `gq = q @ flip_y` | Wrong (but manual Y+180 in BL "helps") |
| 5 | Component remap only | `qx=q.x, qy=q.z, qz=-q.y, qw=q.w` | Correct direction, upside down |
| 6 | Look-dir + world-up | Extract -local_Z, remap, build from world-down | "Did not work" |

---

## The Plan: Diagnostics First

**See `scratch/camera-diagnostics.md` for the full nREPL command suite.**

The key commands:
1. Read entity quat after level load — confirm export is correct
2. Read `*camera-combiner* inv-camera-rot` AFTER triggering custom cam — this is ground truth
3. Manually set known quats via nREPL and read back what matrix they produce
4. Find a vanilla game camera entity and read its quat

Once we have Step 2, we can reverse-engineer the correct formula in minutes.

---

## Alternative: "interesting" lump (bypass quat entirely)

Add `"interesting": ["vector3m", [x, y, z]]` to the camera lump.
Camera looks at that world position. No quaternion needed.
This is the escape hatch if diagnostics are too painful.

Code to add to addon (Blender UI: "Look At" empty object):
```python
if cam_obj.get("og_cam_look_at"):
    look_obj = scene.objects.get(cam_obj["og_cam_look_at"])
    if look_obj:
        lt = look_obj.matrix_world.translation
        lump["interesting"] = ["vector3m", [round(lt.x,4), round(lt.z,4), round(-lt.y,4)]]
```

---

## Architecture Reference

### obs.gc types:
```lisp
(deftype camera-marker (process-drawable) () (:states camera-marker-idle))
(deftype camera-trigger (process-drawable)
  ((cam-name string) (xmin float) (xmax float) (ymin float) (ymax float) (zmin float) (zmax float) (inside symbol)))
```

### JSONC format:
```jsonc
{ "trans": [gx,gy,gz], "etype": "camera-marker", "quat": [qx,qy,qz,qw],
  "lump": { "name": "CAMERA_0", "interpTime": ["float", 1.0] } }
{ "trans": [cx,cy,cz], "etype": "camera-trigger",
  "lump": { "name": "camtrig-camera_0", "cam-name": "CAMERA_0",
            "bound-xmin": ["meters", -5.0], ... } }
```

### Key source:
- `cam-slave-get-rot` → `camera.gc:87`
- `quaternion->matrix` → `quaternion.gc:329` (VU0 assembly, hard to verify)
- `forward-down->inv-matrix` → `geometry.gc:255`
- `vector_from_json` → `common/Entity.cpp:32` reads [x,y,z,w] straight
- Coord remap position: `gx=bl.x, gy=bl.z, gz=-bl.y`

### Files:
- `addons/opengoal_tools.py` on `feature/camera`
- `scratch/camera-diagnostics.md` — nREPL commands to run
- `knowledge-base/opengoal/camera-system.md` — full research notes
