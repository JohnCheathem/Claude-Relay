# Research Notes — Community Feedback (15/04/2026)

Deep-dive into all issues raised by community tester.
Env: Blender 5.0.1 · mod-base `5599be3` · addon `b0577ea`

**Status:** Multiple fixes implemented on `research/community-feedback-apr15`.
Awaiting test on real builds before merge to main.

---

## FIXES IMPLEMENTED

### 1. 🔴 Dev Build Path Bug (Priority #1) — FIXED

Root cause and fix documented in commit `2bc1234`. Auto-detect logic:
```python
def _data():
    root = _data_root()
    if (root / "goal_src" / "jak1").exists():
        return root       # dev env — goal_src at project root
    return root / "data"  # release — data/ subfolder
```
Affects `export.py`, `build.py`, `model_preview.py`, `textures.py`, `panels.py`.
Vol-h.gc inverse bug (worked on dev, broke on release) also fixed.

**Data path description updated:** Now says "point to the `data/` subfolder for
release, or repository root for dev env. Both the correct folder and its parent
will work — the addon auto-detects the layout."

---

### 2. `og_no_export` Bug — FIXED

`_level_objects` and `_recursive_col_objects` defaulted to `exclude_no_export=True`,
meaning any collection marked no-export dropped ALL its objects (actors, spawns,
checkpoints) from the level data — not just geometry.

Fix: defaults changed to `False`. The flag now only applies when `export_glb`
explicitly passes `exclude_no_export=True` for geometry collection.

**This was very likely why checkpoint triggers weren't working** — if checkpoints
were in a no-export collection, they never appeared in the JSONC.

---

### 3. REPL Warning "Compilation generated code, but wasn't supposed to" — FIXED

Caused by `user.gc` containing `define-extern` declarations compiled with
`allow_emit=false` (the user profile compilation path in GOALC). `define-extern`
generates code which is forbidden in that context.

Fix: removed the `define-extern` lines from `user.gc`. The symbols `bg`,
`bg-custom`, and `*artist-all-visible*` are already in the game's symbol table
once connected via `(lt)`, so no forward declarations are needed in `user.gc`.

---

### 4. Checkpoint Empty Display — FIXED

Changed `SINGLE_ARROW` → `ARROWS` display type on spawn_checkpoint operator.
Now shows all three axes clearly — user can see which way the checkpoint faces.

---

### 5. Camera Anchor Parenting — FIXED

`spawn_cam_anchor` now parents the camera empty to the spawn/checkpoint empty
using `matrix_parent_inverse`. Moving or rotating the spawn drags the camera.

`collect_spawns` updated to use `cam_obj.matrix_world.translation` (world coords)
instead of `cam_obj.location` (local coords). Required for correct export when
the camera is parented.

Spawn/checkpoint position in `collect_spawns` also updated to use
`o.matrix_world.translation` for consistency and correctness if ever parented.

---

### 6. Misc Code Quality — FIXED

- `patch_level_info`, `patch_game_gp`, `patch_entity_gc` now raise instead of silently
  skipping when target files aren't found (was "Build complete!" with broken level)
- Build & Play panel shows specific missing-path messages; buttons disabled appropriately
- Level name validation: min 3 chars, `^[a-z][a-z0-9-]*$` regex, max 10
- export_build_play operator was missing the len>10 check
- Duplicate len>10 check removed from two operators
- `vis_nick_override` sanitised before embedding in GOAL
- Spawn/checkpoint uid sanitised before embedding in GOAL string literals
- `_apply_engine_patches` was missing from `_bg_build_and_play` Phase 1
- `vol-h pref`: `patch_vol_h: BoolProperty` added to OGPreferences (default True)
- `_data()` result cached per unique data_path to avoid repeated stat() on panel redraws

---

## OPEN ISSUES (documented, not yet fixed)

### A. Per-Level `deftype` Architecture — NEEDS WORK

**Problem:** `checkpoint-trigger`, `camera-trigger`, `camera-marker`, `aggro-trigger`,
`vol-trigger` are all defined as `deftype` in each level's `*-obs.gc`. If two custom
levels are loaded simultaneously, the type gets defined twice with identical code.
This is technically safe (same layout = clean re-definition) but:
- Wastes DGO disk space (same code in every level)
- GOALC warns during compilation of type redefinitions
- If the addon's generated type ever changes between levels (different field layout),
  it would corrupt memory at runtime

**Proper fix:** Move shared types to a single common file loaded once. Options:
1. A mod-base community common file (`goal_src/jak1/engine/mods/og-tools-common.gc`)
   compiled into GAME.CGO — clearest but requires upstream mod-base changes
2. A per-mod common DGO compiled alongside the level DGOs, always loaded
3. Guard with `(when (not (method-of-object (new-stack-vector0) checkpoint-trigger)) (deftype ...))`
   — pragmatic bandaid but doesn't eliminate code duplication

Recommendation for now: live with it (safe for single-level use), document the
limitation clearly, plan for option 1 when coordinating with mod-base maintainers.

---

### B. Spawn/Checkpoint Rotation for Non-Axis-Aligned Empties — NEEDS TESTING

Tester reports: "rotation isn't consistent when rotating the checkpoint's empty in
blender — only seems to work properly when aligned exactly with the global axis."

**Analysis:** The math (`R_remap @ m3 @ R_remap^T` then conjugate) looks correct
for single-axis rotations — verified with Python. Could be:
1. Combined (multi-axis) rotation producing unexpected results
2. The `ARROWS` empty type in Blender — which arrow represents "forward"?
   Currently: Blender +Y (green arrow) → game +Z (forward). User might expect +Z (blue) = forward.
3. A more subtle quaternion sign convention issue

**For next test session:** Verify with specific test cases:
- Rotate checkpoint empty 90° around Blender Z only → does Jak face left in game?
- Rotate 90° around Blender Z + 45° around X → does facing make sense?
- Which Blender arrow should the user align with the desired facing direction?

The addon needs a clear UI label: "Green arrow (+Y) = Jak's facing direction"

---

### C. Volume Trigger System Overhaul — FUTURE WORK

Current limitations reported by tester:
- Volume triggers only support AABB (axis-aligned bounding box) — can't create
  arbitrary-shape volumes
- Vol-mark debug display doesn't show our volumes (they may use a different system
  than the game's native volumes)

**Tester-provided Discord resource:**
https://discord.com/channels/967812267351605298/973327696459358218/1280548232283557938
A script for creating volumes from arbitrary mesh using the game's native volume
system via res lumps. This approach should replace the current AABB system.

This would also fix water volumes (which the tester mentions needing the same approach).

**Impact:** Major architectural change to the trigger/volume system. High priority
for usability but significant work.

---

### D. Checkpoint Radius Sphere Mode — VERIFY AFTER og_no_export FIX

Tester reports: "radius doesn't work even at 10 meters."

The JSONC writes `["meters", r]` for the radius lump. The GOAL code reads this via
`res-lump-float` with `:default 12288.0` (3m). This should work.

**Most likely explanation:** Checkpoints were in a no-export collection (issue #2 above)
so the checkpoint-trigger actor was never in the JSONC. Fix #2 should resolve this.
**Verify in next test session** after the og_no_export fix is deployed.

If still broken after fix #2: check the `res-lump-float` reading of a `meters`-type
tag in checkpoint-trigger GOAL code.

---

### E. Light Baking UI Reorganization — FUTURE WORK

Tester: "Light baking should probably be its whole new category."

Currently buried in Level settings. Should be a top-level panel, especially when
time-of-day gets added. Low priority, trivial to implement when ready.

---

### F. Blender 5.0.1 GLB Exporter Bug — NOT ADDON ISSUE

Blender 5.0.1 drops custom properties during GLB export. Confirmed not addon-related
— affects manual exports too. Users should use Blender 4.5.2 until upstream fixes it.

---

## QUICK REFERENCE: Path Convention for Spawns

In Blender → In Game:
- Blender +X (red arrow)  → Game +X (right)
- Blender +Y (green arrow) → Game +Z (forward = Jak's facing)
- Blender +Z (blue arrow)  → Game -Y (up)

The green (+Y) arrow should point in the direction Jak faces after spawning.
