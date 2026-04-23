# PM Widget — Oversight Plan

Migration guide from the claude-code-config conversation to canon-tui.
Open this file in a new Claude Code session at `/Users/cerratoa/dega/canon-tui`.

---

## Context

Carlos needs the Canon TUI to be an interactive PM dashboard — not just
a read-only Gantt chart. The PRD is at `docs/prd-pm-widget.md`. This
document covers the full execution sequence.

## Step 1: Install skills

Install these skills into `.claude/skills/` in this repo (canon-tui).
Workers will reference them during implementation.

### Required skills

| Skill | Source | Why |
|-------|--------|-----|
| textual-tui-skill | `https://github.com/aperepel/textual-tui-skill` | 40+ Textual widget patterns, layout system, styling |
| TUI Design System | `https://mcpmarket.com/es/tools/skills/tui-design-system` | Layout paradigms: Miller Columns, Widget Dashboards, Multi-panel |
| impeccable | `https://github.com/pbakaus/impeccable` | UX audit/polish — `/audit`, `/polish`, `/distill` commands |
| neo-user-journey | `https://github.com/Cornjebus/neo-user-journey` | Nielsen's heuristics scoring, anti-pattern detection |

### How to install

For each skill, fetch the main `.md` file and save it:

```bash
# Example for textual-tui-skill
curl -sL https://raw.githubusercontent.com/aperepel/textual-tui-skill/main/textual-tui.md \
  -o .claude/skills/textual-tui.md

# Repeat for each skill — check each repo for the correct file name
```

Or tell Claude: "Install these skills into `.claude/skills/`" and give
it the table above. It will fetch and save them.

## Step 2: Create execution plan

Run `/plan` with a reference to the PRD:

```
/plan Implement the interactive PM widget per docs/prd-pm-widget.md
```

The plan should follow these constraints (from exec-plans rules):
- 4-8 items max
- Tests before implementation (TDD)
- Every item has `(deps: N)` annotations
- Shell-verifiable completion criteria
- Max 3 files per item

### Suggested plan structure

```
1. Data layer — task_provider.py (fetch full issue data from GitHub)
2. Tests — test_task_widgets.py with mocked gh output (deps: 1)
3. TaskTable widget — DataTable with row selection (deps: 1)
4. TaskDetail widget — ContentSwitcher with markdown body (deps: 1)
5. FilterToolbar widget — status/milestone/priority filtering (deps: 1)
6. Integration — wire into ProjectStatePane "Tasks" tab (deps: 2, 3, 4, 5)
7. Drill-down screen — TaskDetailScreen with push/pop (deps: 6)
8. Verify — verify-tui.py checks + smoke test (deps: 7)
```

Items 2-5 can run in parallel (all depend only on item 1).

## Step 3: Run the orchestrator

```bash
bash ~/.claude/scripts/orch-run.sh <YYYYMMDD-slug> --issue N
```

Workers spawn in worktrees, execute items respecting deps, verifier
agents run `verify-tui.py` + `pytest` + `ruff` after each item.

## Step 4: Verify

After orchestrator completes:

```bash
# Headless widget verification
uv run python tools/verify-tui.py --verbose

# Unit tests
pytest -q tests/test_task_widgets.py

# Lint + types
ruff check . && ty check

# Visual smoke test
uv run canon .
# → Open project state pane → Tasks tab → verify table loads
# → Select a row → detail panel appears
# → Press Enter on "View comments" → drill-down screen opens
# → Press Escape → returns to task list
```

## Textual patterns to use

These are the key patterns from the research. Workers should follow them.

### Master-detail (DataTable + ContentSwitcher)

```python
@on(DataTable.RowSelected)
def show_detail(self, event: DataTable.RowSelected) -> None:
    issue = self.issues[event.row_key.value]
    self.query_one(TaskDetail).load(issue)
    self.query_one(ContentSwitcher).current = "detail"
```

### Drill-down (screen stack)

```python
class TaskDetailScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, issue_id: int) -> None:
        super().__init__()
        self.issue_id = issue_id
```

### Row keys = issue IDs

```python
table.add_row(status, title, milestone, priority, key=str(issue.id))
```

## Reference apps to study

Workers should look at these for layout and interaction patterns:

- **Posting** (posting.sh) — sidebar + detail panels, closest to our layout
- **Harlequin** — DataTable at scale
- **Elia** — master-detail navigation

## Key files in this repo

| Existing file | Relevance |
|---------------|-----------|
| `src/toad/widgets/project_state_pane.py` | Add "Tasks" tab here |
| `src/toad/widgets/github_views/github_timeline_provider.py` | Extend with issue detail fetch |
| `src/toad/widgets/github_views/timeline_data.py` | Data models to extend or parallel |
| `src/toad/widgets/github_views/fetch.py` | `_run_gh()` — reuse for all gh calls |
| `src/toad/widgets/gantt_timeline.py` | Reference for how existing widgets work |
| `tools/verify-tui.py` | Add new widget checks here |
| `dega-core.yaml` | GitHub project config (repo, project_number) |

## What NOT to do

- Don't edit the Gantt timeline or existing GitHub views — additive only
- Don't add issue editing (read-only for v1)
- Don't add natural language querying (future phase)
- Don't redesign the ProjectStatePane layout — just add a tab
- Don't add new dependencies unless absolutely necessary
