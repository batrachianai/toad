from textual import on, work
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual import widgets
from textual import containers
from textual import getters


class CommandEditModal(ModalScreen[str | None]):
    BINDINGS = [
        ("ctrl+c", "copy", "Copy to clipboard"),
        ("escape", "dismiss", "Dismiss"),
    ]
    AUTO_FOCUS = "Button"

    text_area = getters.query_one(widgets.TextArea)

    def __init__(
        self,
        command: str,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        self.command = command
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="container"):
            with containers.Center():
                yield widgets.Label(
                    "[b]Run command",
                    classes="instructions",
                )
            yield widgets.Static(
                "Canon will run the following command (edit if you need to).",
                classes="instructions",
            )
            yield widgets.TextArea(
                self.command,
                language="bash",
                highlight_cursor_line=False,
                soft_wrap=False,
            )
            with containers.HorizontalGroup(id="button-container"):
                yield widgets.Button("OK", variant="primary", id="ok")
                yield widgets.Button(
                    "Cancel", id="cancel", action="screen.dismiss(None)"
                )
        yield widgets.Footer()

    @on(widgets.Button.Pressed, "#ok")
    def on_ok_pressed(self, event: widgets.Button.Pressed) -> None:
        self.dismiss(self.text_area.text)

    @on(widgets.Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: widgets.Button.Pressed) -> None:
        self.dismiss(None)

    def action_copy(self) -> None:
        self.app.copy_to_clipboard(self.text_area.text)
        self.notify("Command copied to clipboard", title="Copy")


if __name__ == "__main__":
    from textual.app import App

    class ModalApp(App):
        @work
        async def on_mount(self) -> None:
            result = await self.push_screen_wait(CommandEditModal("ls -al"))
            self.notify(str(result))

    ModalApp().run()
