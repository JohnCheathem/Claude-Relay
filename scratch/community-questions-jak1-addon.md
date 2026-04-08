# Community Questions — Jak 1 Addon

Collected for future documentation / FAQ coverage.
These need to be addressed eventually, likely in a public-facing doc.

---

## Source: Community feedback (Discord / forums)

> "Great job with the addon at the moment, definitely looks like it'd be a big help to get in to jak 1 level making. I'd probably be interested later on but there would be a few things of note for me to consider using it:"

---

### Q1 — Custom Actors & Custom Lumps

> "How does it deal with custom actors and custom actor lumps? Do these need to be added to the addon or there's a way to add custom types and lumps directly?"

**Status:** Unanswered — needs investigation / design decision.

Things to consider when answering:
- Does the current entity system support arbitrary lump key/value pairs per object?
- Is there a freeform lump editor in the addon?
- Do new actor types need to be hardcoded into the dropdown, or can the user type a custom type string?
- How does the JSONC export handle unknown/custom types?
- Could we add a "custom lumps" property group (freeform key/value pairs) per entity empty?

---

### Q2 — Multiple Levels Per Blend File

> "Does it only work as 1 level per blend file? When working on TFL, I had several levels all loaded at once, in different collections with each their own export settings, so it was really easy to work on both levels at the same time and make them match and export the GLB to the correct locations."

**Status:** Unanswered — likely a known limitation, needs design thought.

Things to consider:
- Currently export settings (level name, output path, etc.) appear to be stored as scene properties — one set per .blend
- Multi-level support would require per-collection export settings
- Could potentially use Collection Custom Properties for level name / path per collection
- The export operator would need to either export all collections or let the user pick which one
- GLB export paths would also need to be per-collection

---

### Q3 — Incremental JSON Editing vs Full Regeneration

> "Does it regenerate the whole json every time or does it edit it somehow? If it's the latter, is it possible to have some part of the json that are manually added and don't get wiped out? (not as important if custom types and lumps are possible on point 1 but if neither are possible then that's a pretty big issue)"

**Status:** Unanswered — need to confirm current behaviour and decide on approach.

Current likely behaviour: full regeneration on every export (writes JSONC from scratch).

Things to consider:
- If Q1 is solved (custom lumps), manual JSON edits become less necessary
- If full regen is kept: could we support a "manual override" block in the JSONC that gets preserved?
  (e.g. a comment-delimited section the exporter skips over)
- Alternatively: merge strategy — read existing JSONC, merge with Blender-generated data, write back
- Risk of merge approach: stale data if user deletes entities in Blender but JSONC still has them
- Simplest solution: solve Q1 so the user never needs to manually edit the JSONC at all

---

## Notes

- Q1 and Q3 are linked — if custom lumps are fully supported in the addon, Q3 becomes low priority
- Q2 is independent and is a genuine workflow improvement for multi-level projects
- These likely represent common concerns from anyone coming from a modding background (e.g. TFL, other level editors)
