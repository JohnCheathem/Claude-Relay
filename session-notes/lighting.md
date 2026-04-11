# Lighting Session Notes

## Status: TOD system implemented — ready for testing

## Branch: feature/lighting

## Base
Addon replaced with main branch (10,738 lines) as clean starting point.
All previous feature/lighting work (mood dropdown, sky, sun_fade, bake ops) has been re-implemented on top of main.

---

## What's Implemented (this session)

### Constants (top of file, after enum items)
- `MOOD_ITEMS` — 21 mood presets with descriptions
- `MOOD_FUNC_OVERRIDES` — handles beach→village1 mood-func quirk
- `TOD_SLOTS` — 8 slots: _SUNRISE, _MORNING, _NOON, _AFTERNOON, _SUNSET, _TWILIGHT, _EVENING, _GREENSUN
- `TOD_COLLECTION_NAMES` / `TOD_SLOT_IDS` — convenience lists

### OGProperties (new fields)
- `mood` — EnumProperty(MOOD_ITEMS, default="village1")
- `sky` — BoolProperty(default=True)
- `sun_fade` — FloatProperty(0.0–1.0, default=1.0)
- `tod_slot` — EnumProperty(TOD_SLOTS, default="_NOON")

### patch_level_info update
- Reads mood/sky/sun_fade from scene.og_props (was hardcoded village1/#t/1.0)
- Writes: `:mood '*{mood_id}-mood*`, `:mood-func 'update-mood-{mood_func}`, `:sky #t/#f`, `:sun-fade {val}`
- beach override handled via MOOD_FUNC_OVERRIDES

### New Operators
- `OG_OT_SetupTOD` (og.setup_tod) — creates `{level}_TOD` collection inside level collection, with 8 sub-collections named `{level}_TOD_Sunrise` etc.
- `OG_OT_BakeToDSlot` (og.bake_tod_slot) — bakes selected slot on selected meshes using BYTE_COLOR/CORNER attribute
- `OG_OT_BakeAllToDSlots` (og.bake_all_tod_slots) — bakes all 8 slots, resets active to _NOON

### New Panel: OG_PT_TODSub
- Location: Levels > Light Baking > Time of Day (DEFAULT_CLOSED)
- Section 1 — Level Lighting Settings box: mood dropdown, sky toggle, sun_fade slider
- Section 2 — TOD Collections box: description + Setup TOD button
- Section 3 — Bake ToD Slots box: mesh count, slot picker, Bake Slot button, Bake All 8 button + warning

---

## UI Location
Levels → Light Baking → 🕐 Time of Day

---

## Next Steps
- [ ] Test in Blender — install addon from feature/lighting
- [ ] Verify Setup TOD creates correct collection hierarchy
- [ ] Test Bake Slot on a mesh — confirm _NOON attribute created + baked
- [ ] Verify patch_level_info emits correct mood/sky/sun_fade on export
- [ ] Test beach mood → emits update-mood-village1 (not update-mood-beach)
- [ ] Future: expose num-stars control
- [ ] Future: custom mood tables (still requires manual GOAL)
- [ ] Merge to main when tested and approved

## Known Gaps
- Custom mood tables (fog/lights/sun per slot) still require manual GOAL editing
- Blender <3.4: export_attributes not available, ToD slots bake but won't export

---

## Bug Audit Session — 9 fixes applied

### Confirmed Bugs Fixed
1. **sun_fade precision** — `:.1f` formatted `0.25` as `0.2` in GOAL output → fixed to `:.4g`
2. **SetupTOD double-link crash** — `children_recursive` check ran after `level_col.children.link()` already called, causing `RuntimeError: already in collection` → guard now checks `level_col.children` instead
3. **`hasattr(scene, "cycles")` wrong guard** — this always returns True (scene.cycles always exists); used in both bake ops → removed, access scene.cycles directly
4. **No try/finally in BakeToDSlot** — if bake raised, engine/selection never restored → wrapped in try/finally
5. **`target="ACTIVE_COLOR_ATTRIBUTE"`** — requires Blender 3.4+, inconsistent with existing BakeLighting → changed to `target="VERTEX_COLORS"` (works from 3.1+)
6. **`active_index` assignment** — color_attributes.active_index deprecated path; should set `.active_color = mesh.color_attributes[name]` → fixed in both bake ops
7. **BakeAllToDSlots** — same bugs 3–6 present, all fixed
8. **`export_attributes` missing from export_glb** — ToD vertex color slots (`_SUNRISE` etc.) were not being exported to GLB → added `export_attributes=True` with version guard `bpy.app.version >= (3, 4, 0)` to both export paths (selection and fallback)
9. **Leftover bad display lookup** — a broken first attempt at slot display name resolution (`d for _, d, _ in TOD_SLOTS if _ == slot`) left in alongside the correct one → removed

### Minor Cleanup
- Removed unused `TOD_COLLECTION_NAMES` / `TOD_SLOT_IDS` constants (SetupTOD iterates TOD_SLOTS directly)

---

## Session — April 11 2026 — Testing & Status

### What was tested
- Level compiled successfully after sun_fade float fix (`:sun-fade 1` → `:sun-fade 1.0`)
- Level loaded in-game (`NOTICE: loaded my-level`)
- `(set-time-of-day 12.0)` etc. commands work — only very subtle change visible
- Vertex color slots confirmed different in Blender viewport (bakes are correct)
- In-game geometry appears stuck on what looks like _SUNRISE for all times of day

### Root cause hypothesis
**export_attributes was missing when the GLB was last exported.**
The `export_attributes=True` fix (required for Blender 3.4+ to export `_SUNRISE`, `_NOON` etc. custom attributes) was added this session. If the user's last export happened before that patch, the ToD attributes were silently dropped from the GLB. The game would only have whichever slot was `active_color` at export time baked into a single vertex color set — no interpolation possible.

### Next step to confirm
Re-export from Blender using the patched addon (feature/lighting, commit c1a1f37 or later), rebuild, and test `(set-time-of-day)` again. If ToD variation appears, pipeline is confirmed working end-to-end.

### Collection visibility fix (also this session)
BakeToDSlot and BakeAllToDSlots now isolate the correct TOD sub-collection during baking:
- Bake Slot: hides all TOD sub-collections except the active slot's
- Bake All: steps through each slot, isolating one at a time
- Both restore original visibility in finally block

### Current branch state
feature/lighting is clean, syntax OK, all known bugs fixed.
Ready to test after re-export.

### Remaining unknowns
- Whether export_attributes fix resolves the in-game flat lighting
- Whether Blender version on user's machine is >= 3.4 (required for export_attributes)
  - If <3.4, ToD slots will never export regardless of the fix — would need a different approach

### Stop point
Signing off for the night. Resume by: install latest addon → re-export level → rebuild → test set-time-of-day.

---

## Session — April 11 2026 (evening) — Diagnostic run, hypothesis narrowed

### GLB diagnostic ran on user-supplied my-level.glb
- All 8 `_NAME` slots present on all 28/28 primitives ✓
- Export side is NOT dropping ToD attributes
- BUT: COLOR_0 through COLOR_8 (nine numbered streams) also present

### Why that's suspicious
Per Blender bug tracker #118563 and upstream glTF-Blender-IO #1740/#2063,
modern Blender (4.0+) glTF exporter does NOT emit COLOR_1 and above. Color
attributes beyond COLOR_0 are only reachable as `_NAME` custom attributes.
Addon export call uses `export_vertex_color="ACTIVE"` at lines 4422/4440,
which reinforces that only one COLOR_N stream should exist.

The presence of COLOR_1..COLOR_8 in the uploaded GLB contradicts both.
Either:
  (a) the GLB was not produced by current feature/lighting addon code, or
  (b) the user's Blender version has different exporter behavior, or
  (c) something in the bake setup is causing numbered exports despite ACTIVE

### Hypothesis status
- H1 (export drops _NAME): DISPROVEN
- H3 (importer reads only COLOR_0, ignores _NAME): STRONGLY ELEVATED
  → would explain perfectly the "stuck on one slot" symptom
- H5 (Blender < 3.4): DISPROVEN
- H7 (NEW: numbered COLOR_N exist contrary to docs): needs answer
- H8 (NEW: COLOR_0 != _NOON despite addon resetting active to _NOON): worth checking

### Next-session next actions (in order)
1. Confirm with user: was uploaded GLB exported by CURRENT feature/lighting addon?
2. Extend diagnostic: dump first-vertex bytes of COLOR_0 and each _NAME to identify
   which named slot COLOR_0 actually equals. Also dump per-prim attribute domain/type.
3. Search jak-project source for level GLB importer to confirm whether it reads
   by name or by COLOR_N index. This is the central unknown.
4. Only then propose fix.

### Open questions for user
- Was my-level.glb re-exported with c1a1f37 or later? (Critical)
- In-game flat lighting: does it match _NOON in Blender viewport, or different slot?

### Stop point
End of session 2. NO fix proposed yet, NO changes to addons/opengoal_tools.py.
Diagnostic data captured. Awaiting user answers + session 3.

---

## Session 3 — April 11 evening — ROOT CAUSE IDENTIFIED

### Test result from user
- (set-time-of-day) DOES affect Jak's lighting (mood-tables.gc actor pipeline working)
- (set-time-of-day) does NOT affect level geometry baked colors
- Confirms the bug is on the vertex-color palette path, NOT the mood callback path

### Byte-level GLB diagnostic (scratch/inspect_glb_tod_v2.py)
On user's my-level.glb produced by current feature/lighting addon:

GLB contains BOTH:
- COLOR_0..COLOR_7 (8 numbered glTF color streams)
- _SUNRISE.._GREENSUN (8 named custom attributes)

SHA1 byte-comparison shows COLOR_N → _NAME mapping:
  COLOR_0 == _SUNRISE       (engine expects SUNRISE — OK)
  COLOR_1 == _MORNING       (engine expects MORNING — OK)
  COLOR_2 == _AFTERNOON     (engine expects NOON — WRONG)
  COLOR_3 == _AFTERNOON     (DUPLICATE)
  COLOR_4 == _SUNSET        (engine expects SUNSET — OK)
  COLOR_5 == _TWILIGHT      (engine expects TWILIGHT — OK)
  COLOR_6 == _GREENSUN      (engine expects EVENING — WRONG)
  COLOR_7 == _GREENSUN      (DUPLICATE)

_NOON and _EVENING never reach the numbered COLOR_N streams at all.
Only present as named _NAME accessors.

### Root cause
The OpenGOAL level builder reads vertex colors from COLOR_N by INDEX,
not from _NAME custom attributes. The Blender glTF exporter is leaking
custom color-typed _NAME attributes into the COLOR_N numbered slots in
addition to writing them as named accessors. This contradicts the
upstream Blender doc claim that "COLOR_1 and above are never exported"
but the bytes show it's happening. Pattern: alphabetical-ish ordering,
with 2 duplicates and 2 dropouts. Not random.

The geometry lighting therefore appears frozen near sunrise (because
COLOR_0 == _SUNRISE) and the engine's interpolation runs between
miscoded/duplicated slots.

The mood/actor pipeline (Jak responds to set-time-of-day) is unaffected
because it uses mood-tables.gc light-groups, not the GLB vertex colors.

### Confidence: HIGH
Byte-perfect SHA1 match on every primitive verifies the mapping.
Symptoms predicted by hypothesis match symptoms reported by user exactly.

### Outliers to investigate
- Plane.005 reports COLOR_0 NO MATCH — likely a non-baked stray mesh
  (sky? water? collider?). Not blocking.

### NEXT (session 4) — fix design, NOT YET IMPLEMENTED
Two avenues:
A) Stop the leak — find what export setting / attribute property prevents
   custom color attrs from also being written as COLOR_N. Possibly: change
   bake to FLOAT_COLOR/POINT instead of BYTE_COLOR/CORNER, or use a non-
   color attribute domain entirely so the gltf exporter doesn't see them
   as color streams.
B) Embrace the indexed pipeline — explicitly set up the 8 attributes such
   that they end up in COLOR_0..COLOR_7 in the correct engine slot order,
   accepting that named accessors are decorative.

Option A is cleaner if achievable. Option B is a guaranteed-working
fallback. Need to test which Blender does what.
