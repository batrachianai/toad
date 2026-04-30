# Plan Execution Tab — Follow-ups & Open Questions

Notes captured during the 0.7.5/0.7.6 cleanup pass so they don't get lost
in chat. Review when convenient.

## Decisions made

- Verification line is **hidden entirely** in the terminal banner.
  Engine treats verify as advisory (`SHIP` proceeds even when verify
  flags unchecked criteria), so showing `verify: failed` next to
  `✓ Completed (SHIP)` reads as a contradiction. We may surface it
  differently later (see open questions).
- PR is now reachable through a `→ PR` button in the header (opens
  `terminal.pr_url` via `webbrowser.open`). PR # still inline in the
  title so the run identity stays scannable.
- Close button (`✕`) lives in the header row. Emits
  `PlanExecutionTab.CloseRequested(slug)`; the section handles it via
  the existing `close_tab(slug)` path.
- Bottom `PlanStatusRail` removed from this tab. The widget still
  exists for any other consumer.

## Open questions for review

### 1. Should advisory verification be visible at all?

Right now it's invisible. Two reasonable alternatives if you want it
back without the contradiction:

- **Quiet badge.** Add `⚠` token after the completed badge: `✓ Completed
  (SHIP) ⚠`. Hover/tooltip explains advisory verify.
- **Detail line on demand.** A small `verify ⓘ` button that expands
  to show the unchecked criteria when clicked.

Decision needed before re-enabling.

- not visible now

### 2. PR button: open in browser vs. switch to in-TUI PR view?

Today the button uses `webbrowser.open(pr_url)`. The TUI also has a PR
view at *Planning > tab-tasks* with a `type=pr` filter chip
(`PANEL_ROUTES["prs"]` in `project_state_pane.py`). We could route
there instead — but it lists *all* PRs, not just this run's. Best path
is probably both: primary action = browser; secondary = "show in PR
list" with a filter.

-  we should route to the tui pr view in state view. something clean. nice and local, dry, reuse, not awkward.

### 3. Close button visibility while a plan is still running

Should `✕` close a *running* plan tab? Right now it always closes —
the orchestrator process is detached (tmux), so closing the tab does
not stop the run. May need a confirm dialog if the run is still live.
Easy follow-up.

- yeah we can add a confirmation, stating the process will continue you are just closing the view. could we reopen if we request it to the agent?

### 4. Donut name vs. shape

The widget is `PlanDonut` but renders a flat 2-row gauge. Kept the
name to avoid churn on imports. Worth renaming in a sweep when
nothing else is in flight.

- rename it to progress bar or something more appropiare

### 5. Pre-existing test failures on develop

- ✅ **`test_plan_execution_section.py` (5 tests).** Fixed in this PR
  by extending `_StubModel` to satisfy the full `PlanExecutionModel`
  protocol (`plan_dir`, `poll_now`, `set_target`).
- ⏭ **`test_gantt_timeline.py` (16 tests).** The render functions
  changed signature — `render_bar_row` / `render_group_header` /
  `render_gantt` now return single `Text` objects, not
  `(label, track)` tuples — but the tests still unpack tuples. Needs
  a wholesale rewrite. Deferred to its own PR; not blocking.
- ⏭ **`test_canon_sections.py` (7 tests).** Tests assert that
  `_render_log` emits the level token (`INFO`, `WARN`, …) inline,
  but the current implementation only varies colour. Either
  reintroduce the token or rewrite the assertions. Deferred.

## Abstract / placeholder implementations

None in this pass — every change is concrete. The PR-button → browser
behaviour is the simplest viable wiring; replace it when the in-TUI
PR view filter route is wired (see open question #2).