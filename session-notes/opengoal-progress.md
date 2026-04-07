# OpenGOAL Blender Addon — Session Progress

## Status: WORKING ✅
Play button successfully launches game and spawns in custom level.

## Official Addon
`addons/opengoal_tools.py` — install this in Blender.
**Important:** After installing, close and reopen Blender to clear module cache.

## Scratch / In-Progress
`scratch/opengoal_tools_camera_test.py` — camera feature branch, not yet merged to main.

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
- `"ready" in r` matched console noise → triggered spawn too early
- Fix: `"'ready" in r` — matches GOAL symbol return only

### 5. (bg) in run_after_listen causing repeating REPL warnings
- Fix: startup.gc contains ONLY `(lt)`. `(bg)` sent manually after `*game-info*` confirmed ready.

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
7. sleep 2.0s → `goalc_send("{camera_nrepl_expr}")` for each camera trigger

## Camera System (feature/camera branch)

### Research complete — 3 iterations
Full research document: `knowledge-base/opengoal/camera-system.md`

### Architecture confirmed:
- Camera entities go in JSONC **actors array** (not a separate cameras array)
- `etype: "camera-tracker"` — safe, no init-from-entity!
- `change-to-entity-by-name` finds actors by `name` lump ✓
- `cam-state-from-entity` reads lumps to determine camera mode:
  - no special lumps → `cam-fixed` (locked camera)
  - `align` lump → `cam-standoff` (side-scroller, follows player at offset)
  - `pivot` lump → `cam-circular` (orbit around point)
- Trigger volumes spawned via nREPL after level load (obs.gc AABB approach)

### Current scratch build bugs (priority order):
1. **Camera quat export** — needs testing in-game. Blender camera -Z = look direction,
   game camera -Z = look direction, but Blender Y-up vs game Y-up may need adjustment.
2. **vol lump format** — currently exports 8 corners, should be 6 plane equations.
   Low priority — vol lump not used by runtime trigger (we use obs.gc AABB).
3. **No standoff support** — only cam-fixed implemented. Need `align` lump export.
4. **Trigger volumes are AABB only** — no OBB/rotation support yet.

### Key source file confirmed working:
`scratch/opengoal_tools_camera_test.py` — has camera panel, JSONC export, nREPL trigger spawning

### 📌 NEXT SESSION: Implementation
1. Start from `scratch/opengoal_tools_camera_test.py`
2. Fix camera quat export (test simple forward-facing camera first)
3. Add cam-standoff mode (add `align` property to CAMERA_ empty, export `trans`+`align` lumps)
4. Add `interpTime` and `fov` controls to Blender camera panel
5. Consider OBB trigger volumes (use mesh rotation matrix for plane normals)
6. Once working → promote to `addons/opengoal_tools.py` on `feature/camera`

---

## Enemy Spawning Status

### ✅ Confirmed Working
- babak, hopper, junglesnake

### 🔲 To Test Next (in tpage group order)
- **Sunken group**: bully, puffer, double-lurker
- **Misty group**: quicksandlurker, muse, bonelurker, balloonlurker
- **Maincave group**: gnawer, driller-lurker, dark-crystal (baby-spider partial)
- **Ogre group**: plunger-lurker (flying-lurker already works)
- **Robocave group**: cavecrusher

### ❌ Known Issues
- navmesh full pathfinding — no engine support yet

---

## Audio

### Status: ✅ CONFIRMED WORKING (merged to main)
- Feature branch: `feature/audio`
- Sound emitters work in-game (waterfall, village1 bank)
- See `session-notes/audio-panel-progress.md` for full details

---

## Branch Strategy

```
main            ← always installable, user-approved only
feature/audio   ← audio panel, sound emitters, music zones (clean)
feature/camera  ← camera trigger system (in progress)
```

Camera work lives on: **`feature/camera`**
- Working file: `scratch/opengoal_tools_camera_test.py`
- When ready to promote: copy to `addons/opengoal_tools.py` on this branch

