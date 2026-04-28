"""Tests for the ``SubagentTabSection`` widget.

The subagent tab section is an on-demand ``ProjectStatePane`` section that
hosts one tab per live subagent. Each tab mounts a ``Conversation`` widget
paired with an ``Agent`` instance (a ``claude-code-acp`` subprocess).

These tests drive the widget contract:

- Dynamic add / remove of tabs via ``open_tab`` / ``close_tab``
- Section visibility: hidden with zero tabs, shown as soon as a tab exists,
  hidden again when the last tab closes
- Each opened tab mounts a ``Conversation`` + ``Agent`` pair produced by an
  injectable factory (so tests never spawn a real subprocess)

The tests use a stub ``agent_factory`` so no ACP subprocess is spawned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from toad.widgets.subagent_tab_section import SubagentTabSection


# ------------------------------------------------------------------
# Test doubles
# ------------------------------------------------------------------


class _StubConversation(Static):
    """Minimal widget standing in for a real ``Conversation``.

    The real ``Conversation`` depends on an ``Agent`` + DB plumbing; for
    widget-layout tests we just need something mountable inside a
    ``TabPane``.
    """

    def __init__(self, name: str, objective: str) -> None:
        super().__init__(f"[conv {name}] {objective}", id=f"conv-{name.lower().replace(' ', '-')}")
        self.subagent_name = name
        self.objective = objective


@dataclass
class _FactoryCall:
    name: str
    objective: str


@dataclass
class _RecordingFactory:
    """Factory capturing every ``(name, objective)`` pair it was asked for."""

    calls: list[_FactoryCall] = field(default_factory=list)
    agents: list[MagicMock] = field(default_factory=list)
    conversations: list[_StubConversation] = field(default_factory=list)

    def __call__(self, name: str, objective: str) -> tuple[_StubConversation, MagicMock]:
        self.calls.append(_FactoryCall(name=name, objective=objective))
        conv = _StubConversation(name, objective)
        agent = MagicMock(name=f"Agent<{name}>")
        agent.subagent_name = name
        self.conversations.append(conv)
        self.agents.append(agent)
        return conv, agent


# ------------------------------------------------------------------
# Harness
# ------------------------------------------------------------------


class _Harness(App[None]):
    """App that mounts a single ``SubagentTabSection`` for testing."""

    def __init__(self, factory: _RecordingFactory) -> None:
        super().__init__()
        self._factory = factory

    def compose(self) -> ComposeResult:
        yield SubagentTabSection(
            project_path=Path("/tmp/test-project"),
            agent_factory=self._factory,
            id="section-subagents",
        )


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def factory() -> _RecordingFactory:
    return _RecordingFactory()


# ------------------------------------------------------------------
# Visibility tests
# ------------------------------------------------------------------


class TestSectionVisibility:
    """Section is hidden when empty, shown when it has tabs."""

    @pytest.mark.asyncio
    async def test_hidden_when_empty(self, factory: _RecordingFactory) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            assert section.is_empty is True
            assert section.display is False

    @pytest.mark.asyncio
    async def test_shown_after_first_tab(self, factory: _RecordingFactory) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research competitor streaming")
            await pilot.pause()
            assert section.is_empty is False
            assert section.display is True
            assert section.tab_names == ["Strategy"]

    @pytest.mark.asyncio
    async def test_hidden_again_when_last_tab_closes(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            await pilot.pause()
            section.close_tab("Strategy")
            await pilot.pause()
            assert section.is_empty is True
            assert section.display is False
            assert section.tab_names == []

    @pytest.mark.asyncio
    async def test_stays_visible_while_any_tab_remains(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            section.open_tab("CanonCLI", "draft cli spec")
            await pilot.pause()
            section.close_tab("Strategy")
            await pilot.pause()
            assert section.display is True
            assert section.tab_names == ["CanonCLI"]


# ------------------------------------------------------------------
# Dynamic add / remove tests
# ------------------------------------------------------------------


class TestDynamicTabs:
    """Tabs can be added and removed at runtime."""

    @pytest.mark.asyncio
    async def test_open_multiple_tabs(self, factory: _RecordingFactory) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            section.open_tab("CanonCLI", "spec Y")
            section.open_tab("Docs", "write Z")
            await pilot.pause()
            assert section.tab_names == ["Strategy", "CanonCLI", "Docs"]

    @pytest.mark.asyncio
    async def test_close_middle_tab_preserves_others(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("A", "a")
            section.open_tab("B", "b")
            section.open_tab("C", "c")
            await pilot.pause()
            section.close_tab("B")
            await pilot.pause()
            assert section.tab_names == ["A", "C"]

    @pytest.mark.asyncio
    async def test_close_unknown_tab_is_noop(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "x")
            await pilot.pause()
            # Closing an unknown tab should not raise or affect existing tabs.
            section.close_tab("does-not-exist")
            await pilot.pause()
            assert section.tab_names == ["Strategy"]

    @pytest.mark.asyncio
    async def test_duplicate_name_gets_suffix(
        self, factory: _RecordingFactory
    ) -> None:
        """Opening a second tab with the same name must not collide."""
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            first = section.open_tab("Strategy", "first")
            second = section.open_tab("Strategy", "second")
            await pilot.pause()
            assert first == "Strategy"
            assert second != "Strategy"
            assert second.startswith("Strategy")
            assert set(section.tab_names) == {first, second}


# ------------------------------------------------------------------
# Pair mounting tests
# ------------------------------------------------------------------


class TestConversationAgentPair:
    """Each tab mounts a ``Conversation`` + ``Agent`` pair via the factory."""

    @pytest.mark.asyncio
    async def test_factory_called_per_tab(self, factory: _RecordingFactory) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            section.open_tab("CanonCLI", "spec Y")
            await pilot.pause()
            assert [c.name for c in factory.calls] == ["Strategy", "CanonCLI"]
            assert [c.objective for c in factory.calls] == [
                "research X",
                "spec Y",
            ]

    @pytest.mark.asyncio
    async def test_conversation_is_mounted_in_tab(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            await pilot.pause()
            # The stub conversation produced by the factory must be part
            # of the widget tree, inside the section.
            stub = factory.conversations[0]
            assert stub.is_mounted
            assert section in stub.ancestors

    @pytest.mark.asyncio
    async def test_agent_is_paired_with_tab(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            await pilot.pause()
            agent = section.get_agent("Strategy")
            assert agent is factory.agents[0]

    @pytest.mark.asyncio
    async def test_closing_tab_removes_conversation_from_tree(
        self, factory: _RecordingFactory
    ) -> None:
        app = _Harness(factory)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)
            section.open_tab("Strategy", "research X")
            await pilot.pause()
            stub = factory.conversations[0]
            assert stub.is_mounted
            assert stub in section.walk_children()
            section.close_tab("Strategy")
            await pilot.pause()
            # Textual never flips ``is_mounted`` back to False; detachment
            # is observable via the DOM tree + parent pointer.
            assert stub not in section.walk_children()
            assert stub.parent is None
            assert section.get_agent("Strategy") is None


# ------------------------------------------------------------------
# Module-level contract tests
# ------------------------------------------------------------------


class TestModuleSurface:
    """The widget exposes the attributes the socket layer depends on."""

    def test_section_id_constant(self) -> None:
        assert SubagentTabSection.SECTION_ID == "section-subagents"

    def test_has_public_api(self) -> None:
        for attr in ("open_tab", "close_tab", "tab_names", "is_empty", "get_agent"):
            assert hasattr(SubagentTabSection, attr), f"missing {attr}"
