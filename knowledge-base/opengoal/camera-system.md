# OpenGOAL Camera System — Research Notes

**Status:** Research complete (iterations 1–3)  
**Branch:** `feature/camera`  
**Last updated:** 2026-04-07

---

## 1. Architecture Overview

The camera system has four main components:

| Component | Type | Role |
|---|---|---|
| `*camera*` | `camera-master` process | Manages camera slaves, handles events, runs region checks |
| `camera-slave` | sub-process of camera-master | Implements a specific camera mode (fixed, follow, etc.) |
| `*camera-combiner*` | `camera-combiner` process | Blends between two slaves during transitions |
| `*camera-engine*` | connection list | Registry of all active `entity-camera` objects |

---

## 2. camera-master Event API

All sent via `(send-event *camera* 'EVENT_NAME args...)`

| Event | Args | Effect |
|---|---|---|
| `'change-to-entity-by-name` | `"camera-name"` (string) | Switch to named camera entity — **main entry point** |
| `'clear-entity` | none | Return to default follow camera |
| `'change-state` | state, blend-frames | Switch to a camera state directly |
| `'teleport-to-transformq` | transformq pointer | Instantly move camera to transform |
| `'set-fov` | float (game angle units) | Change field of view |
| `'point-of-interest` | vector or `#f` | Point camera at world position |
| `'no-intro` | none | Skip intro animation (blend in immediately) |
| `'force-blend` | time | Force a specific blend time |
| `'teleport` | none | Instant cut with no blend |

---

## 3. Camera States

Determined by `cam-state-from-entity` reading lump data:

| Lump present | State | Behaviour |
|---|---|---|
| `pivot` vector | `cam-circular` | Camera orbits a fixed world point, follows player angle |
| `align` vector | `cam-standoff-read-entity` → `cam-standoff` | Fixed offset from player — **side-scroller** |
| `campath`/`campath-k` | `cam-spline` | Camera follows a spline path |
| `stringMaxLength > 0` | `*camera-base-mode*` (cam-string) | Normal third-person follow, constrained |
| nothing above | `cam-fixed-read-entity` → `cam-fixed` | Locked to entity position/rotation |

### How `cam-state-from-entity` decides (from `camera.gc:101`):
```lisp
(cond
  ((not arg0) #f)
  ((res-lump-struct arg0 'pivot structure) cam-circular)
  ((res-lump-struct arg0 'align structure) cam-standoff-read-entity)
  ((get-curve-data! arg0 s5-0 'campath 'campath-k -1000000000.0) cam-spline)
  ((< 0.0 (cam-slave-get-float arg0 'stringMaxLength 0.0)) *camera-base-mode*)
  (else cam-fixed-read-entity))
```

---

## 4. What Each State Reads from Entity Lumps

### `cam-fixed-read-entity` (locked camera)
- `trans` → camera world position (reads entity-actor.trans directly)
- `quat` → camera rotation (reads entity-actor.quat directly)  
- `fov` → optional, in game angle units (65536 = 360°)
- `interesting` → optional vector3m, point camera looks at
- `interpTime` → blend duration in seconds

### `cam-standoff-read-entity` (side-scroller)
- `trans` → camera world position (vector3m lump overrides entity.trans)
- `align` → player world anchor position (vector3m)
- `pivot_pt = trans - align` — camera offset relative to player
- `fov`, `tiltAdjust`, `flags`, `interpTime` — optional

### `cam-circular` (orbit)
- `pivot` → world position of orbit center (vector3m)
- `trans` → starting camera position (vector3m)
- `pivot_rad` computed from `length(trans - pivot)`
- `maxAngle`, `focalPull`, `fov`, `tiltAdjust` — optional

### All states support:
- `interesting` → `["vector3m", [x,y,z]]` — world point to look at
- `interpTime` → `["float", seconds]` — blend-in time
- `fov` → `["degrees", angle]` — field of view override
- `tiltAdjust` → `["degrees", angle]` — camera tilt adjustment
- `flags` → `["int32", value]` — bitmask options

---

## 5. Entity Structure: Actors Array Approach

### Why NOT entity-camera in bsp.cameras array
`LevelFile.cpp` line 155 has the cameras array write **commented out**:
```cpp
//(cameras  (array entity-camera)  :offset-assert 116)
```
So `reset-cameras()` and `master-check-regions()` can never find native entity-cameras in custom levels.

### Why actors array works
`entity-by-name` (used by `change-to-entity-by-name`) searches:
1. `bsp.actors` — **searched first** ✓  
2. `bsp.ambients`  
3. `bsp.cameras` (empty for custom levels)

Camera entities placed in actors array ARE found by `change-to-entity-by-name`.

### Required JSONC fields
```jsonc
{
  "trans": [gx, gy, gz],          // world position in meters
  "etype": "camera-tracker",       // safe type with no init-from-entity!
  "game_task": 0,
  "quat": [qx, qy, qz, qw],       // rotation quaternion (Blender -> game)
  "bsphere": [gx, gy, gz, 30.0],  // bounding sphere (radius doesn't matter)
  "lump": {
    "name": "camera-0"            // MUST match name used in change-to-entity-by-name
    // Optional extras below
  }
}
```

---

## 6. Complete JSONC Examples

### Fixed Camera (locked position/rotation)
```jsonc
{
  "trans": [0.0, 5.0, 10.0],
  "etype": "camera-tracker",
  "game_task": 0,
  "quat": [0, 0, 0, 1],
  "bsphere": [0.0, 5.0, 10.0, 30.0],
  "lump": {
    "name": "camera-0",
    "interpTime": ["float", 1.0]
  }
}
```

### Side-Scroller Camera (tracks player at fixed offset)
```jsonc
{
  "trans": [0.0, 5.0, 15.0],
  "etype": "camera-tracker",
  "game_task": 0,
  "quat": [0, 0, 0, 1],
  "bsphere": [0.0, 5.0, 15.0, 30.0],
  "lump": {
    "name": "camera-side",
    "trans": ["vector3m", [0.0, 5.0, 15.0]],
    "align": ["vector3m", [0.0, 5.0,  0.0]],
    "interpTime": ["float", 1.5]
  }
}
```
`pivot_pt = trans - align = (0,0,15)` — camera stays 15m in front of player.

### Orbit Camera (rotates around a world point)
```jsonc
{
  "trans": [10.0, 8.0, 0.0],
  "etype": "camera-tracker",
  "game_task": 0,
  "quat": [0, 0, 0, 1],
  "bsphere": [10.0, 8.0, 0.0, 30.0],
  "lump": {
    "name": "camera-orbit",
    "pivot": ["vector3m", [0.0, 3.0, 0.0]],
    "trans": ["vector3m", [10.0, 8.0, 0.0]],
    "maxAngle": ["degrees", 30.0],
    "interpTime": ["float", 1.0]
  }
}
```

### Custom FOV Camera
```jsonc
{
  "lump": {
    "name": "camera-wide",
    "fov": ["degrees", 75.0],
    "interpTime": ["float", 0.5]
  }
}
```

---

## 7. Coordinate System Conversions

| Property | Blender → JSONC trans | Blender → JSONC quat |
|---|---|---|
| Actor trans | `[bx, bz, -by]` | `[bx, bz, -by, bw]` (swap y/z, negate new y) |
| Lump `trans` | `["vector3m", [bx, bz, -by]]` | |
| Lump `align` | `["vector3m", [bx, bz, -by]]` | |
| Lump `pivot` | `["vector3m", [bx, bz, -by]]` | |

**Rotation for fixed camera:**  
Blender: object `-Z` = look direction  
Game: camera `-Z` = look direction  
Quaternion conversion: apply an additional -90° rotation on X to convert from Blender camera convention to game convention. (Exact: rotate by 90° around X before exporting quat.)

---

## 8. Trigger Volume: obs.gc vs Native vol Lump

### Current Approach: obs.gc AABB (what we implemented)
```lisp
;; Spawned after level load via goalc_send()
(process-spawn-function process
  (lambda ()
    (let ((inside #f))
      (loop
        (when *target*
          (let* ((pos (-> *target* control trans))
                 (in-vol (and
                   (< gx0_units (-> pos x)) (< (-> pos x) gx1_units)
                   (< gy0_units (-> pos y)) (< (-> pos y) gy1_units)
                   (< gz0_units (-> pos z)) (< (-> pos z) gz1_units))))
            (cond
              ((and in-vol (not inside))
               (set! inside #t)
               (send-event *camera* 'change-to-entity-by-name "camera-0"))
              ((and (not in-vol) inside)
               (set! inside #f)
               (send-event *camera* 'clear-entity)))))
        (suspend))))
  :to *entity-pool*)
```
✅ Works now. Limitations: AABB only, no rotation support, spawned via nREPL after load.

### Future Approach: Native vol Lump (engine-driven)
Requires LevelFile.cpp cameras array fix (PR to OpenGOAL upstream).  
Format: 6 half-space plane equations on the camera entity in bsp.cameras.

---

## 9. vol/pvol Lump Format (for future native approach)

**Runtime check** (`in-cam-entity-volume?`):  
Each vector in the `vol`/`pvol` array is a **half-space plane equation**:  
- `xyz` = inward unit normal  
- `w` = signed distance offset in **meters** (multiplied by 4096 by C++ loader)  
- Point is INSIDE if `dot(pos, normal) - w ≤ tolerance` for ALL planes

**⚠️ Bug in current scratch code:** The `vol` lump is written with 8 raw bounding-box corner points — this is wrong. The runtime expects plane equations.

### Correct AABB → plane equations (Python):
```python
def aabb_to_vol_planes(b_min, b_max):
    """b_min/b_max in GAME space meters (after Blender coord conversion)"""
    mn = (min(b_min[i], b_max[i]) for i in range(3))
    mx = (max(b_min[i], b_max[i]) for i in range(3))
    mn = tuple(min(b_min[i], b_max[i]) for i in range(3))
    mx = tuple(max(b_min[i], b_max[i]) for i in range(3))
    return [
        [ 1.0,  0.0,  0.0,  mx[0]],  # +X
        [-1.0,  0.0,  0.0, -mn[0]],  # -X
        [ 0.0,  1.0,  0.0,  mx[1]],  # +Y
        [ 0.0, -1.0,  0.0, -mn[1]],  # -Y
        [ 0.0,  0.0,  1.0,  mx[2]],  # +Z
        [ 0.0,  0.0, -1.0, -mn[2]],  # -Z
    ]
```

### OBB (rotated box) approach for Blender meshes:
```python
import mathutils
def obb_to_vol_planes(obj):
    """Generate vol planes from a Blender mesh object (supports rotation)."""
    rot = obj.matrix_world.to_3x3().normalized()
    center_bl = obj.matrix_world.translation
    cx, cy, cz = center_bl.x, center_bl.z, -center_bl.y  # Blender->game
    half = [d / 2.0 for d in obj.dimensions]  # local half-extents
    planes = []
    # Each local axis (Blender) -> game space
    axes_bl = [rot.col[0], rot.col[2], -rot.col[1]]  # X,Y,Z -> game X,Y,Z
    for i, ax in enumerate(axes_bl):
        n = [ax.x, ax.y, ax.z]  # already in game space
        c_proj = n[0]*cx + n[1]*cy + n[2]*cz
        planes.append([n[0],  n[1],  n[2],  c_proj + half[i]])
        planes.append([-n[0], -n[1], -n[2], -(c_proj - half[i])])
    return planes
```

---

## 10. Current Implementation Status

### What works (scratch build):
- ✅ Camera entities exported as `entity-actor` in actors array
- ✅ `change-to-entity-by-name` / `clear-entity` events sent correctly  
- ✅ AABB trigger volumes via obs.gc spawned after level load
- ✅ Basic GOAL process trigger loop structure

### Known bugs to fix:
- ❌ `vol` lump format wrong (8 corners instead of 6 plane equations) — low priority, not used by runtime yet
- ❌ Camera rotation export may be incorrect (Blender cam convention vs game)
- ❌ No support for `cam-standoff` (side-scroller) mode — only `cam-fixed-read-entity`
- ❌ Trigger volume only supports AABB — no rotation
- ❌ `(bg)` after spawn: obs_init timing may still be fragile (2s sleep)

### Next implementation tasks:
1. Add `cam-standoff` support (export `trans` + `align` lumps, expose in Blender UI)
2. Fix trigger volume to support rotated meshes (OBB planes or GOAL transformed AABB)
3. Add `interpTime` / FOV controls to the panel
4. Fix camera rotation quaternion export (test in-game)
5. (Long term) PR to OpenGOAL: fix LevelFile.cpp cameras array → enable native vol-based regions

---

## 11. Source File Reference

| File | Purpose |
|---|---|
| `goal_src/jak1/engine/camera/camera.gc` | `cam-state-from-entity`, `cam-slave-get-*` helpers |
| `goal_src/jak1/engine/camera/cam-master.gc` | `camera-master` process, event handler, `master-check-regions` |
| `goal_src/jak1/engine/camera/cam-states.gc` | All camera slave states |
| `goal_src/jak1/engine/camera/cam-layout.gc` | Camera editor tool, volume info |
| `goal_src/jak1/engine/camera/cam-start.gc` | `cam-start`, `cam-stop` |
| `goal_src/jak1/engine/entity/entity.gc` | `entity-camera` birth/kill, `entity-by-name`, `reset-cameras` |
| `goal_src/jak1/engine/entity/entity-h.gc` | `entity-camera` type def |
| `goalc/build_level/jak1/LevelFile.cpp` | BSP header generation (cameras array commented out) |
| `goalc/build_level/jak1/Entity.cpp` | Actor JSONC → binary |
| `goalc/build_level/common/Entity.cpp` | `res_from_json_array`, `vector_vol_from_json` |
