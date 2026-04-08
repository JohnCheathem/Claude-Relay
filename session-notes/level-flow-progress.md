# Level Flow Feature — Session Notes
Last updated: April 2026

---

## Status: Research phase complete. No code written.

---

## Active Branch: `feature/level-flow`

---

## What Was Researched This Session

Full source crawl of the OpenGOAL jak1 codebase covering:

**Core system files read in full:**
- `engine/game/game-info-h.gc` — all type defs
- `engine/game/game-info.gc` — full continue-point logic
- `engine/level/level-info.gc` — all level-load-info definitions + test-zone
- `engine/level/level-h.gc` — level/level-group type defs
- `engine/level/level.gc` — activate-levels!, load machine, inside detection
- `engine/level/load-boundary-h.gc` — all boundary types
- `engine/level/load-boundary.gc` — full execute-command implementation (all 20+ cmd types)
- `engine/level/load-boundary-data.gc` — 170 vanilla boundaries (first 200 lines + stats)
- `engine/target/target-death.gc` — full target-continue state
- `engine/target/logic-target.gc` — start/stop functions
- `engine/common-obs/basebutton.gc` — warp-gate actor
- `levels/common/launcherdoor.gc` — full
- `levels/jungle/jungle-elevator.gc` — full

---

## Knowledge Base Location

`knowledge-base/opengoal/level-flow.md`

Contains:
- `continue-point` type + all fields documented
- `continue-flags` enum fully documented
- All `display?` mode values documented (display, special, special-vis, display-self, display-no-wait)
- `load-state` two-slot machine explained
- Full `execute-command` language (20+ commands documented with syntax)
- `level-load-info` all fields documented
- `alt-load-commands` indexing explained
- `load-boundary` structure documented
- All 5 boundary command types (checkpt, load, display, vis, force-vis)
- Vanilla boundary count breakdown: 71 checkpt, 97 display, 28 load, 40 vis
- `launcherdoor` and `jungle-elevator` continue-name lump pattern
- `warp-gate` *warp-info* array + flow
- Full 13-step `target-continue` respawn sequence
- Auto checkpoint assignment algorithm
- Inside-detection (inside-boxes? / inside-sphere? / meta-inside?)
- Custom level requirements checklist

---

## Key Findings

### The two ways to set a continue-point
1. **Passive (automatic):** Load boundaries with `checkpt` command, OR the per-frame auto-nearest-continue loop (zero-flag continues only, while player moves around)
2. **Active (triggered):** Actor reads `continue-name` lump → `(set-continue! *game-info* name)` → optionally `(load-commands-set! *level* ...)`. Both launcherdoor and jungle-elevator do this.

### Load boundaries are globally compiled
`load-boundary-data.gc` is a single global file for all levels. Not per-level.
Custom level transitions need to either add to this file, or use actor-based triggers.

### continue-point lev0/lev1 slots
- Slot 0 = primary level (where the point is)
- Slot 1 = adjacent level to also load (often the hub village)
- At most 2 levels active at any time

### warp-flag continues need special handling
`target-continue` has hardcoded case statements for each warp gate name.
Custom levels cannot add new warp-flag continues without adding cases to `target-death.gc`.
Normal (zero-flag) continues work freely.

### `test-zone` in level-info.gc
OpenGOAL ships with a `test-zone` level example at the bottom of `level-info.gc`.
Index 26, vis-nick 'tsz, has one continue at (0, 10m, 10m).
Good template reference.

---

## Next Steps (not started)
- Addon UI for continue-point placement (Blender → JSONC entity? Or direct level-info.gc edit?)
- Load boundary export from Blender (polygon drawn in 3D → XZ points + top/bot)
- `execute-command` command builder for continue-point load-commands
- Research how custom continues interact with save/load (game-save.gc)

---

## Second Research Session (April 2026)

### Additional files read:
- `engine/game/game-save.gc` — full save/load implementation
- `goalc/build_level/common/Entity.cpp` — full JSONC actor compiler
- `goalc/build_level/common/ResLump.cpp` — all lump type implementations
- `goalc/build_level/jak1/Entity.cpp` — jak1-specific add_actors_from_json
- `common/goal_constants.h` — METER_LENGTH=4096, DEGREES_LENGTH=182.044, DEFAULT_RES_TIME=-1e9
- `custom_assets/jak1/levels/test-zone/test-zone.jsonc` — canonical custom level example
- `custom_assets/jak1/levels/test-zone/testzone.gd` — DGO definition format
- `goal_src/jak1/game.gp` — build-custom-level macro, registration pattern
- `goal_src/jak1/levels/test-zone/test-zone-obs.gc` — full custom actor example
- `goal_src/jak1/engine/game/task/task-control-h.gc` — task-status enum, process-taskable
- `goal_src/jak1/engine/game/task/game-task-h.gc` — full game-task enum (116 slots)
- `goal_src/jak1/engine/target/logic-target.gc` — bottom-height death check

### New sections added to knowledge-base:
- §13: Save/Load safety analysis (continue name only serialized, graceful fallback)
- §14: Complete JSONC actor format with full lump type table
- §15: Build system registration (game.gp + .gd format)
- §16: Task system — what custom levels need (use game-task none, 116 fixed slots)
- §17: Death plane (bottom-height mechanics, grace period, recommended values)

### Key findings from second session:
- Saves store ONLY the continue-point name string. Custom continues are save-safe.
- `continue-name` lump must be a bare string (no `'`), becomes ResString not ResSymbol
- All 18 JSONC lump type strings documented with exact formats
- Custom levels need 3 things in game.gp: build-custom-level, custom-level-cgo, goal-src
- Task system has 116 fixed slots — custom levels should use `(game-task none)` throughout
- `bottom-height` is checked every frame against player Y with 2s grace period
