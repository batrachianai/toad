# Textual Widget Gallery

Comprehensive examples of all built-in Textual widgets.

## Basic Widgets

### Label

Display static or dynamic text:
```python
from textual.widgets import Label

# Simple label
yield Label("Hello World")

# With styling
yield Label("Important!", classes="highlight")

# With markup
yield Label("[bold]Bold[/] and [italic]italic[/]")

# Dynamic label with reactive
class DynamicLabel(Widget):
    message = reactive("Initial")
    
    def compose(self) -> ComposeResult:
        yield Label(self.message)
```

### Static

Display Rich renderables:
```python
from textual.widgets import Static
from rich.table import Table

table = Table()
table.add_column("Name")
table.add_column("Value")
table.add_row("Alpha", "100")

yield Static(table)
```

### Button

Interactive buttons with variants:
```python
from textual.widgets import Button

# Standard button
yield Button("Click me", id="action")

# Button variants
yield Button("Primary", variant="primary")
yield Button("Success", variant="success")
yield Button("Warning", variant="warning")
yield Button("Error", variant="error")

# Disabled button
yield Button("Disabled", disabled=True)

# Handle click
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "action":
        self.action_perform()
```

## Input Widgets

### Input

Single-line text input:
```python
from textual.widgets import Input

# Basic input
yield Input(placeholder="Enter text...", id="name")

# Password input
yield Input(placeholder="Password", password=True, id="pass")

# Validated input
yield Input(
    placeholder="Email",
    validators=[Email()],  # Built-in validators
    id="email"
)

# Handle submission
def on_input_submitted(self, event: Input.Submitted) -> None:
    value = event.value
    self.log(f"Submitted: {value}")

# Handle changes
def on_input_changed(self, event: Input.Changed) -> None:
    self.validate_live(event.value)
```

### TextArea

Multi-line text editor:
```python
from textual.widgets import TextArea

# Basic text area
yield TextArea(id="editor")

# With initial content
yield TextArea(
    text="Initial content\nLine 2",
    language="python",  # Syntax highlighting
    theme="monokai",
    id="code"
)

# Handle changes
def on_text_area_changed(self, event: TextArea.Changed) -> None:
    content = event.text_area.text
```

### Select

Dropdown selection:
```python
from textual.widgets import Select

# Basic select
options = [
    ("Option A", "a"),
    ("Option B", "b"),
    ("Option C", "c"),
]
yield Select(options=options, prompt="Choose...", id="choice")

# Handle selection
def on_select_changed(self, event: Select.Changed) -> None:
    value = event.value  # "a", "b", or "c"
    self.log(f"Selected: {value}")
```

### Checkbox

Boolean input:
```python
from textual.widgets import Checkbox

yield Checkbox("Enable feature", id="feature")

# Handle changes
def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
    is_checked = event.value
    self.toggle_feature(is_checked)
```

### RadioButton and RadioSet

Mutually exclusive options:
```python
from textual.widgets import RadioButton, RadioSet

with RadioSet(id="size"):
    yield RadioButton("Small")
    yield RadioButton("Medium", value=True)  # Default
    yield RadioButton("Large")

# Handle selection
def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
    selected = event.pressed.label
    self.log(f"Size: {selected}")
```

### Switch

Toggle switch:
```python
from textual.widgets import Switch

yield Switch(value=True, id="notifications")

# Handle toggle
def on_switch_changed(self, event: Switch.Changed) -> None:
    is_on = event.value
    self.toggle_notifications(is_on)
```

## Data Display Widgets

### DataTable

Tabular data with selection and sorting:
```python
from textual.widgets import DataTable

table = DataTable(id="users")

# Add columns
table.add_columns("Name", "Age", "City")

# Add rows (returns row key)
row_key = table.add_row("Alice", 30, "NYC")
table.add_row("Bob", 25, "LA")

# Cursor control
table.cursor_type = "row"  # or "cell", "column", "none"

# Handle selection
def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    row_key = event.row_key
    row_data = event.row
    self.log(f"Selected: {row_data}")

# Update cells
table.update_cell(row_key, "Age", 31)

# Remove rows
table.remove_row(row_key)

# Sort
table.sort("Age", reverse=True)
```

### Tree

Hierarchical data:
```python
from textual.widgets import Tree

tree = Tree("Root", id="file-tree")

# Add nodes
root = tree.root
folder = root.add("Folder", expand=True)
folder.add_leaf("file1.txt")
folder.add_leaf("file2.txt")

subfolder = folder.add("Subfolder")
subfolder.add_leaf("nested.txt")

# Handle selection
def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
    node = event.node
    self.log(f"Selected: {node.label}")

# Expand/collapse
def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
    # Load children dynamically
    node = event.node
    self.load_children(node)
```

### ListView

List with selection:
```python
from textual.widgets import ListView, ListItem, Label

list_view = ListView(id="menu")

# Add items
list_view.append(ListItem(Label("Item 1")))
list_view.append(ListItem(Label("Item 2")))
list_view.append(ListItem(Label("Item 3")))

# Handle selection
def on_list_view_selected(self, event: ListView.Selected) -> None:
    item = event.item
    self.log(f"Selected: {item}")
```

### Log / RichLog

Scrollable log output:
```python
from textual.widgets import Log, RichLog

# Simple log
log = Log(id="output", auto_scroll=True)
log.write_line("Log entry")
log.write_lines(["Line 1", "Line 2"])

# Rich log with markup
rich_log = RichLog(id="rich-output", highlight=True)
rich_log.write("[bold green]Success![/]")
rich_log.write("[red]Error occurred[/]")

# Clear log
log.clear()
```

### ProgressBar

Progress indicator:
```python
from textual.widgets import ProgressBar

# Determinate progress
progress = ProgressBar(total=100, id="progress")
progress.advance(25)  # 25%
progress.update(progress=50)  # 50%

# Indeterminate progress
progress = ProgressBar(total=None)  # Animated spinner
```

### Sparkline

Inline data visualization:
```python
from textual.widgets import Sparkline

data = [1, 2, 3, 5, 8, 13, 21]
yield Sparkline(data, id="chart")

# Update data
sparkline = self.query_one(Sparkline)
sparkline.data = new_data
```

## Navigation Widgets

### Header / Footer

Standard app chrome:
```python
from textual.widgets import Header, Footer

def compose(self) -> ComposeResult:
    yield Header(show_clock=True)
    # ... content ...
    yield Footer()
```

### TabbedContent / TabPane

Tabbed interface:
```python
from textual.widgets import TabbedContent, TabPane

with TabbedContent(id="tabs"):
    with TabPane("Tab 1", id="tab1"):
        yield Label("Content 1")
    with TabPane("Tab 2", id="tab2"):
        yield Label("Content 2")
    with TabPane("Tab 3", id="tab3"):
        yield Label("Content 3")

# Handle tab changes
def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
    tab_id = event.pane.id
    self.log(f"Switched to {tab_id}")
```

### ContentSwitcher

Programmatically switch content:
```python
from textual.widgets import ContentSwitcher

with ContentSwitcher(initial="view1", id="switcher"):
    yield Label("View 1", id="view1")
    yield Label("View 2", id="view2")
    yield Label("View 3", id="view3")

# Switch views
def switch_view(self, view_id: str) -> None:
    switcher = self.query_one(ContentSwitcher)
    switcher.current = view_id
```

### OptionList

Selectable list of options:
```python
from textual.widgets import OptionList
from textual.widgets.option_list import Option

option_list = OptionList(
    Option("Option 1", id="opt1"),
    Option("Option 2", id="opt2"),
    Option("Option 3", id="opt3"),
)

# Handle selection
def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
    option_id = event.option.id
    self.log(f"Selected: {option_id}")
```

## Loading Widgets

### LoadingIndicator

Spinning loader:
```python
from textual.widgets import LoadingIndicator

# Show while loading
with LoadingIndicator():
    # Content loading...
    pass

# Or standalone
yield LoadingIndicator(id="loader")
```

### Placeholder

Development placeholder:
```python
from textual.widgets import Placeholder

# Quick placeholder during development
yield Placeholder("Chart goes here")
yield Placeholder(label="[b]User Profile[/]", variant="text")
```

## Special Widgets

### Markdown

Render markdown:
```python
from textual.widgets import Markdown

markdown_content = """
# Title
This is **bold** and *italic*.

- Item 1
- Item 2

```python
code block
```
"""

yield Markdown(markdown_content, id="docs")
```

### DirectoryTree

File system browser:
```python
from textual.widgets import DirectoryTree

tree = DirectoryTree("/home/user", id="files")

# Handle file selection
def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
    file_path = event.path
    self.open_file(file_path)
```

## Custom Widget Example

Create composite widgets:
```python
from textual.widget import Widget
from textual.containers import Horizontal, Vertical

class UserCard(Widget):
    """Display user information."""
    
    def __init__(self, name: str, email: str, role: str) -> None:
        super().__init__()
        self.name = name
        self.email = email
        self.role = role
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="card"):
            yield Label(self.name, classes="name")
            yield Label(self.email, classes="email")
            with Horizontal():
                yield Label(f"Role: {self.role}", classes="role")
                yield Button("Edit", variant="primary")
    
    DEFAULT_CSS = """
    UserCard {
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    UserCard .name {
        text-style: bold;
        color: $text;
    }
    
    UserCard .email {
        color: $text-muted;
    }
    """

# Use the widget
yield UserCard("Alice Smith", "alice@example.com", "Admin")
```

## Widget Composition Patterns

### Form Layout
```python
def compose(self) -> ComposeResult:
    with Container(id="form"):
        yield Label("Registration Form")
        yield Input(placeholder="Name", id="name")
        yield Input(placeholder="Email", id="email")
        yield Input(placeholder="Password", password=True, id="pass")
        with Horizontal():
            yield Button("Submit", variant="primary")
            yield Button("Cancel")
```

### Dashboard Layout
```python
def compose(self) -> ComposeResult:
    yield Header()
    with Container(id="dashboard"):
        with Horizontal(classes="stats"):
            yield Static("[b]Users:[/] 1,234", classes="stat")
            yield Static("[b]Active:[/] 567", classes="stat")
            yield Static("[b]Revenue:[/] $12K", classes="stat")
        with Horizontal(classes="content"):
            with Vertical(id="sidebar"):
                yield Label("Menu")
                yield Button("Dashboard")
                yield Button("Users")
                yield Button("Settings")
            with Container(id="main"):
                yield DataTable()
        yield Footer()
```
