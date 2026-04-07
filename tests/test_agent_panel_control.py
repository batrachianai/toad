"""Tests for agent-controlled panels and Conductor TUI integration.

Verifies:
- OpenPanel/ClosePanel ACP messages exist and have correct fields
- sessionUpdate "open_panel"/"close_panel" in agent.py dispatch correctly
- MainScreen handles OpenPanel by mounting GitHub panel
- Claude agent config has Conductor awareness (welcome message)
"""

from __future__ import annotations

from pathlib import Path

from toad.acp import messages as acp_messages


class TestACPPanelMessages:
    """OpenPanel and ClosePanel message types exist with correct fields."""

    def test_open_panel_message(self):
        msg = acp_messages.OpenPanel(panel_id="github")
        assert msg.panel_id == "github"
        assert msg.context is None

    def test_open_panel_message_with_context(self):
        ctx = {"project_path": "/some/path"}
        msg = acp_messages.OpenPanel(panel_id="github", context=ctx)
        assert msg.panel_id == "github"
        assert msg.context == ctx

    def test_close_panel_message(self):
        msg = acp_messages.ClosePanel(panel_id="github")
        assert msg.panel_id == "github"

    def test_messages_are_agent_messages(self):
        assert issubclass(acp_messages.OpenPanel, acp_messages.AgentMessage)
        assert issubclass(
            acp_messages.ClosePanel, acp_messages.AgentMessage
        )


class TestSessionUpdateDispatch:
    """agent.py dispatches open_panel/close_panel sessionUpdate events."""

    def test_open_panel_session_update_dispatches(self):
        """Verify the match arm for open_panel exists in rpc_session_update."""
        import inspect

        from toad.acp.agent import Agent

        source = inspect.getsource(Agent.rpc_session_update)
        assert '"sessionUpdate": "open_panel"' in source
        assert "OpenPanel" in source

    def test_close_panel_session_update_dispatches(self):
        """Verify the match arm for close_panel exists in rpc_session_update."""
        import inspect

        from toad.acp.agent import Agent

        source = inspect.getsource(Agent.rpc_session_update)
        assert '"sessionUpdate": "close_panel"' in source
        assert "ClosePanel" in source


class TestMainScreenPanelHandlers:
    """MainScreen has @on handlers for OpenPanel and ClosePanel."""

    def test_open_panel_handler_exists(self):
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "on_acp_open_panel")

    def test_close_panel_handler_exists(self):
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "on_acp_close_panel")

    def test_toggle_github_still_works(self):
        """ctrl+g binding is still present for manual toggle."""
        from toad.screens.main import MainScreen

        binding_keys = [b.key for b in MainScreen.BINDINGS]
        assert "ctrl+g" in binding_keys


class TestClaudeAgentConfig:
    """Claude agent TOML config includes Conductor awareness."""

    def _config_text(self) -> str:
        config_path = (
            Path(__file__).parent.parent
            / "src"
            / "toad"
            / "data"
            / "agents"
            / "claude.com.toml"
        )
        return config_path.read_text()

    def test_welcome_field_exists(self):
        assert "welcome" in self._config_text()

    def test_welcome_mentions_conductor(self):
        assert "Conductor" in self._config_text()

    def test_welcome_mentions_socket_commands(self):
        assert "socket commands" in self._config_text()

    def test_welcome_mentions_ctrl_g(self):
        assert "ctrl+g" in self._config_text()
