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
