# Community Tools — OpenGOAL Blender Addons (gratefulforest)

> Logged April 2026 for future study / reference.
> These are third-party tools to learn from, not tools we maintain.
> Author: gratefulforest (GitHub: https://github.com/gratefulforest)

---

## OpenGOAL-Platform-Tools
**Repo:** https://github.com/gratefulforest/OpenGOAL-Platform-Tools  
**Description:** One-Click Curve Generator — spawns moving platforms along a Nurbs Curve for Jak 1.  
**Latest release:** v1.0.6

### What it does
- Spawns N platforms along a Nurbs curve via a slider (real-time preview in Blender).
- Blender animation matches in-game platform motion exactly.
- Exports all platform GOAL code formatted and ready — user just CTRL-V into game code.

### Install / use
1. Drag `.zip` onto Blender.
2. Add a Nurbs Curve.
3. `Object Data > Platform Control` → export.

### Why it's worth studying
- Demonstrates real-time Blender↔game preview workflow.
- Shows how to drive GOAL code generation from Blender curve data.
- One-click export pattern is something we want to learn from for our own addon.

---

## OpenGOAL-Navmesh-Tools
**Repo:** https://github.com/gratefulforest/OpenGOAL-Navmesh-Tools  
**Description:** One-Click Monster Maker — generates navmesh + enemy patrol paths for Jak 1.  
**Latest release:** v1.0.0  
**Dependency:** Requires LuminarLight's navmesh support — https://github.com/LuminarLight/LL-OpenGOAL-ModBase/commit/4f897008fa2ec8809e04c2b32d5ef9c329afede8

### What it does
- Draw a shape = define monster roam area.
- Instant menus, instant export.
- Handles internally:
  - Monster path point formatting
  - Route table generation + bitpacking
  - Nav-spheres on first actors
  - `nav-mesh-actor` for secondary actors
  - Navmesh simplification (minimum points to avoid hex limits)
  - Jump triangle generation from painted regions
  - Re-export safety (old navmeshes updated without conflicts)

### Why it's worth studying
- Bitpacking route tables from Blender geometry is non-trivial — worth reverse-engineering.
- `nav-mesh-actor` vs primary actor distinction maps to something real in GOAL source.
- Jump triangle painting workflow — useful reference for any terrain-aware system.
- Hex limit on navmesh points is a confirmed engine constraint worth knowing.

---

## General Notes on gratefulforest's Approach
Both tools share the same design philosophy:
- Single `.zip` drag-to-install Blender addon.
- Export produces raw GOAL code — no intermediate files.
- "One click to see it in game" as the primary UX goal.

This is a good reference pattern for our own addon's export UX direction.

