"""
Todo List Application - Complete Textual TUI Example

A fully functional todo list app demonstrating:
- Input handling and forms
- List view and selection
- State management with reactive attributes
- Custom styling
- Keyboard shortcuts
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, ListView, ListItem, Label, Static
from textual.binding import Binding
from textual.reactive import reactive


class TodoItem(ListItem):
    """A todo list item with completion status."""
    
    def __init__(self, text: str, completed: bool = False) -> None:
        super().__init__()
        self.text = text
        self.completed = completed
        self.update_display()
    
    def update_display(self) -> None:
        """Update the display based on completion status."""
        if self.completed:
            self.add_class("completed")
            prefix = "✓"
        else:
            self.remove_class("completed")
            prefix = "○"
        
        # Clear and re-render
        self._nodes.clear()
        self._nodes.append(Label(f"{prefix} {self.text}"))
    
    def toggle(self) -> None:
        """Toggle completion status."""
        self.completed = not self.completed
        self.update_display()


class TodoApp(App):
    """A todo list application."""
    
    CSS = """
    Screen {
        background: $background;
        layout: vertical;
    }
    
    Header {
        background: $primary;
    }
    
    #main-container {
        height: 1fr;
        padding: 1 2;
    }
    
    #input-container {
        height: auto;
        margin-bottom: 1;
    }
    
    #todo-input {
        width: 1fr;
        margin-right: 1;
        border: solid $accent;
    }
    
    #todo-input:focus {
        border: solid $success;
    }
    
    #add-button {
        min-width: 12;
    }
    
    #todo-list {
        border: solid $primary;
        height: 1fr;
        background: $surface;
    }
    
    #stats {
        height: 3;
        margin-top: 1;
        border: solid $accent;
        padding: 0 2;
        background: $panel;
    }
    
    TodoItem {
        padding: 0 1;
    }
    
    TodoItem:hover {
        background: $boost;
    }
    
    TodoItem.completed {
        color: $text-muted;
        text-style: strike;
    }
    
    .stat {
        margin: 0 2;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+n", "new_todo", "New Todo"),
        Binding("ctrl+d", "delete_todo", "Delete"),
        Binding("space", "toggle_todo", "Toggle"),
        Binding("ctrl+c", "clear_completed", "Clear Completed"),
        ("q", "quit", "Quit"),
    ]
    
    total_count = reactive(0)
    completed_count = reactive(0)
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        
        with Container(id="main-container"):
            with Horizontal(id="input-container"):
                yield Input(
                    placeholder="What needs to be done?",
                    id="todo-input"
                )
                yield Button("Add", variant="primary", id="add-button")
            
            yield ListView(id="todo-list")
            
            with Horizontal(id="stats"):
                yield Static("", id="total-stat", classes="stat")
                yield Static("", id="completed-stat", classes="stat")
                yield Static("", id="remaining-stat", classes="stat")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app."""
        self.query_one("#todo-input").focus()
        self.update_stats()
        
        # Add some example todos
        self.add_todo_item("Learn Textual", False)
        self.add_todo_item("Build amazing TUI apps", False)
        self.add_todo_item("Share with the world", False)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "add-button":
            self.add_todo_from_input()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "todo-input":
            self.add_todo_from_input()
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle todo item selection."""
        if isinstance(event.item, TodoItem):
            event.item.toggle()
            self.update_stats()
    
    def add_todo_from_input(self) -> None:
        """Add a todo from the input field."""
        todo_input = self.query_one("#todo-input", Input)
        text = todo_input.value.strip()
        
        if text:
            self.add_todo_item(text)
            todo_input.value = ""
            todo_input.focus()
    
    def add_todo_item(self, text: str, completed: bool = False) -> None:
        """Add a todo item to the list."""
        list_view = self.query_one("#todo-list", ListView)
        todo = TodoItem(text, completed)
        list_view.append(todo)
        self.update_stats()
    
    def action_new_todo(self) -> None:
        """Focus the input for a new todo."""
        self.query_one("#todo-input").focus()
    
    def action_delete_todo(self) -> None:
        """Delete the selected todo."""
        list_view = self.query_one("#todo-list", ListView)
        if list_view.highlighted_child:
            list_view.highlighted_child.remove()
            self.update_stats()
    
    def action_toggle_todo(self) -> None:
        """Toggle the selected todo."""
        list_view = self.query_one("#todo-list", ListView)
        if isinstance(list_view.highlighted_child, TodoItem):
            list_view.highlighted_child.toggle()
            self.update_stats()
    
    def action_clear_completed(self) -> None:
        """Clear all completed todos."""
        list_view = self.query_one("#todo-list", ListView)
        for item in list_view.query(TodoItem):
            if item.completed:
                item.remove()
        self.update_stats()
    
    def update_stats(self) -> None:
        """Update the statistics display."""
        list_view = self.query_one("#todo-list", ListView)
        todos = list(list_view.query(TodoItem))
        
        total = len(todos)
        completed = sum(1 for t in todos if t.completed)
        remaining = total - completed
        
        self.total_count = total
        self.completed_count = completed
        
        self.query_one("#total-stat", Static).update(f"Total: {total}")
        self.query_one("#completed-stat", Static).update(f"Completed: {completed}")
        self.query_one("#remaining-stat", Static).update(f"Remaining: {remaining}")


if __name__ == "__main__":
    app = TodoApp()
    app.run()
