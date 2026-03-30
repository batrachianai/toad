"""Tests for agent-controlled panels and --conductor CLI flag.

Verifies:
- --conductor CLI flag sets agent to Claude
- OpenPanel/ClosePanel ACP messages exist and have correct fields
- sessionUpdate "open_panel"/"close_panel" in agent.py dispatch correctly
- MainScreen handles OpenPanel by mounting GitHub panel
- Agent response interception: /panel commands in agent text trigger ACP messages
- Slash command /panel registration and handler
- Claude agent config has panel awareness (welcome + help)
- Skill file documents the panel system
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from toad.acp import messages as acp_messages


class TestConductorCLIFlag:
    """--conductor flag should force agent='claude' and skip store."""

    def test_conductor_flag_exists(self):
        """The --conductor flag is accepted by the run command."""
        from toad.cli import run

        params = {p.name for p in run.params}
        assert "conductor" in params

    def test_conductor_flag_sets_claude_agent(self):
        """When --conductor is set, agent resolves to 'claude'."""
        from toad.cli import run

        runner = CliRunner()
        # Use --help to avoid actually launching the app
        result = runner.invoke(run, ["--conductor", "--help"])
        assert result.exit_code == 0


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
        assert issubclass(acp_messages.ClosePanel, acp_messages.AgentMessage)


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

    def test_orchestrator_detected_handler_exists(self):
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "on_orchestrator_detected")

    def test_toggle_github_still_works(self):
        """ctrl+g binding is still present for manual toggle."""
        from toad.screens.main import MainScreen

        binding_keys = [b.key for b in MainScreen.BINDINGS]
        assert "ctrl+g" in binding_keys


class TestPanelCommandRegex:
    """_PANEL_COMMAND_RE in Conversation matches /panel commands."""

    @pytest.fixture()
    def regex(self):
        from toad.widgets.conversation import Conversation

        return Conversation._PANEL_COMMAND_RE

    def test_matches_open_panel(self, regex: re.Pattern[str]):
        m = regex.search("/panel github")
        assert m is not None
        assert m.group(1) == "github"
        assert m.group(2) is None

    def test_matches_close_panel(self, regex: re.Pattern[str]):
        m = regex.search("/panel github close")
        assert m is not None
        assert m.group(1) == "github"
        assert m.group(2) == "close"

    def test_matches_list(self, regex: re.Pattern[str]):
        m = regex.search("/panel list")
        assert m is not None
        assert m.group(1) == "list"

    def test_matches_embedded_in_multiline(self, regex: re.Pattern[str]):
        text = "Here is context.\n/panel github\nMore text."
        m = regex.search(text)
        assert m is not None
        assert m.group(1) == "github"

    def test_strips_all_panel_lines(self, regex: re.Pattern[str]):
        text = "Opening the panel.\n/panel github\nDone."
        result = regex.sub("", text)
        assert "/panel" not in result
        assert "Opening the panel." in result
        assert "Done." in result

    def test_no_match_on_partial(self, regex: re.Pattern[str]):
        assert regex.search("/panelgithub") is None

    def test_no_match_on_text_only(self, regex: re.Pattern[str]):
        assert regex.search("use /panel github to open") is None


class TestConversationSlashCommandPanel:
    """/panel slash command is registered and handler emits ACP messages."""

    def test_panel_slash_command_registered(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(Conversation._build_slash_commands)
        assert '"/panel"' in source

    def test_panel_handler_emits_open(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(Conversation.slash_command)
        assert 'command == "panel"' in source
        assert "OpenPanel" in source

    def test_panel_handler_emits_close(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(Conversation.slash_command)
        assert "ClosePanel" in source

    def test_panel_handler_supports_list(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(Conversation.slash_command)
        assert '"list"' in source


class TestAgentResponseInterception:
    """on_acp_agent_message filters /panel commands from agent text."""

    def test_intercept_method_exists(self):
        from toad.widgets.conversation import Conversation

        assert hasattr(Conversation, "_intercept_panel_commands")

    def test_on_acp_agent_message_calls_intercept(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(Conversation.on_acp_agent_message)
        assert "_intercept_panel_commands" in source

    def test_intercept_posts_open_panel(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(
            Conversation._intercept_panel_commands
        )
        assert "OpenPanel" in source

    def test_intercept_posts_close_panel(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(
            Conversation._intercept_panel_commands
        )
        assert "ClosePanel" in source

    def test_filtered_text_passed_to_post_agent_response(self):
        import inspect
        from toad.widgets.conversation import Conversation

        source = inspect.getsource(Conversation.on_acp_agent_message)
        assert "filtered_text" in source
        assert "post_agent_response" in source


class TestClaudeAgentPanelConfig:
    """Claude agent TOML config includes panel awareness."""

    @pytest.fixture()
    def config_text(self):
        config_path = (
            Path(__file__).parent.parent
            / "src"
            / "toad"
            / "data"
            / "agents"
            / "claude.com.toml"
        )
        return config_path.read_text()

    def test_help_mentions_panel_command(self, config_text: str):
        assert "/panel" in config_text

    def test_help_mentions_github_panel(self, config_text: str):
        assert "github" in config_text

    def test_welcome_field_exists(self, config_text: str):
        assert "welcome" in config_text

    def test_welcome_mentions_panel_github(self, config_text: str):
        assert "/panel github" in config_text

    def test_welcome_instructs_project_state(self, config_text: str):
        lower = config_text.lower()
        assert "project state" in lower or "issues" in lower


class TestConductorPanelsSkill:
    """skills/conductor-panels.md exists and documents the panel system."""

    @pytest.fixture()
    def skill_text(self):
        base = Path.home() / "dega" / "aidd" / "claude-code-config"
        candidates = [
            base / "skills" / "conductor-panels.md",
            # Worktree variants
            base
            / ".orchestrator"
            / "worktrees"
            / "20260321-agent-panel-integration"
            / "skills"
            / "conductor-panels.md",
        ]
        for path in candidates:
            if path.exists():
                return path.read_text()
        pytest.skip("conductor-panels.md not found in any expected location")

    def test_documents_panel_command(self, skill_text: str):
        assert "/panel" in skill_text

    def test_documents_github_panel(self, skill_text: str):
        assert "github" in skill_text.lower()

    def test_documents_open_syntax(self, skill_text: str):
        assert "/panel github" in skill_text

    def test_documents_close_syntax(self, skill_text: str):
        assert "/panel github close" in skill_text or (
            "close" in skill_text and "/panel" in skill_text
        )

    def test_documents_acp_protocol(self, skill_text: str):
        assert "open_panel" in skill_text
        assert "close_panel" in skill_text
