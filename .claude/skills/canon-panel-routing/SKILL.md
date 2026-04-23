---
name: canon-panel-routing
description: How the Canon TUI right-pane is opened, closed, and filtered from agent messages. Use when adding a new right-pane panel, wiring a `show me X` chat command, extending the filter schema, or debugging why an `open_panel` message didn't land. Triggers on ACP `open_panel`, `close_panel`, `PANEL_ROUTES`, `ProjectStatePane`, or "how do I make the agent open the Board tab?".
---

# Canon Panel Routing

This skill explains the single source of truth that maps agent-facing
panel names (used in chat / ACP messages) to concrete right-pane tabs in
the Canon TUI, and how filters flow from a chat command to the UI.

## The data flow

```
Agent reply (JSON-RPC sessionUpdate)
  ↓
{"sessionUpdate": "open_panel",
 "panelId": "board",
 "context": {"filters": {"priority": "P1", "status": "in_progress"}}}
  ↓
toad.acp.agent.rpc_session_update
  ↓
messages.OpenPanel(panel_id="board", context={"filters": {...}})
  ↓
MainScreen.on_acp_open_panel
  ├─ look up "board" in PANEL_ROUTES → ("section-planning", "tab-tasks")
  ├─ _show_section_tab(...) — opens pane, shows section, activates tab
  └─ if panel supports filters, pane.apply_task_filters(filters)
```

The registry lives in `src/toad/widgets/project_state_pane.py`:

- `PANEL_ROUTES: dict[str, tuple[str, str]]` — panel ID → (section, tab)
- `PANEL_FILTERS: dict[str, tuple[str, ...]]` — panel ID → supported filter keys

Both are imported in `src/toad/screens/main.py`.

## Adding a new panel — 4 steps

Say you want a "Deployments" panel reachable via `open_panel` with
ID `"deployments"`.

### 1. Mount the widget in `ProjectStatePane.compose`

```python
# inside an existing TabbedContent, e.g. section-planning
with TabPane("Deployments", id="tab-deployments"):
    yield DeploymentsWidget(id="deployments-view")
```

### 2. Register the route

Edit `PANEL_ROUTES` in `project_state_pane.py`:

```python
PANEL_ROUTES: dict[str, tuple[str, str]] = {
    # ...
    "deployments": (SECTION_PLANNING, "tab-deployments"),
    "deploys":     (SECTION_PLANNING, "tab-deployments"),  # alias
}
```

### 3. (Optional) Declare filter schema

If the panel accepts filters via chat:

```python
PANEL_FILTERS: dict[str, tuple[str, ...]] = {
    # ...
    "deployments": ("environment", "status", "since"),
}
```

Then expose an `apply_deployment_filters(filters: dict)` method on
`ProjectStatePane` and call it from `MainScreen.on_acp_open_panel`
(follow the pattern used for `"board"`).

### 4. Teach the agent

Mention the panel (and any filters) in the agent prompt so the model
knows it can emit:

```json
{"sessionUpdate": "open_panel",
 "panelId": "deployments",
 "context": {"filters": {"environment": "prod"}}}
```

That's it. Closing works automatically (the `close_panel` handler uses
the same registry to find the section to collapse).

## Filter conventions

- **Keys** are lowercase, snake-case strings.
- **Values** are strings, numbers, or booleans — not nested objects.
- **Unknown keys / invalid values** are ignored, never raised. The
  agent may ship a filter that an older client doesn't understand; the
  UI must not crash.
- The filter-apply method on the pane is responsible for validation;
  log unknowns at `debug` level, not `warning`.

## Chat phrasings the agent supports

Map these to `open_panel` calls in the agent prompt:

| User phrase                   | panelId        | filters                                 |
|-------------------------------|----------------|-----------------------------------------|
| "show me the board"           | `board`        | —                                       |
| "show me P1 tasks"            | `board`        | `{"priority": "P1"}`                    |
| "show me done tasks"          | `board`        | `{"status": "done"}`                    |
| "open the plan"               | `plan`         | —                                       |
| "show me the files"           | `files`        | —                                       |
| "open the timeline"           | `timeline`     | —                                       |
| "hide the right panel"        | —              | send `close_panel` with `project_state` |

## Debugging

Common failures and where to look:

| Symptom                                         | Where to check                              |
|-------------------------------------------------|---------------------------------------------|
| Panel never opens                               | Is the ID in `PANEL_ROUTES`? Typo?          |
| Panel opens but filters ignored                 | Is the panel in `PANEL_FILTERS`? Does `MainScreen.on_acp_open_panel` route to `apply_*_filters`? |
| Filters applied but wrong behaviour             | The pane's `apply_*_filters` method — unit-test it with the same dict |
| Agent sends `close_panel` and nothing happens   | `close_panel` handler uses `PANEL_ROUTES[id][0]` as the section to hide — check the ID |

Runtime tracing: set `log.setLevel(logging.DEBUG)` on the pane logger
and watch `"unknown status filter: %s"` / `"unknown priority filter"`
entries.

## Why a registry, not a dict per screen

Keeping `PANEL_ROUTES` in `project_state_pane.py` (not `main.py`) makes
adding a panel a **single-file change**. The pane owns its tabs; it
should also own the agent-facing names for those tabs. `MainScreen`
just dispatches.

This mirrors how chat-based UIs work outside Canon — the surface area
(panel names the agent sees) is tightly coupled to the widgets, and
both move together.

## What NOT to do

- Don't add a panel ID to `PANEL_ROUTES` that points at a tab that
  doesn't exist yet — the open will silently fail with no user-visible
  error.
- Don't invent a new filter key the panel doesn't read. Declare in
  `PANEL_FILTERS` first; unrecognised keys are logged and dropped.
- Don't re-implement routing inline in a widget. If something in the
  right pane needs to open a different panel, send an ACP message
  through the agent, not a direct call. Keeps the routing auditable
  from the agent's perspective.
