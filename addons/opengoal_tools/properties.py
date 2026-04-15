# ---------------------------------------------------------------------------
# properties.py — OpenGOAL Level Tools
# Blender PropertyGroups, AddonPreferences, and UILists.
# ---------------------------------------------------------------------------

import bpy
from bpy.props import (StringProperty, BoolProperty, IntProperty,
                       EnumProperty, PointerProperty, FloatProperty,
                       CollectionProperty)
from bpy.types import Panel, Operator, PropertyGroup, AddonPreferences
from .data import (
    ENTITY_ENUM_ITEMS, PLATFORM_ENUM_ITEMS, CRATE_ITEMS,
    ENEMY_ENUM_ITEMS, PROP_ENUM_ITEMS, NPC_ENUM_ITEMS, PICKUP_ENUM_ITEMS,
    LUMP_TYPE_ITEMS, AGGRO_EVENT_ENUM_ITEMS, ALL_SFX_ITEMS,
    LEVEL_BANKS, SBK_SOUNDS, MUSIC_FLAVA_TABLE, _music_flava_items_cb,
    TPAGE_FILTER_ITEMS, GLOBAL_TPAGE_GROUPS,
    _enemy_enum_cb, _prop_enum_cb, _npc_enum_cb, _pickup_enum_cb, _platform_enum_cb,
    _search_results_cb,
    _parse_lump_row,
)
from .collections import (
    _active_level_items, _on_active_level_changed,
    _get_death_plane, _set_death_plane,
)

# --- OGPreferences ---
class OGPreferences(AddonPreferences):
    bl_idname = "opengoal_tools"

    # ── Auto-detect fields ────────────────────────────────────────────────────
    og_root_path: StringProperty(
        name="OpenGOAL Root",
        description=(
            "Parent folder of your OpenGOAL install — the one whose subfolders contain "
            "gk / goalc. E.g. if your exe is at .../OpenGOAL/jak1/v0.2.29/gk.exe, "
            "point this at .../OpenGOAL/jak1/"
        ),
        subtype="DIR_PATH",
        default="",
    )
    og_active_version: StringProperty(
        name="Active Version",
        description="Currently selected version subfolder name",
        default="",
    )
    show_manual_paths: BoolProperty(
        name="Manual path overrides (advanced)",
        default=False,
    )

    # ── Manual overrides ──────────────────────────────────────────────────────
    exe_path: StringProperty(
        name="EXE folder (override)",
        description="Override: folder containing gk / goalc. Leave blank to use auto-detected version.",
        subtype="DIR_PATH",
        default="",
    )
    data_path: StringProperty(
        name="Data folder (override)",
        description=(
            "Override: release build = parent of data/, dev build = repository root. "
            "Leave blank to use auto-detected version folder."
        ),
        subtype="DIR_PATH",
        default="",
    )
    decompiler_path: StringProperty(
        name="Decompiler output (override)",
        description=(
            "Override: path to decompiler_out/jak1/. "
            "Leave blank to auto-detect from the active version folder."
        ),
        subtype="DIR_PATH",
        default="",
    )
    preview_models: BoolProperty(
        name="Preview Models",
        description="Automatically show the enemy's game model as a viewport stand-in when spawning",
        default=True,
    )

    def draw(self, ctx):
        import sys
        from pathlib import Path
        layout = self.layout

        # ── Root path + scan button ───────────────────────────────────────────
        row = layout.row(align=True)
        row.prop(self, "og_root_path", text="OpenGOAL Root")
        row.operator("og.scan_paths", text="Find Files", icon="VIEWZOOM")

        # ── Version picker ────────────────────────────────────────────────────
        if self.og_root_path.strip():
            root     = Path(self.og_root_path.strip().rstrip("\\/"))
            exe_ext  = ".exe" if sys.platform == "win32" else ""
            versions = []
            if root.exists():
                try:
                    for d in sorted(root.iterdir()):
                        if d.is_dir() and (d / f"gk{exe_ext}").exists() and (d / f"goalc{exe_ext}").exists():
                            versions.append(d.name)
                except PermissionError:
                    pass

            if versions:
                box = layout.box()
                box.label(text="Versions found:")
                for v in versions:
                    row = box.row(align=True)
                    is_active = (v == self.og_active_version)
                    op = row.operator("og.set_active_version", text=v,
                                      icon="CHECKMARK" if is_active else "RADIOBUT_OFF",
                                      emboss=is_active)
                    op.version = v

                # Status for selected version
                if self.og_active_version and self.og_active_version in versions:
                    ver_path = root / self.og_active_version
                    has_exe  = (ver_path / f"gk{exe_ext}").exists() and (ver_path / f"goalc{exe_ext}").exists()
                    has_dev  = (ver_path / "goal_src" / "jak1").exists()
                    has_rel  = (ver_path / "data" / "goal_src" / "jak1").exists()
                    sbox = layout.box()
                    sbox.scale_y = 0.8
                    sbox.label(
                        text="EXE: gk + goalc found" if has_exe else "EXE: not found — check folder",
                        icon="CHECKMARK" if has_exe else "ERROR",
                    )
                    if has_dev:
                        sbox.label(text="Data: dev layout (goal_src at root)", icon="CHECKMARK")
                    elif has_rel:
                        sbox.label(text="Data: release layout (goal_src inside data/)", icon="CHECKMARK")
                    else:
                        sbox.label(text="Data: goal_src not found — run extractor first", icon="ERROR")
            else:
                box = layout.box()
                box.scale_y = 0.75
                if root.exists():
                    box.label(
                        text="No versions found — no subfolders with gk + goalc. Check path or use overrides below.",
                        icon="ERROR",
                    )
                else:
                    box.label(text="Folder not found — check path", icon="ERROR")

        # ── Manual overrides (collapsible) ────────────────────────────────────
        layout.separator()
        row = layout.row()
        row.prop(self, "show_manual_paths",
                 icon="TRIA_DOWN" if self.show_manual_paths else "TRIA_RIGHT",
                 emboss=False)
        if self.show_manual_paths:
            col = layout.column()
            col.label(text="EXE folder (overrides auto-detected version):")
            col.prop(self, "exe_path", text="")
            col.separator()
            col.label(text="Data folder (release: parent of data/  |  dev: repo root):")
            col.prop(self, "data_path", text="")
            if self.data_path.strip():
                r = Path(self.data_path.strip().rstrip("\\/"))
                b = col.box(); b.scale_y = 0.75
                if (r / "goal_src" / "jak1").exists():
                    b.label(text="Dev layout detected", icon="CHECKMARK")
                elif (r / "data" / "goal_src" / "jak1").exists():
                    b.label(text=f"Release layout detected — using: {r / 'data'}", icon="CHECKMARK")
                else:
                    b.label(text="goal_src/jak1/ not found — check path", icon="ERROR")
            col.separator()
            col.label(text="Decompiler output (leave blank to auto-detect):")
            col.prop(self, "decompiler_path", text="")
            if self.decompiler_path.strip():
                dp = Path(self.decompiler_path.strip().rstrip("\\/"))
                b = col.box(); b.scale_y = 0.75
                has_tex  = (dp / "textures").exists()
                has_glbs = any(
                    list((dp / d).glob("*.glb"))
                    for d in ["beach", "jungle", "village", "misty", "snow"]
                    if (dp / d).is_dir()
                )
                if has_tex and has_glbs:
                    b.label(text="Textures and models found", icon="CHECKMARK")
                elif has_tex:
                    b.label(text="Textures found — enable rip_levels for models", icon="INFO")
                elif dp.exists():
                    b.label(text="Folder exists but empty — run decompiler first", icon="ERROR")
                else:
                    b.label(text="Folder not found", icon="ERROR")
            else:
                if self.og_root_path.strip() or self.data_path.strip():
                    try:
                        from .build import _decompiler_path
                        auto = _decompiler_path()
                        b = col.box(); b.scale_y = 0.75
                        if auto.exists():
                            b.label(text=f"Auto-detected: {auto}", icon="CHECKMARK")
                        else:
                            b.label(text=f"Auto-detect: {auto} (not found — run decompiler)", icon="INFO")
                    except Exception:
                        pass

        layout.separator()
        layout.prop(self, "preview_models")



# --- OGProperties ---
class OGProperties(PropertyGroup):
    # Collection-based level selection
    active_level:   EnumProperty(name="Active Level", items=_active_level_items,
                                 update=_on_active_level_changed,
                                 description="Select which level collection is active")
    level_name:  StringProperty(name="Name", description="Lowercase with dashes", default="my-level")
    entity_type:    EnumProperty(name="Entity Type",    items=ENTITY_ENUM_ITEMS)
    # Search bar (Spawn Objects panel)
    entity_search:          StringProperty(name="", description="Search all spawnable objects by name", default="")
    entity_search_selected: StringProperty(name="", description="Currently selected search result", default="")
    show_search_results:    BoolProperty(name="Results", default=True)
    entity_search_results:  EnumProperty(
                                name="",
                                description="Matching spawnable objects — select one then hit Spawn",
                                items=_search_results_cb,
                                update=lambda self, ctx: setattr(
                                    self, "entity_search_selected",
                                    self.entity_search_results
                                    if self.entity_search_results != "__empty__" else ""
                                ),
                            )
    tpage_limit_enabled:    BoolProperty(name="Enable Limit Search", default=False,
                                description="Hide spawnable objects outside the selected tpage groups")
    tpage_filter_1:         EnumProperty(name="Group 1", items=TPAGE_FILTER_ITEMS, default="NONE",
                                description="First tpage group to allow")
    tpage_filter_2:         EnumProperty(name="Group 2", items=TPAGE_FILTER_ITEMS, default="NONE",
                                description="Second tpage group to allow")
    platform_type:  EnumProperty(name="Platform Type",  items=_platform_enum_cb)
    crate_type:  EnumProperty(name="Crate Type",  items=CRATE_ITEMS)
    # Per-category entity pickers — each Spawn sub-panel uses its own prop
    # so the dropdown only shows types relevant to that sub-panel.
    # items= uses a dynamic callback so the Limit Search tpage filter is respected.
    enemy_type:     EnumProperty(name="Enemy Type",   items=_enemy_enum_cb,
                                 description="Select an enemy or boss to place")
    prop_type:      EnumProperty(name="Prop Type",    items=_prop_enum_cb,
                                 description="Select a prop or object to place")
    npc_type:       EnumProperty(name="NPC Type",     items=_npc_enum_cb,
                                 description="Select an NPC to place")
    pickup_type:    EnumProperty(name="Pickup Type",  items=_pickup_enum_cb,
                                 description="Select a pickup to place")
    waypoint_spawn_at_actor: BoolProperty(
        name="Spawn at Position",
        default=False,
        description="Spawn waypoint at the actor current position instead of the 3D cursor",
    )
    nav_radius:  FloatProperty(name="Nav Sphere Radius (m)", default=6.0, min=0.5, max=50.0,
                               description="Fallback navmesh sphere radius for nav-unsafe enemies")
    # Custom GOAL type spawn
    custom_type_name: StringProperty(
        name="Type Name",
        description=(
            "Name of your custom GOAL deftype (e.g. 'spin-prop', 'prox-music-zone'). "
            "Must be lowercase with hyphens, matching the deftype name in your GOAL code block. "
            "Cannot be a name that already exists in the addon's entity list."
        ),
        default="",
    )
    base_id:     IntProperty(name="Base Actor ID", default=10000, min=1000, max=60000,
                             description="Starting actor ID for this level. Must be unique across all custom levels to avoid ghost entity spawns.")
    lightbake_samples: IntProperty(name="Sample Count", default=128, min=1, max=4096,
                                   description="Number of Cycles render samples used when baking lighting to vertex colors")
    # Audio
    sound_bank_1:           EnumProperty(name="Bank 1", items=LEVEL_BANKS, default="none",
                                         description="First level sound bank (max 2 total)")
    sound_bank_2:           EnumProperty(name="Bank 2", items=LEVEL_BANKS, default="none",
                                         description="Second level sound bank (max 2 total)")
    music_bank:             EnumProperty(name="Music Bank", items=LEVEL_BANKS, default="none",
                                         description="Music bank to load for this level")
    sfx_sound:              EnumProperty(name="Sound", items=ALL_SFX_ITEMS, default="waterfall",
                                         description="Currently selected sound for emitter placement")
    ambient_default_radius: FloatProperty(name="Default Emitter Radius (m)", default=15.0, min=1.0, max=200.0,
                                          description="Bsphere radius for new sound emitter empties")
    # Music zone emitter props
    og_music_amb_bank:     EnumProperty(name="Music Bank", items=LEVEL_BANKS, default="village1",
                                        description="Music bank this zone will activate when the player enters",
                                        update=lambda self, ctx: setattr(self, "og_music_amb_flava", "default"))
    og_music_amb_flava:    EnumProperty(name="Flava", items=_music_flava_items_cb,
                                        description="Music variant/sub-track for this zone (filtered by selected bank)")
    og_music_amb_priority: FloatProperty(name="Priority", default=10.0, min=0.0, max=100.0,
                                         description="Zone priority — higher value wins when zones overlap. Vanilla uses 10.0 normal, 40.0 boss/race")
    og_music_amb_radius:   FloatProperty(name="Zone Radius (m)", default=40.0, min=1.0, max=500.0,
                                         description="Bsphere radius of this music zone")
    # Level flow spawn type picker
    spawn_flow_type: EnumProperty(
        name="Type",
        items=[
            ("SPAWN",      "Player Spawn",  "Place a player spawn / continue point", "EMPTY_ARROWS",        0),
            ("CHECKPOINT", "Checkpoint",    "Place a mid-level checkpoint trigger",  "EMPTY_SINGLE_ARROW",  1),
        ],
        default="SPAWN",
        description="Select the type of level flow object to place",
    )
    # Level flow
    bottom_height:     FloatProperty(name="Death Plane (m)", default=-20.0, min=-500.0, max=-1.0,
                                     get=_get_death_plane, set=_set_death_plane,
                                     description="Y height below which the player gets an endlessfall death (negative = below level floor)")
    vis_nick_override: StringProperty(name="Vis Nick Override", default="",
                                      description="Override the auto-generated 3-letter vis nickname (leave blank to use auto)")
    # UI collapse state
    show_camera_list:       BoolProperty(name="Show Camera List",       default=True)
    show_volume_list:       BoolProperty(name="Show Volume List",       default=True)
    show_spawn_list:        BoolProperty(name="Show Spawn List",        default=True)
    show_checkpoint_list:   BoolProperty(name="Show Checkpoint List",   default=True)
    show_platform_list:     BoolProperty(name="Show Platform List",     default=True)
    # Collection Properties panel
    selected_collection:    StringProperty(name="Selected Collection", default="")

    # ── Texture browser ──────────────────────────────────────────────────────
    tex_group:    EnumProperty(
        name="Texture Group",
        description="Filter textures by level/category",
        items=[
            ("ALL",         "All",          ""),
            ("COMMON",      "Common",       ""),
            ("EFFECTS",     "Effects",      ""),
            ("CHARACTERS",  "Characters",   ""),
            ("BEACH",       "Beach",        ""),
            ("JUNGLE",      "Jungle",       ""),
            ("SWAMP",       "Swamp",        ""),
            ("MISTY",       "Misty",        ""),
            ("SNOW",        "Snow",         ""),
            ("FIRE_CANYON", "Fire Canyon",  ""),
            ("LAVA_TUBE",   "Lava Tube",    ""),
            ("OGRE",        "Ogre",         ""),
            ("SUNKEN",      "Sunken",       ""),
            ("ROLLING",     "Rolling",      ""),
            ("CAVE",        "Cave",         ""),
            ("VILLAGE",     "Village",      ""),
            ("TRAINING",    "Training",     ""),
            ("CITADEL",     "Citadel",      ""),
            ("FINAL_BOSS",  "Final Boss",   ""),
            ("HUD",         "HUD / UI",     ""),
        ],
        default="BEACH",
    )
    tex_page:     IntProperty(name="Texture Page", default=0, min=0)
    tex_search:   StringProperty(name="Search", default="",
                                 description="Filter textures by name")
    tex_selected: StringProperty(name="Selected Texture", default="")


# --- OGLumpRow ---
class OGLumpRow(bpy.types.PropertyGroup):
    """One custom lump entry on an ACTOR_ empty.
    Stored as a CollectionProperty on the Object (og_lump_rows).
    Rendered as a scrollable list in OG_PT_SelectedLumps.
    """
    key:   StringProperty(
        name="Key",
        description="Lump key name (e.g. notice-dist, mode, num-lurkers)",
        default="",
    )
    ltype: EnumProperty(
        name="Type",
        items=LUMP_TYPE_ITEMS,
        default="meters",
        description="JSONC lump value type",
    )
    value: StringProperty(
        name="Value",
        description="Value(s) — space-separated for multi-value types",
        default="",
    )



# --- OG_OT_AddLumpRow + OG_OT_RemoveLumpRow ---
class OG_OT_AddLumpRow(bpy.types.Operator):
    bl_idname  = "og.add_lump_row"
    bl_label   = "Add Lump Row"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        obj = ctx.active_object
        if obj is None:
            self.report({"ERROR"}, "No active object"); return {"CANCELLED"}
        obj.og_lump_rows.add()
        obj.og_lump_rows_index = len(obj.og_lump_rows) - 1
        return {"FINISHED"}


class OG_OT_RemoveLumpRow(bpy.types.Operator):
    bl_idname  = "og.remove_lump_row"
    bl_label   = "Remove Lump Row"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        obj = ctx.active_object
        if obj is None:
            self.report({"ERROR"}, "No active object"); return {"CANCELLED"}
        rows = obj.og_lump_rows
        idx  = obj.og_lump_rows_index
        if not rows or idx < 0 or idx >= len(rows):
            self.report({"ERROR"}, "Nothing to remove"); return {"CANCELLED"}
        rows.remove(idx)
        obj.og_lump_rows_index = max(0, min(idx, len(rows) - 1))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Lump UIList
# ---------------------------------------------------------------------------


# --- OG_UL_LumpRows ---
class OG_UL_LumpRows(bpy.types.UIList):
    """Scrollable list of custom lump rows for an ACTOR_ empty."""

    def draw_item(self, ctx, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        # Key field — reasonably wide
        row.prop(item, "key",   text="", emboss=True, placeholder="key")
        # Type dropdown — compact
        sub = row.row(align=True)
        sub.scale_x = 0.9
        sub.prop(item, "ltype", text="")
        # Value field
        row.prop(item, "value", text="", emboss=True, placeholder="value(s)")
        # Live parse indicator — red dot on bad rows
        _, err = _parse_lump_row(item.key, item.ltype, item.value)
        if err:
            row.label(text="", icon="ERROR")

    def filter_items(self, ctx, data, propname):
        # No filtering — just return defaults
        return [], []


# ===========================================================================
# VOLUME LINK SYSTEM
# ---------------------------------------------------------------------------
# A trigger volume (VOL_ mesh) holds a CollectionProperty of OGVolLink entries.
# Each entry links the volume to one target (camera / checkpoint / nav-enemy).
# Multiple entries per volume = one volume drives multiple things on enter.
#
# Behaviour field is per-link, only meaningful for nav-enemy targets:
#   cue-chase        — wake up + chase player (default)
#   cue-patrol       — return to patrol
#   go-wait-for-cue  — freeze until next cue
# Translated to integer enum at build time and emitted as a uint32 lump.
# Camera and checkpoint links ignore this field.
# ===========================================================================


# --- OGActorLink + OGVolLink ---
class OGActorLink(bpy.types.PropertyGroup):
    """One entity link slot on an ACTOR_ empty.

    Stored as og_actor_links CollectionProperty on the Object.
    Each entry maps (lump_key, slot_index) → target_name.
    At export these are serialised as  lump_key: ["string", name0, name1, ...]
    """
    lump_key:     bpy.props.StringProperty(
        name="Lump Key",
        description="The res-lump key this link writes to (e.g. alt-actor, water-actor)",
    )
    slot_index:   bpy.props.IntProperty(
        name="Slot Index",
        description="Index within the lump array (0 = first element)",
        default=0,
        min=0,
    )
    target_name:  bpy.props.StringProperty(
        name="Target",
        description="Name of the linked ACTOR_ empty",
    )


class OGVolLink(PropertyGroup):
    """One link between a trigger volume and a target object.
    Stored in a CollectionProperty on the volume mesh as og_vol_links.
    """
    target_name: StringProperty(
        name="Target",
        description="Name of the linked target object (camera, checkpoint, or enemy)",
    )
    behaviour:   EnumProperty(
        name="Behaviour",
        items=AGGRO_EVENT_ENUM_ITEMS,
        default="cue-chase",
        description="Event sent to the enemy on volume enter (nav-enemies only — ignored for cameras/checkpoints)",
    )


class OGGoalCodeRef(bpy.types.PropertyGroup):
    """Reference to a Blender text block containing custom GOAL code.

    Stored as og_goal_code_ref PointerProperty on ACTOR_ empties.
    On export, the referenced text block is appended verbatim to *-obs.gc
    after the addon's generated types.  Multiple actors can share one block —
    it will only be emitted once (deduplication by text block name).
    """
    text_block: bpy.props.PointerProperty(
        name="GOAL Code",
        description="Blender text block whose contents will be injected into the level's obs.gc on export",
        type=bpy.types.Text,
    )
    enabled: bpy.props.BoolProperty(
        name="Inject on Export",
        description="When enabled this code block will be included in obs.gc. Disable to temporarily exclude it without deleting the block",
        default=True,
    )


class OGAuditResult(PropertyGroup):
    """One issue produced by the Level Audit.
    Stored as og_audit_results CollectionProperty on the Scene.
    """
    severity: EnumProperty(
        name="Severity",
        items=[
            ("ERROR",   "Error",   "Will break export or crash in-game"),
            ("WARNING", "Warning", "Probably wrong, worth checking"),
            ("INFO",    "Info",    "Informational"),
        ],
        default="INFO",
    )
    message:  StringProperty(name="Message",  default="")
    obj_name: StringProperty(name="Object",   default="")
