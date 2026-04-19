# Smoothing Pass (branch: feature/smooth-editing)

Active work on eliminating hitches during editing and rendering. Plan split into three phases (see "Smoothing plan — original analysis" below). User opted to ship only Phase 1 first.

## Phase 1 — SHIPPED (commit 0fe7a9c), awaiting testing

Two changes that together target the per-GI-pass rendering ripple:

### 1. Separate static / dynamic VBOs
- `_batch_dict` entry shape CHANGED: was `(batch, texture)`, now `(batch, bounce_vbo, texture)`. All call sites updated (`_rebuild_inner`, `_incremental_rebuild`, `_apply_gi_update`, `view_draw`).
- New helper `_build_vbos_and_batch(cached, gi_per_vert=None)` builds:
  - Static VBO: position/normal/vertColor/texCoord, uploaded once, never touched again
  - Bounce VBO: bounceColor only, updated in place via `attr_fill`
  - Single batch combines them via `batch.vertbuf_add(bounce_vbo)` (confirmed supported in Blender 4.x, max 6 VBOs per batch)
- New helper `_update_bounce_vbo(bounce_vbo, cached, gi_per_vert)` — hot path for GI updates. Uses numpy fancy indexing (`gi_np[vi_map_np]`) to expand per-vertex → per-loop, then `attr_fill("bounceColor", bounces)`. No batch rebuild, no re-upload of static data.
- `vi_map_np` (numpy int32 view of `vi_map`) cached lazily on each mesh's cached dict.
- Removed the `from gpu_extras.batch import batch_for_shader` import (no longer used).

### 2. Lock-free GI conversion
- `ProgressiveGI.get_update` was holding the lock during `arr / self._count` + Python per-vertex tuple conversion for every object — stalling the GI thread during every main-thread apply.
- New behavior: snapshot accumulator dict under lock (numpy `.copy()`, microseconds), release lock, then do division + cap + `astype(float32)` outside. Returns numpy arrays.
- `_incremental_rebuild` also switched to numpy for reused GI during topology-preserving edits.

### What to watch when testing
- Visual correctness should be identical — same shader inputs, just delivered differently.
- First GI pass after scene load should look the same (uHasGI=0 fallback path is unchanged while bounce_vbo is zeros).
- Edit a mesh and leave edit mode → incremental path rebuilds VBOs for that object, should not flash.
- Big GI-converging scenes: this is where the smoothness win should be most visible.
- If `batch.vertbuf_add` or numpy-to-attr_fill ever errors, watch console for `[VertexLit] bounce attr_fill failed`. Unlikely but that's the diagnostic.
- Delete hitch / grey flash on deletion is still present — that's Phase 2, not in this commit.

## Phase 2 — PENDING (not on branch yet)

Incremental object deletion. Current code forces a full rebuild (`_dirty=True`, `_gi_preserve=False`) on any deletion, causing the grey-screen hitch the user flagged.

**Plan, when we resume:**
1. Add `decay` param to `_restart_gi_for_transforms(vls, decay=0.1)` so deletion can pass `decay=1.0` (keep remaining objects' GI fully intact). Default 0.1 preserves existing move/light behavior.
2. In `view_update`, replace the deletion-detection block (currently ~lines 371–377):
   - Old: set `_dirty=True` and `_gi_preserve=False`, full rebuild next view_draw
   - New: `deleted = set(_mesh_cache.keys()) - current` → pop deleted from `_mesh_cache` and `_batch_dict` → `_restart_gi_for_transforms(vls, decay=1.0)` → tag_redraw → return
3. Do NOT touch `_dirty`. Main thread continues drawing with existing batches (no grey). BVH rebuilds with smaller caster set; GI keeps accumulating.

## Phase 3 — DEFERRED

Numpy-cached geometry paths (items 4, 6, 7 from original analysis). User is OK with caching as long as scene stays editable and overhead is low.

**Edit-mode decision:** user wants to PAUSE rendering while in edit mode and only refresh on exit, rather than keep trying to make edit-mode updates smooth. Simpler than the current `depsgraph_update_post` + debounce machinery. Implementation sketch: if active object is in EDIT mode, skip `_incremental_rebuild` entirely in view_draw; on mode change to OBJECT, do one targeted rebuild for that object.

## Smoothing plan — original analysis

Ranked hitch sources (chat history has full reasoning):
1. Delete-object grey flash — Phase 2
2. `_apply_gi_update` rebuilt every batch every GI sample — Phase 1 ✓
3. Main thread held GI lock during conversion — Phase 1 ✓
4. Python per-vertex world-transform on every transform event — Phase 3
5. Light geometry update → full rebuild (unnecessary) — Phase 3
6. `_extract_mesh_data` Python loops (edit mode) — may be replaced by edit-mode pause instead
7. Minor: tuple conversion in batch builder — folded into Phase 1

---

# Older notes (pre-smoothing)

## Change triggers and incremental paths

- Transform event: `_transform_dirty` + 0.3s debounce → `_restart_gi_for_transforms` (no rebuild, no grey flash)
- Light transform: `_light_dirty` + 0.3s debounce → re-collect lights + `_restart_gi_for_transforms`
- Both paths retransform cached verts only; no bpy calls or mesh extraction.
- Geometry batches stay intact across transform events.

## Per-Object Cast Shadow

### Object Property (working)
- `bpy.types.Object.vertex_lit_cast_shadow` BoolProperty
- Shown in Object Properties → Vertex Lit panel
- Excludes object from BVH (no shadow casting, no GI blocking)
- Object still receives shadows and GI

### GeoNodes Named Attribute (NOT WORKING — needs fix)
- Intended: Store Named Attribute node, Boolean, Point domain, name='vertex_lit_cast_shadow'
- Code reads `mesh.attributes['vertex_lit_cast_shadow']` in `_extract_mesh_data`
- Stores `gn_cast_shadow` in mesh data dict
- `_build_raw_bvh_data` checks it before Object property
- **BUG: doesn't work in practice — needs debugging**
- Possible causes: attribute domain issue, evaluated mesh timing, logic inversion

## Known Issues / Pending
- GeoNodes cast shadow attribute not working (see above)
- GI bounce color might still show subtle own-color tint in some scenes (self-intersection bias raised to 0.01, MIN_DIST filter added — may need tuning)
- GPU GI would be 1000x faster but requires architecture rewrite

## Settings (Render Properties)
- Samples Per Cycle: how many samples per viewport update (GI runs indefinitely)
- Rays Per Pass: hemisphere samples per vertex per pass (quality vs update rate)
- Bounce Strength / Sky Color / Ground Color / Energy Scale
- Thread Pause: only shown when embreex unavailable (BVHTree fallback)

## Install Notes
- embreex installs on first addon register (~30s, one time only)
- Blender 4.4, Python 3.11, Windows confirmed working
- embreex-2.17.7 bundles its own Embree + TBB DLLs
