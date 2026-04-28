---
name: textual-tui
description: Build modern, interactive terminal user interfaces with Textual. Use when creating command-line applications, dashboard tools, monitoring interfaces, data viewers, or any terminal-based UI. Covers architecture, widgets, layouts, styling, event handling, reactive programming, workers for background tasks, and testing patterns.
---

# Textual TUI Development

Build production-quality terminal user interfaces using Textual, a modern Python framework for creating interactive TUI applications.

## Quick Start

Install Textual:
```bash
pip install textual textual-dev
```

Basic app structure:
```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button

class MyApp(App):
    """A simple Textual app."""
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Button("Click me!", id="click")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        self.exit()

if __name__ == "__main__":
    app = MyApp()
    app.run()
```

Run with hot reload during development:
```bash
textual run --dev your_app.py
```

Use the Textual console for debugging:
```bash
textual console
```

## Core Architecture

### App Lifecycle

1. **Initialization**: Create App instance with config
2. **Composition**: Build widget tree via `compose()` method
3. **Mounting**: Widgets mounted to DOM
4. **Running**: Event loop processes messages and renders UI
5. **Shutdown**: Cleanup and exit

### Message Passing System

Textual uses an async message queue for all interactions:

```python
from textual.message import Message

class CustomMessage(Message):
    """Custom message with data."""
    def __init__(self, value: int) -> None:
        self.value = value
        super().__init__()

class MyWidget(Widget):
    def on_click(self) -> None:
        # Post message to parent
        self.post_message(CustomMessage(42))

class MyApp(App):
    def on_custom_message(self, message: CustomMessage) -> None:
        # Handle message with naming convention: on_{message_name}
        self.log(f"Received: {message.value}")
```

### Reactive Programming

Use reactive attributes for automatic UI updates:

```python
from textual.reactive import reactive

class Counter(Widget):
    count = reactive(0)  # Reactive attribute
    
    def watch_count(self, new_value: int) -> None:
        """Called automatically when count changes."""
        self.refresh()
    
    def increment(self) -> None:
        self.count += 1  # Triggers watch_count
```

## Layout System

### Container Layouts

Textual provides flexible layout options:

**Vertical Layout (default)**:
```python
def compose(self) -> ComposeResult:
    yield Label("Top")
    yield Label("Bottom")
```

**Horizontal Layout**:
```python
class MyApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }
    """
```

**Grid Layout**:
```python
class MyApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;  /* 3 columns, 2 rows */
    }
    """
```

### Sizing and Positioning

Control widget dimensions:
```python
class MyApp(App):
    CSS = """
    #sidebar {
        width: 30;      /* Fixed width */
        height: 100%;   /* Full height */
    }
    
    #content {
        width: 1fr;     /* Remaining space */
    }
    
    .compact {
        height: auto;   /* Size to content */
    }
    """
```

## Styling with CSS

Textual uses CSS-like syntax for styling.

### Inline Styles

```python
class StyledWidget(Widget):
    DEFAULT_CSS = """
    StyledWidget {
        background: $primary;
        color: $text;
        border: solid $accent;
        padding: 1 2;
        margin: 1;
    }
    """
```

### External CSS Files

```python
class MyApp(App):
    CSS_PATH = "app.tcss"  # Load from file
```

### Color System

Use Textual's semantic colors:
```css
.error { background: $error; }
.success { background: $success; }
.warning { background: $warning; }
.primary { background: $primary; }
```

Or define custom colors:
```css
.custom {
    background: #1e3a8a;
    color: rgb(255, 255, 255);
}
```

## Common Widgets

### Input and Forms

```python
from textual.widgets import Input, Button, Select
from textual.containers import Container

def compose(self) -> ComposeResult:
    with Container(id="form"):
        yield Input(placeholder="Enter name", id="name")
        yield Select(options=[("A", 1), ("B", 2)], id="choice")
        yield Button("Submit", variant="primary")

def on_button_pressed(self, event: Button.Pressed) -> None:
    name = self.query_one("#name", Input).value
    choice = self.query_one("#choice", Select).value
```

### Data Display

```python
from textual.widgets import DataTable, Tree, Log

# DataTable for tabular data
table = DataTable()
table.add_columns("Name", "Age", "City")
table.add_row("Alice", 30, "NYC")

# Tree for hierarchical data
tree = Tree("Root")
tree.root.add("Child 1")
tree.root.add("Child 2")

# Log for streaming output
log = Log(auto_scroll=True)
log.write_line("Log entry")
```

### Containers and Layout

```python
from textual.containers import (
    Container, Horizontal, Vertical,
    Grid, ScrollableContainer
)

def compose(self) -> ComposeResult:
    with Vertical():
        yield Header()
        with Horizontal():
            with Container(id="sidebar"):
                yield Label("Menu")
            with ScrollableContainer(id="content"):
                yield Label("Content...")
        yield Footer()
```

## Event Handling

### Built-in Events

```python
from textual.events import Key, Click, Mount

def on_mount(self) -> None:
    """Called when widget is mounted."""
    self.log("Widget mounted!")

def on_key(self, event: Key) -> None:
    """Handle all key presses."""
    if event.key == "q":
        self.app.exit()

def on_click(self, event: Click) -> None:
    """Handle mouse clicks."""
    self.log(f"Clicked at {event.x}, {event.y}")
```

### Widget-Specific Handlers

```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    """Handle input submission."""
    self.query_one(Log).write(event.value)

def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    """Handle table row selection."""
    row_key = event.row_key
```

### Keyboard Bindings

```python
class MyApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("ctrl+s", "save", "Save"),
    ]
    
    def action_quit(self) -> None:
        self.exit()
    
    def action_toggle_dark(self) -> None:
        self.dark = not self.dark
```

## Advanced Patterns

### Custom Widgets

Create reusable components:
```python
from textual.widget import Widget
from textual.widgets import Label, Button

class StatusCard(Widget):
    """A card showing status info."""
    
    def __init__(self, title: str, status: str) -> None:
        super().__init__()
        self.title = title
        self.status = status
    
    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="title")
        yield Label(self.status, classes="status")
```

### Workers and Background Tasks

CRITICAL: Use workers for any long-running operations to prevent blocking the UI. The event loop must remain responsive.

#### Basic Worker Usage

Run tasks in background threads:
```python
from textual.worker import Worker, WorkerState

class MyApp(App):
    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Start background task
        self.run_worker(self.process_data(), exclusive=True)
    
    async def process_data(self) -> str:
        """Long-running task."""
        # Simulate work
        await asyncio.sleep(5)
        return "Processing complete"
```

#### Worker with Progress Updates

Update UI during processing:
```python
from textual.widgets import ProgressBar

class MyApp(App):
    def compose(self) -> ComposeResult:
        yield ProgressBar(total=100, id="progress")
    
    def on_mount(self) -> None:
        self.run_worker(self.long_task())
    
    async def long_task(self) -> None:
        """Task with progress updates."""
        progress = self.query_one(ProgressBar)
        
        for i in range(100):
            await asyncio.sleep(0.1)
            progress.update(progress=i + 1)
            # Use call_from_thread for thread safety
            self.call_from_thread(progress.update, progress=i + 1)
```

#### Worker Communication Patterns

Use `call_from_thread` for thread-safe UI updates:
```python
import time
from threading import Thread

class MyApp(App):
    def on_mount(self) -> None:
        self.run_worker(self.fetch_data(), thread=True)
    
    def fetch_data(self) -> None:
        """CPU-bound task in thread."""
        # Blocking operation
        result = expensive_computation()
        
        # Update UI safely from thread
        self.call_from_thread(self.display_result, result)
    
    def display_result(self, result: str) -> None:
        """Called on main thread."""
        self.query_one("#output").update(result)
```

#### Worker Cancellation

Cancel workers when no longer needed:
```python
class MyApp(App):
    worker: Worker | None = None
    
    def start_task(self) -> None:
        # Store worker reference
        self.worker = self.run_worker(self.long_task())
    
    def cancel_task(self) -> None:
        # Cancel running worker
        if self.worker and not self.worker.is_finished:
            self.worker.cancel()
            self.notify("Task cancelled")
    
    async def long_task(self) -> None:
        for i in range(1000):
            await asyncio.sleep(0.1)
            # Check if cancelled
            if self.worker.is_cancelled:
                return
```

#### Worker Error Handling

Handle worker failures gracefully:
```python
class MyApp(App):
    def on_mount(self) -> None:
        worker = self.run_worker(self.risky_task())
        worker.name = "data_processor"  # Name for debugging
    
    async def risky_task(self) -> str:
        """Task that might fail."""
        try:
            result = await fetch_from_api()
            return result
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            raise
    
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.ERROR:
            self.log.error(f"Worker failed: {event.worker.name}")
        elif event.state == WorkerState.SUCCESS:
            self.log.info(f"Worker completed: {event.worker.name}")
```

#### Multiple Workers

Manage concurrent workers:
```python
class MyApp(App):
    def on_mount(self) -> None:
        # Run multiple workers concurrently
        self.run_worker(self.task_one(), name="task1", group="processing")
        self.run_worker(self.task_two(), name="task2", group="processing")
        self.run_worker(self.task_three(), name="task3", group="processing")
    
    async def task_one(self) -> None:
        await asyncio.sleep(2)
        self.notify("Task 1 complete")
    
    async def task_two(self) -> None:
        await asyncio.sleep(3)
        self.notify("Task 2 complete")
    
    async def task_three(self) -> None:
        await asyncio.sleep(1)
        self.notify("Task 3 complete")
    
    def cancel_all_tasks(self) -> None:
        """Cancel all workers in a group."""
        for worker in self.workers:
            if worker.group == "processing":
                worker.cancel()
```

#### Thread vs Process Workers

Choose the right worker type:
```python
class MyApp(App):
    def on_mount(self) -> None:
        # Async task (default) - for I/O bound operations
        self.run_worker(self.fetch_data())
        
        # Thread worker - for CPU-bound tasks
        self.run_worker(self.process_data(), thread=True)
    
    async def fetch_data(self) -> str:
        """I/O bound: use async."""
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com")
            return response.text
    
    def process_data(self) -> str:
        """CPU bound: use thread."""
        # Heavy computation
        result = [i**2 for i in range(1000000)]
        return str(sum(result))
```

#### Worker Best Practices

1. **Always use workers for**:
   - Network requests
   - File I/O
   - Database queries
   - CPU-intensive computations
   - Anything taking > 100ms

2. **Worker patterns**:
   - Use `exclusive=True` to prevent duplicate workers
   - Name workers for easier debugging
   - Group related workers for batch cancellation
   - Always handle worker errors

3. **Thread safety**:
   - Use `call_from_thread()` for UI updates from threads
   - Never modify widgets directly from threads
   - Use locks for shared mutable state

4. **Cancellation**:
   - Store worker references if you need to cancel
   - Check `worker.is_cancelled` in long loops
   - Clean up resources in finally blocks

### Modal Dialogs

```python
from textual.screen import ModalScreen

class ConfirmDialog(ModalScreen[bool]):
    """Modal confirmation dialog."""
    
    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("Are you sure?")
            with Horizontal():
                yield Button("Yes", variant="primary", id="yes")
                yield Button("No", variant="error", id="no")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

# Use in app
async def confirm_action(self) -> None:
    result = await self.push_screen_wait(ConfirmDialog())
    if result:
        self.log("Confirmed!")
```

### Screens and Navigation

```python
from textual.screen import Screen

class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Button("Go to Settings")
        yield Footer()
    
    def on_button_pressed(self) -> None:
        self.app.push_screen("settings")

class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Label("Settings")
        yield Button("Back")
    
    def on_button_pressed(self) -> None:
        self.app.pop_screen()

class MyApp(App):
    SCREENS = {
        "main": MainScreen(),
        "settings": SettingsScreen(),
    }
```

## Testing

Test Textual apps with pytest and the Pilot API:

```python
import pytest
from textual.pilot import Pilot
from my_app import MyApp

@pytest.mark.asyncio
async def test_app_starts():
    app = MyApp()
    async with app.run_test() as pilot:
        assert app.screen is not None

@pytest.mark.asyncio
async def test_button_click():
    app = MyApp()
    async with app.run_test() as pilot:
        await pilot.click("#my-button")
        # Assert expected state changes
        
@pytest.mark.asyncio
async def test_keyboard_input():
    app = MyApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
        # Verify app exited or state changed
```

## Best Practices

### Performance

- Use `Lazy` for expensive widgets loaded on demand
- Implement efficient `render()` methods, avoid unnecessary work
- Use reactive attributes sparingly for truly dynamic values
- Batch UI updates when processing multiple changes

### State Management

- Keep app state in the App instance for global access
- Use reactive attributes for UI-bound state
- Store complex state in dedicated data models
- Avoid deeply nested widget communication

### Error Handling

```python
from textual.widgets import RichLog

def compose(self) -> ComposeResult:
    yield RichLog(id="log")

async def action_risky_operation(self) -> None:
    try:
        result = await some_async_operation()
        self.notify("Success!", severity="information")
    except Exception as e:
        self.notify(f"Error: {e}", severity="error")
        self.query_one(RichLog).write(f"[red]Error:[/] {e}")
```

### Accessibility

- Always provide keyboard navigation
- Use semantic widget names and IDs
- Include ARIA-like descriptions where appropriate
- Test with screen reader compatibility in mind

## Development Tools

### Textual Console

Debug running apps:
```bash
# Terminal 1: Run console
textual console

# Terminal 2: Run app with console enabled
textual run --dev app.py
```

App code to enable console:
```python
self.log("Debug message")  # Appears in console
self.log.info("Info level")
self.log.error("Error level")
```

### Textual Devtools

Use the devtools for live inspection:
```bash
pip install textual-dev
textual run --dev app.py  # Enables hot reload
```

## References

- **Widget Gallery**: See references/widgets.md for comprehensive widget examples
- **Layout Patterns**: See references/layouts.md for common layout recipes
- **Styling Guide**: See references/styling.md for CSS patterns and themes
- **Official Guides Index**: See references/official-guides-index.md for URLs to all official Textual documentation guides (use web_fetch for detailed information on-demand)
- **Example Apps**: See assets/ for complete example applications

## Common Pitfalls

1. **Forgetting async/await**: Many Textual methods are async, always await them
2. **Blocking the event loop**: CRITICAL - Use `run_worker()` for long-running tasks (network, I/O, heavy computation). Never use `time.sleep()` or blocking operations in the main thread
3. **Incorrect message handling**: Method names must match `on_{message_name}` pattern
4. **CSS specificity issues**: Use IDs and classes appropriately for targeted styling
5. **Not using query methods**: Use `query_one()` and `query()` instead of manual traversal
6. **Thread safety violations**: Never modify widgets directly from worker threads - use `call_from_thread()`
7. **Not cancelling workers**: Workers continue running even when screens close - always cancel or store references
8. **Using time.sleep in async**: Use `await asyncio.sleep()` instead of `time.sleep()` in async functions
9. **Not handling worker errors**: Workers can fail silently - always implement error handling
10. **Wrong worker type**: Use async workers for I/O, thread workers for CPU-bound tasks
