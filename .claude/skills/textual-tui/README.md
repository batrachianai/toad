# Textual TUI Skill

A comprehensive skill for Claude Code to build professional terminal user interfaces with Textual.

**Version:** 1.0.0 (active development)

## Overview

This skill enables Claude Code to generate production-quality terminal user interface applications using the Textual framework. It includes comprehensive documentation, examples, and patterns for building modern TUI applications.

## Features

- **40+ Widgets** - Complete coverage of all Textual widgets with examples
- **Layout System** - Vertical, horizontal, grid, and dock layouts
- **Styling** - Full CSS/TCSS styling guide with themes
- **Reactive Programming** - Patterns for automatic UI updates
- **Background Tasks** - Worker patterns for non-blocking operations
- **Official Docs Integration** - Index with web_fetch URLs for on-demand documentation
- **Example Applications** - Four complete working examples

## Installation

### For Claude Code Users

1. Download `textual-tui.skill` from the [releases](../../releases)
2. Install in Claude Code
3. The skill activates automatically for TUI development

### For Skill Development

```bash
# Clone the repository
git clone https://github.com/yourusername/textual-tui-skill.git
cd textual-tui-skill

# Install dependencies (for testing examples)
pip install textual textual-dev psutil

# Package the skill
python scripts/package.py
```

## Quick Start

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button

class MyApp(App):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Button("Click me!")
        yield Footer()
    
    def on_button_pressed(self) -> None:
        self.notify("Button clicked!")

if __name__ == "__main__":
    MyApp().run()
```

## Documentation

- **[Skill Guide](docs/SKILL-GUIDE.md)** - Complete guide to using the skill
- **[Examples](examples/)** - Working example applications
- **[Contributing](CONTRIBUTING.md)** - How to contribute to the skill

## What's Included

### Core Documentation (skill/SKILL.md)
- Quick start and installation
- Core architecture patterns
- Layout system
- CSS styling guide
- Event handling
- Advanced patterns
- Testing strategies

### Reference Files (skill/references/)
- `widgets.md` - Gallery of 40+ widgets
- `layouts.md` - Layout patterns and recipes
- `styling.md` - Complete TCSS guide
- `official-guides-index.md` - Index of official Textual documentation

### Example Applications (examples/)
- `todo_app.py` - Todo list with state management
- `dashboard_app.py` - System monitor with live updates
- `data_viewer.py` - JSON/CSV file viewer
- `worker_demo.py` - Background task patterns

## Structure

```
textual-tui-skill/
├── skill/                      # Skill source files
│   ├── SKILL.md               # Main skill documentation
│   ├── references/            # Reference documentation
│   │   ├── widgets.md
│   │   ├── layouts.md
│   │   ├── styling.md
│   │   └── official-guides-index.md
│   └── assets/                # Example applications
│       ├── todo_app.py
│       ├── dashboard_app.py
│       ├── data_viewer.py
│       ├── worker_demo.py
│       └── README.md
├── examples/                   # Standalone examples (symlink)
├── docs/                       # Additional documentation
├── scripts/                    # Build and package scripts
│   └── package.py
├── .gitignore
├── LICENSE
├── README.md
└── CONTRIBUTING.md
```

## Example Applications

### Todo List
Full-featured todo application demonstrating input handling, list views, and reactive state.

```bash
python examples/todo_app.py
```

### System Dashboard
Real-time system monitor with CPU/memory charts and metrics.

```bash
python examples/dashboard_app.py
```

### Data Viewer
JSON/CSV file viewer with table and tree views.

```bash
python examples/data_viewer.py
```

### Worker Demo
Background task processing with progress updates and cancellation.

```bash
python examples/worker_demo.py
```

## Development

### Building the Skill

```bash
# From repository root
python scripts/package.py
```

This creates `textual-tui.skill` ready for distribution.

### Testing Examples

```bash
# Install dependencies
pip install textual textual-dev psutil

# Run with hot reload
textual run --dev examples/todo_app.py
```

## Resources

- **Textual Documentation**: https://textual.textualize.io/
- **Textual GitHub**: https://github.com/Textualize/textual

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Version History

**1.0.0** (Current)
- Initial release
- Full widget and layout coverage
- Complete styling guide
- Four example applications
- Official documentation index

---

Built for Claude Code • Powered by Textual
