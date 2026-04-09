# UI Restructure — Session Notes
Last updated: 2026-04-09

## Branch: `feature/ui-restructure`
## Commit: c5f0be6

## Status: BUILT, TESTED (static analysis 24/24), ready for Blender install test

---

## Panel Hierarchy

```
📁 Level              OG_PT_Level            (parent, always open)
  🗺 Level Flow        OG_PT_LevelFlow        (sub, DEFAULT_CLOSED)  idname: OG_PT_level_flow
  🗂 Level Manager     OG_PT_LevelManagerSub  (sub, DEFAULT_CLOSED)  idname: OG_PT_level_manager_sub
  💡 Light Baking      OG_PT_LightBakingSub   (sub, DEFAULT_CLOSED)  idname: OG_PT_lightbaking_sub
  🎵 Music             OG_PT_Music            (sub, DEFAULT_CLOSED)  idname: OG_PT_music

📁 Spawn Objects      OG_PT_Spawn            (parent, DEFAULT_CLOSED)
  ⚔ Enemies           OG_PT_SpawnEnemies     (sub, DEFAULT_CLOSED)  cats: Enemies, Bosses
  🟦 Platforms         OG_PT_SpawnPlatforms   (sub, DEFAULT_CLOSED)  uses platform_type prop
  📦 Props & Objects   OG_PT_SpawnProps       (sub, DEFAULT_CLOSED)  cats: Props, Objects, Debug
  🧍 NPCs              OG_PT_SpawnNPCs        (sub, DEFAULT_CLOSED)  cats: NPCs
  ⭐ Pickups           OG_PT_SpawnPickups     (sub, DEFAULT_CLOSED)  cats: Pickups
  🔊 Sound Emitters    OG_PT_SpawnSounds      (sub, DEFAULT_CLOSED)

〰 Waypoints          OG_PT_Waypoints        (context poll: actor with waypoints selected)
🔗 Triggers           OG_PT_Triggers         (always visible — no DEFAULT_CLOSED)
📷 Camera             OG_PT_Camera           (DEFAULT_CLOSED, unchanged)
▶ Build & Play        OG_PT_BuildPlay        (always visible)
🔧 Developer Tools    OG_PT_DevTools         (DEFAULT_CLOSED)
OpenGOAL Collision    OG_PT_Collision        (object context)
```

---

## Key Design Decisions

- **Triggers**: always visible (removed DEFAULT_CLOSED) — general purpose
- **Camera**: unchanged
- **NavMesh panel removed**: navmesh link UI is now inline in Enemies sub-panel.
  Shows whenever ANY nav-enemy ACTOR_ is the active object, regardless of
  what entity type is selected in the dropdown.
- **Audio panel removed**: Music + sound banks → Level > Music sub-panel.
  Sound emitters → Spawn > Sound Emitters sub-panel.
- **Entity picker in Spawn subs**: uses shared `entity_type` prop. If selected
  type is outside the sub-panel's category, shows a "Select a type from this
  category" hint and early-returns. Clean UX, no crash.

---

## Bugs Found and Fixed During Testing

| Bug | Severity | Fix |
|---|---|---|
| 17 operators dropped during UI splice | Critical | Restored from main |
| Duplicate OG_PT_LightBaking panel | Critical | Removed old standalone |
| Duplicate validate_ambients (truncated) | Critical | Removed fragment |
| Duplicate bl_idname OG_PT_lightbaking | Critical | Renamed sub idnames |
| Inline navmesh only showed when actor etype == dropdown etype | UX | Fixed to match any nav-enemy actor |

---

## Orphaned Operators (pre-existing, not caused by restructure)

These are registered but have no panel UI entry point. They're harmless —
registered in case users assign keymaps, and removing them could break saves.

- `og.mark_navmesh` / `og.unmark_navmesh` — were in old NavMesh panel
- `og.pick_navmesh` — was in old NavMesh panel
- `og.export_build_play` — BuildPlay panel shows 3 buttons only
- `og.play_autoload` — intentionally not shown

---

## Static Analysis Results (24/24 pass)

1. Syntax ✓
2. Duplicate classes ✓
3. Duplicate functions ✓
4. Duplicate bl_idnames ✓
5. Registered but not defined ✓
6. Defined but not registered ✓
7. Broken bl_parent_id refs ✓
8. Broken operator string refs in UI ✓
9. Missing show_ BoolProps ✓
10-24. All OGProperties props present ✓

---

## Testing Checklist (Blender install required)

- [ ] Level panel: name, ID, death plane visible at top
- [ ] Level > Level Flow: spawns, checkpoints, bsphere
- [ ] Level > Level Manager: level list, remove, refresh
- [ ] Level > Light Baking: samples, bake button
- [ ] Level > Music: music bank, sound bank 1/2, live count
- [ ] Spawn parent: collapses cleanly
- [ ] Spawn > Enemies: shows only enemy/boss types, hint for others
- [ ] Spawn > Enemies: with nav-enemy ACTOR_ selected → navmesh section appears
- [ ] Spawn > Enemies: navmesh section shows correct actor name in header
- [ ] Spawn > Enemies: link/unlink navmesh works
- [ ] Spawn > Platforms: type dropdown, Add Platform, active settings
- [ ] Spawn > Props: shows Props/Objects/Debug types only
- [ ] Spawn > NPCs: shows NPC types only
- [ ] Spawn > Pickups: shows Pickup types only
- [ ] Spawn > Sound Emitters: pick sound, add emitter, emitter list
- [ ] Waypoints: still context-sensitive, shows on enemy/platform actor
- [ ] Triggers: ALWAYS visible (not collapsed by default)
- [ ] Camera: unchanged and functional
- [ ] Build & Play: always visible, 3 buttons work
- [ ] Collision: still appears on mesh objects

