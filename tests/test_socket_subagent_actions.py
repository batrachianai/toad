"""Tests for socket-controller subagent actions and status query.

These tests pin the external protocol that Conductor's agent will use to
drive the Subagents pane from outside the TUI. They are intentionally
written before item 4's implementation (TDD) — item 4 makes them pass by
extending ``socket_controller._dispatch`` and adding the matching action
methods on ``MainScreen``.

Protocol under test
-------------------

Open a subagent tab::

    {"cmd": "action",
     "name": "open_subagent_tab",
     "args": {"name": "strategy",
              "objective": {"objective": "Plan the migration"}}}

Close a subagent tab::

    {"cmd": "action",
     "name": "close_subagent_tab",
     "args": {"name": "strategy"}}

Query open tabs::

    {"cmd": "subagent_status"}
    -> {"ok": True, "tabs": ["strategy", ...], "count": N}

Structured objective payload
----------------------------

v1 populates only ``objective``. ``output_format``, ``tool_scope``, and
``boundary`` are reserved keys — accepted but not yet consumed by the
subagent runtime. Unknown keys must be rejected so typos in Conductor's
agent surface early.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from toad.socket_controller import _dispatch


# ---------------------------------------------------------------------------
# Test double — a minimal fake App that _dispatch can drive
# ---------------------------------------------------------------------------


class _FakeApp:
    """Mimics the subset of ``textual.app.App`` used by ``_dispatch``."""

    def __init__(self, tab_names: list[str] | None = None) -> None:
        self.run_action = AsyncMock()
        self.log = MagicMock()
        screen = MagicMock()
        screen.action_open_subagent_tab = AsyncMock(return_value=None)
        screen.action_close_subagent_tab = AsyncMock(return_value=None)
        screen.subagent_status = MagicMock(
            return_value={
                "tabs": list(tab_names or []),
                "count": len(tab_names or []),
            }
        )
        self.screen = screen

    def query(self, _selector: str) -> list[Any]:
        return []


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ---------------------------------------------------------------------------
# MainScreen surface — item 4 must add these
# ---------------------------------------------------------------------------


class TestMainScreenSubagentActions:
    def test_action_open_subagent_tab_exists(self) -> None:
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "action_open_subagent_tab"), (
            "MainScreen.action_open_subagent_tab must exist (item 4)"
        )

    def test_action_close_subagent_tab_exists(self) -> None:
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "action_close_subagent_tab"), (
            "MainScreen.action_close_subagent_tab must exist (item 4)"
        )

    def test_subagent_status_handler_exists(self) -> None:
        """A status accessor must be callable without the socket layer."""
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "subagent_status"), (
            "MainScreen.subagent_status must exist (item 4) — returns "
            "{'tabs': [...], 'count': N} from the SubagentTabSection"
        )

    def test_action_open_subagent_tab_accepts_name_and_objective(self) -> None:
        """Signature must accept ``name`` and ``objective`` (either kw or pos)."""
        from toad.screens.main import MainScreen

        sig = inspect.signature(MainScreen.action_open_subagent_tab)
        params = [p for p in sig.parameters if p != "self"]
        assert "name" in params, "expected 'name' parameter"
        assert "objective" in params, "expected 'objective' parameter"

    def test_action_close_subagent_tab_accepts_name(self) -> None:
        from toad.screens.main import MainScreen

        sig = inspect.signature(MainScreen.action_close_subagent_tab)
        params = [p for p in sig.parameters if p != "self"]
        assert "name" in params, "expected 'name' parameter"


# ---------------------------------------------------------------------------
# Socket dispatch — open / close
# ---------------------------------------------------------------------------


class TestSocketOpenSubagentTab:
    def test_dispatch_routes_open_to_screen_action(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "open_subagent_tab",
            "args": {
                "name": "strategy",
                "objective": {"objective": "Plan the migration"},
            },
        }

        response = asyncio.run(_dispatch(app, request))

        assert response.get("ok") is True, response
        app.screen.action_open_subagent_tab.assert_awaited_once()
        # Accept either kw-call or positional-call style
        call = app.screen.action_open_subagent_tab.await_args
        bound_kwargs = {**dict(zip(("name", "objective"), call.args)), **call.kwargs}
        assert bound_kwargs["name"] == "strategy"
        assert bound_kwargs["objective"] == {"objective": "Plan the migration"}

    def test_dispatch_open_accepts_namespaced_action_name(self) -> None:
        """``screen.open_subagent_tab`` is the canonical agent-facing name."""
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "screen.open_subagent_tab",
            "args": {"name": "s", "objective": {"objective": "x"}},
        }

        response = asyncio.run(_dispatch(app, request))

        assert response.get("ok") is True, response
        app.screen.action_open_subagent_tab.assert_awaited_once()

    def test_dispatch_open_requires_args(self) -> None:
        app = _FakeApp()
        request = {"cmd": "action", "name": "open_subagent_tab"}
        response = asyncio.run(_dispatch(app, request))
        assert "error" in response
        app.screen.action_open_subagent_tab.assert_not_called()

    def test_dispatch_open_requires_name_arg(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "open_subagent_tab",
            "args": {"objective": {"objective": "x"}},
        }
        response = asyncio.run(_dispatch(app, request))
        assert "error" in response
        app.screen.action_open_subagent_tab.assert_not_called()

    def test_dispatch_open_requires_objective_arg(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "open_subagent_tab",
            "args": {"name": "s"},
        }
        response = asyncio.run(_dispatch(app, request))
        assert "error" in response
        app.screen.action_open_subagent_tab.assert_not_called()


class TestSocketCloseSubagentTab:
    def test_dispatch_routes_close_to_screen_action(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "close_subagent_tab",
            "args": {"name": "strategy"},
        }

        response = asyncio.run(_dispatch(app, request))

        assert response.get("ok") is True, response
        app.screen.action_close_subagent_tab.assert_awaited_once()
        call = app.screen.action_close_subagent_tab.await_args
        bound = {**dict(zip(("name",), call.args)), **call.kwargs}
        assert bound["name"] == "strategy"

    def test_dispatch_close_requires_name(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "close_subagent_tab",
            "args": {},
        }
        response = asyncio.run(_dispatch(app, request))
        assert "error" in response
        app.screen.action_close_subagent_tab.assert_not_called()


# ---------------------------------------------------------------------------
# Socket dispatch — subagent.status query
# ---------------------------------------------------------------------------


class TestSocketSubagentStatus:
    def test_status_empty(self) -> None:
        app = _FakeApp(tab_names=[])
        response = asyncio.run(_dispatch(app, {"cmd": "subagent_status"}))
        assert response.get("ok") is True, response
        assert response.get("tabs") == []
        assert response.get("count") == 0

    def test_status_lists_open_tabs(self) -> None:
        app = _FakeApp(tab_names=["strategy", "research"])
        response = asyncio.run(_dispatch(app, {"cmd": "subagent_status"}))
        assert response.get("ok") is True, response
        assert response.get("tabs") == ["strategy", "research"]
        assert response.get("count") == 2
        app.screen.subagent_status.assert_called_once()


# ---------------------------------------------------------------------------
# Structured objective payload schema
# ---------------------------------------------------------------------------


RESERVED_OBJECTIVE_KEYS = {"objective", "output_format", "tool_scope", "boundary"}


def _validate_objective(payload: Any) -> dict[str, Any]:
    """Local mirror of the schema contract — a regression anchor.

    Item 4's implementation must enforce the same rules inside the socket
    dispatch path (reject when they are violated, accept otherwise).
    """
    if not isinstance(payload, dict):
        raise TypeError("objective payload must be a dict")
    if "objective" not in payload or not isinstance(payload["objective"], str):
        raise ValueError("objective payload must contain a string 'objective'")
    extras = set(payload) - RESERVED_OBJECTIVE_KEYS
    if extras:
        raise ValueError(f"unknown objective keys: {sorted(extras)}")
    return payload


class TestObjectivePayloadSchema:
    def test_minimal_payload_is_valid(self) -> None:
        assert _validate_objective({"objective": "Plan X"}) == {
            "objective": "Plan X"
        }

    def test_reserved_keys_are_accepted(self) -> None:
        payload = {
            "objective": "Plan X",
            "output_format": "markdown",
            "tool_scope": ["Read", "Grep"],
            "boundary": "read-only",
        }
        assert _validate_objective(payload) == payload

    def test_missing_objective_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            _validate_objective({"output_format": "markdown"})

    def test_unknown_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            _validate_objective({"objective": "x", "budget": 100})

    def test_non_dict_is_rejected(self) -> None:
        with pytest.raises(TypeError):
            _validate_objective("just a string")

    def test_non_string_objective_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            _validate_objective({"objective": 42})

    def test_dispatch_rejects_payload_with_unknown_key(self) -> None:
        """The socket layer must refuse unknown objective keys up-front."""
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "open_subagent_tab",
            "args": {
                "name": "s",
                "objective": {"objective": "x", "bogus": True},
            },
        }
        response = asyncio.run(_dispatch(app, request))
        assert "error" in response, response
        app.screen.action_open_subagent_tab.assert_not_called()

    def test_dispatch_rejects_payload_without_objective(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "open_subagent_tab",
            "args": {"name": "s", "objective": {"output_format": "md"}},
        }
        response = asyncio.run(_dispatch(app, request))
        assert "error" in response, response
        app.screen.action_open_subagent_tab.assert_not_called()

    def test_dispatch_accepts_reserved_keys(self) -> None:
        app = _FakeApp()
        request = {
            "cmd": "action",
            "name": "open_subagent_tab",
            "args": {
                "name": "s",
                "objective": {
                    "objective": "x",
                    "output_format": "markdown",
                    "tool_scope": ["Read"],
                    "boundary": "read-only",
                },
            },
        }
        response = asyncio.run(_dispatch(app, request))
        assert response.get("ok") is True, response
        app.screen.action_open_subagent_tab.assert_awaited_once()
