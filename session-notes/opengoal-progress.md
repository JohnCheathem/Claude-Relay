# OpenGOAL Blender Addon — Session Progress

## Status: WORKING ✅ (camera trigger works, rotation export is BROKEN)

## Active Branch: `feature/camera`
Install `addons/opengoal_tools.py` from this branch for camera work.

---

## Camera System — What Works

### Trigger volume ✅
- Walk into CAMVOL mesh → camera switches → walk out → camera reverts
- Entity-based: `camera-trigger` actor births on level load, no nREPL needed
- Works with manual level loading AND Build & Play

### Camera placement ✅
- `camera-marker` entity exports correctly to actors array
- `entity-by-name` finds it → `change-to-entity-by-name` works
- Level doesn't crash

### Blender UI ✅
- Add Camera → places Blender CAMERA object (Numpad-0 to preview)
- Add Volume → places CAMVOL wireframe cube
- Shift-select both → Link Trigger Volume
- Panel shows live rotation wxyz for debugging

---

## Camera Rotation Export — BROKEN ❌

### The core problem (plain English)
Blender and the game have different coordinate systems:
- Blender: Z=up, Y=forward into scene
- Game: Y=up, Z=forward into scene

A camera at zero rotation in Blender points in a different real-world direction
than a camera at zero rotation in the game. The quaternion that represents
"looking forward" is different in each system.

### What the user confirmed (ground truth)
- User's camera at **zero rotation** in Blender → game cam points **forward** (wrong)
- User manually rotates camera **Y+180** in Blender → game cam points **correctly**
- This has been consistent across multiple test sessions

### What we've tried (all failed)
1. Raw component remap: `qx=-bl.x, qy=bl.z, qz=-bl.y, qw=bl.w`
2. Component remap + conjugate (negate xyz)
3. Pre-multiply by flip_y (world space)
4. Post-multiply by flip_y (local space): `q @ flip_y`
5. Left-multiply by -90° X correction
6. Combined -90X + Y180

Every attempt either produces the same wrong result or a different wrong result.

### Why it's hard
The game's `cam-slave-get-rot` calls `quaternion->matrix(entity.quat)` and stores
the result as `inv-mat` (camera-to-world matrix). The camera looks along -Z column
of that matrix. The quaternion→matrix math is standard, but determining the RIGHT
quaternion to produce the correct orientation requires knowing the exact relationship
between Blender's quaternion representation and the game's coordinate frame.

The math appears correct in isolation but produces wrong results in practice,
suggesting either:
- The JSONC quat field component order is different from what we think [x,y,z,w]
- The game's `quaternion->matrix` uses a different convention (row vs column major)
- There's a coordinate handedness issue we're not accounting for correctly
- The `inv-mat` usage in cam-combiner does something we haven't traced fully

### Diagnostic approach (not yet tried)
Send REPL commands to query the actual camera matrix in-game after switching:
```lisp
;; After camera switches, read the inv-mat to see what orientation it has
(-> *camera-combiner* inv-camera-rot vector 0)  ; right vector
(-> *camera-combiner* inv-camera-rot vector 1)  ; up vector  
(-> *camera-combiner* inv-camera-rot vector 2)  ; forward vector
```
This would tell us exactly what matrix the game computed from our quat,
and we can work backwards to what quat we should have sent.

Also useful: print the raw quat from the entity after level load:
```lisp
(let ((e (entity-by-name "CAMERA_0")))
  (-> e quat))
```

### Current state of the code
`addons/opengoal_tools.py` on `feature/camera`, current rotation code:
```python
q = cam_obj.matrix_world.to_quaternion()
flip = mathutils.Quaternion((0, 1, 0), math.radians(180))
gq = q @ flip
qx, qy, qz, qw = gq.x, gq.y, gq.z, gq.w
```
This is the latest attempt (Y+180 post-multiply). Also wrong.

---

## Bug History (camera system)

| Bug | Root cause | Fix |
|---|---|---|
| Art group not found | `camera-tracker` etype doesn't exist | Define `camera-marker` in obs.gc |
| Level crash on load | `process-drawable-from-entity!` dereferences null root | `(set! (-> this root) (new 'process 'trsqv))` first |
| Trigger never fires (manual load) | nREPL obs_init call only runs via Build & Play | Replaced with `camera-trigger` entity-actor |
| Volume visible/collidable | dict-style props export as JSON bool, C++ reads as 0 | Use registered `BoolProperty` (`vol.set_invisible = True`) |
| Camera rotation wrong | See above — unresolved | — |

---

## Architecture (correct parts)

### obs.gc defines two types:
```lisp
;; camera-marker: inert, holds position/rotation
(deftype camera-marker (process-drawable) () (:states camera-marker-idle))
(defmethod init-from-entity! ((this camera-marker) (arg0 entity-actor))
  (set! (-> this root) (new 'process 'trsqv))
  (process-drawable-from-entity! this arg0)
  (go camera-marker-idle) (none))

;; camera-trigger: AABB volume, polls player position each frame
(deftype camera-trigger (process-drawable)
  ((cam-name string :offset 176) (xmin float :offset 180) ... (inside symbol :offset 204))
  :heap-base #x60 :size-assert #xd0)
(defmethod init-from-entity! ((this camera-trigger) (arg0 entity-actor))
  (set! (-> this root) (new 'process 'trsqv))
  (process-drawable-from-entity! this arg0)
  (set! (-> this cam-name) (res-lump-struct arg0 'cam-name string))
  (set! (-> this xmin) (res-lump-float arg0 'bound-xmin))
  ... go camera-trigger-active)
```

### JSONC format:
```jsonc
// Camera marker (holds position + rotation)
{ "trans": [gx,gy,gz], "etype": "camera-marker", "quat": [qx,qy,qz,qw],
  "lump": { "name": "CAMERA_0", "interpTime": ["float", 1.0] } }

// Camera trigger (AABB volume → switches camera)
{ "trans": [cx,cy,cz], "etype": "camera-trigger",
  "lump": { "name": "camtrig-camera_0", "cam-name": "CAMERA_0",
            "bound-xmin": ["meters", -5.0], "bound-xmax": ["meters", 5.0], ... } }
```

### Key source references:
- `cam-slave-get-rot` → `camera.gc:87` — reads entity-actor.quat, calls quaternion->matrix
- `quaternion->matrix` stores into `tracking.inv-mat` (cam-rotation-tracker at offset 0)
- `cam-combiner` copies `slave[0].tracking.inv-mat` → `self.inv-camera-rot`
- `cam-update` multiplies view frustum corners by `inv-camera-rot`
- `entity-by-name` searches actors array first → our camera-marker IS found

### Coordinate system:
- Position remap: `gx=bl.x, gy=bl.z, gz=-bl.y`
- Quaternion: unknown correct remap (the broken part)

---

## Files
- `addons/opengoal_tools.py` on `feature/camera`
- `knowledge-base/opengoal/camera-system.md` — full research notes
