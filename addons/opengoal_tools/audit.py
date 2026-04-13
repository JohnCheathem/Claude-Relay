# audit.py — Level Audit checks for the OpenGOAL Blender addon.
#
# Each check function returns a list of AuditIssue dicts:
#   {
#     "severity": "ERROR" | "WARNING" | "INFO",
#     "message":  str,
#     "obj_name": str | None   # name of offending object, or None for scene-level
#   }
#
# run_audit(scene) → sorted list of all issues across all checks.

from .data import (
    ENTITY_DEFS,
    NAV_UNSAFE_TYPES,
    NEEDS_PATH_TYPES,
    GLOBAL_TPAGE_GROUPS,
    ACTOR_LINK_DEFS,
    _actor_link_slots,
)
from .collections import _level_objects, _active_level_col, _get_level_prop

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _etype(o):
    """Return the etype string for an ACTOR_ empty, or None."""
    name = o.name
    if not (name.startswith("ACTOR_") and o.type == "EMPTY"):
        return None
    parts = name.split("_", 2)   # ACTOR_<etype>_<uid>
    return parts[1] if len(parts) >= 2 else None


def _actor_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("ACTOR_") and o.type == "EMPTY"
            and "_wp_" not in o.name and "_wpb_" not in o.name]


def _vol_objs(scene):
    return [o for o in _level_objects(scene)
            if o.type == "MESH" and o.name.startswith("VOL_")]


def _spawn_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("SPAWN_") and o.type == "EMPTY"]


def _checkpoint_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY"]


def _camera_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("CAMERA_") and o.type == "CAMERA"]


def _issue(severity, message, obj_name=None):
    return {"severity": severity, "message": message, "obj_name": obj_name}


# ---------------------------------------------------------------------------
# Check 1 — Tpage budget
# ---------------------------------------------------------------------------

def check_tpage_budget(scene):
    issues = []
    groups = set()
    counts = {}
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et:
            continue
        info = ENTITY_DEFS.get(et, {})
        grp  = info.get("tpage_group")
        if grp and grp not in GLOBAL_TPAGE_GROUPS:
            groups.add(grp)
            counts[grp] = counts.get(grp, 0) + 1

    if len(groups) > 2:
        group_list = ", ".join(sorted(groups))
        issues.append(_issue(
            "WARNING",
            f"Tpage budget: {len(groups)} non-global groups in use ({group_list}). "
            "Jak 1 loads at most 2 non-global tpage groups per level — "
            "extra groups will fail to stream art assets.",
        ))
    elif len(groups) == 2:
        issues.append(_issue(
            "INFO",
            f"Tpage groups: 2 non-global groups in use ({', '.join(sorted(groups))}). "
            "This is the maximum — adding more enemy/actor types may break art loading.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Check 2 — Nav-enemy has no navmesh link
# ---------------------------------------------------------------------------

def check_navmesh_links(scene):
    issues = []
    objects = scene.objects
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et:
            continue
        if et not in NAV_UNSAFE_TYPES:
            continue
        nm_name = o.get("og_navmesh_link", "")
        if not nm_name:
            issues.append(_issue(
                "ERROR",
                f"Nav-enemy '{o.name}' ({et}) has no navmesh link. "
                "It will freeze or crash in-game without one.",
                o.name,
            ))
        elif objects.get(nm_name) is None:
            issues.append(_issue(
                "ERROR",
                f"Nav-enemy '{o.name}' ({et}) navmesh link '{nm_name}' "
                "does not exist in the scene.",
                o.name,
            ))
    return issues


# ---------------------------------------------------------------------------
# Check 3 — Actor missing required path waypoints
# ---------------------------------------------------------------------------

def check_missing_paths(scene):
    issues = []
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et or et not in NEEDS_PATH_TYPES:
            continue
        info = ENTITY_DEFS.get(et, {})

        # Count waypoints — waypoints are named ACTOR_<etype>_<uid>_wp_<n>
        base = o.name  # e.g. ACTOR_snow-bunny_3
        wp_prefix = base + "_wp_"
        wpb_prefix = base + "_wpb_"
        wp_count  = sum(1 for ob in _level_objects(scene) if ob.name.startswith(wp_prefix))
        wpb_count = sum(1 for ob in _level_objects(scene) if ob.name.startswith(wpb_prefix))

        if wp_count == 0:
            issues.append(_issue(
                "ERROR",
                f"'{o.name}' ({et}) requires path waypoints but has none. "
                "Export will warn; actor may crash or behave incorrectly.",
                o.name,
            ))
        if info.get("needs_pathb") and wpb_count == 0:
            issues.append(_issue(
                "ERROR",
                f"'{o.name}' ({et}) also requires a B-path (pathb) but has none.",
                o.name,
            ))
    return issues


# ---------------------------------------------------------------------------
# Check 4 — Required actor link slots unset
# ---------------------------------------------------------------------------

def check_actor_links(scene):
    issues = []
    objects = scene.objects
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et:
            continue
        slots = _actor_link_slots(et)
        for slot in slots:
            if not slot.get("required"):
                continue
            # Find the link for this slot
            links = getattr(o, "og_actor_links", None)
            if links is None:
                continue
            filled = any(lk.lump_key == slot["lump_key"] and lk.target_name.strip()
                         for lk in links)
            if not filled:
                issues.append(_issue(
                    "WARNING",
                    f"'{o.name}' ({et}): required link slot '{slot['lump_key']}' is unset.",
                    o.name,
                ))

        # Also check that any set links point to objects that exist
        for lk in getattr(o, "og_actor_links", []):
            if not lk.target_name.strip():
                continue
            if objects.get(lk.target_name) is None:
                issues.append(_issue(
                    "ERROR",
                    f"'{o.name}' ({et}): link '{lk.lump_key}' points to "
                    f"'{lk.target_name}' which does not exist.",
                    o.name,
                ))
    return issues


# ---------------------------------------------------------------------------
# Check 5 — Volume links
# ---------------------------------------------------------------------------

def check_volumes(scene):
    issues = []
    objects = scene.objects
    for vol in _vol_objs(scene):
        links = getattr(vol, "og_vol_links", [])
        if len(links) == 0:
            issues.append(_issue(
                "WARNING",
                f"Trigger volume '{vol.name}' has no links. "
                "It will be exported as dead weight — nothing will happen when entered.",
                vol.name,
            ))
            continue

        for lk in links:
            target = lk.target_name.strip()
            if not target:
                issues.append(_issue(
                    "WARNING",
                    f"Volume '{vol.name}' has a link with an empty target name.",
                    vol.name,
                ))
                continue
            if objects.get(target) is None:
                issues.append(_issue(
                    "ERROR",
                    f"Volume '{vol.name}' links to '{target}' which does not exist.",
                    vol.name,
                ))
    return issues


# ---------------------------------------------------------------------------
# Check 6 — Spawn point
# ---------------------------------------------------------------------------

def check_spawn_points(scene):
    issues = []
    spawns = _spawn_objs(scene)
    if len(spawns) == 0:
        issues.append(_issue(
            "ERROR",
            "No SPAWN_ empty found. The level has no player start position.",
        ))
    elif len(spawns) > 1:
        names = ", ".join(o.name for o in spawns)
        issues.append(_issue(
            "WARNING",
            f"Multiple SPAWN_ empties found ({names}). "
            "The engine picks one arbitrarily — remove extras.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Check 7 — Duplicate actor names
# ---------------------------------------------------------------------------

def check_duplicate_names(scene):
    issues = []
    seen = {}
    for o in _actor_objs(scene):
        seen.setdefault(o.name, []).append(o)
    for name, objs in seen.items():
        if len(objs) > 1:
            issues.append(_issue(
                "ERROR",
                f"Duplicate object name '{name}' ({len(objs)} objects). "
                "The engine resolves actors by name — duplicates cause wrong-entity lookups.",
                name,
            ))
    return issues


# ---------------------------------------------------------------------------
# Check 8 — VOL_ camera links target a non-CAMERA_ object
# ---------------------------------------------------------------------------

def check_camera_targets(scene):
    issues = []
    objects = scene.objects
    for vol in _vol_objs(scene):
        for lk in getattr(vol, "og_vol_links", []):
            target = lk.target_name.strip()
            if not target:
                continue
            obj = objects.get(target)
            if obj is None:
                continue  # caught by check_volumes
            # If it looks like a camera link but target isn't a CAMERA_ object
            if target.startswith("CAMERA_") and obj.type != "CAMERA":
                issues.append(_issue(
                    "WARNING",
                    f"Volume '{vol.name}' links to '{target}' which is not a Camera object.",
                    vol.name,
                ))
    return issues


# ---------------------------------------------------------------------------
# Check 9 — Informational scene summary
# ---------------------------------------------------------------------------

def check_scene_summary(scene):
    issues = []
    actors   = _actor_objs(scene)
    vols     = _vol_objs(scene)
    spawns   = _spawn_objs(scene)
    cameras  = _camera_objs(scene)
    checkpts = _checkpoint_objs(scene)

    # Count by category
    cats = {}
    for o in actors:
        et = _etype(o)
        info = ENTITY_DEFS.get(et, {}) if et else {}
        cat = info.get("cat", "Unknown")
        cats[cat] = cats.get(cat, 0) + 1

    cat_str = ", ".join(f"{v} {k}" for k, v in sorted(cats.items()))
    issues.append(_issue(
        "INFO",
        f"Scene has {len(actors)} actors ({cat_str}), "
        f"{len(vols)} trigger volumes, "
        f"{len(cameras)} cameras, "
        f"{len(checkpts)} checkpoints, "
        f"{len(spawns)} spawn point(s).",
    ))

    # Tpage group breakdown (informational)
    groups = {}
    for o in actors:
        et = _etype(o)
        info = ENTITY_DEFS.get(et, {}) if et else {}
        grp = info.get("tpage_group")
        if grp:
            groups[grp] = groups.get(grp, 0) + 1
    if groups:
        non_global = {k: v for k, v in groups.items() if k not in GLOBAL_TPAGE_GROUPS}
        always     = {k: v for k, v in groups.items() if k in GLOBAL_TPAGE_GROUPS}
        parts = []
        if non_global:
            parts.append("non-global: " + ", ".join(f"{k}×{v}" for k, v in sorted(non_global.items())))
        if always:
            parts.append("always-resident: " + ", ".join(f"{k}×{v}" for k, v in sorted(always.items())))
        issues.append(_issue("INFO", "Tpage groups — " + "; ".join(parts)))

    return issues


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}

_CHECKS = [
    check_tpage_budget,
    check_navmesh_links,
    check_missing_paths,
    check_actor_links,
    check_volumes,
    check_spawn_points,
    check_duplicate_names,
    check_camera_targets,
    check_scene_summary,
]


def run_audit(scene):
    """Run all checks and return a sorted list of AuditIssue dicts."""
    issues = []
    for check in _CHECKS:
        try:
            issues.extend(check(scene))
        except Exception as exc:
            issues.append(_issue("WARNING", f"Audit check '{check.__name__}' failed: {exc}"))
    issues.sort(key=lambda i: _SEVERITY_ORDER.get(i["severity"], 99))
    return issues
