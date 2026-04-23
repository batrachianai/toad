# Adding a Theme

How to add a custom Textual theme to the Canon TUI.

## Files to modify

### 1. `src/toad/app.py` — Define the theme and terminal palette

Add two objects:

**Textual `Theme`** — controls the TUI widget colors via semantic variables
(`$primary`, `$secondary`, `$warning`, `$error`, `$success`, etc.) used
throughout the `.tcss` stylesheets.

```python
from textual.theme import Theme

MY_THEME = Theme(
    name="my-theme",
    primary="#00fffc",
    secondary="#7f00ff",
    accent="#7f00ff",
    foreground="#ffffff",
    background="#000000",
    surface="#111111",
    panel="#151515",
    warning="#cfaa01",
    error="#ff007f",
    success="#00fffc",
    dark=True,
)
```

**`TerminalTheme`** — controls ANSI color rendering inside terminal output
widgets. Maps the 16 standard ANSI colors (8 normal + 8 bright) to your
palette so subprocess output matches the UI.

```python
from rich.terminal_theme import TerminalTheme

MY_TERMINAL_THEME = TerminalTheme(
    background=(0, 0, 0),
    foreground=(255, 255, 255),
    normal=[
        (21, 21, 21),    # black
        (255, 0, 127),   # red
        (0, 255, 252),   # green
        (207, 170, 1),   # yellow
        (127, 0, 255),   # blue
        (255, 0, 127),   # magenta
        (0, 255, 252),   # cyan
        (255, 255, 255), # white
    ],
    bright=[
        (42, 42, 42),    # bright black
        (255, 51, 153),  # bright red
        (51, 255, 253),  # bright green
        (223, 192, 51),  # bright yellow
        (153, 51, 255),  # bright blue
        (255, 51, 153),  # bright magenta
        (51, 255, 253),  # bright cyan
        (255, 255, 255), # bright white
    ],
)
```

Register the Textual theme in `on_load`:

```python
async def on_load(self) -> None:
    self.register_theme(MY_THEME)
```

Wire the terminal theme in the `ui.theme` handler:

```python
elif key == "ui.theme":
    if isinstance(value, str):
        self.theme = value
        if value == "my-theme":
            self.ansi_theme_dark = MY_TERMINAL_THEME
```

### 2. `src/toad/settings_schema.py` — Add to the choices list

Add the theme name to the `choices` array in the `theme` setting so it
appears in the settings UI:

```python
"choices": [
    "my-theme",
    "dega",
    "conductor",
    # ... other themes
]
```

To make it the default, set `"default": "my-theme"`.

## How it works

The TCSS stylesheets (`toad.tcss`, `screens/*.tcss`) reference semantic
color variables like `$primary`, `$secondary`, `$error`, `$warning`,
`$success`, `$background`, `$surface`, and `$panel`. When a Textual
`Theme` is active, these variables resolve to the hex values defined in
the theme. No stylesheet changes are needed when adding a new theme.

The `TerminalTheme` is separate — it only affects Rich's rendering of
ANSI escape codes in terminal output widgets. Without a matching terminal
theme, subprocess output uses Textual's default ANSI palette, which may
clash with the UI colors.

## Existing themes

| Name | Primary | Secondary | Source |
|------|---------|-----------|--------|
| `dega` | `#00fffc` (Neon Teal) | `#7f00ff` (Cosmic Purple) | Canon brand palette |
| `conductor` | `#00ff41` (Neon Green) | `#00d4ff` (Cyan) | Original Conductor palette |

All other themes in the choices list (dracula, monokai, etc.) are
Textual built-ins and don't need registration.
