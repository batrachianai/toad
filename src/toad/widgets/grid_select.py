from dataclasses import dataclass

from textual import containers
from textual.binding import Binding
from textual import events
from textual.message import Message
from textual.reactive import reactive
from textual.layouts.grid import GridLayout
from textual.widget import Widget


class GridSelect(containers.ItemGrid, can_focus=True):
    FOCUS_ON_CLICK = False
    CURSOR_GROUP = Binding.Group("Select")
    FOCUS_GROUP = Binding.Group("Focus")
    BINDINGS = [
        Binding("up", "cursor_up", "Cursor Up", group=CURSOR_GROUP),
        Binding("down", "cursor_down", "Cursor Down", group=CURSOR_GROUP),
        Binding("left", "cursor_left", "Cursor Left", group=CURSOR_GROUP),
        Binding("right", "cursor_right", "Cursor Right", group=CURSOR_GROUP),
        Binding("enter", "select", "Select"),
    ]

    highlighted: reactive[int | None] = reactive(None)

    @dataclass
    class Selected(Message):
        grid_select: "GridSelect"
        selected_widget: Widget

        @property
        def control(self) -> Widget:
            return self.grid_select

    @dataclass
    class Highlighted(Message):
        grid_select: "GridSelect"
        widget: Widget

        @property
        def control(self) -> Widget:
            return self.grid_select

    @dataclass
    class LeaveUp(Message):
        grid_select: "GridSelect"

    @dataclass
    class LeaveDown(Message):
        grid_select: "GridSelect"

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        min_column_width: int = 30,
        max_column_width: int | None = None,
    ):
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            min_column_width=min_column_width,
            max_column_width=max_column_width,
        )

    @property
    def grid_size(self) -> tuple[int, int] | None:
        assert isinstance(self.layout, GridLayout)
        return self.layout.grid_size

    def highlight_first(self) -> None:
        self.highlighted = 0

    def highlight_last(self) -> None:
        if (grid_size := self.grid_size) is not None:
            width, height = grid_size

            if width == 1:
                self.highlighted = len(self.children) - 1
            else:
                self.highlighted = (height - 1) * width

    def on_focus(self):
        if self.highlighted is None:
            self.highlighted = 0
        self.reveal_highlight()

    def on_blur(self) -> None:
        self.highlighted = None

    def reveal_highlight(self):
        if self.highlighted is None:
            return
        try:
            highlighted_widget = self.children[self.highlighted]
        except IndexError:
            pass
        else:
            if not self.screen.can_view_entire(highlighted_widget):
                self.screen.scroll_to_center(highlighted_widget, origin_visible=True)

    def watch_highlighted(
        self, old_highlighted: int | None, highlighted: int | None
    ) -> None:
        if old_highlighted is not None:
            try:
                self.children[old_highlighted].remove_class("-highlight")
            except IndexError:
                pass
        if highlighted is not None:
            try:
                highlighted_widget = self.children[highlighted]
                highlighted_widget.add_class("-highlight")
                self.post_message(self.Highlighted(self, highlighted_widget))
            except IndexError:
                pass

        self.reveal_highlight()

    def validate_highlighted(self, highlighted: int | None) -> int | None:
        if highlighted is None:
            return None

        if not self.children:
            return None
        if highlighted < 0:
            return 0
        if highlighted >= len(self.children):
            return len(self.children) - 1
        return highlighted

    def action_cursor_up(self):
        if (grid_size := self.grid_size) is None:
            self.post_message(self.LeaveUp(self))
            return
        if self.highlighted is None:
            self.highlighted = 0
        else:
            width, _height = grid_size
            if self.highlighted >= width:
                self.highlighted -= width
            else:
                self.post_message(self.LeaveUp(self))

    def action_cursor_down(self):
        if (grid_size := self.grid_size) is None:
            self.post_message(self.LeaveDown(self))
            return

        if self.highlighted is None:
            self.highlighted = 0
        else:
            width, height = grid_size
            if self.highlighted + width < len(self.children):
                self.highlighted += width
            else:
                self.post_message(self.LeaveDown(self))

    def action_cursor_left(self):
        if self.highlighted is None:
            self.highlighted = 0
        else:
            self.highlighted -= 1

    def action_cursor_right(self):
        if self.highlighted is None:
            self.highlighted = 0
        else:
            self.highlighted += 1

    def on_click(self, event: events.Click) -> None:
        if event.widget is None:
            return

        highlighted_widget: Widget | None = None
        if self.highlighted is not None:
            try:
                highlighted_widget = self.children[self.highlighted]
            except IndexError:
                pass
        for widget in event.widget.ancestors_with_self:
            if widget in self.children:
                if highlighted_widget is not None and highlighted_widget is widget:
                    self.action_select()
                else:
                    self.highlighted = self.children.index(widget)
                break
        self.focus()

    def action_select(self):
        if self.highlighted is not None:
            try:
                highlighted_widget = self.children[self.highlighted]
            except IndexError:
                pass
            else:
                self.post_message(self.Selected(self, highlighted_widget))


if __name__ == "__main__":
    from textual.app import App, ComposeResult
    from textual import widgets

    class GridApp(App):
        CSS = """
        .grid-item {
            width: 1fr;
            padding: 0 1;
            # background: blue 20%;        
            border: blank;

            &:hover {
                background: $panel;
            }

            &.-highlight {
                border: tall $primary;
                background: $panel;
            }
        }
        """

        def compose(self) -> ComposeResult:
            yield widgets.Footer()
            with GridSelect():
                for n in range(50):
                    yield widgets.Label(
                        f"#{n} Where there is a Will, there is a Way!",
                        classes="grid-item",
                    )

    GridApp().run()
