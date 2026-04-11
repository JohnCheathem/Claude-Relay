# Addon Split — Session Notes

**Branch:** `feature/addon-split`
**Status:** Not started — analysis complete, ready for implementation
**Last updated:** 2026-04-11

---

## Goal

Split `addons/opengoal_tools.py` (12,429 lines, single file) into a Blender
package (`addons/opengoal_tools/`) with logical sub-modules. Pure refactor —
zero logic changes.

---

## Why

- File is too large to load in full context for editing (~12k lines)
- Changes to data tables cause full-file re-reads/rewrites
- Easier to reason about: "I need to change a panel" → open `panels.py`
- Reduces token cost for future sessions

---

## How Blender Multi-File Addons Work

Rename `addons/opengoal_tools.py` → `addons/opengoal_tools/__init__.py`.
Blender loads the folder as a package. Add sibling `.py` files, import them
in `__init__.py`.

```
addons/
  opengoal_tools/
    __init__.py          ← bl_info, register(), unregister(), top-level imports
    data.py              ← all data tables (ENTITY_DEFS, LUMP_REFERENCE, etc.)
    collections.py       ← collection helpers, path constants
    export.py            ← collect_*, write_gc, patch_level_info, build pipeline
    properties.py        ← OGProperties, OGAddonPreferences, PropertyGroups
    operators.py         ← all OG_OT_* classes
    panels.py            ← all OG_PT_* classes
    utils.py             ← shared helpers (_lname, _get_level_prop, log, etc.)
```

**Install method stays the same** — user zips the `opengoal_tools/` folder,
installs via Blender preferences. No change to user workflow.

---

## Current File Stats

| Metric | Count |
|---|---|
| Total lines | 12,429 |
| Top-level functions | 358 |
| Top-level classes | 149 (65 panels, 78 operators, 4 prop groups, 2 other) |
| Top-level constants | 89 |

---

## Proposed Module Breakdown

| File | Content | Est. lines |
|---|---|---|
| `data.py` | `ENTITY_DEFS`, `CRATE_ITEMS`, `ENTITY_WIKI`, `ETYPE_CODE`, `ETYPE_TPAGES`, all `*_TPAGES` constants, `LUMP_REFERENCE`, `ACTOR_LINK_DEFS`, `LUMP_TYPE_ITEMS`, `AGGRO_TRIGGER_EVENTS`, `LEVEL_BANKS`, `SBK_SOUNDS`, `ALL_SFX_ITEMS` | ~3,500 |
| `collections.py` | `_COL_PATH_*` constants, `_ENTITY_CAT_TO_COL_PATH`, `_LEVEL_COL_DEFAULTS`, `_active_level_col`, `_level_objects`, `_recursive_col_objects`, `_ensure_sub_collection`, `_classify_object`, `_get_level_prop` | ~400 |
| `export.py` | `collect_actors`, `collect_ambients`, `collect_spawns`, `collect_cameras`, `collect_nav_mesh_geometry`, `_collect_navmesh_actors`, `collect_load_boundaries`, `_convex_hull_2d`, `write_gc`, `patch_level_info`, `_make_continues`, `_lname`, `_nick` | ~1,500 |
| `build.py` | `launch_goalc`, `_bg_build`, `_bg_build_and_play`, `_bg_geo_rebuild`, `_build_state`, `_play_state`, `_find_free_nrepl_port`, `_goal_src`, `_level_info`, `_user_dir`, `_exe_root`, `_data_root` | ~1,300 |
| `properties.py` | `OGProperties`, `OGAddonPreferences`, `OGLumpRow`, `OGVolLink`, `OGActorLink`, `OG_UL_LumpRows`, all `EnumProperty`/`BoolProperty` definitions | ~700 |
| `operators.py` | All `OG_OT_*` classes (78 total) | ~3,500 |
| `panels.py` | All `OG_PT_*` classes (65 total) | ~2,500 |
| `utils.py` | `log()`, `_canonical_actor_objects`, `_vol_links`, `_classify_target`, `_vol_for_target`, `_clean_orphaned_vol_links`, shared math helpers | ~300 |
| `__init__.py` | `bl_info`, imports from all modules, `classes` list, `register()`, `unregister()` | ~150 |

---

## Dependency Graph (import order)

```
data.py          ← no internal imports
utils.py         ← no internal imports (or just data.py)
collections.py   ← data.py, utils.py
properties.py    ← data.py, utils.py
export.py        ← data.py, utils.py, collections.py
build.py         ← data.py, utils.py, export.py
operators.py     ← data.py, utils.py, collections.py, export.py, build.py, properties.py
panels.py        ← data.py, utils.py, collections.py, properties.py, operators.py (for poll refs)
__init__.py      ← all modules
```

**No circular imports** — data/utils at the bottom, panels/operators at the top.

---

## Known Risks

| Risk | Mitigation |
|---|---|
| `log()` used everywhere | Put in `utils.py`, import in every module |
| `_lname(ctx)` used in panels AND export | Put in `utils.py` or `export.py`, import where needed |
| `OGProperties` accessed as `ctx.scene.og_props` — no import needed for property access, but the class must be registered before panels | `properties.py` registered before `panels.py` in `__init__.py` |
| Some operators reference panel draw helpers defined in panels | Move shared draw helpers to `utils.py` |
| `ENTITY_ENUM_ITEMS` and friends call `_build_entity_enum()` at module load time | Keep builder functions in `data.py` alongside the tables |
| `_KEY_MAP` is defined twice (L1337 and L1363) | Fix this bug during split |
| Relative imports vs absolute | Use relative: `from . import data` or `from .data import ENTITY_DEFS` |

---

## Implementation Plan

### Phase 1 — Scaffolding (safe, no logic change)
1. Create `addons/opengoal_tools/` directory
2. Copy current `opengoal_tools.py` to `opengoal_tools/__init__.py` verbatim
3. Verify addon still installs and works — this is the regression baseline

### Phase 2 — Extract data.py (lowest risk, no function dependencies)
1. Move all data tables to `data.py`
2. Add `from .data import *` in `__init__.py`
3. Test install

### Phase 3 — Extract utils.py
1. Move `log()`, `_lname`, `_nick`, `_canonical_actor_objects`, shared helpers
2. Update imports
3. Test

### Phase 4 — Extract collections.py, export.py, build.py
1. One file at a time
2. Test after each

### Phase 5 — Extract properties.py
1. Move all PropertyGroup classes and OGProperties
2. Update `__init__.py` registration order
3. Test

### Phase 6 — Extract operators.py + panels.py
1. Largest step — 78 + 65 classes
2. May need to split operators into sub-files if still too large
3. Full regression test

### Phase 7 — Clean up __init__.py
1. Should be ~150 lines: bl_info, imports, classes list, register/unregister

---

## Regression Test Checklist

Run after each phase:
- [ ] Addon installs without error in Blender 4.4
- [ ] N-panel shows up in viewport
- [ ] Level panel shows active level settings
- [ ] Spawn an enemy — routes to correct sub-collection
- [ ] Build & Play completes without GOAL compile error
- [ ] Camera trigger works in-game
- [ ] Checkpoint trigger fires and re-arms

---

## Files

- `addons/opengoal_tools.py` on `main` — source of truth, do not touch during split
- `addons/opengoal_tools/` on `feature/addon-split` — working directory
- `session-notes/addon-split-progress.md` — this file

---

## Session Log

- 2026-04-11: Branch created. Analysis complete. File is 12,429 lines,
  65 panels, 78 operators, 89 constants. Dependency graph mapped.
  No circular import risks identified. `_KEY_MAP` double-definition bug
  noted at L1337 and L1363 — fix during split.
  Implementation plan written. Ready to start Phase 1.
