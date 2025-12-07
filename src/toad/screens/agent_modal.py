from typing import cast

from textual import on
from textual import getters
from textual.app import ComposeResult

from textual import work
from textual.screen import ModalScreen
from textual import containers
from textual import widgets
from textual.reactive import var

import toad
from toad.agent_schema import Action, Agent, OS, Command
from toad.app import ToadApp


class AgentModal(ModalScreen):
    AUTO_FOCUS = "#launcher-checkbox"

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    action = var("")

    app = getters.app(ToadApp)
    action_select = getters.query_one("#action-select", widgets.Select)
    launcher_checkbox = getters.query_one("#launcher-checkbox", widgets.Checkbox)

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        super().__init__()

    def compose(self) -> ComposeResult:
        launcher_set = frozenset(
            self.app.settings.get("launcher.agents", str).splitlines()
        )

        agent = self._agent

        app = self.app
        launcher_set = frozenset(app.settings.get("launcher.agents", str).splitlines())
        agent = self._agent
        actions = agent["actions"]

        script_os = cast(OS, toad.os)
        if script_os not in actions:
            script_os = "*"

        commands: dict[Action, Command] = actions[cast(OS, script_os)]
        script_choices = [
            (action["description"], name) for name, action in commands.items()
        ]

        with containers.Vertical(id="container"):
            with containers.VerticalScroll(id="description-container"):
                yield widgets.Markdown(agent["help"], id="description")
            with containers.VerticalGroup():
                with containers.HorizontalGroup():
                    yield widgets.Checkbox(
                        "Show in launcher",
                        value=agent["identity"] in launcher_set,
                        id="launcher-checkbox",
                    )
                    yield widgets.Select(
                        script_choices,
                        prompt="Actions",
                        allow_blank=True,
                        id="action-select",
                    )
                    yield widgets.Button(
                        "Go", variant="primary", id="run-action", disabled=True
                    )

    @on(widgets.Checkbox.Changed)
    def on_checkbox_changed(self, event: widgets.Select.Changed) -> None:
        launcher_set = set(self.app.settings.get("launcher.agents", str).splitlines())
        agent_identity = self._agent["identity"]
        if event.value:
            launcher_set.add(agent_identity)
        else:
            launcher_set.discard(agent_identity)
        self.app.settings.set("launcher.agents", "\n".join(launcher_set))

    @on(widgets.Select.Changed)
    def on_select_changed(self, event: widgets.Select.Changed) -> None:
        self.action = event.value if isinstance(event.value, str) else ""

    @work
    @on(widgets.Button.Pressed)
    async def on_button_pressed(self) -> None:
        agent = self._agent
        action = self.action_select.value
        assert isinstance(action, str)
        agent_actions = self._agent["actions"]

        if (commands := agent_actions.get(toad.os, None)) is None:
            commands = agent_actions.get("*", None)
        if commands is None:
            self.notify(
                "Action is not available on this platform",
                title="Agent action",
                severity="error",
            )
            return
        command = commands[action]

        from toad.screens.action_modal import ActionModal

        title = command["description"]
        action_command = command["command"]
        bootstrap_uv = command.get("bootstrap_uv", False)

        agent = self._agent
        # Focus the select
        # It's unlikely the user wants to re-run the action
        self.action_select.focus()
        return_code = await self.app.push_screen_wait(
            ActionModal(
                title,
                action_command,
                bootstrap_uv=bootstrap_uv,
            )
        )
        if return_code == 0 and action in {"install", "install-acp"}:
            # Add to launcher if we installed something
            if not self.launcher_checkbox.value:
                self.notify(
                    f"{agent['name']} has been added to your launcher",
                    title="Add agent",
                    severity="information",
                )
                self.launcher_checkbox.value = True

    def watch_action(self, action: str) -> None:
        go_button = self.query_one("#run-action", widgets.Button)
        go_button.disabled = not action
