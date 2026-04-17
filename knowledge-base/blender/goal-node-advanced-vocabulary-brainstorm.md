# GOAL Node Editor — Advanced Vocabulary Brainstorm

> **Status:** Brainstorm / research doc. No implementation yet.
> **Purpose:** Catalogue everything a serious modder plausibly wants beyond the Level-A starter vocabulary, organised by user intent rather than GOAL primitive. Source pointers per category so future implementation sessions have a starting point.
> **Partner docs:** `goal-node-compiler-design.md`, `goal-node-vocabulary.md`, and every doc in `knowledge-base/opengoal/`.

---

## 0. Organising principle

The Level-A vocabulary was built bottom-up from GOAL primitives — "what can a deftype do in :trans, :event, :code." That works but doesn't answer "what does a modder want to accomplish." This doc inverts that: categorise by modder intent, then list the nodes that serve each intent. Many categories cross-cut the existing Level-A vocabulary, which is fine — the goal is coverage, not orthogonality.

Three-tier priority:

- **T1** — must-have for a convincing demo; covers the patterns already in `goal-code-examples.md` and `goal-scripting.md`
- **T2** — advanced but well-scoped; serious modders will want these within a few weeks
- **T3** — ambitious, speculative, or needs substantial research before scoping

Implementation status key:
- `DONE` — already in Level-A vocabulary
- `skeleton` — good candidate to add as an IR stub with no emitter template yet
- `full` — needs IR + template + validation + tests
- `research` — design questions unresolved

---

## 1. Scene-query & iteration nodes — **the critical gap**

The user flagged this directly: *"lets maybe add nodes for referencing collections, for each object etc."* This is the biggest category the Level-A vocabulary doesn't touch. Level A assumes one actor = one target. Real modding scenarios almost always involve *sets* of actors.

These nodes output **actor references** (or lists thereof) that downstream Action nodes consume.

### 1.1 Collection references

| Node | What it does | T | Notes |
|---|---|---|---|
| `ActorsInCollection` | All `ACTOR_*` objects inside a named Blender collection → list of lump names | T1 | `full` — walks scene at compile time, emits a static list into the deftype's init |
| `ActorsByType` | All actors with etype `babak` in scene → list | T1 | `full` — resolves at compile time |
| `ActorsByNamePattern` | Regex/glob match on object names → list | T2 | `full` |
| `ActorInCollection` | Single actor by name inside a collection, with fallback warning if absent | T1 | `full` |

**Why important:** A "spawn-all-wave-1-enemies" or "open-all-doors-in-this-area" node needs a way to name a *set*. Without this, users must manually list every target — node graphs get enormous fast.

**Design question:** does the list resolve at *compile time* (list of lump names is baked into GOAL source) or *runtime* (GOAL iterates `*active-pool*` and filters)? Compile-time is simpler and covers most cases — but if actors are birthed dynamically, it misses them. Start compile-time; add runtime version only if needed.

**Validation:** warn on empty collections (probably a bug). Error if collection doesn't exist.

### 1.2 ForEach iteration

| Node | What it does | T | Notes |
|---|---|---|---|
| `ForEachActor` | Runs connected action(s) once per actor in a list, binding `$current` | T1 | `full` — emits a GOAL `foreach` over a static list |
| `ForEachInCollection` | Convenience: combines `ActorsInCollection` + `ForEachActor` | T1 | `full` |

**Design question:** GOAL's stack discipline makes `dolist` style fine but closures that reference `$current` need lexical resolution. For Level-A-style emission, unroll at compile time — emit one copy of the body per actor. That's ugly in generated source (20 babaks = 20 copies of the action body) but trivially correct. Compact emission (`(dolist (x '("a" "b" "c")) ...)`) needs deeper GOAL research.

Unrolling is the pragmatic default. Generated code gets big but goalc doesn't care.

### 1.3 Scene queries at runtime

| Node | What it does | T | Notes |
|---|---|---|---|
| `ClosestActorToJak` | Output the closest actor of a given type — polls each frame | T2 | `full` — emits a loop over the list |
| `ActorCount` | Number of live actors matching a predicate | T2 | `full` |
| `CountByPermStatus` | Count actors with `complete` or `dead` flag set — progression tracking | T2 | `full` |

These resolve at runtime, not compile time. Useful for "close the door when all switches are pressed" patterns.

### 1.4 Blender-side geometry nodes

These read Blender scene data and emit static values into compiled GOAL. They don't correspond to GOAL calls at runtime — they're *scene queries*.

| Node | What it does | T | Notes |
|---|---|---|---|
| `SpawnPointRef` | Read the `SPAWN_` empty's position → vector | T1 | `full` — emits hardcoded coords |
| `CameraPoseRef` | Read a `CAMERA_` empty's trans + quat → vector + quat | T1 | `full` |
| `PathPointAt` | Read Nth vertex of a curve → vector | T2 | `full` |
| `GetObjectPosition` | Arbitrary Blender object's world position → vector | T2 | `full` |
| `GetObjectBoundingBox` | AABB of a mesh → 6 floats (xmin/xmax/ymin/ymax/zmin/zmax) | T2 | `full` |
| `CustomProperty` | Read a Blender custom property from an object → value of declared type | T2 | `full` |

**Why powerful:** user can design a level in Blender and wire positions/bounds into GOAL code declaratively. No more typing coordinates into a node's float socket.

---

## 2. Level & world control

Source: `knowledge-base/opengoal/level-flow.md`, `level-transitions.md`.

The level-flow command system has a rich vocabulary the Level-A doesn't touch. Each of these maps to a `load-command` or `execute-command` call.

### 2.1 Level loading

| Node | Emits | T | Notes |
|---|---|---|---|
| `LoadLevel` | `(want-levels 'level-name #f)` | T2 | `full` |
| `LoadTwoLevels` | `(want-levels 'lev0 'lev1)` — both slots | T2 | `full` |
| `UnloadLevel` | `(want-levels #f #f)` | T2 | `full` |
| `SetVisLevel` | `(want-vis 'nick)` | T3 | `research` — vis-nick to level mapping is per-level |
| `DisplayLevel` | `(display-level 'name 'mode)` | T2 | `full` |

**Modder use case:** A multi-zone custom level transitions between rooms by loading/unloading sub-levels.

### 2.2 Continues & checkpoints

| Node | Emits | T | Notes |
|---|---|---|---|
| `SetCheckpoint` | Writes a `continue-point` ref, sends `'update-continue` to Jak | T2 | `research` — interacts with existing `CHECKPOINT_` system in the addon |
| `GetContinueByName` | Looks up `continue-point` from `*game-info*` → ref | T2 | `full` |
| `TeleportToContinue` | `(start 'play (get-continue-by-name ...))` | T3 | `research` — might only be safe from startup.gc |

### 2.3 Load-boundary triggers

`load-boundary` is how vanilla levels fire level-load commands when the player crosses an invisible polygon. The addon does not support them yet (flagged in `future-research.md §14`). A node-graph trigger type could let modders define them visually.

| Node | Purpose | T | Notes |
|---|---|---|---|
| `OnLoadBoundaryCrossed` | Fire when player crosses a `BOUNDARY_` mesh | T3 | `research` — needs `load-boundary-data.gc` injection, which is a global file patch |

### 2.4 Screen effects

| Node | Emits | T |
|---|---|---|
| `Blackout` | `(blackout <frames>)` — pure black for N frames | T1 `full` |
| `FadeToBlack` | Animated `set-setting! 'bg-a` lerp | T1 `full` (we already have SetSetting; this is a convenience node) |
| `FadeFromBlack` | Inverse | T1 `full` |
| `SetBackgroundTint` | `set-setting! 'bg-r/g/b/a` all at once | T2 `full` |

### 2.5 Time of day & mood

Source: `lighting-system.md`, `time-of-day-mood.md`.

| Node | Emits | T | Notes |
|---|---|---|---|
| `SetTimeOfDay` | `(time-of-day N)` — 0-24 | T2 `full` |
| `ResumeTimeOfDay` | `(time-of-day -1)` | T2 `full` |
| `SetMood` | `set-setting! 'mood 'name` | T3 `research` — may need per-level mood registration |
| `SetFog` | set-setting! fog params | T3 `research` |

### 2.6 Auto-save

| Node | Emits | T |
|---|---|---|
| `AutoSave` | `(auto-save ...)` | T3 `research` — Jak 1 has no free save slots; may only work in specific contexts |

---

## 3. Game state & progression

Source: `knowledge-base/opengoal/trigger-system.md §6`, `entity-spawning.md §14`.

### 3.1 Perm-status manipulation

The `entity-perm-status` bitfield is already used by `KillTarget` (sets `dead`). Broader control:

| Node | Purpose | T | Notes |
|---|---|---|---|
| `SetPermFlag` | Set any perm-status bit on an actor | T1 `full` — generalises KillTarget |
| `ClearPermFlag` | Inverse | T1 `full` |
| `CheckPermFlag` | Returns boolean — usable as a trigger condition | T2 `full` (needs conditional trigger support, see §5) |
| `MarkComplete` | Shortcut: set `complete` bit | T1 `full` |
| `MarkRealComplete` | Shortcut: set `real-complete` (power cells etc.) | T2 `full` |

**Why important:** `trigger-system.md §1` documents that the `complete` bit is the main wiring mechanism for buttons → doors. Doors poll their `state-actor`'s complete bit. Modders will want to set/check this constantly.

### 3.2 Game-task system

Source: `trigger-system.md §6-7`. Limited to 116 slots (2 usable for custom tasks without patching).

| Node | Purpose | T | Notes |
|---|---|---|---|
| `SetTaskStatus` | `(task-node-close-all! ...)` / similar | T3 `research` — task system is delicate |
| `CheckTaskStatus` | conditional on `(closed?! ...)` | T3 `research` |
| `GrantPowerCell` | spawn a `fuel-cell` with the right task index | T3 `research` — requires task slot management |

**Why hard:** task slots are a global resource. Misuse corrupts save games. Modders need clear UI boundaries. Not T1.

### 3.3 Pickup spawning

| Node | Emits | T | Notes |
|---|---|---|---|
| `SpawnOrb` | Spawn a `money` (orb) at position | T2 `full` — needs spawn-in-void pattern |
| `SpawnFuelCell` | Spawn a `fuel-cell` | T3 `research` — needs task wiring |
| `SpawnBuzzer` | Spawn a scout fly | T3 `research` |
| `SpawnCrate` | Spawn a `crate` with a drop-table | T2 `full` — uses `crate-type` lump |

---

## 4. Entity lifecycle (spawn/despawn beyond KillTarget)

Source: `trigger-system.md §9`, `goal-scripting.md §16`.

### 4.1 Spawn commands

| Node | Emits | T | Notes |
|---|---|---|---|
| `BirthEntity` | `(alive "name")` load-command or runtime `(birth ...)` | T2 `full` |
| `SpawnEntityAt` | `(process-spawn ...)` with explicit position | T3 `research` — spawn-without-entity-actor is advanced |
| `SpawnChildProcess` | `(get-process *default-dead-pool* ...)` | T3 `research` — needed to unblock sequences-pause-other-behaviour |

The `SpawnChildProcess` node is the key unlock for sequences that don't halt the rest of the entity's behaviour. Worth T2 if we want Level B.

### 4.2 Lifecycle events

| Node (trigger) | Fires on | T |
|---|---|---|
| `OnDestroy` | When this entity dies — emit `:exit` body | T2 `full` |
| `OnTouchedByJak` | `:event 'touch` | T1 `full` — already expressible via OnEvent but worth a dedicated node |
| `OnAttackedByJak` | `:event 'attack` | T1 `full` |

---

## 5. Conditionals & data flow

### 5.1 Conditional triggers

Level A has triggers that fire on events or polled conditions. Missing: triggers that fire **once a predicate turns true** — stateless boolean checks as gates.

| Node | Purpose | T | Notes |
|---|---|---|---|
| `If` | Wrap an action with a condition; only runs if condition is true | T1 `full` |
| `And`/`Or`/`Not` | Logical combinators over conditions | T2 `full` |
| `CompareValue` | numeric/string comparison → boolean | T2 `full` |
| `CheckPlayerState` | Jak-is-grounded, in-air, attacking, swimming, etc. | T2 `research` — maps to `*target* control status` flags |
| `RandomChance` | Fire with N% probability (1-in-N) | T2 `full` — emits `(< (rand-vu-int-count N) threshold)` |

### 5.2 Variables

Currently every Action that needs state adds its own field. For more general state sharing across actions on one entity:

| Node | Purpose | T | Notes |
|---|---|---|---|
| `DeclareVariable` | Add a named field to the entity with a type | T2 `full` |
| `SetVariable` | `(set! (-> self NAME) value)` | T2 `full` |
| `GetVariable` | Reference `(-> self NAME)` in other nodes' inputs | T2 `full` (needs data-flow sockets) |
| `IncrementVariable` | `(+! (-> self N) value)` | T2 `full` |
| `TimerVariable` | A field that tracks elapsed time since a reset | T2 `full` |

**Design question:** this crosses into Level-B territory because it introduces data flow between nodes beyond the pure control flow we have today. Worth it for flexibility but big UX surface. Might warrant a *separate* follow-up design document.

---

## 6. Motion & physics (beyond Rotate/Oscillate/Lerp)

### 6.1 More motion primitives

| Node | Purpose | T |
|---|---|---|
| `LookAtJak` | Every frame, rotate to face Jak on Y axis | T1 `full` |
| `LookAtTarget` | Rotate to face arbitrary actor | T1 `full` |
| `MoveTowardsTarget` | Walk toward another actor | T2 `research` — needs nav awareness |
| `PathFollow` | Follow a waypoint path (addon already exports `path` lumps) | T1 `full` |
| `PathPingPong` | Path + ping-pong direction | T1 `full` |
| `OrbitAround` | Circle a point | T2 `full` |
| `ConstrainToSphere` | Clamp position to within a sphere of centre | T2 `full` |

### 6.2 Jak interactions

| Node | Emits | T |
|---|---|---|
| `LaunchJak` | `(send-event *target* 'launch N #f #f 0)` — jump pads | T1 `full` |
| `PushJak` | apply momentum | T2 `research` |
| `TeleportJak` | Move `*target* control trans` directly | T2 `research` |
| `ResetJakHeight` | `(send-event *target* 'reset-height)` | T1 `full` |
| `KillJak` | Triggers death | T3 — gameplay hazard, needs care |

---

## 7. Camera control (expanded)

Source: `camera-system.md`, `future-research.md §2-3`.

| Node | Purpose | T | Notes |
|---|---|---|---|
| `CameraSwitchToMarker` | `(send-event *camera* 'change-to-entity-by-name "cam-marker-N")` | T1 `full` |
| `CameraClear` | `(send-event *camera* 'clear-entity)` | T1 `full` |
| `CameraTeleport` | `'teleport` (hard cut, no blend) | T1 `full` |
| `CameraBlend` | `'blend-from-as-fixed` | T2 `full` |
| `CameraSpline` | Activate cam-spline mode for a scripted fly-through | T3 `research` — `future-research.md §2` flags this as unexplored territory |
| `CameraString` | Rubber-band follow mode | T3 `research` — `future-research.md §6` |
| `CameraShake` | Play a shake preset | T2 `research` — need to find the right engine hook |

---

## 8. Animation & skeletons

Source: `goal-scripting.md §14`.

Requires art assets baked in the DGO — so these are T2 at best for a general-purpose tool.

| Node | Purpose | T |
|---|---|---|
| `PlayAnimation` | `(ja :group! name-ja :num! (seek!))` | T2 `full` |
| `LoopAnimation` | `(ja :group! name-ja :num! (loop!))` | T2 `full` |
| `BlendAnimation` | Channel-push two animations with crossfade | T3 `full` |
| `WaitForAnimation` | `(until (ja-done? 0) (suspend))` — only in sequences | T2 `full` |
| `SpawnManipy` | Scripted animation on an existing engine actor (no custom art) | T2 `full` — the `manipy-spawn` pattern |

---

## 9. Sound (expanded)

Source: `audio-system.md`, `goal-scripting.md §12`.

We already have `PlaySound`. Extend with:

| Node | Purpose | T |
|---|---|---|
| `PlayMusicTrack` | `set-setting! 'music 'name` | T1 `full` |
| `StopMusic` | `set-setting! 'music #f` | T1 `full` |
| `SetMusicVolume` | `set-setting! 'music-volume 'abs N` | T1 `full` (already expressible via SetSetting) |
| `StopSound` | `(sound-stop <id>)` — needs sound-ID tracking | T2 `full` |
| `SetSoundFlava` | `set-setting! 'sound-flava` | T2 `full` |

---

## 10. Particle effects

Source: `particle-effects-system.md`, `future-research.md §11`.

| Node | Purpose | T | Notes |
|---|---|---|---|
| `SpawnPart` | Spawn a named particle group at a position | T2 `research` — need confirmation that vanilla particle groups work from custom obs.gc |
| `PartTracker` | Attach a particle group to an actor that follows it | T2 `research` |
| `ParticleBurst` | One-shot particle emission | T2 `full` |

Flagged as unexplored in `future-research.md`. Real research needed before locking in a node vocabulary.

---

## 11. Enemy AI control

Source: `enemy-activation.md`, `goal-scripting.md §7`.

Limited to nav-enemies (babak, lurker-crab, hopper, snow-bunny, kermit).

| Node | Emits | T |
|---|---|---|
| `CueEnemyChase` | `(send-event enemy 'cue-chase)` | T1 `full` |
| `CueEnemyPatrol` | `(send-event enemy 'cue-patrol)` | T1 `full` |
| `FreezeEnemy` | `(send-event enemy 'go-wait-for-cue)` | T1 `full` |
| `SetIdleDistance` | res-lump override (currently a no-op per `future-research.md §4`) | T3 `research` |
| `EnemyDropReward` | Spawn orb/cell on kill — existing addon logic | T2 `research` |

---

## 12. Water, environment, hazards

Source: `water-system.md`.

| Node | Purpose | T | Notes |
|---|---|---|---|
| `SetWaterHeight` | Animate water surface Y | T2 `research` — water-anim has its own subsystem |
| `SpawnWaterSplash` | Particle + sound at position | T3 `research` |
| `SetAmbientIntensity` | fog/light overrides via settings | T3 `research` |

---

## 13. Doors & buttons (wiring shortcuts)

Source: `door-system.md`.

The addon already exposes `eco-door`, `sun-iris-door`, `basebutton`, `plat-button`, `launcherdoor` as entity types. What we'd add are **wiring shortcuts** that emit the correct trigger/event relationships without the user typing lump keys:

| Node | Purpose | T |
|---|---|---|
| `WireButtonToDoor` | button's `notify-actor` → door's `state-actor`, both wired | T2 `full` — emits proper lump configuration |
| `DoorOpenOnAllComplete` | Door opens when all listed actors have `complete` flag — for "kill all enemies to open door" patterns | T2 `full` |
| `ShortcutIrisDoor` | Pre-wired proximity iris door | T2 `full` |

These are *authoring shortcuts* — they don't add new runtime capability but compress common wiring patterns into one node.

---

## 14. Dialogue & HUD

Source: scattered; probably needs more research.

| Node | Purpose | T | Notes |
|---|---|---|---|
| `ShowSubtitle` | Display a text line for a duration | T3 `research` — subtitle system entry points unclear |
| `ShowHUDIcon` | Show a status indicator | T3 `research` |
| `DebugPrint` | `(format 0 "msg~%")` — developer output | T1 `full` — can already do via Raw GOAL; a dedicated node is friendlier |
| `HidePauseMenu` | `set-setting! 'allow-progress #f` | T1 `full` — already expressible via SetSetting |

---

## 15. Debug & authoring tools

| Node | Purpose | T |
|---|---|---|
| `DebugPrint` | Log a message | T1 `full` |
| `DebugAssert` | Crash the game if condition false (catch bugs early) | T2 `full` |
| `DebugDrawSphere` | Draw a debug sphere in-game (only visible in debug builds) | T2 `research` — needs engine debug API |
| `Comment` | Graph-only node — holds notes, emits nothing | T1 `full` — purely UI, contributes an empty `Contributions` |
| `Group` | Visual grouping of related nodes — emits frame, no code | T1 `full` — UI-only |

Purely UX nodes (Comment/Group) are important for large graph readability. Zero emission work, just registration.

---

## 16. Advanced flow control

Beyond Sequence + Wait:

| Node | Purpose | T | Notes |
|---|---|---|---|
| `Repeat` | Run a sequence N times | T2 `full` |
| `RepeatUntil` | Run a sequence until a condition | T2 `full` |
| `Branch` | If-then-else flow (different steps per branch) | T2 `full` |
| `Switch` | Multi-way dispatch on a value | T2 `full` |
| `ParallelSequence` | Multiple step-chains in parallel (needs child processes) | T3 `research` |
| `YieldUntil` | Wait until a condition becomes true | T2 `full` — effectively `(until cond (suspend))` |

`Branch` and `Switch` are the big gaps in Level A's expressivity. Without them, users fall back to `Raw GOAL` for anything involving runtime decisions.

---

## 17. Multi-entity composition (SUBGRAPHS)

Possibly the largest opportunity — and the most UX-intensive.

### 17.1 Reusable subgraphs

| Node | Purpose | T | Notes |
|---|---|---|---|
| `Subgraph` | Reference a named subgraph — inputs/outputs match socket declarations | T2 `full` — Blender node groups support this natively |
| `SubgraphInput` / `SubgraphOutput` | Define subgraph boundaries | T2 `full` |

**Modder use case:** a "damage-on-contact" subgraph that can be reused across many actors. Without this, the same pattern is re-authored per actor.

### 17.2 Cross-entity wiring

| Node | Purpose | T | Notes |
|---|---|---|---|
| `SceneLevelEvent` | Broadcast an event to all actors matching a predicate | T2 `full` — iteration-based |
| `GlobalVariable` | Shared state across multiple entity graphs (one backing `define` in a shared code block) | T3 `research` — needs non-entity GOAL output |

---

## 18. Meta: compiler hints & export control

| Node | Purpose | T |
|---|---|---|
| `DisableExport` | Mark a subgraph as disabled — emitter skips it | T1 `full` |
| `PlatformGate` | Only emit if in `debug` or `release` build | T3 `full` |
| `PerformanceNote` | Warn at compile time if this node pattern is expensive | T3 `full` — validation, not emission |

---

## 19. What haven't we thought of? (open brainstorm)

### Genuinely novel categories worth exploring

**Replays and deterministic playback.** Jak 1 has no native replay system but a "record my sequence" node could be powerful for cutscene authoring — watch Jak in the scene, bake his positions into a scripted path for future playback.

**Live parameter tweaking.** An addon panel that exposes graph parameters as sliders during gameplay (via nREPL). "Make this door open slower" without recompile-rebuild.

**Graph diff + merge.** As two modders collaborate, merging graph changes. The text-block approach can use git; graphs need structural diffing. Not a node; a tooling concern.

**AI-assisted authoring.** Given a natural-language description, generate a graph. Leverages the Claude integration this project is already built around. Doesn't need node changes — needs a separate operator that produces a graph from a prompt.

**Template library with previews.** Pre-built subgraphs for "rotating door," "three-platform bridge," "enemy patrol with chase." Node palette becomes a recipe browser. Zero runtime cost, enormous onboarding win.

**Runtime graph editing.** Edit a graph while the game runs, nREPL pushes changes live. Requires incremental compile + hot-swap of GOAL types. Very ambitious; probably needs its own design round.

### Categories we've underweighted

**Error recovery in sequences.** What if a `SendEvent To` inside a sequence fails (target doesn't exist)? Right now: silent. Should sequences have an `OnStepFailed` branch? Current answer: no, use `RawGoal` for advanced error handling. But worth surfacing.

**Sequence cancellation.** Once a sequence is running, can another trigger abort it? Currently: no explicit mechanism. Would need a `CancelSequence` node or automatic gate-flag interlocking.

**Time synchronisation.** Multiple actors doing synchronised animation (opening door + playing sound + camera shake all exactly in sync). Can do today with one sequence driving everything, but if the sources need to be separate actors, needs either a shared clock or a master-slave setup.

**Per-instance configuration at compile time.** The Blender object has custom properties; a node reads those and emits different GOAL per-instance. This is a bigger version of our lump-mode targeting — essentially template parameters for reused deftypes.

---

## 20. Prioritised implementation roadmap

### T1 additions to round out the Level-A vocabulary (aim: another ~15 nodes)

**Scene-query (critical):** ActorsInCollection, ActorsByType, ActorInCollection, ForEachActor/InCollection, SpawnPointRef, CameraPoseRef
**Game state:** SetPermFlag, ClearPermFlag, MarkComplete
**Flow:** If, DebugPrint, Comment, Group
**Camera:** CameraSwitchToMarker, CameraClear, CameraTeleport
**Screen:** Blackout, FadeToBlack, FadeFromBlack
**Motion:** LookAtJak, LookAtTarget, PathFollow, PathPingPong
**Sound:** PlayMusicTrack, StopMusic
**Enemy:** CueEnemyChase, CueEnemyPatrol, FreezeEnemy
**Jak:** LaunchJak, ResetJakHeight

Rough count: ~25 T1 additions, bringing the vocabulary to ~45 nodes total.

### T2 for serious modding (next phase)

**Variables:** DeclareVariable, SetVariable, GetVariable
**Conditionals:** And/Or/Not, CompareValue, CheckPlayerState, RandomChance
**Subgraphs:** Subgraph, SubgraphInput/Output
**Lifecycle:** BirthEntity, OnDestroy
**Animation:** PlayAnimation, LoopAnimation, WaitForAnimation, SpawnManipy
**Advanced flow:** Branch, Switch, Repeat, YieldUntil
**Level control:** LoadLevel, UnloadLevel, DisplayLevel, SetTimeOfDay
**Wiring shortcuts:** WireButtonToDoor, DoorOpenOnAllComplete, ShortcutIrisDoor

### T3 — ambitious, research-first

**CameraSpline, CameraString, load-boundaries, particle system, battlecontroller, global variables, live parameter tweaking.**

Each needs dedicated research before it can be scoped. `future-research.md` already has some of the upfront work for camera-spline and particles.

---

## 21. Open questions for discussion

1. **Scope ceiling.** Is the goal a polished Level-A addon (~25-45 nodes) or an ambitious Animation-Nodes-level platform (~100+ nodes)? These are wildly different engineering investments.

2. **Subgraphs or no?** Blender supports node groups natively. Adding them unlocks huge expressivity but demands UX decisions (input/output declaration, parameterisation, versioning). T2 priority but a big T2.

3. **Runtime iteration or compile-time unrolling?** Simple unrolling handles 90% of cases and keeps emission straightforward. Runtime `dolist`-style needs deeper GOAL research. Recommend starting unrolled.

4. **Variables & data flow.** Do we want nodes that output values to other nodes' inputs (true data-flow graph) or keep the current pure-control-flow model? The Value sockets we have today are *parameter* sockets (static at compile time); runtime data flow is categorically different.

5. **Validation vs permissiveness.** Today's validator is strict. Advanced modders may want to silence certain warnings (e.g. "yes I really want two Rotates on the same axis"). Do we add a per-node `_suppress` mechanism?

6. **Integration with existing Blender concepts.** Does the graph system *own* trigger wiring, or does it coexist with the Actor Links / Volume Links panels already in the addon? Clarity needed before UI work.

7. **Name collision across actor types.** Two actors with etype `door-slow` and `door-fast` sharing the name prefix `door-` — should `ActorsByType("door-")` match both via prefix, or require exact match? Modders will expect both at different times.

---

## 22. Source pointers per category

| Category | Primary source doc |
|---|---|
| Level loading | `level-flow.md` |
| Entity spawning | `entity-spawning.md` |
| Game state | `trigger-system.md` §6-7 |
| Camera | `camera-system.md` |
| Platforms | `platform-system.md` |
| Doors | `door-system.md` |
| Particles | `particle-effects-system.md` |
| Enemy activation | `enemy-activation.md` |
| Navmesh | `navmesh-system.md` |
| Audio | `audio-system.md` |
| Lighting / ToD | `lighting-system.md`, `time-of-day-mood.md` |
| Water | `water-system.md` |
| Lumps | `lump-system.md` |
| Future work | `future-research.md` |

---

## 23. Next steps (proposed)

Before any more code:

1. **User decision on scope ceiling** (Q1 above) — sets the project shape.
2. **Pick 8-10 T1 candidates** from §20 to add as IR skeletons + basic templates. Stop there, get those to compile cleanly, commit.
3. **One more research pass** on particle effects and camera-spline (T3 candidates currently marked `research`) so we know which are realistic T2 candidates.
4. **Then, and only then, UI design conversation.** The full vocab needs to be picked before we can design a UI that handles it.
