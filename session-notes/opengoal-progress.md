# OpenGOAL Addon — Session Notes

## Current State (merged to main)
All features below are live on main.

## Features Shipped

### Waypoint Spawn Controls
- All "Add Waypoint at Cursor" buttons → "Spawn Waypoint"
- "Add Path B Waypoint" → "Spawn Path B Waypoint"  
- New "Spawn at Position" checkbox (waypoint_spawn_at_actor BoolProperty)
  - When checked: waypoint spawns at actor's world location
  - When unchecked (default): spawns at 3D cursor
  - Shared across all 6 waypoint buttons in 3 panels

### Duplicate Entity
- "Duplicate" button in Selected Object panel (ACTOR empties only)
- Operator: og.duplicate_entity
- Duplicates empty, strips inherited preview children, re-attaches fresh preview
- Inherits level collection membership from source (export-safe)
- Names follow ACTOR_<etype>_<n> convention

### Empty Fits to Viz Mesh Bounds
- On spawn, empty_display_size auto-set to largest bounding box half-extent
- Only runs on first GLB (double-lurker uses first mesh to size)
- Guarded: no-ops if mesh is degenerate (size <= 0.001)
- Purely cosmetic — never touches .scale, children unaffected

## Bug Fixed
- ctx->scene in _draw_selected_actor (standalone function, no ctx param)
  Would have crashed panel draw for any selected ACTOR entity

## Active Branch
feature/duplicate-entity-preview (merged to main, can be deleted)

## Files Changed
- addons/opengoal_tools/properties.py — waypoint_spawn_at_actor prop
- addons/opengoal_tools/operators.py — OG_OT_AddWaypoint update, OG_OT_DuplicateEntity
- addons/opengoal_tools/panels.py — waypoint buttons, duplicate button
- addons/opengoal_tools/model_preview.py — _fit_empty_to_mesh, fit call in attach_preview
- addons/opengoal_tools/__init__.py — register OG_OT_DuplicateEntity

---

## Session — 2026-04-14 (waypoints, duplicate, viz mesh, bug fixes)

### Features Added
- **Waypoint spawn controls** — buttons renamed "Spawn Waypoint" / "Spawn Path B Waypoint"; new "Spawn at Position" checkbox (`waypoint_spawn_at_actor` BoolProperty) spawns at actor location instead of 3D cursor. Defaults off. Shared across all 6 waypoint buttons.
- **Duplicate Entity** — "Duplicate" button in Selected Object panel (ACTOR empties only). Operator `og.duplicate_entity` duplicates empty, strips inherited preview children, re-attaches fresh preview. Inherits level collection membership — export-safe. Follows `ACTOR_<etype>_<n>` naming.
- **Empty fits to viz mesh bounds** — `empty_display_size` auto-set to largest bounding box half-extent on spawn. First GLB only (double-lurker). Guarded against degenerate mesh. Purely cosmetic — never touches `.scale`.

### Bugs Fixed
- `ctx` → `scene` in `_draw_selected_actor` (NameError crash on panel draw)
- `OG_OT_DuplicateEntity` missing from `classes` tuple (button rendered but operator not registered)
- Preview meshes being exported to game (`og_no_export` set as custom dict prop `col["og_no_export"]` instead of RNA property `col.og_no_export` — `getattr` reads RNA, not custom dict)
- Preview meshes being sorted into Geometry/Solid (`_classify_object` had no `og_preview_mesh` guard)
- `_prop_row` write-in-draw crash on Blender 4.4 — `obj[key]=val` in draw context now raises `AttributeError`. Fixed with `bpy.app.timers` one-shot callback to write outside draw. Shows greyed placeholder on first frame, live input on next redraw.

### Files Changed
- `operators.py` — `OG_OT_DuplicateEntity`, `OG_OT_AddWaypoint` spawn-at-actor
- `panels.py` — waypoint buttons, duplicate button, `ctx`→`scene` fix
- `properties.py` — `waypoint_spawn_at_actor` BoolProperty
- `model_preview.py` — `_fit_empty_to_mesh`, fit call in `attach_preview`, `col.og_no_export` RNA fix
- `collections.py` — `_classify_object` preview mesh guard
- `export.py` — fallback export path preview mesh filter
- `utils.py` — `_prop_row` timer-based write-outside-draw fix
- `__init__.py` — register `OG_OT_DuplicateEntity` in import + classes tuple

### Key Technical Notes
- `bpy.types.Collection.og_no_export` is a registered RNA BoolProperty — must be set via `col.og_no_export = True`, NOT `col["og_no_export"] = True` (custom prop dict, invisible to `getattr`)
- Blender 4.4 blocks ALL ID property writes in draw() including `obj["key"] = val`. Use `bpy.app.timers.register(fn, first_interval=0.0)` for safe deferred writes.
- `bpy.ops.object.duplicate` preserves collection membership — duplicated actors land in correct level sub-collection without manual routing.
