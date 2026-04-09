# Platform System — Session Progress

## Status: REBASED ON MAIN + PLATFORM PANEL ADDED — ready for in-game testing

## Active Branch: `feature/platforms`

---

## What's Done

- ✅ Rebased on main (level flow, UI tweaks, camera CAMVOL_ rename all included)
- ✅ `knowledge-base/opengoal/platform-system.md` — complete source reference (on main)
- ✅ Entity defs: all 14 platform types have `needs_sync`, `needs_path`, `needs_notice_dist` flags
- ✅ `PLATFORM_ENUM_ITEMS` — platform-only enum for spawn dropdown
- ✅ `platform_type` EnumProperty on OGProperties
- ✅ `show_platform_list` BoolProperty on OGProperties
- ✅ `_actor_is_platform()` helper
- ✅ `_actor_uses_waypoints()` — updated to include `needs_sync` (Waypoints panel works for moving platforms)
- ✅ Duplicate `_actor_uses_waypoints` definition removed (was in main twice)
- ✅ Lump export in `collect_actors`:
  - `sync` lump: `["float", period, phase, ease_out, ease_in]` — only when waypoints present
  - `options` lump: `["uint32", 8]` when og_sync_wrap=1 (wrap-phase bit 3 = value 8)
  - `path` lump: for plat-button (needs_path) and sync platforms with waypoints
  - `notice-dist` lump: `["meters", val]` for plat-eco
- ✅ `OG_OT_NudgeFloatProp` — generic nudge with val_min/val_max clamping
- ✅ `OG_OT_TogglePlatformWrap` — toggles og_sync_wrap 0↔1
- ✅ `OG_OT_SetPlatformDefaults` — resets sync props to defaults
- ✅ `OG_OT_SpawnPlatform` — places ACTOR_<etype>_<uid> empty at 3D cursor
- ✅ `OG_PT_Platforms` panel:
  - Spawn section (always visible): type dropdown + Add Platform at Cursor button
  - Settings section (shown only when a platform actor is the active object):
    - Sync: period, phase, ease-out, ease-in, wrap-phase toggle, reset button
    - Path status for plat-button
    - Eco notice-dist for plat-eco
  - Collapsible scene list: all ACTOR_plat* empties, frame-select + delete per entry
  - Framing an entry selects it → settings section appears naturally

---

## Per-Actor Custom Properties

| Property           | Default | Range    | Notes                                    |
|--------------------|---------|----------|------------------------------------------|
| `og_sync_period`   | 4.0     | 0.5–300s | Seconds for one full A→B→A cycle         |
| `og_sync_phase`    | 0.0     | 0–0.9    | Staggers multiple platforms              |
| `og_sync_ease_out` | 0.15    | 0–0.5    | Fraction of period spent easing out      |
| `og_sync_ease_in`  | 0.15    | 0–0.5    | Fraction of period spent easing in       |
| `og_sync_wrap`     | 0       | 0 or 1   | 0=ping-pong, 1=one-way loop              |
| `og_notice_dist`   | -1.0    | -1 or ≥0 | plat-eco only; -1=always active          |

---

## Testing Checklist

- [ ] plat with 2 waypoints moves back and forth in game
- [ ] plat sits idle when placed without waypoints
- [ ] plat-eco sits idle, activates when player has blue eco (notice-dist > 0)
- [ ] plat-eco always moves when notice-dist = -1
- [ ] plat-button moves when Jak stands on top
- [ ] wrap-phase: loops one-way when og_sync_wrap=1
- [ ] phase offset: two platforms with phase=0.0 and phase=0.5 are staggered
- [ ] Platform panel: spawn dropdown shows all platform types
- [ ] Platform panel: Add Platform places correct actor at cursor
- [ ] Platform panel: settings hidden when no platform selected
- [ ] Platform panel: selecting from list makes settings appear
- [ ] Platform panel: collapsible list shows all platforms in scene
- [ ] Platform panel: frame button selects + frames the platform
- [ ] Platform panel: delete button removes the platform
- [ ] Waypoints panel still appears for sync platforms (plat, plat-eco)
