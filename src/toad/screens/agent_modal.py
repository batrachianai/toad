from typing import cast

from textual import on
from textual import getters
from textual.app import ComposeResult

from textual import work
from textual.content import Content
from textual.screen import ModalScreen
from textual import containers
from textual import widgets
from textual.reactive import var

import toad
from textual.binding import Binding
from toad.agent_schema import Action, Agent, OS, Command
from toad.app import ToadApp


class DescriptionContainer(containers.VerticalScroll):
    def allow_focus(self) -> bool:
        """Focus only if it can be scrolled."""
        return self.show_vertical_scrollbar


class AgentModal(ModalScreen):
    AUTO_FOCUS = "Select#action-select"

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Dismiss", show=False),
        Binding("space", "dismiss('launch')", "Launch agent", priority=True),
    ]

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
        commands: dict[Action, Command] = {}
        if actions:
            script_os = cast(OS, toad.os)
            commands = actions.get(script_os) or actions.get("*") or {}
        script_choices = [
            (action["description"], name) for name, action in commands.items()
        ]
        script_choices.append((f"Launch {agent['name']}", "__launch__"))

        with containers.Vertical(id="container"):
            with DescriptionContainer(id="description-container"):
                yield widgets.Markdown(agent["help"], id="description")
            with containers.VerticalGroup():
                if "install_acp" in commands:
                    yield widgets.Static(
                        Content(
                            f"{agent['name']} requires an ACP adapter to work with Toad. Install from the actions list."
                        ),
                        classes="acp-warning",
                    )
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
        yield widgets.Footer()

    def on_mount(self) -> None:
        self.query_one("Footer").styles.animate("opacity", 1.0, duration=500 / 1000)

    @on(widgets.Checkbox.Changed)
    def on_checkbox_changed(self, event: widgets.Select.Changed) -> None:
        launcher_agents = self.app.settings.get("launcher.agents", str).splitlines()
        agent_identity = self._agent["identity"]
        if agent_identity in launcher_agents:
            launcher_agents.remove(agent_identity)
        if event.value:
            launcher_agents.insert(0, agent_identity)
        self.app.settings.set("launcher.agents", "\n".join(launcher_agents))

    @on(widgets.Select.Changed)
    def on_select_changed(self, event: widgets.Select.Changed) -> None:
        self.action = event.value if isinstance(event.value, str) else ""

    @work
    @on(widgets.Button.Pressed)
    async def on_button_pressed(self) -> None:
        agent = self._agent
        action = self.action_select.value

        assert isinstance(action, str)
        if action == "__launch__":
            self.dismiss("launch")
            return

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
        from toad.screens.command_edit_modal import CommandEditModal

        title = command["description"]
        agent_id = self._agent["identity"]
        action_command = command["command"]
        bootstrap_uv = command.get("bootstrap_uv", False)

        agent = self._agent
        # Focus the select
        # It's unlikely the user wants to re-run the action
        self.action_select.focus()

        action_command = await self.app.push_screen_wait(
            CommandEditModal(action_command)
        )
        if action_command is None:
            return

        return_code = await self.app.push_screen_wait(
            ActionModal(
                action,
                agent_id,
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
