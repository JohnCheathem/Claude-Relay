# GOAL Code System — Custom Logic in Custom Levels

> Covers the full goal-code feature on `feature/goal-code`: how custom GOAL types are defined, spawned, wired to trigger volumes, and exported into obs.gc.

---

## Overview

The GOAL Code system lets you define arbitrary GOAL logic directly in Blender and have it compiled into your level automatically on export. No manual file editing required.

Three components work together:

| Component | What it does |
|---|---|
| **Custom Type Spawner** | Places a correctly-named `ACTOR_` empty for any deftype you write |
| **GOAL Code Panel** | Attaches a Blender text block to an actor; exported verbatim into `*-obs.gc` |
| **VOL_ → custom actor wiring** | Links a trigger volume to a custom actor; auto-emits a `vol-trigger` GOAL entity |

---

## 1. Custom Type Spawner

**Location:** Spawn panel → **⚙ Custom Types**

Type any deftype name (lowercase, hyphens allowed, e.g. `die-relay`) and hit **Spawn**. Places an `ACTOR_die-relay_0` empty at the 3D cursor, coloured yellow-green to distinguish it from built-in actors.

The name must:
- Be lowercase letters, digits, hyphens only
- Not already be a built-in entity type (the spawner rejects conflicts)
- Match the `deftype` name in your GOAL code exactly

---

## 2. GOAL Code Panel

**Location:** N-panel → OpenGOAL tab → Selected Object → **GOAL Code** (sub-panel)

Only appears when a non-built-in `ACTOR_` empty is selected.

### Workflow

1. Select your custom `ACTOR_` empty
2. **Create boilerplate block** — creates a Blender text block pre-filled with a minimal `deftype` / `defstate` / `init-from-entity!` skeleton
3. Open the text editor (Shift+F11) → **Open in Editor** button to jump straight to the block
4. Replace the boilerplate with your actual GOAL code
5. Export — the block is appended verbatim to `goal_src/levels/<n>/<n>-obs.gc`

### Rules
- One text block per actor, but multiple actors can share the same block — it's emitted only once
- The **enabled** toggle (checkbox in the panel header row) controls whether the block exports
- The panel shows a line count and "will inject / disabled" status
- Compile errors appear in the goalc build log, not in Blender

### Boilerplate template

```lisp
;;-*-Lisp-*-
(in-package goal)

(deftype <etype> (process-drawable)
  ()   ;; add fields here starting at :offset-assert 176
  (:states <etype>-idle))

(defstate <etype>-idle (<etype>)
  :code
    (behavior ()
      (loop (suspend))))

(defmethod init-from-entity! ((this <etype>) (arg0 entity-actor))
  (set! (-> this root) (new 'process 'trsqv))
  (process-drawable-from-entity! this arg0)
  (go <etype>-idle)
  (none))
```

---

## 3. VOL_ → Custom Actor Wiring

Place a `VOL_` mesh trigger volume. In its **Volume Links** panel, set the target to any `ACTOR_<custom-type>_N` empty.

On export the exporter:
1. Detects the custom target via `_classify_target` → `"custom"`
2. Calls `collect_custom_triggers` → emits a `vol-trigger` JSONC actor with AABB bounds + `target-name` lump
3. Emits the `vol-trigger` GOAL deftype in obs.gc via `write_gc(has_custom_triggers=True)`

The `vol-trigger` entity sends:
- `'trigger` to the target when Jak **enters** the volume
- `'untrigger` to the target when Jak **exits** the volume

The target's GOAL code handles `'trigger` in its `:event` handler.

**No manual lump work needed** — bounds are derived from the VOL_ mesh automatically.

---

## 4. Complete Example: Trigger Volume Kills a Platform

### What it does
Jak walks into a zone → platform disappears → relay process dies (nothing keeps running).

### Step by step

**In Blender:**

1. Spawn a platform (e.g. `eco-platform`). Note its entity lump name: `eco-platform-0`
2. Spawn Panel → ⚙ Custom Types → type `die-relay` → Spawn
3. Select `ACTOR_die-relay_0` → GOAL Code → Create boilerplate → replace with:

```lisp
(deftype die-relay (process-drawable)
  ((target-name string :offset-assert 176))
  :heap-base #x70
  :size-assert #xb4
  (:states die-relay-idle))

(defstate die-relay-idle (die-relay)
  :event
  (behavior ((proc process) (argc int) (message symbol) (block event-message-block))
    (case message
      (('trigger)
       (let ((target (process-by-ename (-> self target-name))))
         (when target
           (format 0 "[die-relay] killing ~A~%" (-> self target-name))
           (send-event target 'die)))
       (deactivate self))))
  :code
  (behavior ()
    (loop (suspend))))

(defmethod init-from-entity! ((this die-relay) (arg0 entity-actor))
  (set! (-> this root) (new 'process 'trsqv))
  (process-drawable-from-entity! this arg0)
  (set! (-> this target-name) (res-lump-struct arg0 'target-name string))
  (format 0 "[die-relay] armed -> ~A~%" (-> this target-name))
  (go die-relay-idle)
  (none))
```

4. Select `ACTOR_die-relay_0` → Custom Lumps → add:
   - Key: `target-name` | Type: `string` | Value: `eco-platform-0`

5. Place a `VOL_` mesh over the trigger zone → Volume Links → target: `ACTOR_die-relay_0`

6. Export + Build

**Expected debug output (OpenGOAL console):**
```
[vol-trigger] armed -> die-relay-0
[die-relay] armed -> eco-platform-0
[vol-trigger] enter -> die-relay-0
[die-relay] killing eco-platform-0
```

### Why `target-name` uses the lump name not the Blender name

`process-by-ename` looks up the entity's `'name` lump string at runtime — not the Blender object name. The addon sets the name lump as `<etype>-<uid>`, so:

| Blender object name | Entity lump name (what to put in target-name) |
|---|---|
| `ACTOR_eco-platform_0` | `eco-platform-0` |
| `ACTOR_jng-iris-door_2` | `jng-iris-door-2` |
| `ACTOR_die-relay_0` | `die-relay-0` |

---

## 5. Other Useful Patterns

### Hide/show via draw flag (reversible)

```lisp
;; In :event handler:
(case message
  (('trigger)
   (let ((proc (process-by-ename (-> self target-name))))
     (when proc
       (logior! (-> proc draw status) (draw-control-status hidden))
       (clear-collide-with-as (-> proc root))
       (clear-collide-as (-> proc root)))))
  (('untrigger)
   (let ((proc (process-by-ename (-> self target-name))))
     (when proc
       (logclear! (-> proc draw status) (draw-control-status hidden))
       (restore-collide-with-as (-> proc root))))))
```

### Kill target permanently (one-way)

```lisp
(send-event target 'die)
```

Sets the `dead` perm bit — entity won't respawn until level reload.

### Forward 'trigger to a door

```lisp
;; die-relay style, but send 'trigger instead of 'die:
(send-event target 'trigger)   ;; opens sun-iris-door
```

---

## 6. What Gets Written to obs.gc

On export, obs.gc contains (in order):

1. `camera-marker` type (always)
2. `camera-trigger` type (if camera volumes exist)
3. `checkpoint-trigger` type (if checkpoints exist)
4. `aggro-trigger` type (if enemy aggro volumes exist)
5. **`vol-trigger` type** (if VOL_ → custom actor links exist)
6. **Custom GOAL code blocks** (from text blocks attached to ACTOR_ empties)

The `vol-trigger` type is always emitted as a built-in — you don't need to write it. Your custom entity just needs to handle `'trigger` in its `:event` handler.

---

## 7. Known Issues / Registration History

### Bug: panels not appearing (fixed f509e96)
`OG_PT_SpawnCustomTypes` and `OG_PT_ActorGoalCode` were in the import-time `classes` tuple but missing from the actual `register()` tuple. `bpy.utils.register_class` was never called on them.

### Bug: duplicate registration (fixed 8fc7e79)
`OG_PT_SpawnCustomTypes` was listed twice in the import tuple, causing Blender to silently fail registration of everything after it — which included `OG_PT_ActorGoalCode`.

### Status as of feature/goal-code (April 2026)
- Both panels register correctly
- `vol-trigger` export pipeline fully wired
- **Not yet live-tested in-game** — awaiting first test session
