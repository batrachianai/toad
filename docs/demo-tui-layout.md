# Demo TUI Layout — Orchestrator-Aware Split Screen

## Goal

Restructure the conductor-view TUI for the Canon demo. The layout shows the
agent conversation alongside live orchestrator state, timeline, and GitHub
context — all in one screen.

## Layout

```
+---------------------------+------------------------+
|                           |  [Timeline] [GitHub]   |
|                           |                        |
|  Conductor Agent          |  (top-right quarter)   |
|  (conversation + prompt)  |                        |
|                           +------------------------+
|                           |  [Plans]   [Workers]   |
|  Left half — always       |                        |
|  visible, unchanged       |  (bottom-right quarter)|
|                           |                        |
+---------------------------+------------------------+
```

- **Left half**: Agent conversation + prompt (existing, untouched)
- **Sidebar**: Stays as-is (file browser, plan collapsible, Ctrl+B toggle)
- **Right half**: Split horizontally into two quarters, each with tabs

### Top-right quarter — Context tabs

| Tab | Content | Source |
|-----|---------|--------|
| Timeline | Gantt chart (existing GanttTimeline widget) | Live GitHub API via `gh` CLI |
| GitHub | PRs + Issues dashboard (existing GitHubStateWidget) | GitHub API via `gh` CLI |

The Timeline tab is the existing ProjectStatePane content. The GitHub tab
is the existing GitHubStateWidget (currently in the sidebar) — move it here
as a tab peer.

### Bottom-right quarter — Orchestrator tabs

| Tab | Content | Source |
|-----|---------|--------|
| Plans | Active plan list with item-level progress | `.orchestrator/plans/*/state.json` |
| Workers | Per-worker status for selected plan, expandable rows | `.orchestrator/plans/<slug>/state.json` items |

**Plans tab**: Shows all active orchestrator plans. Each plan row shows:
slug, item counts (done/running/queued/failed), elapsed time. Clicking or
selecting a plan switches the Workers tab to that plan.

**Workers tab**: Shows items for the selected plan. Each row: item ID,
description (truncated), status badge (done/running/queued/failed),
iteration count. Running items are highlighted. Future enhancement: expand
a row to see tmux pane output from the worker.

## Data flow

```
.orchestrator/plans/*/state.json  -->  OrchestratorStateWidget (new)
                                        |
                                        +--> PlanListView (Plans tab)
                                        +--> WorkerListView (Workers tab)
```

- File watcher (watchdog, already a dependency) monitors `.orchestrator/plans/`
- On state.json change, re-read and update widgets
- Fallback: poll every 5 seconds if watchdog misses events
- No changes needed in claude-code-config orchestrator — it already writes state.json

## Implementation notes

- Textual's `TabbedContent` widget handles the tab system natively
- The right pane already exists as ProjectStatePane (Ctrl+G toggle) — restructure
  its content from a single GanttTimeline into the two-quarter tabbed layout
- GitHubStateWidget moves from sidebar to top-right tab (keep sidebar mount as
  fallback if right pane is closed)
- New widgets needed:
  - `OrchestratorStateWidget` — reads state.json, manages plan/worker data
  - `PlanListView` — renders plan rows with progress indicators
  - `WorkerListView` — renders item rows for selected plan
- CSS: split ProjectStatePane into two `fr` rows, each containing TabbedContent

## Running for any repo

The TUI works from any directory. To use with a Canon project:

```bash
cd /path/to/canon-project && toad --conductor
```

It reads `dega-core.yaml` from cwd for timeline config and watches
`.orchestrator/` relative to the project root. This replaces the old
`canon.sh` terminal showcase.

## Future enhancements (not in this plan)

- Tab for live tmux output from workers (embedded terminal)
- Tab for orchestrator engine log streaming
- Keyboard shortcut to jump to a specific plan/worker
- Notification badges on tabs when state changes
