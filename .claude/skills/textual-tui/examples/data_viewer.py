"""
Data Viewer Application - Textual TUI Example

Demonstrates:
- File browser and selection
- DataTable for displaying tabular data
- Tree for displaying hierarchical data
- Modal screens for dialogs
- File loading and parsing
- Search and filter functionality
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, DirectoryTree, DataTable, Tree, Static,
    Button, Input, TabbedContent, TabPane
)
from textual.screen import ModalScreen
from textual.binding import Binding
import json
import csv
from pathlib import Path


class ErrorDialog(ModalScreen[bool]):
    """Modal dialog for displaying errors."""
    
    DEFAULT_CSS = """
    ErrorDialog {
        align: center middle;
    }
    
    #error-dialog {
        width: 60;
        height: 11;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    
    #error-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    
    #error-message {
        margin-bottom: 1;
    }
    """
    
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.title = title
        self.message = message
    
    def compose(self) -> ComposeResult:
        with Container(id="error-dialog"):
            yield Static(self.title, id="error-title")
            yield Static(self.message, id="error-message")
            yield Button("OK", variant="error", id="ok")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)


class DataViewer(App):
    """A data viewer for JSON and CSV files."""
    
    CSS = """
    Screen {
        background: $background;
        layout: horizontal;
    }
    
    Header {
        background: $primary;
    }
    
    #sidebar {
        width: 35;
        border-right: solid $accent;
        background: $panel;
    }
    
    #file-tree {
        height: 1fr;
    }
    
    #main-content {
        width: 1fr;
        padding: 1 2;
    }
    
    #toolbar {
        height: auto;
        margin-bottom: 1;
    }
    
    #search-input {
        width: 1fr;
        margin-right: 1;
    }
    
    #content-tabs {
        height: 1fr;
    }
    
    DataTable {
        height: 100%;
    }
    
    Tree {
        height: 100%;
    }
    
    #info-panel {
        border: solid $primary;
        padding: 1;
        background: $surface;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+o", "open_file", "Open File"),
        Binding("ctrl+f", "focus_search", "Search"),
        ("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        
        with Container(id="sidebar"):
            yield Static("📁 File Browser", id="sidebar-title")
            yield DirectoryTree(str(Path.home()), id="file-tree")
        
        with Vertical(id="main-content"):
            with Horizontal(id="toolbar"):
                yield Input(placeholder="Search...", id="search-input")
                yield Button("Clear", id="clear-button")
            
            with TabbedContent(id="content-tabs"):
                with TabPane("Table View", id="table-tab"):
                    yield DataTable(id="data-table", cursor_type="row")
                
                with TabPane("Tree View", id="tree-tab"):
                    yield Tree("Data", id="data-tree")
                
                with TabPane("Info", id="info-tab"):
                    yield Static("No file loaded", id="info-panel")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app."""
        table = self.query_one("#data-table", DataTable)
        table.show_header = True
        table.zebra_stripes = True
    
    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection from the tree."""
        file_path = event.path
        if file_path.suffix.lower() in ['.json', '.csv']:
            self.load_file(file_path)
        else:
            self.notify("Only JSON and CSV files are supported", severity="warning")
    
    def load_file(self, file_path: Path) -> None:
        """Load and display a data file."""
        try:
            if file_path.suffix.lower() == '.json':
                self.load_json(file_path)
            elif file_path.suffix.lower() == '.csv':
                self.load_csv(file_path)
            
            self.notify(f"Loaded: {file_path.name}", severity="information")
            
        except Exception as e:
            self.push_screen(
                ErrorDialog("Error Loading File", f"Failed to load {file_path.name}:\n{str(e)}")
            )
    
    def load_json(self, file_path: Path) -> None:
        """Load a JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Update info panel
        info = self.query_one("#info-panel", Static)
        info.update(f"File: {file_path.name}\nType: JSON\nSize: {file_path.stat().st_size} bytes")
        
        # Update tree view
        tree = self.query_one("#data-tree", Tree)
        tree.clear()
        tree.root.label = file_path.name
        self._build_json_tree(tree.root, data)
        
        # Update table view (if data is a list of dicts)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            self._populate_table_from_list(data)
        else:
            table = self.query_one("#data-table", DataTable)
            table.clear(columns=True)
            self.notify("JSON structure not suitable for table view", severity="warning")
    
    def load_csv(self, file_path: Path) -> None:
        """Load a CSV file."""
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        # Update info panel
        info = self.query_one("#info-panel", Static)
        info.update(
            f"File: {file_path.name}\n"
            f"Type: CSV\n"
            f"Rows: {len(data)}\n"
            f"Columns: {len(data[0]) if data else 0}"
        )
        
        # Update table view
        self._populate_table_from_list(data)
        
        # Update tree view
        tree = self.query_one("#data-tree", Tree)
        tree.clear()
        tree.root.label = file_path.name
        for i, row in enumerate(data[:100]):  # Limit to 100 for performance
            row_node = tree.root.add(f"Row {i+1}")
            for key, value in row.items():
                row_node.add_leaf(f"{key}: {value}")
    
    def _populate_table_from_list(self, data: list) -> None:
        """Populate the DataTable from a list of dicts."""
        if not data:
            return
        
        table = self.query_one("#data-table", DataTable)
        table.clear(columns=True)
        
        # Add columns
        columns = list(data[0].keys())
        table.add_columns(*columns)
        
        # Add rows
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in columns])
    
    def _build_json_tree(self, node, data, max_depth: int = 10, depth: int = 0) -> None:
        """Recursively build a tree from JSON data."""
        if depth >= max_depth:
            node.add_leaf("... (max depth reached)")
            return
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    child = node.add(f"📂 {key}")
                    self._build_json_tree(child, value, max_depth, depth + 1)
                else:
                    node.add_leaf(f"{key}: {value}")
        
        elif isinstance(data, list):
            for i, item in enumerate(data[:50]):  # Limit to 50 items for performance
                if isinstance(item, (dict, list)):
                    child = node.add(f"[{i}]")
                    self._build_json_tree(child, item, max_depth, depth + 1)
                else:
                    node.add_leaf(f"[{i}]: {item}")
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            search_term = event.value.lower()
            if search_term:
                self.filter_table(search_term)
    
    def filter_table(self, search_term: str) -> None:
        """Filter table rows based on search term."""
        table = self.query_one("#data-table", DataTable)
        # Note: This is a simple example. Real implementation would need
        # to store original data and rebuild filtered rows
        pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "clear-button":
            search_input = self.query_one("#search-input", Input)
            search_input.value = ""
    
    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()
    
    def action_open_file(self) -> None:
        """Focus the file tree."""
        self.query_one("#file-tree", DirectoryTree).focus()


if __name__ == "__main__":
    app = DataViewer()
    app.run()
