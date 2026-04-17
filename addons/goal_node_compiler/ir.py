"""
GOAL Node Compiler — Intermediate Representation

A Blender-independent representation of a compiled-ready node graph.
The emitter consumes IR; a separate Blender-side adapter (not in this file)
is responsible for walking a GoalNodeTree and producing IR.

Keeping IR pure-Python-stdlib means the emitter is unit-testable without
Blender running. Every dataclass here is JSON-serialisable — useful for
fixtures, goldens, and debugging.

Shape of things:

    Graph
      Entity (root)
      Actions[]           continuous + timed actions attached directly to entity
      Triggers[]
        Trigger.condition        how it fires
        Trigger.gated_actions[]  continuous/timed actions it toggles on
        Trigger.instant_actions[] instant actions that run inline when it fires

All nodes carry a stable `id` (string) used for:
  - Deterministic field name generation (`angle-<id>`)
  - Error messages ("action 'rotate-a' has no source")
  - Future cross-refs from a Blender node UUID -> IR id
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ============================================================================
# UNIT-TYPED VALUES
# ============================================================================
# Every numeric socket in the graph carries a unit. The emitter wraps values
# with the correct GOAL macro based on unit. Mixing is a compile error.

class Unit(str, Enum):
    RAW     = "raw"       # bare float, no wrapping
    METERS  = "meters"    # (meters N)
    DEGREES = "degrees"   # (degrees N)
    SECONDS = "seconds"   # (seconds N)


class AddressMode(str, Enum):
    """How a target is resolved. LITERAL bakes the name into the compiled code;
    LUMP reads it from a lump on the actor at init time. LUMP lets many actors
    share one etype and point at different targets per-instance."""
    LITERAL = "literal"
    LUMP    = "lump"


@dataclass
class Value:
    """A numeric input with a unit."""
    n:    float
    unit: Unit = Unit.RAW

    def emit(self) -> str:
        """Return the GOAL source form of this value."""
        if self.unit == Unit.RAW:
            return f"{self.n}"
        if self.unit == Unit.METERS:
            return f"(meters {self.n})"
        if self.unit == Unit.DEGREES:
            return f"(degrees {self.n})"
        if self.unit == Unit.SECONDS:
            return f"(seconds {self.n})"
        raise ValueError(f"unknown unit {self.unit}")


# ============================================================================
# AXIS ENUM
# ============================================================================

class Axis(str, Enum):
    X = "X"
    Y = "Y"
    Z = "Z"

    def vec_triple(self) -> str:
        """GOAL axis triple for quaternion-axis-angle! and friends."""
        return {
            Axis.X: "1.0 0.0 0.0",
            Axis.Y: "0.0 1.0 0.0",
            Axis.Z: "0.0 0.0 1.0",
        }[self]

    def field(self) -> str:
        """GOAL field path for trans vector component."""
        return {Axis.X: "x", Axis.Y: "y", Axis.Z: "z"}[self]


# ============================================================================
# ACTIONS
# ============================================================================
# Every action is a dataclass. Common fields (id, gate_flag) live on the base.
# Subclasses carry their specific parameters.
#
# Category is a class-level constant: INSTANT / CONTINUOUS / TIMED.
# The emitter routes contributions differently based on category.

class ActionCategory(str, Enum):
    INSTANT    = "instant"      # runs once, inline-able into event/code
    CONTINUOUS = "continuous"   # per-frame code in :trans
    TIMED      = "timed"        # per-frame code in :trans with internal timer
    SEQUENCE   = "sequence"     # compiles to a dedicated defstate
    WAIT       = "wait"         # only meaningful inside a SEQUENCE


@dataclass
class Action:
    """Base class — do not instantiate directly."""
    id:        str                             # stable identifier
    # Set by normalisation pass, not user input:
    index:     int            = 0              # disambiguates field names
    gate_flag: str | None     = None           # None = always active


@dataclass
class ActionRotate(Action):
    """Continuously rotate around an axis. Engine source: quaternion-axis-angle!."""
    axis:     Axis  = Axis.Y
    speed:    Value = field(default_factory=lambda: Value(1.0, Unit.DEGREES))

    CATEGORY = ActionCategory.CONTINUOUS


@dataclass
class ActionOscillate(Action):
    """Sine-wave oscillate along an axis (bob / swing).
    Engine: (sin (* 65536.0 phase)) * amplitude, phase = timer / period_ticks."""
    axis:      Axis  = Axis.Y
    amplitude: Value = field(default_factory=lambda: Value(0.5, Unit.METERS))
    period:    Value = field(default_factory=lambda: Value(3.0, Unit.SECONDS))

    CATEGORY = ActionCategory.CONTINUOUS


@dataclass
class ActionLerpAlongAxis(Action):
    """Lerp a relative distance along an axis over duration.
    Drives self's position from base + 0 to base + distance over duration."""
    axis:     Axis  = Axis.Y
    distance: Value = field(default_factory=lambda: Value(4.0, Unit.METERS))
    duration: Value = field(default_factory=lambda: Value(0.5, Unit.SECONDS))

    CATEGORY = ActionCategory.TIMED


@dataclass
class ActionPlaySound(Action):
    """Play a named sound. Engine: sound-play."""
    sound_name: str   = ""
    volume:     float = 100.0           # 0..100
    positional: bool  = True

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionSendEvent(Action):
    """send-event to a named target process.

    LITERAL mode: target_name is the entity lump name (e.g. "plat-eco-0"),
                  baked into the compiled code.
    LUMP    mode: target_name is the lump KEY (e.g. "target-name"), and the
                  actual target string is read from that lump at init time.
                  Lets many actors share this etype with different targets.
    """
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL
    event_name:  str         = "trigger"

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionKillTarget(Action):
    """Kill a named target process permanently within this session.
    Pattern from goal-code-runtime.md: perm-status dead + deactivate.

    LITERAL / LUMP modes: see ActionSendEvent."""
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionDeactivateSelf(Action):
    """Kill this actor immediately. Engine: (deactivate self)."""
    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionSetSetting(Action):
    """set-setting! on a named game setting."""
    setting_key: str  = "bg-a"           # see goal-scripting.md §13
    mode:        str  = "abs"            # "abs" or "rel"
    value:       float = 0.0
    duration:    Value = field(default_factory=lambda: Value(0.0, Unit.SECONDS))

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionRawGoal(Action):
    """Escape hatch. Emits `body` verbatim into the named slot.
    slot ∈ { "trans", "code", "event", "init", "top_level" }."""
    slot: str = "trans"
    body: str = ""

    # Routed by slot, not a fixed category. Emitter handles specially.
    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionWait(Action):
    """Pause for a duration. Only meaningful as a step inside ActionSequence.
    Emits (suspend-for (seconds N)) — suspend-for is coroutine-only, which is
    why Waits can't appear outside sequences."""
    duration: Value = field(default_factory=lambda: Value(1.0, Unit.SECONDS))

    CATEGORY = ActionCategory.WAIT


@dataclass
class ActionSequence(Action):
    """Run a linear chain of actions in order, with Waits for time-based
    pauses. Compiles to a dedicated defstate; the firing trigger emits
    (go <etype>-seq-<id>) to jump into it.

    Validation enforces: steps must be INSTANT or WAIT — no CONTINUOUS
    or TIMED actions allowed (they'd never complete)."""
    steps: list[Action] = field(default_factory=list)

    CATEGORY = ActionCategory.SEQUENCE


# ============================================================================
# TRIGGERS
# ============================================================================
# Triggers are how actions get gated. Each trigger's `gated_actions` list
# contains continuous/timed actions it activates; `instant_actions` list
# contains instant actions that run inline when the trigger fires.

class TriggerKind(str, Enum):
    ON_SPAWN      = "on_spawn"         # fires once in init-from-entity! / enter
    ON_EVENT      = "on_event"         # :event case branch
    ON_PROXIMITY  = "on_proximity"     # polled in :trans, distance check
    ON_VOL        = "on_vol"           # :event 'trigger — vol-trigger feeds it
    ON_TIME       = "on_time"          # polled in :trans, time-elapsed check
    ON_EVERY_N    = "on_every_n"       # polled in :trans, mod frame-counter


@dataclass
class Trigger:
    """Base class — subclass per kind."""
    id:              str
    kind:            TriggerKind
    gated_actions:   list[Action] = field(default_factory=list)
    instant_actions: list[Action] = field(default_factory=list)


@dataclass
class TriggerOnSpawn(Trigger):
    def __init__(self, id: str, gated_actions=None, instant_actions=None):
        super().__init__(id, TriggerKind.ON_SPAWN,
                         gated_actions or [], instant_actions or [])


@dataclass
class TriggerOnEvent(Trigger):
    event_name: str = "trigger"

    def __init__(self, id: str, event_name="trigger",
                 gated_actions=None, instant_actions=None):
        super().__init__(id, TriggerKind.ON_EVENT,
                         gated_actions or [], instant_actions or [])
        self.event_name = event_name


@dataclass
class TriggerOnVolEntered(Trigger):
    """Fires when Jak enters a VOL_ that's wired to this actor in Blender.
    The vol-trigger subsystem sends `'trigger` on enter; we listen for it."""
    def __init__(self, id: str, gated_actions=None, instant_actions=None):
        super().__init__(id, TriggerKind.ON_VOL,
                         gated_actions or [], instant_actions or [])


@dataclass
class TriggerOnProximity(Trigger):
    distance: Value = field(default_factory=lambda: Value(5.0, Unit.METERS))
    xz_only:  bool  = False

    def __init__(self, id: str, distance=None, xz_only=False,
                 gated_actions=None, instant_actions=None):
        super().__init__(id, TriggerKind.ON_PROXIMITY,
                         gated_actions or [], instant_actions or [])
        self.distance = distance if distance is not None else Value(5.0, Unit.METERS)
        self.xz_only  = xz_only


@dataclass
class TriggerOnTimeElapsed(Trigger):
    delay: Value = field(default_factory=lambda: Value(2.0, Unit.SECONDS))

    def __init__(self, id: str, delay=None,
                 gated_actions=None, instant_actions=None):
        super().__init__(id, TriggerKind.ON_TIME,
                         gated_actions or [], instant_actions or [])
        self.delay = delay if delay is not None else Value(2.0, Unit.SECONDS)


@dataclass
class TriggerOnEveryNFrames(Trigger):
    every_n: int = 4

    def __init__(self, id: str, every_n=4,
                 gated_actions=None, instant_actions=None):
        super().__init__(id, TriggerKind.ON_EVERY_N,
                         gated_actions or [], instant_actions or [])
        self.every_n = every_n


# ============================================================================
# ENTITY + GRAPH
# ============================================================================

@dataclass
class Entity:
    """The root. Compiles to one `deftype` + one `defstate` + one `defmethod`."""
    etype:               str                   # matches Blender ACTOR_<etype>_<N>
    direct_actions:      list[Action]   = field(default_factory=list)
    triggers:            list[Trigger]  = field(default_factory=list)
    # Lumps the entity reads at init-from-entity time. Keyed by GOAL symbol.
    # value = (lump_type, goal_field_type, field_name)
    lumps:               dict[str, tuple[str, str, str]] = field(default_factory=dict)


@dataclass
class Graph:
    """Top-level IR wrapper. One entity = one compilation unit."""
    entity: Entity


# ============================================================================
# T1 SKELETONS — declared, not yet templated/emitted
# ============================================================================
# These are IR types for the next wave of nodes identified in the advanced
# brainstorm doc (knowledge-base/blender/goal-node-advanced-vocabulary-brainstorm.md).
# They exist so that:
#   - Callers can construct graphs using these types today
#   - The Blender-side walker knows what shapes to produce
#   - Templates can be filled in one by one without IR churn
#
# IMPORTANT: compile_graph() will raise NotImplementedError for any of these
# until its template function lands in templates.py. Attempting to compile a
# graph containing these today is a hard error, by design.


# --- Scene-query & iteration -------------------------------------------------

class ActorSetSource(str, Enum):
    """How an ActorSet is populated."""
    COLLECTION    = "collection"      # all actors in a named Blender collection
    BY_ETYPE      = "by_etype"        # all actors of a given etype in scene
    BY_NAME_GLOB  = "by_name_glob"    # object name matches a glob pattern
    EXPLICIT      = "explicit"        # user-provided list of lump names


@dataclass
class ActorSet(Action):
    """A named set of actor lump names, resolved at COMPILE time.

    Emits: a list embedded into the deftype. Actions downstream that consume
    an ActorSet reference iterate it via ForEach or broadcast-send.

    Category: INSTANT (doesn't do work per frame — just a data source).
    """
    source:          ActorSetSource = ActorSetSource.EXPLICIT
    collection_name: str            = ""        # when source=COLLECTION
    etype_filter:    str            = ""        # when source=BY_ETYPE
    name_pattern:    str            = ""        # when source=BY_NAME_GLOB
    explicit_names:  list[str]      = field(default_factory=list)

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionForEach(Action):
    """Runs `body_actions` once per actor in `actor_set`.

    For T1: unroll at compile time — emit one copy of the body per actor,
    with a `$current` placeholder substituted to the literal lump name.
    Ugly in generated source, but structurally trivial and always correct.

    Child actions that reference the current actor do so via a distinguished
    `TARGET_CURRENT = "$CURRENT$"` target_name. The emitter rewrites this
    during unrolling.
    """
    actor_set:     str           = ""   # ID of an ActorSet in the same graph
    body_actions:  list[Action]  = field(default_factory=list)

    CATEGORY = ActionCategory.INSTANT

    # Marker value for actions inside ForEach that should receive the current
    # iterator actor. Compare with `a.target_name == TARGET_CURRENT`.
    TARGET_CURRENT = "$CURRENT$"


# --- Game state & progression ------------------------------------------------

@dataclass
class ActionSetPermFlag(Action):
    """Set a named entity-perm-status bit on a target actor.

    Flags from engine: dead, complete, real-complete, user-set-from-cstage,
    bit-0 ... bit-10. See goal-scripting.md §15.
    """
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL
    flag_name:   str         = "complete"   # enum-ish in practice
    value:       bool        = True

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionCheckPermFlag(Action):
    """Query a perm-status bit — emits a boolean expression for conditional use.

    This is a *condition producer*, not a body-emitter. Until we have explicit
    conditional nodes (ActionIf etc.), it's only useful as a predicate inside
    a RawGoal or as a trigger's condition source.
    """
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL
    flag_name:   str         = "complete"

    CATEGORY = ActionCategory.INSTANT


# --- Screen effects ----------------------------------------------------------

@dataclass
class ActionBlackout(Action):
    """`(blackout N)` — N frames of pure black. From the continue-point
    load-command vocabulary documented in level-flow.md §3.
    """
    frames: int = 30

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionFadeToBlack(Action):
    """Animated bg-a lerp 0→1. Composes with SetSetting 'bg-a but bundles
    the ramp into one node for convenience (the core of the scripted-sequence
    Ex.4 pattern from goal-scripting.md §17)."""
    duration: Value = field(default_factory=lambda: Value(0.5, Unit.SECONDS))

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionFadeFromBlack(Action):
    """Inverse of FadeToBlack — 1→0."""
    duration: Value = field(default_factory=lambda: Value(0.5, Unit.SECONDS))

    CATEGORY = ActionCategory.INSTANT


# --- Camera (expanded) -------------------------------------------------------

@dataclass
class ActionCameraSwitchToMarker(Action):
    """`(send-event *camera* 'change-to-entity-by-name "marker-name")`.
    Covers the common case cleanly — SendEvent can do it too but this is
    one node instead of three inputs to configure."""
    marker_name: str = ""

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionCameraClear(Action):
    """`(send-event *camera* 'clear-entity)` — revert to default."""
    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionCameraTeleport(Action):
    """`(send-event *camera* 'teleport)` — instant cut, no blend."""
    CATEGORY = ActionCategory.INSTANT


# --- Motion primitives -------------------------------------------------------

@dataclass
class ActionLookAtTarget(Action):
    """Continuously rotates entity's Y-axis to face target.
    Engine: rotate-toward-point / matrix-from-two-vectors patterns.
    """
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LUMP   # usually per-instance
    smooth:      bool        = True               # false = snap each frame

    CATEGORY = ActionCategory.CONTINUOUS


@dataclass
class ActionLookAtJak(Action):
    """Continuously faces the player. Simpler than LookAtTarget — no
    target resolution."""
    smooth: bool = True

    CATEGORY = ActionCategory.CONTINUOUS


@dataclass
class ActionPathFollow(Action):
    """Move along a waypoint path at a speed. The path data comes from the
    existing `path` lump exported by the addon (goal-scripting.md §10).

    speed is fraction-of-path per tick; 0.003 ≈ full loop in 5 seconds.
    """
    speed:     float = 0.003
    ping_pong: bool  = False            # else loop

    CATEGORY = ActionCategory.CONTINUOUS


# --- Jak interactions --------------------------------------------------------

@dataclass
class ActionLaunchJak(Action):
    """`(send-event *target* 'launch VELOCITY #f #f 0)` — jump pad behaviour."""
    velocity: Value = field(default_factory=lambda: Value(16384.0, Unit.RAW))

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionResetJakHeight(Action):
    """`(send-event *target* 'reset-height)` — clears jump-height tracking."""
    CATEGORY = ActionCategory.INSTANT


# --- Enemy AI (nav-enemies only — validator should check) -------------------

@dataclass
class ActionCueEnemyChase(Action):
    """`'cue-chase` — wake enemy, start chasing Jak.
    Only nav-enemies respond (babak, lurker-crab, hopper, snow-bunny, kermit).
    """
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionCueEnemyPatrol(Action):
    """`'cue-patrol` — return enemy to patrol."""
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionFreezeEnemy(Action):
    """`'go-wait-for-cue` — freeze until another cue."""
    target_name: str         = ""
    target_mode: AddressMode = AddressMode.LITERAL

    CATEGORY = ActionCategory.INSTANT


# --- Sound (expanded) --------------------------------------------------------

@dataclass
class ActionPlayMusicTrack(Action):
    """`(set-setting! 'music 'name 0.0 0)`."""
    track_name: str = ""

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionStopMusic(Action):
    """`(set-setting! 'music #f 0.0 0)`."""
    CATEGORY = ActionCategory.INSTANT


# --- Debug / authoring -------------------------------------------------------

@dataclass
class ActionDebugPrint(Action):
    """Emit `(format 0 "text~%")` — developer output only.
    Can do via RawGoal but a dedicated node is friendlier + validatable."""
    text: str = ""

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionComment(Action):
    """Graph-only node. Holds a note for readers. Emits nothing.

    Useful in large graphs for signposting. Emitter returns empty
    Contributions — template function is a 1-liner.
    """
    text: str = ""

    CATEGORY = ActionCategory.INSTANT


# --- Level-flow commands (from level-flow.md §3 load-command vocabulary) ----

@dataclass
class ActionBirthEntity(Action):
    """`(alive "name")` — birth a specific entity by lump name.
    The command saves + restores perm-status as part of the continue mechanism.
    """
    target_name: str = ""

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionMarkEntityDead(Action):
    """`(dead "name")` — kill + mark dead.
    Different from KillTarget in that this goes through the load-command
    route, integrating with save/continue state."""
    target_name: str = ""

    CATEGORY = ActionCategory.INSTANT


# --- Conditional gating — predicate-producing actions -----------------------
# These produce boolean expressions for future If/Branch nodes to consume.
# No template support until control-flow nodes land.

@dataclass
class ActionIf(Action):
    """Run `then_actions` if condition is true, else `else_actions`.
    Condition is currently a raw GOAL predicate string (until we build
    proper predicate nodes). Escape hatch until Level B.
    """
    condition:    str           = ""
    then_actions: list[Action]  = field(default_factory=list)
    else_actions: list[Action]  = field(default_factory=list)

    CATEGORY = ActionCategory.INSTANT


@dataclass
class ActionRandomChance(Action):
    """Fire `body_actions` with given probability. Uses (rand-vu-int-count).
    probability is 0.0..1.0."""
    probability:  float         = 0.5
    body_actions: list[Action]  = field(default_factory=list)

    CATEGORY = ActionCategory.INSTANT

