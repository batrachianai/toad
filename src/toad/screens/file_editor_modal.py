from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import widgets
from textual import containers


EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".toml": "toml",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _language_for_path(path: Path) -> str | None:
    """Return a tree-sitter language id for a file path, or None."""
    return EXTENSION_TO_LANGUAGE.get(path.suffix.lower())


class FileEditorModal(ModalScreen[bool]):
    """A modal for viewing and editing a text file."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "close", "Close"),
        Binding("shift+tab", "focus_save", "Focus save", priority=True),
    ]
    AUTO_FOCUS = "TextArea"

    DEFAULT_CSS = """
    FileEditorModal {
        align: center middle;

        #container {
            border: thick $primary 20%;
            border-title-color: $text;
            margin: 1 2;
            height: 1fr;
            width: 1fr;
            max-width: 120;

            TextArea {
                height: 1fr;
            }

            #button-container {
                height: auto;
                padding: 1 1 0 1;
                width: 1fr;
                align: right top;

                Button {
                    min-width: 12;
                    margin: 0 0 0 1;
                }
            }

            #status {
                height: auto;
                padding: 0 1;
                color: $text 60%;
            }
        }
    }
    """

    def __init__(
        self,
        path: Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._path = path
        self._original_text: str = ""
        self._dirty = False
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        language = _language_for_path(self._path)
        try:
            text = self._path.read_text(errors="replace")
        except OSError as e:
            text = f"Error reading file: {e}"

        self._original_text = text

        with containers.VerticalGroup(id="container") as container:
            container.border_title = str(self._path)
            yield widgets.TextArea(
                text,
                language=language,
                soft_wrap=False,
                show_line_numbers=True,
                tab_behavior="indent",
            )
            yield widgets.Static("", id="status")
            with containers.HorizontalGroup(id="button-container"):
                yield widgets.Button("Save & close", variant="primary", id="save")
                yield widgets.Button("Discard", id="close")

    @property
    def text_area(self) -> widgets.TextArea:
        return self.query_one(widgets.TextArea)

    @on(widgets.TextArea.Changed)
    def on_text_changed(self) -> None:
        self._dirty = self.text_area.text != self._original_text
        status = self.query_one("#status", widgets.Static)
        status.update("Modified" if self._dirty else "")

    def action_save(self) -> None:
        self._save_file()

    def action_focus_save(self) -> None:
        self.query_one("#save", widgets.Button).focus()

    @on(widgets.Button.Pressed, "#save")
    def on_save_pressed(self) -> None:
        self._save_file()

    def _save_file(self) -> None:
        text = self.text_area.text
        try:
            self._path.write_text(text)
        except OSError as e:
            self.notify(f"Error saving: {e}", title="Save failed", severity="error")
            return
        self._original_text = text
        self._dirty = False
        self.notify(f"Saved {self._path.name}", title="File saved")
        self.dismiss(True)

    def action_close(self) -> None:
        self.dismiss(self._dirty)

    @on(widgets.Button.Pressed, "#close")
    def on_close_pressed(self) -> None:
        self.dismiss(False)
