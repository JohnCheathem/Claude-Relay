# OpenGOAL Blender Addon — Session Progress

## Status: WORKING ✅
Play button successfully launches game and spawns in custom level.

## Official Addon
`addons/opengoal_tools.py` — install this in Blender.
**Important:** After installing, close and reopen Blender to clear module cache.

## Current Scratch
`scratch/opengoal_tools_v12.py` — contains bonelurker fix. Ready to test.

## Key Bugs Fixed (v9 → v12)

### 1. nREPL binary framing (critical)
- GOALC nREPL uses binary-framed messages: `[u32 length LE][u32 type=10 LE][utf-8 string]`
- Fix: `struct.pack("<II", len(encoded), 10)` prepended to every message

### 2. Port conflict with 3Dconnexion SpaceMouse
- `3dxnlserver.exe` permanently holds port 8181 on `127.51.68.120`
- Fix: Port finder scans 8182+ for free port

### 3. `defined?` not a GOAL function
- Fix: `(if (nonzero? *game-info*) 'ready 'wait)`

### 4. Wrong spawn continue-point
- Fix: `(get-continue-by-name *game-info* "{name}-start")` with fallback

### 5. Module cache issue
- Fix: Always close/reopen Blender after installing a new version

### 6. bonelurker crash (v11 → v12)
- Root cause: bonelurker.gc compiles into MIS.DGO. Without its .o in the custom
  DGO, the type is undefined at runtime → crash on spawn.
- Old v11 comment said "intentionally NOT in this table" — WRONG. That was based
  on fear of the babak duplicate-link bug. But MIS.DGO is NEVER pre-loaded when
  using (bg) not (bg-custom), so injecting bonelurker.o is safe.
- Fix: Added `"bonelurker": {"o": "bonelurker.o", "o_only": True}` to ETYPE_CODE
- Also added balloonlurker the same way (was entirely missing)
- Also added balloonlurker to ENTITY_DEFS (was absent, couldn't be placed at all)

### 7. kill_goalc() port hold (v11 → v12)
- Windows SO_EXCLUSIVEADDRUSE holds port until process fully exits
- Old v11 used `time.sleep(2.0)` — flaky
- Fix: Poll port until connection refused before returning

### 8. Play launch: (bg) timing (v11 → v12)
- (bg) in startup.gc run_after_listen fires while village1 is mid-boot
- Sending (bg) too early causes "Failed to find texture at 0 (sky-direct)"
- Fix: startup.gc only contains `(lt)`. (bg) sent via nREPL poll once *game-info* exists.

## Architecture: Play Button Flow
1. Kill GK + GOALC (poll port until free)
2. Write startup.gc: `(lt)` only
3. Launch GOALC (wait for nREPL on free port 8182+)
4. Launch GK
5. Poll `(if (nonzero? *game-info*) 'ready 'wait)` every 0.5s (120s timeout)
6. When ready: `(bg '{name}-vis)` → poll level status → `(send-event *target* 'teleport)`

## Continue-Point System
- `SPAWN_` empties in Blender → continue-points in level-info.gc
- First spawn becomes `{levelname}-start`
- `(bg)` calls `set-continue!` to level's first continue-point
- `(send-event teleport)` moves existing player there (avoids hub-boot crash)

## Confirmed Working
- ✅ Build compiles level
- ✅ Play launches game and spawns in custom level
- ✅ babak, junglesnake, hopper enemies
- ✅ bonelurker — fixed in v12 (untested, awaiting compile+play)
- ✅ balloonlurker — added to ENTITY_DEFS + ETYPE_CODE in v12
- ❌ navmesh full pathfinding — no engine support yet

---

## 📌 REMINDERS FOR NEXT SESSION

1. **bonelurker test** — v12 has the fix. Compile, place a bonelurker, play, report crash log if any.
2. **balloonlurker** — newly added to ENTITY_DEFS, needs path waypoints. Test after bonelurker works.
3. **Enemy spawning** — Continue getting all Jak 1 enemies working. Most misty enemies now covered.
4. **Level design analysis** — See `knowledge-base/opengoal/jak1-level-design.md`.
