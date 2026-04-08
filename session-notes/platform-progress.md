# Platform System — Session Progress

## Status: INITIAL IMPLEMENTATION ✅ — on feature/platforms, needs in-game testing

## Active Branch: `feature/platforms`

---

## What's Done

- ✅ `knowledge-base/opengoal/platform-system.md` — complete source reference (on main)
- ✅ Entity defs: all 14 platform types have `needs_sync`, `needs_path`, `needs_notice_dist` flags
- ✅ Lump export at build time:
  - `sync` lump: `[period, phase, ease_out, ease_in]` for plat/plat-eco/side-to-side-plat
  - `path` lump: waypoints for sync platforms and plat-button
  - `fact-options` lump: wrap-phase bit when `og_sync_wrap=1`
  - `notice-dist` lump: plat-eco blue-eco activation radius
- ✅ `_actor_uses_waypoints()`: includes `needs_sync` so Waypoints panel shows for moving platforms
- ✅ `_actor_is_platform()`: helper for Platform panel poll
- ✅ `OG_PT_Platform` panel: sync controls, waypoint count, notice-dist, plat-button path status
- ✅ `OG_OT_TogglePlatformWrap`: toggle wrap-phase (loop vs ping-pong)
- ✅ `OG_OT_SetPlatformDefaults`: reset sync props to defaults

---

## Platform Workflow (for user)

### Moving platform (plat / plat-eco / side-to-side-plat):
1. Place ACTOR_plat_<uid> empty
2. Add ≥2 waypoints via Waypoints panel (Platform panel shows count + status)
3. Set period/phase/easing in Platform panel
4. Export & Build → 'sync' + 'path' lumps emitted

### Elevator (plat-button):
1. Place ACTOR_plat-button_<uid> empty
2. Add ≥2 waypoints (start position + end position)
3. Export & Build → 'path' lump emitted

### Eco platform (plat-eco):
1. Same as moving platform
2. Optionally set Notice Distance (Platform panel) — -1 = always active, >0 = needs blue eco

---

## Per-Actor Custom Properties (stored on the Blender empty)

| Property | Default | Notes |
|---|---|---|
| `og_sync_period` | 4.0 | Seconds for one full cycle |
| `og_sync_phase` | 0.0 | 0–1, staggers multiple platforms |
| `og_sync_ease_out` | 0.15 | 0–1, ease-out fraction of period |
| `og_sync_ease_in` | 0.15 | 0–1, ease-in fraction of period |
| `og_sync_wrap` | 0 | 0=ping-pong, 1=one-way loop |
| `og_notice_dist` | -1.0 | plat-eco only: -1=always active |

---

## Testing Needed

- [ ] plat with 2 waypoints moves back and forth in game
- [ ] plat-eco sits idle until player has blue eco (with notice-dist > 0)
- [ ] plat-eco activates when player carries blue eco within range
- [ ] plat-button moves when Jak stands on it
- [ ] wrap-phase: platform loops one-way (no mirror) when og_sync_wrap=1
- [ ] phase offset staggers two platforms correctly
- [ ] Platform panel appears when ACTOR_plat_xxx selected, not for enemies/pickups

---

## Known Unknowns

- The `sync` lump format `["float", period, phase, ease_out, ease_in]` — verify this
  is the correct JSONC type tag. The engine reads it as a float array.
  See knowledge-base/opengoal/platform-system.md §4 for full sync spec.
- `plat-button` may also need `trans-offset` lump if the platform mesh origin
  doesn't match the collision sphere center. Currently not exported.
