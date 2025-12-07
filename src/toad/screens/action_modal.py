import shutil

from textual.app import ComposeResult
from textual import on, work
from textual import containers
from textual import getters
from textual.screen import ModalScreen
from textual import widgets
from textual.widget import Widget

from toad.widgets.command_pane import CommandPane


UV_INSTALL = "curl -LsSf https://astral.sh/uv/install.sh | sh"


class ActionModal(ModalScreen):
    """Executes an action command."""

    command_pane = getters.query_one(CommandPane)
    ok_button = getters.query_one("#ok", widgets.Button)

    BINDINGS = [("escape", "dismiss_modal", "Dismiss")]

    def __init__(
        self,
        title: str,
        command: str,
        *,
        bootstrap_uv: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._title = title
        self._command = command
        self._bootstrap_uv = bootstrap_uv
        super().__init__(name=name, id=id, classes=classes)

    def get_loading_widget(self) -> Widget:
        return widgets.LoadingIndicator()

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="container"):
            yield CommandPane()
            yield widgets.Button("OK", id="ok", disabled=True)

    def enable_button(self) -> None:
        self.ok_button.loading = False
        self.ok_button.disabled = False
        self.ok_button.focus()

    @on(CommandPane.CommandComplete)
    def on_command_complete(self, event: CommandPane.CommandComplete) -> None:
        self.enable_button()

    def on_mount(self) -> None:
        self.ok_button.loading = True
        self.command_pane.border_title = self._title

        self.run_command()

    @work()
    async def run_command(self) -> None:
        """Write and execute the command."""
        self.command_pane.anchor()
        if self._bootstrap_uv and shutil.which("uv") is None:
            # Bootstrap UV if required
            self.command_pane.write(f"$ {UV_INSTALL}\n")
            await self.command_pane.execute(UV_INSTALL, final=False)

        self.command_pane.write(f"$ {self._command}\n")
        await self.command_pane.execute(self._command)

    @on(widgets.Button.Pressed)
    def on_button_pressed(self) -> None:
        self.action_dismiss_modal()

    def action_dismiss_modal(self) -> None:
        self.dismiss(self.command_pane.return_code)
