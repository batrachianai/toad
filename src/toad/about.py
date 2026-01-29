import os
from importlib.metadata import version
import platform
from string import Template

from toad.app import ToadApp
from toad import paths
from toad import get_version

ABOUT_TEMPLATE = Template(
    """\
# About Toad v${TOAD_VERSION}

© Will McGugan.
                          
Toad is licensed under the terms of the [GNU AFFERO GENERAL PUBLIC LICENSE](https://www.gnu.org/licenses/agpl-3.0.txt).


## Config

config read from `$SETTINGS_PATH`
                                       
```json
$CONFIG                       
```

## Paths

| Name | Path |
| --- | --- |
| App data | `$DATA_PATH` |
| App state | `$STATE_PATH` |
| App logs | `$LOG_PATH` |

                          
## System

| System | Version |
| --- | --- |
| Python | $PYTHON |
| OS | $PLATFORM |
| Terminal | $TERMINAL |

## Dependencies

| Library | Version |
| --- | --- | 
| Toad | $TOAD_VERSION |
| Textual | $TEXTUAL_VERSION |
| Rich | $RICH_VERSION |
                          
## Environment

| Environment variable | Value |                
| --- | --- |
| `SHELL` | $SHELL |
| `TERM` | $TERM |
| `COLORTERM` | $COLORTERM |
| `TERM_PROGRAM` | $TERM_PROGRAM |
| `TERM_PROGRAM_VERSION` | $TERM_PROGRAM_VERSION |
"""
)


def render(app: ToadApp) -> str:
    """Render about markdown.

    Returns:
        Markdown string.
    """

    try:
        config: str | None = app.settings_path.read_text()
    except Exception:
        config = None

    template_data = {
        "COLORTERM": os.environ.get("COLORTERM", ""),
        "CONFIG": config,
        "DATA_PATH": paths.get_data(),
        "LOG_PATH": paths.get_log(),
        "STATE_PATH": paths.get_state(),
        "PLATFORM": platform.platform(),
        "PYTHON": f"{platform.python_implementation()} {platform.python_version()}",
        "RICH_VERSION": version("rich"),
        "SETTINGS_PATH": str(app.settings_path),
        "SHELL": os.environ.get("SHELL", ""),
        "TERM_PROGRAM_VERSION": os.environ.get("TERM_PROGRAM_VERSION", ""),
        "TERM_PROGRAM": os.environ.get("TERM_PROGRAM", ""),
        "TERM": os.environ.get("TERM", ""),
        "TEXTUAL_VERSION": version("textual"),
        "TOAD_VERSION": get_version(),
        "TERMINAL": app.term_program,
    }
    return ABOUT_TEMPLATE.safe_substitute(template_data)
