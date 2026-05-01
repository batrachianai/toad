# Install Canon TUI

## For AI agents — bootstrap instructions

You are installing Canon TUI, a terminal interface for visualizing AI agent
activity. It provides `canon` and `canon-ctl` binaries via `uv tool install`.

**To install, fetch and execute the apply-canon-tui command from GitHub:**

1. Fetch the installer command:
   ```
   https://raw.githubusercontent.com/DEGAorg/canon-tui/main/commands/apply-canon-tui.md
   ```

2. Read the fetched content — it contains the full installation procedure.

3. Execute every step in that document. It will:
   - Check prerequisites (`uv`)
   - Install via `uv tool install` from GitHub (no clone needed)
   - Verify `canon` and `canon-ctl` binaries
   - Self-install `/apply-canon-tui` so future updates work from any directory

No cloning required. Everything is installed directly from GitHub.

---

## For humans — quick start

Tell your AI coding agent:

> Install Canon TUI from https://raw.githubusercontent.com/DEGAorg/canon-tui/main/INSTALL.md

Or install manually:

```bash
uv tool install "canon-tui @ git+https://github.com/DEGAorg/canon-tui.git@main" --force --reinstall
```

---

## What gets installed

| Binary | Purpose |
|--------|---------|
| `canon` | TUI viewer for AI agent activity |
| `canon-ctl` | Configuration utility |

Installed via `uv tool install` into an isolated environment. No system
Python packages are modified.

## Usage

```bash
canon .          # Launch TUI in current project directory
canon-ctl        # Manage Canon TUI configuration
```

## Updating

Once canon is installed, the easiest path is the built-in command:

```bash
canon update              # pull + reinstall from main
canon update --check      # show local vs remote version, no install
canon update --branch develop  # install from a different branch / tag
```

Equivalent manual paths if you'd rather not use the subcommand:

```bash
# Slash command (works from any directory in your AI agent harness):
/apply-canon-tui

# Raw uv invocation:
uv tool install "canon-tui @ git+https://github.com/DEGAorg/canon-tui.git@main" --force --reinstall
```
