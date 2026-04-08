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
