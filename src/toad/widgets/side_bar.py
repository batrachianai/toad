from dataclasses import dataclass

from textual.app import ComposeResult
from textual.widget import Widget
from textual import containers
from textual import widgets
from textual.message import Message


class SideBar(containers.Vertical):
    BINDINGS = [("escape", "dismiss", "Dismiss sidebar")]

    class Dismiss(Message):
        pass

    @dataclass(frozen=True)
    class Panel:
        title: str
        widget: Widget
        flex: bool = False
        collapsed: bool = False
        id: str | None = None

    def __init__(
        self,
        *panels: Panel,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        hide: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.panels: list[SideBar.Panel] = [*panels]
        self.hide = hide

    def on_mount(self) -> None:
        self.trap_focus()

    def compose(self) -> ComposeResult:
        for panel in self.panels:
            yield widgets.Collapsible(
                panel.widget,
                title=panel.title,
                collapsed=panel.collapsed,
                classes="-flex" if panel.flex else "-fixed",
                id=panel.id,
            )

    def action_dismiss(self) -> None:
        self.post_message(self.Dismiss())


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    class SApp(App):
        def compose(self) -> ComposeResult:
            yield SideBar(
                SideBar.Panel("Hello", widgets.Label("Hello, World!")),
                SideBar.Panel(
                    "Files",
                    widgets.DirectoryTree(
                        "~/",
                    ),
                    flex=True,
                ),
                SideBar.Panel(
                    "Hello",
                    widgets.Static("Where there is a Will! " * 10),
                ),
            )

    SApp().run()
