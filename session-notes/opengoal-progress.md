# OpenGOAL Blender Addon — Session Progress

## Status: WORKING ✅
Play button successfully launches game and spawns in custom level.

## Official Addon
`addons/opengoal_tools.py` — install this in Blender.
**Important:** After installing, close and reopen Blender to clear module cache.

## Key Bugs Fixed (v9 → current)

### 1. nREPL binary framing (critical)
- GOALC nREPL uses binary-framed messages: `[u32 length LE][u32 type=10 LE][utf-8 string]`
- Fix: `struct.pack("<II", len(encoded), 10)` prepended to every message

### 2. Port conflict with 3Dconnexion SpaceMouse
- `3dxnlserver.exe` permanently holds port 8181 on `127.51.68.120`
- Fix: Port finder scans 8182+ for free port

### 3. `defined?` not a GOAL function
- Fix: `(if (nonzero? *game-info*) 'ready 'wait)`

### 4. False-positive ready check
- `"ready" in r` matched console noise like `"Listener: ready"` → triggered spawn too early → `*game-info* does not exist` crash
- Fix: `"'ready" in r` — matches GOAL symbol return only

### 5. (bg) in run_after_listen causing repeating REPL warnings
- `(bg)` in startup.gc under `og:run-below-on-listen` re-fires every GK reconnect
- Caused `[Warning] REPL Error: Compilation generated code, but wasn't supposed to` every ~5s after play
- Fix: startup.gc contains ONLY `(lt)`. `(bg)` sent manually via `goalc_send()` after `*game-info*` confirmed ready.

### 6. Wrong spawn continue-point
- Fix: `(get-continue-by-name *game-info* "{name}-start")` with fallback

### 7. Module cache issue
- Fix: Always close/reopen Blender after installing a new version

### 8. bonelurker crash
- bonelurker.gc compiles into MIS.DGO — needs .o injected into custom DGO
- Fix: `"bonelurker": {"o": "bonelurker.o", "o_only": True}` in ETYPE_CODE

### 9. kill_goalc() port hold
- Windows SO_EXCLUSIVEADDRUSE holds port until process fully exits
- Fix: Poll port until connection refused before returning

## Architecture: Play Button Flow
1. Kill GK + GOALC (poll port until free)
2. Write startup.gc: `(lt)` ONLY
3. Launch GOALC (wait for nREPL on free port 8182+)
4. Launch GK
5. Poll `(if (nonzero? *game-info*) 'ready 'wait)` — check `"'ready" in r` (with quote)
6. When ready: `goalc_send("(bg '{name}-vis)")` → sleep 1s → `(start 'play ...)`

## Enemy Spawning Status

### ✅ Confirmed Working
- babak
- hopper
- junglesnake

### 🔲 To Test Next (in tpage group order)
- **Sunken group**: bully, puffer, double-lurker
- **Misty group**: quicksandlurker, muse, bonelurker, balloonlurker
- **Maincave group**: gnawer, driller-lurker, dark-crystal (baby-spider partial)
- **Ogre group**: plunger-lurker (flying-lurker already works)
- **Robocave group**: cavecrusher

### ❌ Known Issues
- navmesh full pathfinding — no engine support yet

## 📌 REMINDERS FOR NEXT SESSION
1. Test spider, lurker-soldier, bonelurker
2. Document results in this file
3. Work toward full enemy compatibility matrix
