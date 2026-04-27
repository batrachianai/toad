# Plan Execution Tab — Production Checklist

Snapshot of what's missing before "open canon → run orch → watch workers"
works without manual coaxing. Everything below is gated on the merge from
`orch/31-20260422-plan-execution-tab` (commit `d9db5eb`) being on canon.

## Status today

| Piece | State |
|---|---|
| `OrchestratorStateWidget` watches `.orchestrator/master.json` | ✅ wired |
| `PlanExecutionSection` mounts on `PlansUpdated` | ✅ wired |
| `PlanExecutionTab` (header, dep graph, status rail, log pane) | ✅ widgets exist |
| `PlanExecutionModel` (Phase B data layer) | ❌ not implemented |
| `configure_plan_execution()` called at startup | ❌ never invoked |
| Right pane auto-opens on plan activity | ❌ pane stays hidden |
| Toolbar button for the plan-execution section | ❌ no entry point |
| Agent-callable `open_panel("plan_execution")` | ❌ not in `PANEL_ROUTES` |

## P0 — Make it work end-to-end

### 1. Implement `PlanExecutionModel`

Phase B data layer. Reads `.orchestrator/<slug>/state.json` and the per-item
log files; emits typed messages the existing widgets already subscribe to:

- `ItemStatusChanged(item_id, status)` → `PlanDepGraph`, `PlanStatusRail`
- `ItemLogAppended(item_id, line)` → `PlanWorkerLogPane`
- `PlanFinished(verdict)` → `PlanExecutionTab` header

File: `src/toad/data/plan_execution_model.py` (new). Watches via
`watchfiles` with a poll fallback, mirrors the pattern in
`OrchestratorStateWidget`.

### 2. Wire the factory at startup

In Canon's ACP bootstrap (likely `src/toad/screens/main.py` or
`src/toad/app.py`), call once after `ProjectStatePane` mounts:

```python
pane.configure_plan_execution(
    model_factory=lambda slug: PlanExecutionModel(project_path, slug),
    get_current_agent=lambda: self.conversation.agent_name,
)
```

Without this, `PlanExecutionSection.open_tab` returns `None` silently.

### 3. Auto-open the right pane on plan activity

Currently `_on_plans_updated` mounts the section but doesn't reveal the
parent pane (which starts `display: none`). Add to that handler:

```python
self.display = True              # show the pane
self._ensure_plan_exec_section()
section.display = True           # already done by open_tab
```

Optionally suppress when the user has explicitly hidden the pane within
the last N seconds (avoid stealing focus during reads).

## P1 — Lifecycle and discoverability

### 4. Persistent tab names

Tabs are keyed by plan slug. Names should stay stable even after
`PlanFinished` so the user can flip back to a SHIPped plan and read
the log. Today the tab persists; double-check that it survives a
`master.json` rewrite that no longer lists the slug as active.

### 5. Empty / idle state

When the section is mounted but no plan has ever run, render a single
placeholder pane:

> No plan running. Start one with `/plan <task>` or
> `bash ~/.claude/scripts/orch-run.sh <slug>`.

When a plan ends and no others are active, keep finished tabs but show
a muted "Idle — last plan finished N min ago" line in the header strip.

### 6. Toolbar button

Add a "Plans" button to the toolbar so the user can reopen the section
after closing it. Add `_SectionDef("section-plan-execution", "Plans")`
to `SECTIONS` (conditional on the section being mountable, like the
outreach section is today).

### 7. Auto-close behavior

Sibling sections collapse the pane when all are hidden
(`AllSectionsHidden`). Plan execution should participate so closing
the last visible section still tears down the pane.

## P2 — Agent-driven control

### 8. Agent can open/close from chat

Register routes so `open_panel("plan_execution", filters={"slug": "..."})`
works from the agent without the user clicking anything:

```python
PANEL_ROUTES["plan_execution"] = (PlanExecutionSection.SECTION_ID, ...)
PANEL_ROUTES["plans"] = ...           # alias, currently routes to Board
PANEL_FILTERS["plan_execution"] = ("slug",)
```

Note the existing `"plans"` alias points at the Planning board chip
filter — pick a non-conflicting name (e.g. `plan_run`, `execution`,
`workers`) or move the Board chip alias.

### 9. Run a plan from inside Canon

Currently the user opens Canon, then runs `orch-run.sh` in another
terminal. Production target: the agent inside Canon can spawn a plan
without the user leaving the TUI.

Two flavors:

- **In-process:** `canon-ctl` exposes a `plan run <slug>` subcommand
  that the agent invokes via its existing tool-call surface. Canon
  spawns the orchestrator as a subprocess inside its own tmux session
  (or as a Textual `Worker`), capturing stdout/stderr into the log
  pane directly. Lifetime is bound to Canon — closing canon kills
  the orch.
- **Detached:** `canon-ctl plan run --detached <slug>` shells out
  to the existing `orch-run.sh`, which already creates its own tmux
  session and worktrees. Canon just watches `.orchestrator/`, same as
  the external-terminal flow today.

The detached path is closer to what we have. Wire it as the default
and add the in-process variant only if users ask for it.

### 10. Cancel / stop from the UI

`PlanExecutionTab` should expose a `Cancel` action that calls
`orch-stop.sh <slug>` or signals the worker tmux session. Today the
user has to drop to a terminal.

## P3 — Polish

- **Verdict badge** in tab title (✓ SHIP, ✗ REVISE, ⏵ running)
- **Notification** when a plan finishes (Textual `Notify` + optional
  desktop notification)
- **History view** — list of past `master.json` plans, click to reopen
  a finished tab from disk
- **Diff view** per item — what changed in the worker's worktree
- **Keybindings** — `g p` to focus the plan section, `]`/`[` to cycle
  tabs

## Files touched, by feature

| Feature | File(s) |
|---|---|
| 1, 2 | `src/toad/data/plan_execution_model.py` (new), `src/toad/screens/main.py` |
| 3, 7 | `src/toad/widgets/project_state_pane.py` |
| 4, 5 | `src/toad/widgets/plan_execution_section.py`, `plan_execution_tab.py` |
| 6 | `src/toad/widgets/project_state_pane.py` (toolbar) |
| 8 | `src/toad/widgets/project_state_pane.py` (`PANEL_ROUTES`) |
| 9 | `src/toad/canon_ctl.py` (or wherever the CLI lives) |
| 10 | `src/toad/widgets/plan_execution_tab.py` |

## Acceptance — production-ready when

- [ ] `canon .` then `bash ~/.claude/scripts/orch-run.sh <slug>` shows
      a tab with live status updates, no manual pane-open.
- [ ] Asking the agent "show me the running plan" inside Canon opens
      the same view, no second terminal.
- [ ] Closing the plan tab and reopening from the toolbar restores it.
- [ ] An idle Canon (no `.orchestrator/`) shows a clear "no plan
      running" message instead of an empty pane.
- [ ] `verify-tui.py --widget plan-execution` covers the empty,
      running, finished, and cancelled states headlessly.
