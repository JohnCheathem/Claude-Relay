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

---

## Session 4 — April 11 — REFRAME after user "why is this easy for others"

### Critical user insight
Others bake to _NAME attributes the same way and it works for them.
This contradicts the session 3 "importer reads by index" hypothesis if
taken at face value — others' GLBs would have the same problem.

### Key finding from OpenGOAL Jan 2024 progress report
"Previously, only .glb files that were exported using versions of Blender
older than 4.0 would be supported for custom levels due to the way the
GLB exporter for Blender 4.0 would store vertex colors."
Source: https://opengoal.dev/blog/progress-report-jan-2024/

### What this tells us
1. OpenGOAL importer is Blender-version-aware re: vertex colors
2. Blender < 4.0 stores color attrs as clean COLOR_N (no _NAME leak,
   no duplicates, no dropouts) — this is what most community users have
3. Blender 4.0+ broke this; OpenGOAL added a compat patch in Jan 2024
4. Our GLB is 4.0+ AND has BOTH COLOR_N (broken/miscoded) AND _NAME
   (clean and complete). The importer may be picking the wrong one.

### Revised hypothesis (HIGH CONFIDENCE)
The OpenGOAL level importer has fallback logic: prefer COLOR_N if
present, fall back to _NAME. Our GLB has COLOR_N present (in the
miscoded form) so the importer never reads the clean _NAME data.

### Why "others" don't hit this
They're likely on Blender 3.x. Their GLB has clean COLOR_N (in correct
slot order, no dupes/dropouts) and may not even have _NAME variants.
Importer reads COLOR_N, all good.

### Verification needed (session 5)
Pull jak-project source for the level extractor (likely tools/build_level
or goalc/build_level) and read the exact attribute lookup logic. Confirm:
- Does it prefer COLOR_N over _NAME, or vice versa?
- What name pattern does it look for? Exact match? Case sensitive?
- Is there a Blender 4.0 compat path and what does it check for?

### Possible fixes (NOT YET PROPOSED — pending source verification)
A) Pin community to Blender 3.6 LTS — matches what works for others
B) On 4.0+, suppress COLOR_N leak so importer falls back to _NAME path
C) On 4.0+, manually arrange attributes so COLOR_N comes out in correct
   engine slot order

### Stop point
Session 4 end. NO fix yet. NO addon changes. Need to read jak-project
importer source before proposing anything.

---

## Session 5 — April 11 — ROOT CAUSE FULLY CONFIRMED + FIX DESIGNED

### Source code trace complete
Full read of jak-project C++ source. Files examined:
- `common/util/gltf_util.cpp` — `gltf_vertices()` + `pack_time_of_day()`
- `common/custom_data/Tfrag3Data.h` — `PackedTimeOfDay` struct
- `goalc/build_level/common/gltf_mesh_extract.cpp` — mesh extraction pipeline
- `goalc/build_level/common/Tfrag.cpp` + `Tie.cpp` — call sites
- `game/graphics/opengl_renderer/background/TFragment.cpp` + `background_common.cpp` — renderer
- `goal_src/jak1/engine/gfx/mood/mood.gc` — `update-mood-itimes`

### What the engine ACTUALLY does (renderer side)
`PackedTimeOfDay` stores 8 palettes × N colors × 4 channels.
Every frame, `interp_time_of_day()` reads `camera.itimes` (the GOAL-packed blend weights from
`update-mood-itimes`) and computes a weighted sum across all 8 palettes for each color entry.
This is SSE-vectorised, fully functional, and used for TFrag, TIE, Shrub, and Hfrag.
The 8 palette slots map DIRECTLY to GOAL `times[0..7].w`:
  palette 0 = times[0] = _SUNRISE
  palette 1 = times[1] = _MORNING
  palette 2 = times[2] = _NOON
  palette 3 = times[3] = _AFTERNOON
  palette 4 = times[4] = _SUNSET
  palette 5 = times[5] = _TWILIGHT
  palette 6 = times[6] = _EVENING
  palette 7 = times[7] = _GREENSUN

### What the level builder ACTUALLY does (builder side)
`pack_time_of_day()` in `common/util/gltf_util.cpp` line 759:
  - Takes ONE `vector<Vector<u8,4>> color_palette`
  - Copies it identically into ALL 8 palette slots
  - Source: only ever called with `mesh_extract_out.color_palette`
  - `mesh_extract_out.color_palette` comes from `gltf_vertices()` which reads `COLOR_0` only

`gltf_vertices()` line 231:
  ```cpp
  const auto& color_attrib = attributes.find("COLOR_0");
  ```
  No code anywhere in the builder reads `_SUNRISE`, `_MORNING`, `_NOON`, etc.
  Zero mentions of these names in the entire jak-project codebase.

### Root cause — one sentence
The level builder reads only `COLOR_0` and writes it into all 8 TOD palette slots,
making them all identical, so `interp_time_of_day` always produces the same result
regardless of the time-of-day blend weights.

### Why community users "have it working"
The community is NOT using per-slot vertex color baking via named attributes.
Their levels show TOD changes in fog/sky/actor lighting (mood system — fully working)
but NOT per-vertex geometry lighting changes across time slots. Either:
  (a) They consider fog+sky change sufficient and call it "TOD working", OR
  (b) They use the full pipeline but accept that all geometry slots are identical
      (baked to one single lighting condition which looks fine since most levels do
       not strongly vary vertex colors across TOD anyway), OR
  (c) A small number use a custom build/fork of jak-project with an extended builder

### The fix — C++ level builder change required
The addon's `_SUNRISE`/`_NOON` export is correct. The fix is in jak-project source.

**Files to change:**
1. `common/util/gltf_util.h` — add declaration:
   ```cpp
   tfrag3::PackedTimeOfDay pack_time_of_day(
     const std::array<std::vector<math::Vector<u8, 4>>, 8>& palettes);
   ```

2. `common/util/gltf_util.cpp` — add overload:
   ```cpp
   tfrag3::PackedTimeOfDay pack_time_of_day(
     const std::array<std::vector<math::Vector<u8, 4>>, 8>& palettes) {
     // all palettes must have same size; use palette[2] (NOON) as size reference
     const auto n = palettes[2].size();
     tfrag3::PackedTimeOfDay colors;
     colors.color_count = (n + 3) & (~3);
     colors.data.resize(colors.color_count * 8 * 4);
     for (u32 color_index = 0; color_index < n; color_index++) {
       for (u32 palette = 0; palette < 8; palette++) {
         for (u32 channel = 0; channel < 4; channel++) {
           colors.read(color_index, palette, channel) =
             palettes[palette][color_index][channel];
         }
       }
     }
     return colors;
   }
   ```
   Also add a helper to read a named attribute (not just COLOR_0):
   ```cpp
   // reads a named vertex color attribute (e.g. "_SUNRISE") instead of COLOR_0
   // returns empty vector if attribute not present
   std::vector<math::Vector<u8, 4>> gltf_colors_for_attribute(
     const tinygltf::Model& model,
     const std::map<std::string, int>& attributes,
     const std::string& attr_name);
   ```

3. `goalc/build_level/common/gltf_mesh_extract.cpp` — change tfrag + TIE extraction to:
   - After collecting vertices per primitive, also collect colors for all 8 named slots
   - If any `_NAME` slot is present on the mesh, use 8-palette path
   - If no `_NAME` slots (legacy mesh), fall back to COLOR_0 + duplicate (existing behavior)
   - Aggregate all-vertex color lists per slot across all primitives, then call new `pack_time_of_day`

### Color quantization consideration
The existing path runs `quantize_colors_kd_tree` on one palette, producing `color_indices` (shared
vertex→palette-entry mapping) + `color_palette`. The 8-palette extension must share the same
`color_indices` — you can't have separate per-slot quantization because vertices need to reference
the same index regardless of TOD slot (the engine uses one index per vertex, not one per slot).

Correct approach:
  - Quantize on the NOON palette (slot 2, the canonical "base" bake)
  - Use the resulting `vtx_to_color` index mapping for all 8 slots
  - Build 8 color palettes where `palette[slot][color_index]` = average color of all vertices
    mapped to that index in that slot's raw color data

### Confidence: VERY HIGH
- Every claim above is sourced from reading actual lines of source code
- The renderer works, the GOAL pipeline works, the GLB export works
- The one broken link is `gltf_vertices` reading `COLOR_0` only and `pack_time_of_day`
  receiving a single palette and duplicating it

### What we should NOT change
- The Blender addon's `_SUNRISE`/`_NOON` etc. export — it is correct
- The renderer — it is correct
- The GOAL mood system — it is correct and unrelated to vertex color TOD

### Stop point / next action
This is a C++ change to jak-project, not a Blender addon change.
To get it working:
  Option A — Submit PR to jak-project with the fix above
  Option B — Build a custom version of jak-project with the change
  Option C — As a workaround: bake all 8 slots to the same lighting (what users already do),
              and accept that geometry color doesn't change with TOD (only fog/sky/actor lighting does)

---

## Session 6 — April 11 — DEFINITIVE ANSWER: geometry TOD not implemented in builder

### Official confirmation
`custom_assets/jak1/levels/test-zone/test-zone.jsonc` comment (OpenGOAL devs):
> "For now, only the first vertex color group is used, so make sure you only have 1."

This is the ground truth. Multi-slot geometry vertex color TOD is explicitly NOT implemented.
It is a future/planned feature. The builder reads COLOR_0 only. Full stop.

### What community members "have working"
Mood-based TOD only:
- Fog color/distance changes with time → works (GOAL mood system, unrelated to GLB)
- Sky texture/color changes → works (GOAL mood system)
- Actor/enemy lighting changes → works (mood-tables.gc light groups)
- Jak's lighting changes → works (target-interp in mood callback)
- Level GEOMETRY vertex colors changing with time → NOT WORKING for anyone
  The community is calling "TOD working" when they see fog+sky+actor changes.
  Nobody has per-vertex geometry light interpolation on custom levels.

### Why the _NAME attributes and 8-slot baking are irrelevant
- `export_attributes=True` exports `_SUNRISE` etc. as glTF custom attributes
- `gltf_vertices()` in gltf_util.cpp reads `COLOR_0` only — zero code reads `_NAME` attrs
- `pack_time_of_day()` takes one palette and copies it 8× — structure exists, not populated
- The `gltf2_blender_extract.py` in custom_assets/blender_plugins/ patches Blender's exporter
  to write all color_attributes as `COLOR_0`, `COLOR_1`, etc. — but builder still reads only `COLOR_0`

### What DOES work right now — and what we should tell users
The current addon correctly handles:
1. Mood selection (fog/sky/actor lighting) — patch_level_info writes correct :mood/:mood-func
2. Sky toggle — :sky #t/#f
3. Sun fade — :sun-fade
4. Single vertex color bake (COLOR_0) — exported as active color attribute → works

The TOD panel (8-slot baking, slot picker, BakeAllToDSlots) is infrastructure for a feature
that doesn't exist yet in the builder. It does no harm but has no effect on geometry in-game.

### What the actual fix requires
A C++ change to jak-project:
- `gltf_mesh_extract.cpp` — read COLOR_0..COLOR_7 (if present) per primitive
- `gltf_util.cpp` — new `pack_time_of_day` overload taking array<palette, 8>
- Color quantization must use shared indices across all 8 slots

The custom `gltf2_blender_extract.py` in the official repo already outputs COLOR_0..COLOR_7
in attribute order. So the Blender side of the fix is: install that plugin and order attributes
correctly. The builder side is still the missing piece.

### Recommended next actions (choose one)
A) File/contribute a PR to jak-project implementing multi-slot builder support — real fix
B) Remove/hide the TOD geometry panel from our addon (it sets false expectations)
C) Keep the TOD panel but document it as "future feature, requires builder update"
D) Provide a workaround: bake all 8 slots to the same lighting → at least export is clean
   and the level will look correct (just won't change with time of day for geometry)
