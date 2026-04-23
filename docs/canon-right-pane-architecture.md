# Canon Right-Pane Architecture

A structural redesign of the Canon TUI's right side, informed by the
phase-1 Tasks widget critique and a UX review against Nielsen heuristics
and TUI design patterns (Posting, k9s, Elia).

This is a decisions document — not an implementation plan. Decisions
here feed a subsequent execution plan.

---

## Design principles

These principles override any individual decision below if they conflict.

### 1. Chat-first, keyboard-second

Users should accomplish every task by **chatting with the agent**
("show me P1 tasks", "open the plan"), with keyboard shortcuts as a
secondary accelerator. Shortcuts that aren't obvious from the UI
(e.g. `Shift+click`, chorded keys, hidden modifiers) are forbidden.
If a feature only exists via a shortcut, it doesn't exist.

Every interaction must have **two paths**:
- **Chat:** a natural-language phrase the agent can route.
- **Click:** a visible affordance (button, tab, row) a mouse can hit.

Keyboard shortcuts are a third path, shown in tooltips or a footer.
Never the only path.

### 2. Clickable exits on every screen

Escape is a shortcut, not a contract. Every full-screen view, modal,
drill-down, or drawer must expose a **visible, clickable back/close**
affordance:

- Full-screen screens: a `← Back` button top-left, plus a `✕` top-right.
- Drawers/overlays: a `✕` close button.
- Inline detail views (replace pattern): a `← Back to list` button above
  the content.

Escape still works — but it's never the only way out.

### 3. One thing on screen at a time

In a 50 %-wide pane on an 80-column terminal, splitting means cramming.
Default to showing **one thing at a time**, with explicit drill-downs
for depth. Multi-pane layouts are opt-in, not the default.

### 4. Progressive disclosure

Don't show every filter, field, and action at once. Show what 80 % of
users need immediately; put the rest one click away. Active filters
appear as removable chips; inactive filter controls live in a
"Filters" popover.

### 5. Anti-generic aesthetic

No decorative emojis. No gradients. No rounded corners where terminals
can't render them. Every glyph, color, and weight must earn its place.
(From `neo-user-journey` / `impeccable` skills.)

---

## Decisions

### D1. Collapse the aggregate "GitHub" tab

**Today:** The Planning section has a "GitHub" tab that stacks three
unrelated widgets (`StatusOverview`, `PlansView`, `PRsView`) into one
scrolling view.

**Decision:** Replace it with three siblings:

- **Board** (the new view, renamed from "Tasks")
- **Plans**
- **PRs**

`StatusOverview` moves to a 1-row summary strip docked at the top of the
Planning section — visible regardless of which tab is active.

**Why:** One tab per question. Users pick by intent, not by scrolling
through a grab-bag.

### D2. Rename "Tasks" → "Board"; add type filter chips

**Today:** Tasks shows every issue on project board #8, which confused
the reviewer who expected plans.

**Decision:**
- Rename tab to **Board** — 1:1 with GitHub Projects V2 terminology.
- Add a row of **type filter chips** above the table: `All · Plans · Bugs · Features`. Click a chip to filter. Multiple chips can be
  stacked as additive filters.
- The existing Plans tab becomes redundant long-term — Board with
  `type=Plans` preset gives the same view. Phase out `PlansView` after
  the Board transition stabilises.

**Why:** Eliminates the "what even is a task?" confusion. The chip row
gives users an obvious click path to the common cases without digging
into the Filters popover.

### D3. Remove the left sidebar — move Plan + Files into the right pane

**Today:** `[SideBar][Conversation][ProjectStatePane]` — three columns.
On anything below 160 cols it's cramped, and the sidebar's Plan + Files
content competes with the right pane for attention.

**Decision:**

- Delete the left `SideBar` widget.
- Main layout becomes **`[Conversation][ProjectStatePane]`** — two
  columns. Conversation claims ~50 %, right pane ~50 % by default;
  users drag the divider to rebalance.
- Right pane grows a new **Context** section with tabs:
  - **Plan** — the Plan widget.
  - **Files** — the `ProjectDirectoryTree`.
- Right-pane toolbar now has three buttons: **Context · Planning · State**.

**Why:** Two columns scale to any terminal width. Plan and Files are
*contextual* references that support the conversation — they belong on
the same side as the other project-state content, not competing in a
separate rail.

### D4. Replace-pattern drill-down (no more horizontal split)

**Today:** Selecting a row splits the Tasks tab into table (3fr) +
detail (2fr). Inside a 50 %-wide pane that's ~25 cols per side.

**Decision:** **Replace, don't split.** When a user selects a row:

1. The table is replaced in-place by the detail view.
2. A **breadcrumb + Back button** appears at the top:
   `← Back to Board   ›   #142 Wire tasks tab`
3. The detail view has full width of the Tasks tab.
4. Clicking **← Back** or pressing Escape returns to the table with the
   previously-selected row still highlighted.

No separate pushed screen for most cases — the drill-down happens
*inside* the Tasks tab. A deeper drill (e.g. viewing comments, linked
PRs) does push `TaskDetailScreen`, which also gains a clickable
`← Back` button.

**Why:** Full width for the content users actually want to read.
Mirrors Posting's detail flow. Keeps the mental model simple (one
thing at a time).

### D5. Accordion sections with radio-style headers

**Today:** Toolbar buttons act like checkboxes — any subset of sections
can be simultaneously visible, stacked vertically. Two visible sections
inside a 50 %-wide pane × 50 % each = everything cramped.

**Decision:** **Accordion by default.**

- Section headers become full-width clickable bars showing the section
  name and a small expand/collapse chevron.
- Clicking a header **expands that section and collapses all others**.
- Toolbar buttons at the top become a **radio-group** (one active at a
  time). Visual state matches: the active button has the accent
  background, others are muted.
- To show multiple sections, users click a **"Stack"** icon-button in
  the pane toolbar (tooltip: *"Show multiple sections at once"*) which
  switches to multi-expand mode — all sections visible, each at 1fr.
- No hidden shortcut. No Shift+click. The Stack button is the only way
  to enter multi-view mode.

**Why:** Principle #1 (no hidden shortcuts). The default case (one
section) matches the most common user goal. Power users get a one-click
path to split-view.

### D6. Panel routing registry + filter-aware intents

**Today:** `main.py:_PANEL_MAP` is a hard-coded dict mapping panel IDs
to `(section_id, tab_id)` tuples. Adding a panel requires editing that
map + the agent prompt.

**Decision:**

- Introduce a **panel registry**: each right-pane section declares its
  panel IDs + filter schema via a classmethod or module-level constant.
  At startup, `MainScreen` scans registered sections and builds the
  routing map dynamically.
- Extend the `open_panel` sessionUpdate schema:
  ```
  {"open_panel": {
     "panel": "board",
     "filters": {"priority": "P1", "status": "in_progress"},
     "highlight": "#142"
  }}
  ```
  Filters apply before the tab becomes visible. `highlight` focuses a
  specific row if present.
- **New skill:** `.claude/skills/canon-panel-routing/SKILL.md`. Documents
  the registry contract, the schema, worked examples for adding a new
  panel ("Deployments panel in 4 steps"). Future panels become hours of
  work, not days.

**Why:** The right pane will grow many panels over time (deployments,
metrics, logs, secrets, docs…). Making each one a single-file addition
with machine-discoverable filters is a forcing function for consistent
UX.

### D7. Every full-screen exit is clickable

Derived from Principle #2.

- `TaskDetailScreen` header grows a `← Back` button + a `✕` close button.
  Both call `app.pop_screen`. Escape still works.
- Any future modal/drawer follows the same rule.
- Footer still shows the keyboard shortcut (`Back  esc`) so keyboard
  users have a hint — but the clickable affordance is primary.

---

## Out of scope (for this architecture round)

These are valid future concerns but not decided here:

- Theming / color palette — covered by `docs/pm-widget-polish.md`.
- Virtualized DataTable / caching — performance phase.
- Command palette `task:` prefix — future integration.
- Sparklines, relative dates, milestone progress glyphs — cosmetic.

---

## Success criteria for the redesign

When the decisions above are implemented:

1. A new user can discover every feature **without reading docs** — by
   clicking around the UI and asking the agent for help.
2. The word "cramped" does not appear in a fresh critique against a
   100-column terminal.
3. Every full-screen view has a visible way out that isn't Escape.
4. Adding a new right-pane panel takes < 1 hour for someone who has
   read the `canon-panel-routing` skill.
5. The `show me X` chat commands support filters, not just panel names.

---

## References

- Phase-1 PRD: `docs/prd-pm-widget.md`
- Phase-1 oversight: `docs/pm-widget-oversight.md`
- Phase-1 polish backlog: `docs/pm-widget-polish.md`
- Phase-1 critique: issue #22, "Critique findings" comment
- Phase-1 PR: #23
- Nielsen heuristics: via `ux-journey-architect` skill
- TUI patterns: via `textual-tui` skill (DataTable, ContentSwitcher,
  Screen stack, responsive layouts)
