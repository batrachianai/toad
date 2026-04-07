# Canon TUI — Agent Capabilities

You are running inside Canon, a terminal UI for AI agents. A Unix socket
controller is available at `/tmp/toad-*.sock` for controlling the TUI.

## Socket commands

Run these via your terminal tool to control the TUI:

```bash
# Open GitHub PRs / plans dashboard (open-only)
canon-ctl action "screen.show_github"

# Open project timeline / Gantt chart (open-only)
canon-ctl action "screen.show_timeline"

# Open canon builder — phase, iteration, build logs (open-only)
canon-ctl action "screen.show_builder"

# Open project state overview (open-only)
canon-ctl action "screen.show_state"

# Toggle the entire right pane open/closed
canon-ctl action "screen.toggle_project_state"

# Refresh timeline data (re-fetch after updates)
canon-ctl action "screen.refresh_timeline"
```

## Behavior

- **`show_*` commands are open-only** — they open (or switch to) their
  section but never close it. Call them to ensure a view is visible.
- **`toggle_project_state` is a true toggle** — it opens the right pane
  if closed, or closes it if open.
- Multiple sections can be visible at once (they share height evenly).
  Hiding all sections auto-closes the pane.

## When to use

- User asks about PRs, plans, or GitHub status → show_github
- User asks about project timeline, milestones, or schedule → show_timeline
- User asks about canon build progress, phases, or iterations → show_builder
- User asks about project state or status overview → show_state
- User asks to see or hide the project panel → toggle_project_state
- After updating the timeline → refresh_timeline

Use your terminal tool to run `canon-ctl`. Do NOT output `/panel` text.
