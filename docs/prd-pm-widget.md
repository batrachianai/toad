# PRD: Interactive Project Management Widget

## Problem

The Canon TUI has a Gantt timeline and status overview, but they are
read-only. Carlos needs to manage work directly from the terminal:
see tasks, drill into details, and query project state — without
leaving Canon. Today he has to go to GitHub, which breaks flow.

## Users

- **Carlos (PM/founder)**: wants one place to see all tasks, click for
  detail, drill deeper, and ask questions about project state.
- **Alberto (engineer)**: needs to see what's assigned, what's blocked,
  and what to work on next — all inside the TUI where agents run.

## Desired outcome

A PM widget inside Canon TUI that supports:

1. **Task list view** — see all issues from the GitHub project board
   in a DataTable with columns: status, title, milestone, priority,
   assignee, effort.
2. **Detail panel** — select a row, a panel opens below or beside with
   the full issue body (rendered markdown), labels, dates, linked PRs.
3. **Drill-down** — from the detail panel, navigate deeper: view
   comments, linked issues, or push a full-screen detail view.
4. **Back navigation** — Escape pops back up the stack at every level.
5. **Filtering** — filter by milestone, status, assignee, priority
   using a toolbar or keyboard shortcuts.
6. **Refresh** — auto-refresh on a timer (configurable, default 60s),
   plus manual refresh keybinding.

## Non-goals

- Editing issues from the TUI (read-only for v1)
- Natural language querying (future phase)
- Notifications or alerts
- Non-GitHub providers

## Technical approach

### Data source

Reuse the existing `GitHubTimelineProvider` and `_run_gh()` infra in
`src/toad/widgets/github_views/`. Add a new fetch method for full issue
details (body, comments, linked PRs) alongside the existing
`fetch_milestones()` and `fetch_items()`.

### Widget architecture

```
ProjectStatePane (existing, add new tab)
  └─ TabbedContent
       ├─ "GitHub" tab (existing timeline + status)
       ├─ "Tasks" tab (NEW)
       │    ├─ FilterToolbar (status, milestone, priority dropdowns)
       │    ├─ TaskTable (DataTable, cursor_type="row")
       │    └─ TaskDetail (ContentSwitcher, shows on row select)
       │         ├─ Markdown body
       │         ├─ Labels, dates, metadata
       │         └─ "View comments" / "View linked PRs" actions
       └─ "State" tab (existing build status)
```

### Textual patterns

| Pattern | Widget | Use |
|---------|--------|-----|
| Master-detail | `DataTable` + `ContentSwitcher` | Task list + detail panel |
| Drill-down | `push_screen` / `pop_screen` | Full issue view, comments |
| Navigation | `OptionList` or filter bar | Milestone/status filtering |
| Rich content | `Markdown` / `MarkdownViewer` | Issue body rendering |
| Collapsible sections | `Collapsible` | Metadata groups in detail |

### Key interactions

- `RowSelected` on DataTable → swap ContentSwitcher to show detail
- `RowHighlighted` → optional preview in a smaller pane
- Enter on "View comments" → `push_screen(CommentsScreen(issue_id))`
- Escape → `pop_screen()` or collapse detail panel
- `r` → manual refresh
- `/` → filter input

### Data model

Extend `TimelineItem` or create a new `TaskItem` dataclass:

```python
@dataclass
class TaskItem:
    id: int
    title: str
    status: str          # Todo | In Progress | Done
    milestone: str
    priority: str        # p1-must-ship .. p4-cut
    assignee: str
    effort: str
    body: str            # markdown
    labels: list[str]
    start_date: str
    target_date: str
    url: str
    comments_count: int
    linked_prs: list[str]
```

### Files to create/modify

| File | Action |
|------|--------|
| `src/toad/widgets/github_views/task_provider.py` | New — fetch full issue data |
| `src/toad/widgets/task_table.py` | New — DataTable widget for tasks |
| `src/toad/widgets/task_detail.py` | New — detail panel (ContentSwitcher) |
| `src/toad/widgets/filter_toolbar.py` | New — filtering controls |
| `src/toad/screens/task_detail_screen.py` | New — full-screen drill-down |
| `src/toad/widgets/project_state_pane.py` | Modify — add "Tasks" tab |
| `src/toad/widgets/github_views/github_timeline_provider.py` | Modify — add issue detail fetch |
| `tools/verify-tui.py` | Modify — add task widget checks |
| `tests/test_task_widgets.py` | New — unit tests |

## Verification

```bash
# All widgets render without error
uv run python tools/verify-tui.py --verbose

# Unit tests pass
pytest -q tests/test_task_widgets.py

# Lint + types clean
ruff check src/toad/widgets/task_table.py src/toad/widgets/task_detail.py
ty check

# Smoke test: tasks tab appears, rows load, detail opens on select
uv run canon . &
# → open Tasks tab → verify DataTable populated → select row → detail shows
```

## Success criteria (shell-verifiable)

- `uv run python tools/verify-tui.py --widget tasks` exits 0
- `pytest -q tests/test_task_widgets.py` exits 0
- `ruff check src/toad/widgets/task_table.py src/toad/widgets/task_detail.py src/toad/widgets/filter_toolbar.py src/toad/screens/task_detail_screen.py` exits 0
- `grep -c 'class TaskTable' src/toad/widgets/task_table.py` returns 1
- `grep -c 'class TaskDetail' src/toad/widgets/task_detail.py` returns 1
- `grep -c '"Tasks"' src/toad/widgets/project_state_pane.py` returns at least 1

## Reference apps

- **Posting** (posting.sh) — sidebar + detail panels, closest layout match
- **Harlequin** — DataTable at scale, SQL IDE
- **Elia** — master-detail chat interface

## Timeline

One day. Workers execute in parallel via orchestrator.
