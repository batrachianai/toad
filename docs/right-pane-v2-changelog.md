# Canon TUI — Right-Pane v2

## Layout

- Removed the left sidebar; TUI is now a 2-column `[Agent][Right Pane]` instead of 3-column
- Plan + Files widgets moved into a new **Context** section inside the right pane
- Right pane has 3 sections: **Context · Planning · State**
- Accordion behavior: clicking a section button opens that one and collapses the others (no hidden shortcuts)
- `⊟` stack-toggle button for power users who want multiple sections open at once

## Board (the new unified view)

- Replaces the old "Tasks" / "Plans" / "PRs" / "Status" / "GitHub" tab sprawl with a single Board tab
- Lists both GitHub issues and PRs side by side
- Type filter chips: **All · Plans · PRs · Bugs · Features**
- Dynamic columns per chip:
  - **Plans** → Progress bar from issue-body checkboxes (`██████░░░░ 65%`)
  - **PRs** → Review state / CI status / Age / Author with glyphs (`✓ approved`, `✓ pass`, `2d`)
  - **All / Bugs / Features** → Status / Title / Milestone / Priority / Assignee
- Filter toolbar: Status / Milestone / Priority dropdowns + title search + Refresh button
- Default status filter is **Active** (Todo + In progress) — Done hidden unless picked explicitly
- Title search jumps into focus via `/` keybinding
- Inline status label is now bold, accent-bordered, hard to miss: "Showing 12 of 34", "No tasks match filters", "Loading", or error

## Drill-down

- Clicking a row **replaces** the list with a full-width detail view inside the Board tab (no more cramped 25-col split)
- Top bar shows `← Back` button + breadcrumb (`Board › #142 Wire tasks tab`)
- Deeper drill into comments/PRs pushes a full-screen `TaskDetailScreen` with `← Back` and `✕` close buttons
- Escape works as a shortcut everywhere, but every view has a visible clickable exit

## Chat-first routing

Natural-language panel routing works without the agent needing any custom knowledge — parsed client-side.

Opens:

- "show me the board" / "show me tasks"
- "show me PRs" / "show me plans" / "show me bugs" / "show me features"
- "show me P1 tasks" / "show me done tasks" / "show me P2 in progress"
- "show me the timeline" / "show me the plan" / "show me the files"
- `open the …`, `go to the …`, `switch to …` variants

Closes:

- "close the board" / "hide the timeline"
- "close the right panel" / "hide everything" → hides all sections

Panel opens instantly on user submit, before the agent replies.

## Data layer

- `TaskProvider` now fetches PRs via `gh pr list` alongside issues
- `TaskItem` gained PR fields: `is_pr`, `review_state`, `ci_state`, `mergeable`, `author`
- Plan items get `progress_pct` computed from markdown checkboxes in the issue body
- PR fetch failures don't block issue fetch (graceful degradation)

## Panel routing registry (for future extension)

- `PANEL_ROUTES`, `PANEL_FILTERS`, `PANEL_TYPE_PRESETS` live in `project_state_pane.py` — adding a new panel is a single-file change
- Filter-aware intents: agent / chat can emit `open_panel` with `context.filters={...}` to open a pre-filtered view
- New skill at `.claude/skills/canon-panel-routing/SKILL.md` documents the registry and gives a 4-step recipe for adding a panel

## Critique fixes (from v1 PR #23)

- Added `/` and `r` keybindings with a title-search input
- Fixed refresh-timer leak when the pane was hidden
- Suppressed spurious `Select.Changed` events during programmatic option resets
- `TaskDetailScreen` now updates live instead of snapshotting stale data
- Replaced bare `except Exception` with typed `NoMatches` where appropriate

## Docs + skills added

- `docs/canon-right-pane-architecture.md` — architectural decisions + chat-first/clickable-exits principles
- `docs/pm-widget-polish.md` — polish backlog for future passes
- `docs/prd-pm-widget.md` — the original PRD
- `docs/pm-widget-oversight.md` — migration notes
- `.claude/skills/canon-panel-routing/SKILL.md` — panel-extension recipe
- Installed reference skills: `textual-tui`, `ux-journey-architect`, impeccable audit/polish/distill/critique/layout/clarify

## What was tried and reverted

- **StatusStrip** (14-day close sparkline + priority distribution bar + milestone summary) was built, shipped, and removed — the signals lacked enough data context to be meaningful in the current state

## Testing

- 44 tests pass: provider parsing, filter predicates, dynamic columns, PR fetch, checkbox-progress, intent detection (open + close), interaction flows via `App.run_test()` pilot
- End-to-end harnesses verify 11 open-phrase cases and 4 close-phrase cases land on the right section/tab with the right filters
- `verify-tui --verbose` passes, `verify-tui --widget live` fetches 100 real tasks from the project board
- `ruff check` clean on all new/modified files

## PRs

- **#23** — Tasks tab foundation (merged-ready)
- **#24** — Right-pane v2 (this consolidation, mergeable to `conductor`)
