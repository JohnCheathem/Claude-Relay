# Vis Blocker — Session Notes

**Branch:** `feature/vis-blocker`
**Status:** Implementation complete, headless tests pass — ready for addon-driven in-game test
**Last updated:** 2026-04-13

---

## What Was Built

A system for hiding/showing mesh objects via trigger volumes. Naming convention:
- `VISMESH_<name>` — the blocking mesh (exports as its own GLB, becomes `vis-blocker` entity)
- `VOL_` linked to `VISMESH_` — becomes `vis-trigger` entity with hide/show/toggle action

---

## User Workflow

1. Name a mesh `VISMESH_wall-1` in Blender, place it in the level collection
2. Place a `VOL_` trigger, shift-select both, link via Triggers panel
3. Choose **Hide / Show / Toggle on enter** from dropdown
4. Hit Build — addon handles everything automatically

---

## Name Derivation

| Blender name | Art-group | Lump name | GLB file |
|---|---|---|---|
| `VISMESH_wall-1` | `wall-1-ag` | `vis-blocker-wall-1` | `wall-1.glb` |
| `VISMESH_my_blocker` | `my-blocker-ag` | `vis-blocker-my-blocker` | `my-blocker.glb` |

Underscores → dashes everywhere downstream.

---

## Test Results

**Headless Blender tests: 16/16 PASS** (`scratch/test_vis_blocker.py`)

All logic verified: classify, name helpers, enum items, collect, hidden-at-start,
is_linkable, trigger actors (hide/show/toggle), jsonc output, gc emission,
GLB exclusion, regression (camera-marker), multi-blocker.

---

## Environment Setup (for next session)

Blender 4.4.3 is installed at `/home/claude/blender-4.4.3-linux-x64/`
OpenGOAL binaries are at `/home/claude/` (extractor, goalc, gk)
Game data is at `/home/claude/data/` — **game has been decompiled**
ISO data at `/home/claude/iso_data/iso_data/jak1/`
Addon is installed at `/home/claude/blender-4.4.3-linux-x64/4.4/scripts/addons/opengoal_tools/`

**IMPORTANT:** The addon in Blender's addons dir is from feature/vis-blocker branch.
If re-cloning, copy from `/home/claude/Claude-Relay/addons/opengoal_tools/` after
checking out feature/vis-blocker.

### Was game compiled?
The compile was running in background when session ended. Check:
```bash
tail -5 /tmp/compile.log | sed 's/\x1b\[[0-9;]*m//g'
```
If not done, re-run:
```bash
cd /home/claude && ./extractor --proj-path /home/claude/data --folder --compile /home/claude/iso_data/iso_data/jak1 2>&1 | tail -20
```

### Addon config needed in Blender
The addon needs these paths set before it can build:
- **Project path** → `/home/claude/data`
- **GOALC path** → `/home/claude/goalc`
- **GK path** → `/home/claude/gk`

These are set in Blender Preferences → Add-ons → OpenGOAL Tools → preferences.
Can also be set via a headless script.

---

## Next Session Plan

**Goal:** Drive the full pipeline through the addon, not manually:

1. **Write a headless Blender script** that:
   - Creates a new level collection named `test-zone` (matches existing level-info.gc entry)
   - Adds a mesh cube named `VISMESH_test-wall`
   - Adds a `VOL_` mesh trigger volume
   - Links them with `og_vol_links` + `behaviour = "hide"`
   - Sets addon preferences (proj path, goalc, gk)
   - Calls the export operator (`og.export_level` or equivalent)
   - Saves the blend

2. **Verify output files** without running the game:
   - `data/custom_assets/jak1/levels/test-zone/test-wall.glb` exists
   - `test-zone.jsonc` has `"test-wall-ag"` in art_groups
   - `test-zone.jsonc` has `vis-blocker` and `vis-trigger` actors
   - `goal_src/jak1/levels/test-zone/test-zone-obs.gc` has the GOAL types

3. **Compile** via goalc (headless or nREPL)

4. **Check game logs** for:
   - `[vis-blocker] born: test-wall-ag`
   - `[vis-trigger] armed: vis-blocker-test-wall action 0 cull-r ...`

### Key operators to call from headless script
Look these up in operators.py:
- Build operator: class with `_bg_build` → probably `og.build_level` or similar
- The export_glb + export_vis_blocker_glbs happen in the operator's `execute` on main thread

### Known constraint
The existing `test-zone` level-info.gc entry uses `'test-zone` as level name.
Addon derives level name from collection name. So the Blender collection must be
named `test-zone` to match.

---

## Files Changed (Summary)

| File | Key changes |
|---|---|
| `export.py` | `_classify_target` vis-blocker; `collect_vis_blockers`; `export_vis_blocker_glbs`; `collect_vis_trigger_actors`; `write_gc` has_vis_blockers; `write_jsonc` vis_blockers kwarg; VISMESH_ excluded from level GLB |
| `build.py` | All 3 build paths call vis-blocker functions |
| `operators.py` | 3 export operators call `export_vis_blocker_glbs`; `OG_OT_ToggleVisBlockerHidden` |
| `panels.py` | VOL link shows hide/show/toggle for VISMESH_; `OG_PT_VisBlockerInfo` panel |
| `properties.py` | `OGVolLink.behaviour` dynamic for VISMESH_ targets |
| `data.py` | `VIS_TRIGGER_ACTIONS` + `VIS_TRIGGER_ENUM_ITEMS` |
| `utils.py` | `_is_linkable` accepts VISMESH_ |
| `__init__.py` | Registered new panel + operator |

---

## Known Gaps / Future Work

- No collision on vis-blocker (uses plain trsqv root) — intentional for v1
- No re-show on exit — need two VOL_ or future `exit_action` lump
- Not persistent across respawn (actor re-inits on death)
- Custom art-group → skeleton resolution untested in-game (the key unknown)

---

## Session Log

- 2026-04-13 (Session 1): Research + full implementation. 466 lines, py_compile pass.
- 2026-04-13 (Session 2): Blender 4.4.3 headless tests — 16/16 pass.
- 2026-04-13 (Session 3): OpenGOAL binaries + ISO data set up. Game decompiled.
  Compile started in background. Test files written manually then REVERTED —
  next session must use addon-driven pipeline, not manual file creation.
  Context window getting full — start fresh session next time.
