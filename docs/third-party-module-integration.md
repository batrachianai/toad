# Third-Party Module Integration

How external modules plug into Canon TUI. This documents the pattern
used by Outreach (the first third-party module) as the reference
implementation.

## Architecture

Canon uses a **conditional plugin model**: modules are discovered at
startup, mounted only if their provider is available, and controlled
through the same section/tab/action/ACP machinery as built-in panels.
No hard dependencies — if the module is missing, Canon runs without it.

```
Discovery (registry.py)
  → Provider satisfies Protocol?
    → yes: append section, mount widgets, start timers
    → no:  skip silently, no section in pane
```

## Integration Points

A module touches **7 files** to integrate. The table below uses
Outreach as the concrete example.

| # | File | What to add |
|---|------|-------------|
| 1 | `src/toad/extensions/<module>/protocol.py` | Provider protocol + data models |
| 2 | `src/toad/extensions/<module>/registry.py` | Discovery function (import + validate) |
| 3 | `src/toad/widgets/<module>_cards.py` | Pure-data card widgets |
| 4 | `src/toad/widgets/project_state_pane.py` | Section constants, conditional mount, fetch/render, timer |
| 5 | `src/toad/screens/main.py` | Screen actions + ACP panel handlers |
| 6 | `src/toad/screens/main.tcss` | Accent styling for the section |
| 7 | Conductor prompt (agent config) | Document canon-ctl commands for agents |

Each point is detailed below.

---

### 1. Provider Protocol

Define a runtime-checkable `Protocol` that any concrete provider must
satisfy. Keep it minimal — one availability check, one data fetch.

```
src/toad/extensions/<module>/protocol.py
```

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MyModuleProvider(Protocol):
    async def available(self) -> bool:
        """Return True if the provider can serve data right now."""
        ...

    async def snapshot(self) -> MySnapshot:
        """Fetch the current data payload."""
        ...
```

**Data models** live in the same file. Use frozen dataclasses for the
snapshot payload — the provider fetches, the pane renders, no shared
mutable state.

**Outreach example:** `OutreachInfoProvider` protocol with
`OutreachSnapshot` containing `ProspectsCard`, `SendsCard`,
`HackathonStat`, and `AccountStat` models.

---

### 2. Discovery (Registry)

A single `discover()` function that attempts to import the concrete
provider, validates it, and returns it or `None`.

```
src/toad/extensions/<module>/registry.py
```

```python
def discover() -> MyModuleProvider | None:
    try:
        mod = __import__(
            "toad.extensions.<module>",
            fromlist=["provider"],
        )
        provider = mod.provider
        if isinstance(provider, MyModuleProvider):
            return provider
    except Exception:
        pass
    return None
```

**Key rules:**
- Never raise — return `None` on any failure
- Validate with `isinstance()` against the protocol
- The concrete provider lives in a private submodule (gitignored or
  separate repo) so Canon itself has no dependency on it
- Config (DSN, API keys) is the provider's problem — Canon passes
  nothing

**Outreach example:** Reads `CANON_RPA_OUTREACH_DATABASE_URL` env var,
falls back to `.env` in the private submodule directory. Canon has zero
config surface for outreach.

---

### 3. Card Widgets

Pure-data display widgets that receive data via `set_data()` calls.
They never fetch data themselves.

```
src/toad/widgets/<module>_cards.py
```

Widgets inherit from a simple `_CardBase` (or `Static`/`Widget`) and
expose one public method:

```python
class MyCard(Static):
    def set_data(self, total: int, segments: tuple) -> None:
        self.update(render_markup(total, segments))
```

**Outreach example:** Four card types — `StatLine` (label + bar),
`Histogram` (24h distribution), `RankedBar` (top-N), `AccountDot`
(per-account status line).

---

### 4. Pane Integration (`project_state_pane.py`)

This is the biggest integration point. Four things to add:

#### a) Section constants

```python
SECTION_MYMODULE = "section-mymodule"
TABS_MYMODULE = "tabs-mymodule"
BADGE_MYMODULE = "badge-mymodule"
MYMODULE_REFRESH_INTERVAL = 30  # seconds
```

#### b) Panel routing entry

Add to `PANEL_ROUTES` so ACP `OpenPanel` messages route correctly:

```python
PANEL_ROUTES: dict[str, tuple[str, str]] = {
    # ... existing entries ...
    "mymodule": (SECTION_MYMODULE, "tab-mymodule"),
}
```

#### c) Conditional init + compose

In `__init__`, discover the provider and conditionally append the
section:

```python
self._mymodule_provider = discover_mymodule()
if self._mymodule_provider is not None:
    self._sections.append(
        _SectionDef(SECTION_MYMODULE, "My Module")
    )
```

In `compose()`, conditionally mount the section with its cards:

```python
if self._mymodule_provider is not None:
    with Vertical(id=SECTION_MYMODULE, classes="pane-section"):
        yield SectionStatusBadge(
            BadgeState.POLLING, id=BADGE_MYMODULE
        )
        with TabbedContent(id=TABS_MYMODULE):
            with TabPane("My Module", id="tab-mymodule"):
                yield MyCard(id="mymodule-card")
```

#### d) Timer + fetch + render

Follow the existing pattern: start a periodic timer when the section
becomes visible, stop it when hidden.

```python
def _sync_mymodule_timer(self, section_id, visible):
    if section_id != SECTION_MYMODULE:
        return
    if self._mymodule_provider is None:
        return
    if visible:
        self._fetch_mymodule()  # immediate fetch
        self._mymodule_timer = self.set_interval(
            MYMODULE_REFRESH_INTERVAL, self._fetch_mymodule
        )
    else:
        self._stop_mymodule_timer()
```

The fetch function is a Textual worker (`@work`) that calls the
provider's `snapshot()` and hands the result to a render function
that updates the card widgets via `set_data()`.

---

### 5. Screen Actions (`main.py`)

Two actions — show and hide — following the existing pattern:

```python
def action_show_mymodule(self) -> None:
    self._show_section_tab(SECTION_MYMODULE, "tab-mymodule")

def action_hide_mymodule(self) -> None:
    self._hide_section(SECTION_MYMODULE)
```

These are automatically available via `canon-ctl action`:

```bash
canon-ctl action screen.show_mymodule
canon-ctl action screen.hide_mymodule
```

**ACP routing** is already handled by `PANEL_ROUTES` — the existing
`on_acp_open_panel()` / `on_acp_close_panel()` handlers look up the
panel ID in the registry and call `_show_section_tab()` /
`hide_section()`. No new handler code needed.

---

### 6. TCSS Styling (`main.tcss`)

Each section gets a colored left border accent to distinguish it
visually:

```tcss
ProjectStatePane #section-mymodule {
    border-left: tall <color> 25%;
}
```

**Existing color assignments:**
- Context: cyan
- Planning: magenta
- State: green
- Plan Execution: yellow
- Outreach: orange

Pick a color not already used.

---

### 7. Agent Awareness (Conductor Prompt)

Agents running inside Canon learn about available commands from the
conductor system prompt. Add the new show/hide commands to the
**Canon TUI — Agent Capabilities** section:

```markdown
# In the Socket commands section:
canon-ctl action "screen.show_mymodule"
canon-ctl action "screen.hide_mymodule"

# In the "When to use" section:
- User asks about <module topic> → `show_mymodule`
- User asks to hide <module> → `hide_mymodule`
```

Without this, agents won't know the commands exist. The conductor
prompt is the only place agents discover available TUI actions.

---

## Checklist for Adding a New Module

- [ ] Provider protocol defined (`extensions/<module>/protocol.py`)
- [ ] Discovery function returns provider or None (`extensions/<module>/registry.py`)
- [ ] Card widgets created with `set_data()` API (`widgets/<module>_cards.py`)
- [ ] Section constants + `PANEL_ROUTES` entry added (`project_state_pane.py`)
- [ ] Conditional init/compose/timer/fetch/render wired (`project_state_pane.py`)
- [ ] Screen actions added (`main.py`)
- [ ] TCSS accent color assigned (`main.tcss`)
- [ ] Conductor prompt updated with new commands
- [ ] `canon-ctl action screen.show_<module>` works
- [ ] ACP `OpenPanel(panel_id="<module>")` routes correctly
- [ ] Module missing → Canon starts clean, no errors
- [ ] `uv run python tools/verify-tui.py --verbose` passes

## Design Principles

1. **No hard dependencies.** Canon must start without the module.
   Discovery returns `None`, compose skips the section, done.

2. **Provider owns its config.** DSN, API keys, credentials — all
   managed by the private submodule. Canon passes nothing.

3. **Cards are dumb.** Widgets receive data via `set_data()`, never
   fetch. The pane orchestrates the fetch→render cycle.

4. **Standard lifecycle.** Show/hide/timer follows the same pattern as
   every other section. No special cases in the socket controller.

5. **Agent-native.** Every UI action is reachable via `canon-ctl` and
   ACP messages. Document commands in the conductor prompt or agents
   can't use them.
