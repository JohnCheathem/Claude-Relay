# Particle Effects — Session Notes

**Branch:** `feature/effects`
**Status:** Implementation complete but blocked on "No rule to make" build error
**Last updated:** 2026-04-14

---

## What Was Built

Full particle effect emitter system:
- `EFFECT_` empty placement via **Spawn Objects → ✨ Particle Effects** panel
- 8 presets: campfire, torch, smoke, sparkles, drip, waterfall, lava_glow, eco_blue
- Auto-generates `<level>-part.gc` at export (part-spawner subtype + defpartgroup/defpart)
- `.o` injected into DGO `.gd`, `goal-src` line added to game.gp
- JSONC actors with `"etype": "<level>-part"` and `"art-name"` pointing to group

## Files Changed

- `collections.py` — `_COL_PATH_EFFECTS`
- `properties.py` — `effect_preset` enum (8 presets)
- `export.py` — `collect_effects()`, `write_part_gc()`, `_part_lines()`, updated `write_gd`/`patch_game_gp`
- `build.py` — all 3 build paths integrated, `force_restart` logic
- `operators.py` — `OG_OT_AddEffect`
- `panels.py` — `OG_PT_SpawnEffects`, `OG_PT_EffectEmitter`, `_draw_selected_effect`
- `__init__.py` — all new classes registered

## Current Bug

**"No rule to make out/jak1/obj/my-level-part.o, required for GROUP:iso"**

Root cause identified but NOT yet fixed. See:
- `knowledge-base/opengoal/particle-effects-debug.md` — full analysis
- `knowledge-base/opengoal/particle-effects-system.md` — has cross-reference pointer

**Short version:** `patch_game_gp` only writes the `goal-src` line for the part file when `has_effects=True` from the current scene state. If on any subsequent export the EFFECT_ empties aren't found (wrong collection, different level selected, etc.), the line gets stripped and not re-added. Next GOALC restart loads game.gp without it.

**Fix:** Check disk for `<level>-part.gc` existence rather than relying on scene state. See debug doc for full plan.

## Bugs Fixed During Session

- `defpart` field ordering: `scalevel-x(28) → rotvel-z(31) → scalevel-y(32)` — campfire smoke and smoke preset had rotvel-z and scalevel-y swapped
- `force_restart` logic: `write_part_gc` now returns `"new"/"updated"/"unchanged"/"none"`, build paths force GOALC restart on new/changed part files

## Safe ID Ranges (Confirmed)

- `defpartgroup :id` — vanilla uses 1–708, safe range: **709–1023**
- `defpart` ID — vanilla uses up to ~2968, safe range: **2969–3583**

## DO NOT MERGE to main until build error is fixed
