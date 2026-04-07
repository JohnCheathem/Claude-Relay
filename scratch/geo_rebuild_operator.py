# ---------------------------------------------------------------------------
# GEO REBUILD — scratch patch
# Adds OG_OT_GeoRebuild operator and wires it into the UI.
#
# PURPOSE:
#   Geometry + actor placement iteration loop without touching GOAL code.
#   Flow: export GLB → write JSONC/GD → run (mi) via existing GOALC → relaunch GK.
#   No GOALC restart, no .gc recompilation (mi skips unchanged files automatically).
#
# HOW TO INTEGRATE:
#   1. Add _bg_geo_rebuild() and OG_OT_GeoRebuild class into opengoal_tools.py
#      (alongside the existing _bg_build / OG_OT_ExportBuild block).
#   2. Add OG_OT_GeoRebuild to the classes list in register().
#   3. Add the button to the UI panel (see draw snippet at bottom).
#
# DOES NOT TOUCH:
#   - .gc source files
#   - game.gp patch (patch_game_gp)       — code deps don't change
#   - entity.gc patch (patch_entity_gc)   — navmesh patch doesn't change
#   - GOALC process                        — reused if already running
# ---------------------------------------------------------------------------

_GEO_REBUILD_STATE = {"done": False, "status": "", "error": None, "ok": False}


def _bg_geo_rebuild(name, scene):
    """
    Background thread: export geo + actor placement, repack DGO, relaunch GK.

    Skips all GOAL compilation steps. (mi) only re-extracts and repacks
    because the .gc files haven't changed — GOALC's incremental build handles this.

    Steps:
      1. Collect actors / ambients / spawns from scene
      2. Write JSONC (actor placement) and GD (DGO manifest) — these drive extraction
      3. Run (mi) via nREPL if GOALC is live, otherwise start GOALC just for (mi)
      4. Kill GK, relaunch GK in debug mode
    """
    state = _GEO_REBUILD_STATE
    try:
        # ── Step 1: collect scene data ─────────────────────────────────────
        state["status"] = "Collecting scene..."
        actors   = collect_actors(scene)
        ambients = collect_ambients(scene)
        spawns   = collect_spawns(scene)
        ags      = needed_ags(actors)
        tpages   = needed_tpages(actors)
        # code_deps intentionally NOT recalculated — we're not changing code

        # ── Step 2: write JSONC + GD ───────────────────────────────────────
        state["status"] = "Writing level files..."
        base_id = scene.og_props.base_id
        write_jsonc(name, actors, ambients, base_id)

        # Rebuild GD with current actors so DGO manifest stays correct.
        # We pass code_deps=[] because we're not changing code — existing
        # compiled .o files are already referenced from the last full build.
        # Note: if you ADD a new enemy type since the last full build, you
        # need Export & Build instead — this path won't patch game.gp.
        code_deps = needed_code(actors)   # still need for DGO .o injection
        write_gd(name, ags, code_deps, tpages)

        # patch_level_info updates spawn continue-points — needed if you moved spawns
        patch_level_info(name, spawns)

        # ── Step 3: run (mi) ──────────────────────────────────────────────
        # (mi) = make-iso: re-extracts GLB → binary level data, repacks DGO.
        # Skips recompiling .gc files that haven't changed (GOALC incremental build).
        if goalc_ok():
            state["status"] = "Running (mi) — re-extracting geo..."
            r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
            if r is None:
                state["error"] = "(mi) timed out or GOALC lost connection"
                return
        else:
            # GOALC not running — launch it just long enough to run (mi)
            state["status"] = "GOALC not running — launching for (mi)..."
            write_startup_gc(["(mi)"])
            ok, msg = launch_goalc(wait_for_nrepl=True)
            if not ok:
                state["error"] = f"GOALC failed to start: {msg}"
                return
            state["status"] = "Running (mi)..."
            r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
            if r is None:
                state["error"] = "(mi) timed out"
                return

        # ── Step 4: relaunch GK ───────────────────────────────────────────
        state["status"] = "Relaunching game..."
        kill_gk()
        ok, msg = launch_gk()
        if not ok:
            state["error"] = msg
            return

        state["ok"] = True
        state["status"] = "Done! Load your level manually via the debug menu."

    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True


class OG_OT_GeoRebuild(Operator):
    """Export GLB, repack DGO (geo + actor placement only), relaunch GK.
    No GOAL recompilation — fastest iteration loop for geometry and enemy placement."""
    bl_idname      = "og.geo_rebuild"
    bl_label       = "Quick Geo Rebuild"
    bl_description = (
        "Re-export geometry and actor placement, repack DGO, relaunch game. "
        "Skips GOAL compilation — use when only geo/placement changed."
    )
    _timer = None

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first")
            return {"CANCELLED"}

        # Export GLB first (same as Export & Build)
        try:
            export_glb(ctx, name)
        except Exception as e:
            self.report({"ERROR"}, f"GLB export failed: {e}")
            return {"CANCELLED"}

        _GEO_REBUILD_STATE.clear()
        _GEO_REBUILD_STATE.update({"done": False, "status": "Starting...", "error": None, "ok": False})
        threading.Thread(
            target=_bg_geo_rebuild,
            args=(name, ctx.scene),
            daemon=True
        ).start()

        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            ctx.workspace.status_text_set(
                "OpenGOAL Geo: " + _GEO_REBUILD_STATE.get("status", "Working...")
            )
            if _GEO_REBUILD_STATE.get("done"):
                ctx.window_manager.event_timer_remove(self._timer)
                ctx.workspace.status_text_set(None)
                if _GEO_REBUILD_STATE.get("error"):
                    self.report({"ERROR"}, _GEO_REBUILD_STATE["error"])
                    return {"CANCELLED"}
                self.report({"INFO"}, "Geo rebuild done — load your level in-game")
                return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, ctx):
        ctx.window_manager.event_timer_remove(self._timer)
        ctx.workspace.status_text_set(None)


# ---------------------------------------------------------------------------
# UI PANEL SNIPPET
# Add this button block in the Build/Play panel draw() method,
# alongside the existing Export & Build / Launch Game buttons.
# ---------------------------------------------------------------------------
#
#   row = layout.row(align=True)
#   row.operator("og.geo_rebuild", text="Quick Geo Rebuild", icon="FILE_REFRESH")
#
#   # Optional: small warning so user knows when NOT to use it
#   if <some_condition_to_detect_new_enemy_types>:
#       layout.label(text="⚠ New enemy types detected — use Export & Build first",
#                    icon="ERROR")
#
# ---------------------------------------------------------------------------
# REGISTER — add to the classes list in register():
# ---------------------------------------------------------------------------
#
#   OG_OT_GeoRebuild,   # ← add alongside OG_OT_ExportBuild
#
