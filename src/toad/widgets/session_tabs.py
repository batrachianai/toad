import asyncio
from functools import partial
from rich.style import Style as RichStyle

from textual import work
from textual.app import ComposeResult, RenderResult

from textual import events
from textual.content import Content
from textual.geometry import Offset
from textual.reactive import reactive
from textual.renderables.bar import Bar
from textual.widget import Widget
from textual import containers
from textual import widgets
from textual import getters
from textual.message import Message

from toad.app import ToadApp
from toad.session_tracker import SessionDetails
from toad import messages


class SessionLabel(widgets.Label):
    ALLOW_SELECT = False

    def on_click(self) -> None:
        if self.id is not None:
            self.post_message(messages.SessionSwitch(self.id))


class Underline(Widget):
    """The animated underline beneath tabs."""

    COMPONENT_CLASSES = {"underline--bar"}
    """
    | Class | Description |
    | :- | :- |
    | `underline--bar` | Style of the bar (may be used to change the color). |
    """

    highlight_start = reactive(0)
    """First cell in highlight."""
    highlight_end = reactive(0)
    """Last cell (inclusive) in highlight."""
    show_highlight: reactive[bool] = reactive(True)
    """Flag to indicate if a highlight should be shown at all."""

    class Clicked(Message):
        """Inform ancestors the underline was clicked."""

        offset: Offset
        """The offset of the click, relative to the origin of the bar."""

        def __init__(self, offset: Offset) -> None:
            self.offset = offset
            super().__init__()

    @property
    def _highlight_range(self) -> tuple[int, int]:
        """Highlighted range for underline bar."""
        return (
            (self.highlight_start, self.highlight_end)
            if self.show_highlight
            else (0, 0)
        )

    def render(self) -> RenderResult:
        """Render the bar."""
        bar_style = self.get_component_rich_style("underline--bar")
        return Bar(
            highlight_range=self._highlight_range,
            highlight_style=RichStyle.from_color(bar_style.color),
            background_style=RichStyle.from_color(bar_style.bgcolor),
        )

    def _on_click(self, event: events.Click):
        """Catch clicks, so that the underline can activate the tabs."""
        event.stop()
        self.post_message(self.Clicked(event.screen_offset))


class SessionsTabs(Widget):

    ALLOW_SELECT = False
    app: getters.app[ToadApp] = getters.app(ToadApp)

    title_container = getters.query_one("#title-container", Widget)

    current_session = reactive("", init=False)

    def on_mount(self) -> None:
        self.current_session = self.app.current_mode
        self.app.mode_change_signal.subscribe(self, self.handle_mode_change)
        self.app.session_update_signal.subscribe(
            self, self.handle_session_update_signal
        )
        self.update_underline(self.current_session, animate=False)
        self.call_after_refresh(self.update_underline, self.current_session)

    def handle_mode_change(self, mode: str) -> None:
        self.current_session = mode

    def watch_current_session(self, old_session: str, new_session: str) -> None:
        self.query(".-current").remove_class("-current")
        self.query(f"#{new_session}").add_class("-current")
        if old_session:
            self.update_underline(old_session, animate=False)

        self.update_underline(new_session, animate=True)

    def update_underline(self, session: str | None = None, animate: bool = True):
        if not self.is_mounted or not self.is_attached:
            return
        if session is None:
            session = self.current_session
        if not session:
            return
        if current_label := self.query_one_optional(f"#{session}", SessionLabel):
            tab_region = current_label.virtual_region.shrink((0, 1, 0, 1))
            if not tab_region:
                return
            start, end = tab_region.column_span
            underline = self.query_one(Underline)
            if animate:
                underline.animate("highlight_start", start, duration=0.3)
                underline.animate(
                    "highlight_end",
                    end,
                    duration=0.3,
                    on_complete=partial(self.scroll_to_center, current_label),
                )
            else:
                underline.highlight_start = start
                underline.highlight_end = end
                self.scroll_to_center(current_label, animate=False)

    def render_session_label(self, session: SessionDetails) -> Content:
        match session.state:
            case "asking":
                return Content.assemble(
                    ("❯ ", "not dim $text-secondary"), session.title
                )
            case "busy":
                return Content(f"⌛ {session.title}")
        return Content(session.title)

    def compose(self) -> ComposeResult:
        with containers.HorizontalGroup(id="title-container"):
            for session in self.app.session_tracker.ordered_sessions:
                yield SessionLabel(
                    self.render_session_label(session),
                    id=session.mode_name,
                    classes="-current" if session.mode_name == self.screen.id else "",
                )
        yield Underline()

    @work
    async def handle_session_update_signal(
        self, update: tuple[str, SessionDetails | None]
    ) -> None:
        mode, details = update
        if details is None:
            await self.query(f"#{mode}").remove()
        else:
            if tab_label := self.query_one_optional(f"#{mode}", SessionLabel):
                tab_label.update(self.render_session_label(details))
            else:
                self.query(SessionLabel).remove_class("-current")
                await self.title_container.mount(
                    SessionLabel(
                        self.render_session_label(details),
                        id=details.mode_name,
                        classes=(
                            "-current" if details.mode_name == self.screen.id else ""
                        ),
                    )
                )
        await asyncio.sleep(0.05)
        self.call_after_refresh(self.update_underline, self.current_session)
