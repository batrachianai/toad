# Apply Canon TUI

@description Install Canon TUI (conductor-view) globally via uv tool install from GitHub. Idempotent — safe to re-run for updates.

Install the Canon TUI terminal interface for visualizing AI agent activity.
Works from any directory — no need to clone the repo. Installs `canon` and
`canon-ctl` binaries globally via `uv tool install`.

## Source

Package: `canon-tui` from `DEGAorg/canon-tui` (conductor branch)

```
git+https://github.com/DEGAorg/canon-tui.git@conductor
```

---

## Steps

### 1. Check prerequisites

Verify that `uv` is installed:

```bash
command -v uv >/dev/null 2>&1
```

**If `uv` is NOT found**, print:

> `uv` is not installed. Install it first:
>
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```
>
> Then re-run `/apply-canon-tui`.

Stop — do not continue without `uv`.

**If `uv` IS found**, continue to Step 2. Python 3.14+ is handled
automatically by `uv` — it fetches the right Python version based on the
package's `requires-python` constraint.

---

### 2. Install Canon TUI

Run the install command:

```bash
uv tool install "canon-tui @ git+https://github.com/DEGAorg/canon-tui.git@conductor" --force --reinstall --quiet
```

- `--force` — overwrite any existing installation
- `--reinstall` — bust the uv cache so source changes are picked up
- `--quiet` — suppress progress output

If the command fails, print the error output and stop.

---

### 3. Verify installation

Check that both binaries are available:

```bash
canon --version
canon-ctl --help
```

**If `canon --version` fails**, check if the uv tool bin directory is on
PATH:

```bash
uv tool dir --bin
```

Print:

> `canon` is not on PATH. Add the uv tool bin directory to your PATH:
>
> ```bash
> export PATH="$(uv tool dir --bin):$PATH"
> ```
>
> Add this line to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.)
> for persistence.

After PATH is confirmed, re-check `canon --version`.

**If `canon-ctl --help` fails**, print the error and warn — `canon-ctl`
is optional but recommended for managing Canon TUI configuration.

---

### 4. Self-install this command

Copy this command file to `~/.degacore/config/commands/` so
`/apply-canon-tui` works from any directory for future updates:

```bash
mkdir -p ~/.degacore/config/commands
```

Fetch the latest version from GitHub and write it to
`~/.degacore/config/commands/apply-canon-tui.md`:

```
https://raw.githubusercontent.com/DEGAorg/canon-tui/conductor/commands/apply-canon-tui.md
```

If the fetch fails (e.g., no network), fall back to copying the local
version that was just executed.

---

### 5. Print summary

```
Canon TUI installed.

  canon     — TUI viewer for AI agent activity
  canon-ctl — configuration utility

Installed from: DEGAorg/canon-tui@conductor
Method: uv tool install (isolated environment)

Run 'canon .' from any project directory to launch.
Run '/apply-canon-tui' from any directory to update.
```
