# Subagent Tabs — Design Brief

> **Status:** Aligned with canon-docs (terminology revised 2026-04-20)
> **Date:** 2026-04-20
> **Related:**
> - `claude-code-config/docs/conductor-session-feedback.md`
> - `canon-docs/Canon_SAS_TUI.md` (Harness OS layering)
> - `canon-docs/specs/SAS_Orchestration_References.md` (delegation metadata)

**Terminology note:** this brief uses **subagent** (one word, lowercase)
uniformly, matching `SAS_Orchestration_References.md` and ecosystem
convention. The Canon-native **Worker Agent** term (per SAS Ralph Loop)
refers to headless executors; the tabs here are *interactive, steerable*
subagents — a new UX contribution this work will upstream to
`Canon_SAS_TUI.md` Layer 3.

## Goal

Let the Conductor spawn visible, interactive subagents without losing
stability, context, or awareness of what the subagent is doing.

## Non-goals

- Replacing or deprecating the existing right-pane panels (Board,
  Timeline, Planning, State). They stay exactly as-is.
- Multi-session refactor of the top-level `MainScreen`. The Conductor
  remains the single primary ACP session in the left pane.
- A session registry, output file viewers, or notification system.

## Shape

A subagent is a **full ACP subprocess** (`claude-code-acp`) rendered
inside a new right-pane section called **Subagents**. Each active
subagent is one tab in that section.

```
┌─ Conductor (left) ──┬─ Project State (right) ─────────────────┐
│                      │ [Context] [Planning] [State] [Subagents]│
│   conversation       │                                          │
│                      │   Subagents: [ Strategy ] [ Canon CLI ]  │
│                      │   ┌─────────────────────────────────┐    │
│                      │   │  subagent conversation view     │    │
│                      │   │  (reuses Conversation widget)   │    │
│                      │   └─────────────────────────────────┘    │
└──────────────────────┴──────────────────────────────────────────┘
```

The left pane does not change. The right pane gains one additional
section that appears dynamically when the first subagent is spawned
and hides when the last one closes.

## Mechanism

### Spawning (Conductor → TUI)

The Conductor calls the existing socket controller:

```
canon-ctl action screen.open_subagent_tab \
  --name "Strategy" \
  --objective "Research how competitor X handles token streaming..."
```

The socket action accepts a structured payload (per
`SAS_Orchestration_References.md:349`); v1 populates only `objective`,
but the schema reserves `output_format`, `tool_scope`, and `boundary`
for future use so we don't have to break the contract later.

The TUI:

1. Ensures the **Subagents** section is mounted in `ProjectStatePane`
2. Creates a new tab with the given name
3. Spawns a fresh `claude-code-acp` subprocess (same binary the
   Conductor uses) and mounts an `Agent` + `Conversation` pair inside
   the tab
4. Sends `--objective` as the subagent's first user message

Each subagent is its own ACP session — same transcript widget, same
input prompt, same streaming behavior the Conductor already has. The
user can type into the subagent tab to steer it directly.

### Awareness (subagent → Conductor)

Two channels, both explicit:

1. **Pull** — Conductor can ask for a status snapshot at any time:
   ```
   canon-ctl query subagent.status --name "Strategy"
   ```
   Returns the latest assistant message, current tool call if any,
   and a `done` flag.

2. **Push on completion** — when the subagent session ends (subprocess
   exits or user closes the tab), the TUI injects a synthetic user
   message into the Conductor's session:
   ```
   [subagent Strategy completed: <final assistant message or summary>]
   ```
   The Conductor sees this in its own stream and can react in the next
   turn.

No polling loop, no background watcher thread. The Conductor decides
when to check in, and gets a guaranteed notification on completion.

### Context sharing

Kept deliberately minimal for v1:

- The `--objective` argument is how Conductor transfers context.
  Conductor is responsible for writing a good objective (it has the
  full project context; the subagent doesn't need a copy).
- Subagents inherit the working directory, so file-based tools (Read,
  Grep, Edit) see the same repo.
- No shared MCP memory, no shared conversation history. If we need
  deeper sharing later, it's a separate conversation.

### Closing

- User closes a tab → TUI kills the subprocess, injects the completion
  message into Conductor, removes the tab
- Last tab closes → Subagents section hides itself
- Conductor can close a tab explicitly:
  ```
  canon-ctl action screen.close_subagent_tab --name "Strategy"
  ```

## Future migration to Harness OS

Per `Canon_SAS_TUI.md:237-244`, subagent lifecycle management
(spawn / status / kill / multiplexing) is a Phase II deliverable of
**Harness OS Session Manager**. This v1 implements that lifecycle
inside the Canon TUI because Harness OS does not yet exist as a shared
library. When it does, the spawn/kill/status concerns migrate out and
the TUI keeps only the tab-rendering concern. The socket contract
(`screen.open_subagent_tab`, `subagent.status`) is designed to survive
that migration: Harness OS will sit behind the same verbs.

## What gets added (rough inventory)

- New widget: `SubagentTabSection` (a `ProjectStatePane` section with
  dynamic tabs hosting `Conversation` widgets)
- New socket actions: `screen.open_subagent_tab`,
  `screen.close_subagent_tab`
- New socket query: `subagent.status`
- One synthetic-message hook in `Agent` to inject completion notices
  into the Conductor session

## What does NOT change

- Existing `PANEL_ROUTES`, `open_panel` / `close_panel` ACP messages
- `ProjectStatePane` sections (Context, Planning, State) and their tabs
- Conductor's ACP client lifecycle
- The Gantt timeline, Board view, or any existing panel
- The left-pane `Conversation` widget

## Why this shape

| Requirement | How this satisfies it |
|---|---|
| Stability | Subagent crash is process-isolated from Conductor |
| Context sharing | Explicit objective + shared working directory |
| Conductor awareness | Pull (query) + push (completion notice) |
| User visibility | Subagent tab is a live, interactive transcript |
| User steering | User can type into the subagent tab |
| Additive, not destructive | No existing panel or message type is removed |

## Patterns to upstream into canon-docs after build

- **Interactive subagent tab** as the canonical rendering for
  `Canon_SAS_TUI.md` Layer 3 "Session multiplexing UI"
- **Synthetic completion message** as the subagent→Conductor completion
  convention

## Open questions

- Tab label collision: two subagents named "Strategy"? Suggest
  appending a numeric suffix (`Strategy`, `Strategy 2`).
- Max concurrent subagents? Suggest a soft cap (e.g. 4) to avoid
  accidental fork-bombs.
- Does the completion notice to the Conductor need the full subagent
  transcript, or just the final message? v1: just the final message.
