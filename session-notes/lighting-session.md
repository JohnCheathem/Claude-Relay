# Lighting / Time of Day — Session Notes

**Branch:** `feature/lighting`
**Status:** Research phase — no implementation yet
**Last updated:** 2026-04-08

---

## Goal
Research and implement addon tools for time-of-day lighting and any other lighting-based systems. Understand the full pipeline so we can expose the right controls to users.

## Scope (research targets)
- Time of day system end-to-end (Blender vertex color baking → export → mood-tables.gc)
- Actor lighting via `mood-tables.gc` — full table structure, how to author for custom levels
- `prt-color` field — unknown, needs investigation
- Whether custom levels can define new mood entries vs only reference existing ones
- `_GREENSUN` and its relationship to sky type
- `levelname-mood-sun-table` structure — not yet documented
- Any other lighting hooks (fog distance/color, ambient overrides, etc.)

## Known so far
- See `knowledge-base/opengoal/time-of-day-mood.md` for current knowledge
- Blender side: vertex color attributes with `_NAME` prefix, bake to each slot
- Game side: `mood-tables.gc` — three tables per level (light, sun, fog)
- Actors handled separately from geometry — mood-tables.gc, not vertex colors
- Custom levels currently hardcoded to village1 mood (addon limitation)

## Open questions
- `prt-color` — what does it control?
- Can we define entirely new mood entries for custom levels?
- What does `mood-sun-table` actually contain / control?
- Fog table — just color + distance, or more parameters?
- Do we need Blender UI for mood table authoring or is it purely game-code-side?

## Research approach
- Study existing level mood-tables.gc entries (village1, misty, etc.) for patterns
- Cross-reference with decompiled engine source for field meanings
- Test minimal custom mood entry on a custom level

## Session log
- 2026-04-08: Branch created. Knowledge base has solid starting point. Research not yet begun.
