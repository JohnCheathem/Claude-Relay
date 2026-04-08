# Platform System — Session Progress

## Status: READY FOR IN-GAME TESTING — on feature/platforms

## Active Branch: `feature/platforms`

---

## What's Done

- ✅ `knowledge-base/opengoal/platform-system.md` — complete source reference + confirmed JSONC formats (on main)
- ✅ Entity defs: all 14 platform types have `needs_sync`, `needs_path`, `needs_notice_dist` flags
- ✅ Lump export (collect_actors):
  - `sync` lump: `["float", period, phase, ease_out, ease_in]` — confirmed correct via Entity.cpp
  - `path` lump: waypoints for sync platforms and plat-button
  - `options` lump: `["uint32", 8]` when og_sync_wrap=1 (wrap-phase = bit 3 = value 8)
  - `notice-dist` lump: `["meters", val]` for plat-eco
- ✅ `_actor_uses_waypoints()`: includes `needs_sync` — Waypoints panel shows for moving platforms
- ✅ `_actor_is_platform()`: helper for Platform panel poll
- ✅ `OG_OT_NudgeFloatProp`: generic nudge with val_min/val_max clamping
- ✅ `OG_PT_Platform` panel:
  - Sync section: period (0.5–300s), phase (0–0.9), ease-out/in (0–0.5), wrap-phase toggle
  - Live waypoint count + status
  - notice-dist section with always-active toggle for plat-eco
  - plat-button path status
- ✅ `OG_OT_TogglePlatformWrap`, `OG_OT_SetPlatformDefaults`
- ✅ Pre-testing bugs fixed:
  - wrap-phase bit: was 1, correct is 8 (bit 3 of fact-options)
  - lump key: was "fact-options", correct is "options"
  - Missing operator: og.nudge_float_prop now exists

---

## Known Unknowns — ALL RESOLVED

- ✅ `sync` lump type tag `"float"` confirmed correct (Entity.cpp iterates json[1..] into vector<float>)
- ✅ `options` lump key confirmed via `(res-lump-value ent 'options fact-options)` in fact-h.gc
- ✅ wrap-phase bit value confirmed: `(defenum fact-options (wrap-phase 3))` → 1<<3 = 8
- `trans-offset` for plat-button: defaults to zero-vector if absent — fine for most cases

---

## Platform Workflow (for user)

### Moving platform (plat / plat-eco / side-to-side-plat):
1. Place ACTOR_plat_<uid> empty in Blender
2. Add ≥2 waypoints via Waypoints panel
3. Adjust period/phase/easing in Platform panel (or leave defaults)
4. Export & Build → `sync` + `path` lumps emitted automatically

### Elevator (plat-button):
1. Place ACTOR_plat-button_<uid> empty
2. Add ≥2 waypoints: wp_00 = start (bottom), wp_01 = end (top)
3. Export & Build → `path` lump emitted

### Eco platform (plat-eco):
1. Same as moving platform
2. Notice Distance in Platform panel:
   - ∞ (always active) = platform moves regardless of eco
   - Set a range (e.g. 20m) = needs blue eco within that range

---

## Per-Actor Custom Properties

| Property         | Default | Range    | Notes                                    |
|------------------|---------|----------|------------------------------------------|
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
- [ ] wrap-phase: loops one-way (A→B→A→B no easing at ends) when og_sync_wrap=1
- [ ] phase offset: two platforms placed with phase=0.0 and phase=0.5 are staggered
- [ ] Platform panel appears only when a platform ACTOR_ empty is selected
- [ ] Waypoints panel appears for plat/plat-eco (not just enemies)
- [ ] Nudge clamping works: period can't go below 0.5s
