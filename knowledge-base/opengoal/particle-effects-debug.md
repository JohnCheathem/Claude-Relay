# Particle Effects — Build System Debug Notes

**Status:** `feature/effects` branch. Part file compiles but hit "No rule to make" error.
**Last updated:** Session ending feature/effects debug

---

## The Problem

When placing EFFECT_ empties and exporting, GOALC throws:

```
No rule to make out/jak1/obj/my-level-part.o, required for GROUP:iso
```

This happens even after manually restarting GOALC.

---

## How the Build System Actually Works

### game.gp is loaded ONCE per GOALC session

`compiler-setup.gc` runs at GOALC startup:
```lisp
(load-project "goal_src/jak1/game.gp")
```

`load_project_file()` in `MakeSystem.cpp` calls `clear_project()` then fully re-evaluates `game.gp`. It does **not** skip already-loaded files — every call does a full fresh reload.

### (mi) does NOT reload game.gp

`(mi)` expands to `(make-group "iso")` via goal-lib.gc macro:
```lisp
(defmacro mi () `(make-group "iso"))
```

`make-group "iso"` calls `m_make.make("iso", ...)` directly — it uses whatever dependency graph was loaded at startup. **No re-read of game.gp happens.**

This means: if game.gp was modified after GOALC started, `(mi)` will not see the changes until GOALC is restarted.

### How GROUP:iso gets my-level-part.o as a dep

Chain:
1. `goal-src "levels/my-level/my-level-part.gc" "process-drawable"` in game.gp registers a `defstep` with tool `goalc`, output `$OUT/obj/my-level-part.o` → remapped to `out/jak1/obj/my-level-part.o`
2. `custom-level-cgo "MYLEVL.DGO" "my-level/myl.gd"` registers a `defstep` with tool `dgo`, reading the `.gd` file
3. `DgoTool::get_additional_dependencies()` in `Tools.cpp` reads the `.gd` and generates deps: `"out/" + output_prefix + "obj/" + x.file_name` → `"out/jak1/obj/my-level-part.o"`
4. These match → dep chain is complete → `(mi)` can build it

**Path matching is correct.** Both sides produce `out/jak1/obj/my-level-part.o`.

---

## What force_restart Does (and Doesn't Do)

In `build.py`, `_bg_build`:

```python
part_status = write_part_gc(name, effects)
has_fx = part_status != "none"
force_restart = part_status in ("new", "updated")

if goalc_ok() and not force_restart:
    # Fast path: send (mi) via nREPL
    r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
    if r is not None:
        return  # done

# Slow path: kill + restart GOALC
write_startup_gc(["(mi)"])
kill_goalc()
launch_goalc()
```

**When `force_restart=True`:** We kill GOALC and restart it. On restart, `compiler-setup.gc` runs → `(load-project game.gp)` → sees new `goal-src` line. Startup.gc runs `(mi)`. Should work.

**When `force_restart=False` (file unchanged):** We use nREPL fast path. Since the part file hasn't changed and game.gp already has the line from the previous restart, this should also work.

---

## Most Likely Root Cause

The error persists even after manual GOALC restart. This suggests our `goal-src` line for `my-level-part.gc` is **not present in game.gp when GOALC loads it**. Possible reasons:

### Theory A: has_effects is False on the export that patches game.gp

`patch_game_gp(name, code_deps, has_effects=has_fx)` only writes the part `goal-src` line when `has_fx=True`. `has_fx = part_status != "none"`. `part_status = write_part_gc(name, effects)`. `write_part_gc` returns `"none"` when `effects` is empty.

`collect_effects(scene)` only returns empties that:
- Have `o.name.startswith("EFFECT_")`
- Have `o.type == "EMPTY"`

**If the EFFECT_ empty is not in the active level collection** (wrong collection, wrong level selected), `_level_objects(scene)` won't return it and `collect_effects` returns `[]`.

### Theory B: The strip regex removes the line then it's not re-added

`patch_game_gp` strips all `goal-src` lines for the level before rewriting:
```python
re.sub(r'\(goal-src "levels/{name}/[^"]+"[^)]*\)\n', '', txt)
```

This removes BOTH the obs and part lines. Then `correct_block` re-adds them. The part line is only included if `has_effects=True`. If a second export runs with `has_effects=False` (no EFFECT_ empties found), the part line gets stripped and not re-added. Next GOALC restart loads game.gp without it.

### Theory C: game.gp write is skipped because correct_block already matches

```python
if correct_block in txt:
    log("game.gp already correct"); return
```

If game.gp was previously written with the part line (when has_effects=True), and then on a subsequent export has_effects=False, the correct_block no longer matches (it doesn't include the part line). So the strip runs, removes the part line, writes back without it. Next restart: no part line.

This is actually consistent with the reported behaviour — works on first export attempt but breaks on subsequent ones.

---

## The Real Fix Needed

The issue is that `write_gd` injects `my-level-part.o` into the DGO, but `patch_game_gp` only adds the `goal-src` line when `has_effects=True`. If on any subsequent export `has_effects` becomes `False` (EFFECT_ empties missing/misrouted), the `.gd` still has `my-level-part.o` but game.gp no longer has the `goal-src` rule for it.

**Fix approach:** The `goal-src` line should be present in game.gp **whenever `my-level-part.o` is in the `.gd` file** — which means checking whether the part file physically exists on disk, not just whether there are active EFFECT_ empties in the scene.

```python
# In patch_game_gp, determine has_effects from disk, not just from scene
part_gc_path = _goal_src() / "levels" / name / f"{name}-part.gc"
has_effects_on_disk = part_gc_path.exists()
```

Or alternatively: always write the `goal-src` line when the part `.o` is in the `.gd`, and write the `.gd` and game.gp in sync.

---

## What Was Also Learned: defpart Field Ordering

The `defpart` macro enforces **strict ascending field ID order** via `*last-field-id*` global in `sparticle-launcher-h.gc`. Fields must appear in the order of their `sp-field-id` enum values:

| Field | ID |
|---|---|
| texture | 1 |
| num | 6 |
| x, y | 10, 11 |
| scale-x | 13 |
| rot-z | 16 |
| scale-y | 17 |
| r, g, b, a | 18–21 |
| vel-y | 26 |
| scalevel-x | 28 |
| rotvel-z | 31 |
| scalevel-y | 32 |
| fade-a | 36 |
| accel-y | 38 |
| timer | 46 |
| flags | 47 |
| conerot-x/y/radius | 58, 59, 62 |

**Common mistake:** placing `scalevel-y :copy scalevel-x` before `rotvel-z` — scalevel-y is ID 32, rotvel-z is 31, so rotvel-z must come first. Fixed in the campfire smoke and smoke presets.

---

## What Was Verified Working

- Path matching between `goal-src` output and `DgoTool` dependency: ✓ both produce `out/jak1/obj/<stem>.o`
- Strip regex correctly removes and rewrites level entries: ✓
- `defpart` field ordering in all 8 presets: ✓ verified by script
- `force_restart` logic fires on new/updated part files: ✓ code path confirmed

---

## Next Steps for Implementation

1. **Fix `patch_game_gp`** to check disk for `<level>-part.gc` existence rather than relying on `has_effects` from the current scene state
2. **Fix `write_gd`** to match — only inject `my-level-part.o` if the part file exists on disk
3. Keep `write_part_gc` creating/updating the file based on scene EFFECT_ empties
4. Add to Audit panel: warn if `EFFECT_` empties exist but `<level>-part.gc` is missing from disk

This decouples "does the part file exist" from "are there currently EFFECT_ empties in the scene" — the `.gd` and game.gp should always agree with the actual file on disk.
