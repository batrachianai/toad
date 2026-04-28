# Textual TUI Skill for Claude Code

**Version 1.0.0** - Active development

Build modern, interactive terminal user interfaces using Textual.

## Contents

### SKILL.md (Main Documentation)
- Quick start guide with basic app structure
- Core architecture (app lifecycle, message passing, reactive programming)
- Layout system (vertical, horizontal, grid, dock)
- Styling with CSS
- Common widgets overview
- Event handling patterns
- **Advanced patterns including workers for background tasks** ⭐
  - Worker basics and usage
  - Progress updates from workers
  - Worker cancellation and lifecycle
  - Thread vs async workers
  - Error handling in workers
  - Multiple concurrent workers
- Testing with pytest
- Best practices
- Development tools

### Reference Documentation
- **widgets.md** - Comprehensive widget gallery with examples for all built-in widgets
- **layouts.md** - Common layout patterns and recipes (split screens, dashboards, grids)
- **styling.md** - Complete TCSS (Textual CSS) guide with colors, typography, borders, and themes
- **official-guides-index.md** - Complete index of all official Textual documentation guides with URLs for on-demand fetching via web_fetch ⭐

### Example Applications
- **todo_app.py** - Full todo list application with state management
- **dashboard_app.py** - Real-time system monitor with charts and metrics
- **data_viewer.py** - JSON/CSV viewer with file browser and multiple views
- **worker_demo.py** - Comprehensive worker patterns (single & multiple workers) ⭐
- **README.md** - Guide to the example applications

## Installation

Download the `textual-tui.skill` file and install it in Claude Code.

## Using with Claude Code

Once installed, Claude Code will automatically use this skill when you:
- Ask to create a TUI or terminal application
- Request a command-line interface
- Build dashboard or monitoring tools
- Create data viewers or interactive terminal tools

### Example Prompts

**Basic TUI:**
```
Create a simple Textual TUI with a header, input field, and button
```

**Dashboard:**
```
Build a system monitoring dashboard using Textual with CPU and memory charts
```

**Data Application:**
```
Create a log viewer TUI that can load and filter log files
```

**Custom Widget:**
```
Make a reusable status card widget in Textual that shows title, value, and a small chart
```

## Key Features

- ✅ Modern async/await architecture
- ✅ Rich widget library (40+ widgets)
- ✅ Flexible CSS-based styling
- ✅ Reactive programming for live updates
- ✅ **Worker system for background tasks** ⭐
- ✅ **Complete official documentation index with on-demand fetching** ⭐
- ✅ Mouse and keyboard input
- ✅ Hot reload during development
- ✅ Testing support with pytest
- ✅ Cross-platform (Linux, macOS, Windows)

## Workers for Background Tasks

The skill covers worker patterns for non-blocking operations:

- When to use workers (network, file I/O, CPU-intensive tasks)
- Async vs thread workers
- Progress updates and UI synchronization
- Worker cancellation and error handling
- Multiple concurrent workers

See `worker_demo.py` for comprehensive examples.

## Official Documentation Index

The skill includes an index of all official Textual guides with URLs for on-demand fetching via `web_fetch`:

- Complete guide listing (30+ topics)
- Direct widget documentation links (40+ widgets)
- Organized by category (Getting Started, Core Concepts, Advanced Features, etc.)

Use built-in skill knowledge for common patterns. Fetch official docs for:
- Latest/updated information
- Detailed API documentation
- Specific widget details
- Edge cases and advanced topics

Example:
```python
web_fetch("https://textual.textualize.io/guide/animation/")
web_fetch("https://textual.textualize.io/widgets/data_table/")
```

See `references/official-guides-index.md` for the complete index.

## Quick Example

The skill includes patterns for common tasks:

**Basic App:**
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

**With Background Worker:**
```python
from textual.app import App, ComposeResult
from textual.widgets import Button, ProgressBar
import asyncio

class MyApp(App):
    def compose(self) -> ComposeResult:
        yield Button("Process Data")
        yield ProgressBar(total=100, id="progress")
    
    def on_button_pressed(self) -> None:
        # Start background task - NEVER blocks UI
        self.run_worker(self.process_data())
    
    async def process_data(self) -> None:
        progress = self.query_one(ProgressBar)
        for i in range(100):
            await asyncio.sleep(0.05)  # Simulated work
            progress.update(progress=i + 1)

if __name__ == "__main__":
    MyApp().run()
```

## Benefits

- Generate production-quality TUI applications
- Follow Textual best practices automatically
- Implement proper architecture patterns
- Handle workers correctly for non-blocking operations
- Create well-styled, professional interfaces
- Avoid common pitfalls (UI blocking, thread safety)

## Development Workflow

Claude Code can help you:
1. Generate initial app structure
2. Add and configure widgets
3. Style with TCSS
4. Implement event handlers
5. Test with the Textual devtools
6. Package and deploy

## Resources

- Textual Documentation: https://textual.textualize.io/
- GitHub: https://github.com/Textualize/textual
