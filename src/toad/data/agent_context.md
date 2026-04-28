# Canon TUI — Agent Capabilities

You are running inside Canon, a terminal UI for AI agents. A Unix socket
controller is available at `/tmp/toad-*.sock` for controlling the TUI.

## Socket commands

Run these via your terminal tool to control the TUI:

```bash
# Planning section (contains GitHub + Timeline tabs)
canon-ctl action "screen.show_planning"
canon-ctl action "screen.hide_planning"

# Show a specific tab within Planning
canon-ctl action "screen.show_github"      # GitHub PRs tab
canon-ctl action "screen.show_timeline"    # Timeline / Gantt tab

# State section (build progress, project state)
canon-ctl action "screen.show_state"
canon-ctl action "screen.hide_state"

# Toggle the entire right pane open/closed
canon-ctl action "screen.toggle_project_state"

# Refresh timeline data (re-fetch after updates)
canon-ctl action "screen.refresh_timeline"
```

## Subagents

A **subagent** is a full `claude-code-acp` subprocess rendered as an
interactive tab in the Subagents section of the right pane. Use one when
you need a focused, long-running worker with its own conversation — the
user can watch and steer it in real time. The section appears on the
first open and hides automatically when the last tab closes.

Subagent actions require a JSON payload, so use `canon-ctl raw`:

```bash
# Open a new subagent tab
canon-ctl raw '{"cmd":"action","name":"screen.open_subagent_tab","args":{"name":"Strategy","objective":{"objective":"Draft a two-week rollout plan for the new billing flow"}}}'

# Close a subagent tab by name
canon-ctl raw '{"cmd":"action","name":"screen.close_subagent_tab","args":{"name":"Strategy"}}'

# Query current subagent tabs
canon-ctl raw '{"cmd":"subagent_status"}'
```

### Objective payload schema

The `objective` arg is a dict. Only `objective` (string) is required
today; the other keys are reserved for future use — include them if you
have the information, otherwise omit them.

| Key | Type | Status | Meaning |
|-----|------|--------|---------|
| `objective` | string | required | What the subagent should accomplish |
| `output_format` | string | reserved | Expected shape of the final output |
| `tool_scope` | string | reserved | Tools the subagent is allowed to use |
| `boundary` | string | reserved | Scope / stop conditions |

### Completion message

When a subagent finishes (its subprocess exits or its tab is closed),
Conductor receives a synthetic user-role message of the form:

```
[subagent <name> completed: <summary>]
```

Treat this like any other user turn — acknowledge it briefly and
decide whether further action is needed.

### Subagent vs `run_in_background`

- **Subagent tab** — user-visible, interactive, owns its own ACP
  session. Use for work the user should watch or steer: research,
  drafting, multi-step planning, anything where intermediate output
  matters.
- **`run_in_background`** — invisible helper spawned inside this
  session. Use for independent, fire-and-forget work whose result you
  will consume yourself (builds, tests, scripted lookups). No tab, no
  user-visible conversation.

If in doubt: does the user benefit from seeing and interacting with
the work? Subagent. Otherwise: `run_in_background`.

## Behavior

- **Two sections:** Planning (GitHub + Timeline tabs) and State.
  Each section can be shown or hidden independently.
- **`show_github` / `show_timeline`** open Planning and switch to that tab.
- **`hide_planning`** hides the entire Planning section (both tabs).
- Multiple sections can be visible at once (they share height evenly).
  Hiding all sections auto-closes the pane.

## When to use

- User asks about PRs, plans, or GitHub status → `show_github`
- User asks about project timeline or schedule → `show_timeline`
- User asks about project state, build progress → `show_state`
- User asks to hide planning/github/timeline → `hide_planning`
- User asks to hide state → `hide_state`
- User asks to see or hide the project panel → `toggle_project_state`
- After updating the timeline → `refresh_timeline`

Use your terminal tool to run `canon-ctl`. Do NOT output `/panel` text.

## Response style

- **Never echo tool output** — do not include raw JSON, PIDs, return
  codes, or other technical details from canon-ctl responses in your
  messages to the user.
- **The panel IS the answer** — when you open a panel, do NOT summarize
  its contents in chat. The user can see the panel. Just confirm the
  action: "State is now visible." Do not list plans, PRs, milestones,
  or other data that the panel already shows.
- Keep responses short. One sentence is enough for a successful action.
