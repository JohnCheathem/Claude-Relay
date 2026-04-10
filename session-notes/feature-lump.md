# Feature: Lump System — Session Notes
Last updated: April 2026

---

## Status: Phase 1 complete. Ready for testing/review.

---

## Branch: `feature/lumps`

Addon: `addons/opengoal_tools.py` — copied from main (v1.2.0) at session start, now at ~9700 lines.

---

## What Was Built This Session

### 1. Assisted Lump Row Panel (OG_PT_SelectedLumps)
- `OGLumpRow` PropertyGroup (key, ltype, value) stored as `og_lump_rows` CollectionProperty on Object
- `LUMP_TYPE_ITEMS` — all 18 valid JSONC type strings with descriptions
- `_parse_lump_row()` — typed value parser, space-separated multi-values
- `_LUMP_HARDCODED_KEYS` — conflict detection set
- `OG_UL_LumpRows` UIList — scrollable, live error icon per row
- `OG_PT_SelectedLumps` sub-panel — poll: ACTOR_ empties only, DEFAULT_CLOSED
- `OG_OT_AddLumpRow` / `OG_OT_RemoveLumpRow` operators
- Export wiring in `collect_actors()` — rows merge after hardcoded values, highest priority
- Conflict logging: warns if row overrides a hardcoded key

### 2. Lump Reference Panel (OG_PT_SelectedLumpReference)
- `LUMP_REFERENCE` table — per-etype lump key list with type + description
- `UNIVERSAL_LUMPS` — 8 keys that apply to all actors
- `_enemy` sentinel — nav-mesh-sphere + nav-max-users injected for all enemies/bosses
- `_lump_ref_for_etype()` helper
- `OG_OT_UseLumpRef` — pre-fills a new Custom Lumps row with key + type on click
- `OG_PT_SelectedLumpReference` sub-panel — read-only reference, DEFAULT_CLOSED

### 3. Selected Object panel refactor
- Main panel (OG_PT_SelectedObject) now shows only name/type label + Frame/Delete
- All content moved to sub-panels with appropriate poll functions:
  - OG_PT_ActorActivation (idle-distance, enemies)
  - OG_PT_ActorTriggerBehaviour (aggro, nav-enemies)
  - OG_PT_ActorNavMesh (navmesh link, nav-enemies)
  - OG_PT_ActorPlatform (sync/path/notice-dist, platforms)
  - OG_PT_ActorCrate (crate type)
  - OG_PT_ActorWaypoints (path + pathB)
  - OG_PT_SpawnSettings (SPAWN_)
  - OG_PT_CheckpointSettings (CHECKPOINT_)
  - OG_PT_AmbientEmitter (AMBIENT_)
  - OG_PT_CameraSettings (CAMERA_)
  - OG_PT_CamAnchorInfo (_CAM suffix)
  - OG_PT_VolumeLinks (VOL_)
  - OG_PT_NavmeshInfo (NAVMESH_)

---

## Verified Working (from user log)

Export log confirmed lump rows exported correctly:
```
[WARNING] ACTOR_babak_0 lump row 'vis-dist' overrides addon default
[lump-row] ACTOR_babak_0  'vis-dist' = ['meters', 22.0]
[WARNING] ACTOR_babak_4 lump row 'vis-dist' overrides addon default
[lump-row] ACTOR_babak_4  'vis-dist' = ['meters', 10.0]
```

Note: vis-dist doesn't visually cull actors in custom levels (no BSP vis system).
Not a bug — expected behaviour. Documented for users.

Also noted: Dev Tools panel has a recurring crash when no level is set after addon
reload — `_user_dir()` resolves to relative `data\` path and fails with PermissionError.
Not blocking, but should be fixed separately.

---

## Design Direction (settled)

### Lump panel purpose
- Custom Lumps = power user escape hatch + learning tool
- Not the primary config path — dedicated per-type UI fields are preferred
- Long term: every lump an actor reads becomes a proper first-class UI element
- Lump panel stays for: exotic overrides, custom data, experimentation

### Priority rule (dedup at export)
1. Hardcoded addon values (lowest)
2. Assisted lump rows (highest — override anything above)
Conflicts logged as warnings, not blocked.

---

## Unsupported Actors Audit

Full audit complete. Results in `scratch/unsupported-actors-draft.md`.
Awaiting approval to promote to `knowledge-base/opengoal/unsupported-actors.md`.

Summary:
- 73 actor types currently in ENTITY_DEFS
- 164 additional placeable types found in source, not yet supported
- Tier 1 (~55): pure props, easy batch add
- Tier 2 (~65): read a few lumps, need testing
- Tier 3 (~35): complex multi-actor systems
- Tier 4 (~9): final-boss/cutscene only, unlikely to be useful

Quick-add batch of ~55 Tier 1 props identified — could be done in one session.

---

## Known Issues / Follow-up

- Dev Tools panel crash on reload with no active level (`_user_dir()` relative path bug)
- Standalone `OG_PT_Waypoints` panel still exists alongside new `OG_PT_ActorWaypoints`
  sub-panel — decide whether to remove the standalone one
- `vis-dist` behaviour in custom levels should be documented in UI tooltip
- Unsupported actors draft needs approval before kb promotion

---

## Files

- `addons/opengoal_tools.py` — working addon on this branch
- `scratch/unsupported-actors-draft.md` — actor audit (pending kb promotion)
- `knowledge-base/opengoal/lump-system.md` — full lump reference (DO NOT overwrite)
