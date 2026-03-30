# Toad TUI — Agent Capabilities

You are running inside Toad, a terminal UI for AI agents. A Unix socket
controller is available at `/tmp/toad-*.sock` for controlling the TUI.

## Socket commands

Run these via your terminal tool to control the TUI:

```bash
# Show GitHub PRs / plans dashboard
tools/toad-ctl.sh action "screen.show_github"

# Show project timeline (Gantt chart)
tools/toad-ctl.sh action "screen.show_timeline"

# Show canon builder (phase, iteration, build logs)
tools/toad-ctl.sh action "screen.show_builder"

# Show canon automation (status, metrics, run logs)
tools/toad-ctl.sh action "screen.show_automation"

# Toggle the entire right pane open/closed
tools/toad-ctl.sh action "screen.toggle_project_state"

# Refresh timeline data (re-fetch after updates)
tools/toad-ctl.sh action "screen.refresh_timeline"
```

## When to use

- User asks about PRs, plans, or GitHub status → show_github
- User asks about project timeline, milestones, or schedule → show_timeline
- User asks about canon build progress, phases, or iterations → show_builder
- User asks about canon automation, metrics, or run status → show_automation
- User asks to see project state, status, or dashboard → toggle_project_state
- User asks to close or hide the panel → toggle_project_state
- After updating the timeline → refresh_timeline

Each command opens only its section. Multiple sections can be visible
at once (they share height evenly). Hiding all sections auto-closes the pane.

Use your terminal tool to run `toad-ctl.sh`. Do NOT output `/panel` text.
