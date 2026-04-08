# OpenGOAL Blender Addon — Session Progress

## Status: CAMERA ROTATION SOLVED ✅ — ready to merge to main

## Active Branch: `feature/camera`

---

## What Works

- ✅ Camera position export (gx=bl.x, gy=bl.z, gz=-bl.y)
- ✅ Camera rotation export (see formula below — confirmed working)
- ✅ Trigger volume (AABB, entity-actor, births on level load)
- ✅ Camera switch on enter, revert on exit
- ✅ Spawned cameras get correct name (no .001 suffix)
- ✅ Look-at target (interesting lump) — optional world-position aim override
- ✅ FOV, blend time, mode (fixed/standoff/orbit) controls
- ✅ Panel UI with Add Camera, Add Volume, Link Trigger Volume

---

## The Quaternion Formula (final, confirmed)

```python
m3 = cam_obj.matrix_world.to_3x3()
bl_look = -m3.col[2]                               # camera looks along -local_Z
gl = Vector((bl_look.x, bl_look.z, -bl_look.y))   # remap bl->game
gl.normalize()
game_down = Vector((0, -1, 0))
right = gl.cross(game_down).normalized()
if right.length < 1e-6: right = Vector((1,0,0))
up = gl.cross(right).normalized()
gq = Matrix([right, up, gl]).to_quaternion()
qx, qy, qz, qw = -gq.x, -gq.y, -gq.z, gq.w      # conjugate — game reads inverse
```

**How we found it:** nREPL `inv-camera-rot` readback after triggering. Sent known quat,
measured actual r2, found game was reading conjugate. All previous attempts were blind math.

---

## Files

- `addons/opengoal_tools.py` on `feature/camera` — working addon
- `knowledge-base/opengoal/camera-system.md` — complete system docs
- `scratch/camera-diagnostics.md` — nREPL commands for future debugging
