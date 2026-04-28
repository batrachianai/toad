"""Tests for synthetic subagent completion message injection (TDD, item 5).

Contract under test
-------------------

When a subagent's ``Agent`` reaches its ``done_event`` (subprocess exits,
user closes the tab, or the subagent session otherwise ends), a synthetic
**user-role** message is posted to the Conductor's ACP session with the
format::

    [subagent <name> completed: <summary>]

That format comes from ``docs/subagent-tabs-brief.md``::

    [subagent Strategy completed: <final assistant message or summary>]

Item 6 must add two helpers to ``src/toad/acp/agent.py``:

- ``inject_subagent_completion(conductor, name, summary)`` — synchronous
  contract: format the message and deliver it to the Conductor's session
  as a user-role prompt (``conductor.send_prompt(...)``).
- ``watch_subagent_completion(subagent, conductor, name, summary_provider=None)``
  — await ``subagent.done_event``, then call
  ``inject_subagent_completion`` with the summary returned by
  ``summary_provider()`` (or ``""`` if none).

These tests are intentionally red today and turn green when item 6
lands.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

# ``toad.acp.agent`` and ``toad.acp.messages`` form a tight circular import
# pair. Importing ``agent`` in isolation fails with a partially-initialized
# module error; the working order is ``messages`` first. Pre-load it here so
# every direct ``from toad.acp import agent`` inside a test succeeds.
from toad.acp import messages as _messages  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers / test doubles
# ---------------------------------------------------------------------------


def _fake_conductor() -> Any:
    """Minimal stand-in for the Conductor ``Agent``.

    We only rely on the public ``send_prompt`` coroutine — that is the
    canonical way to deliver a user-role message into an ACP session.
    """
    conductor = SimpleNamespace()
    conductor.send_prompt = AsyncMock(return_value=None)
    return conductor


def _fake_subagent() -> Any:
    """Minimal stand-in for a subagent ``Agent``.

    The real class sets ``self.done_event = asyncio.Event()`` in
    ``__init__``; the hook only reads that attribute.
    """
    return SimpleNamespace(done_event=asyncio.Event())


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


class TestModuleSurface:
    """``toad.acp.agent`` must expose the two completion-hook helpers."""

    def test_inject_subagent_completion_exists(self) -> None:
        from toad.acp import agent

        assert hasattr(agent, "inject_subagent_completion"), (
            "item 6 must add inject_subagent_completion to toad.acp.agent"
        )

    def test_watch_subagent_completion_exists(self) -> None:
        from toad.acp import agent

        assert hasattr(agent, "watch_subagent_completion"), (
            "item 6 must add watch_subagent_completion to toad.acp.agent"
        )


# ---------------------------------------------------------------------------
# inject_subagent_completion — message formatting + routing
# ---------------------------------------------------------------------------


class TestInjectSubagentCompletion:
    """The injector must deliver the synthetic message to the Conductor."""

    @pytest.mark.asyncio
    async def test_sends_user_role_prompt_to_conductor(self) -> None:
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        await inject_subagent_completion(conductor, "Strategy", "found the answer")

        conductor.send_prompt.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_format_matches_brief(self) -> None:
        """Message format: ``[subagent <name> completed: <summary>]``."""
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        await inject_subagent_completion(conductor, "Strategy", "found the answer")

        (prompt,), _ = conductor.send_prompt.await_args
        assert prompt == "[subagent Strategy completed: found the answer]"

    @pytest.mark.asyncio
    async def test_empty_summary_still_produces_valid_message(self) -> None:
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        await inject_subagent_completion(conductor, "Strategy", "")

        (prompt,), _ = conductor.send_prompt.await_args
        assert prompt.startswith("[subagent Strategy completed:")
        assert prompt.endswith("]")

    @pytest.mark.asyncio
    async def test_name_with_spaces_is_preserved(self) -> None:
        """Duplicate-suffix names like ``Strategy 2`` must flow through verbatim."""
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        await inject_subagent_completion(conductor, "Strategy 2", "done")

        (prompt,), _ = conductor.send_prompt.await_args
        assert prompt == "[subagent Strategy 2 completed: done]"

    @pytest.mark.asyncio
    async def test_multiline_summary_is_preserved(self) -> None:
        """The brief allows the subagent's final message as summary."""
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        summary = "line one\nline two"
        await inject_subagent_completion(conductor, "Strategy", summary)

        (prompt,), _ = conductor.send_prompt.await_args
        assert "line one" in prompt
        assert "line two" in prompt
        assert prompt.startswith("[subagent Strategy completed:")

    @pytest.mark.asyncio
    async def test_each_subagent_gets_its_own_message(self) -> None:
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        await inject_subagent_completion(conductor, "Strategy", "s-done")
        await inject_subagent_completion(conductor, "CanonCLI", "c-done")

        assert conductor.send_prompt.await_count == 2
        prompts = [call.args[0] for call in conductor.send_prompt.await_args_list]
        assert prompts == [
            "[subagent Strategy completed: s-done]",
            "[subagent CanonCLI completed: c-done]",
        ]


# ---------------------------------------------------------------------------
# watch_subagent_completion — the done_event → inject wiring
# ---------------------------------------------------------------------------


class TestWatchSubagentCompletion:
    """The watcher awaits ``done_event`` and then injects the notice."""

    @pytest.mark.asyncio
    async def test_no_message_before_done_event(self) -> None:
        from toad.acp.agent import watch_subagent_completion

        subagent = _fake_subagent()
        conductor = _fake_conductor()

        task = asyncio.create_task(
            watch_subagent_completion(subagent, conductor, "Strategy")
        )
        # Give the event loop a chance to schedule the watcher.
        await asyncio.sleep(0)
        assert conductor.send_prompt.await_count == 0
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_message_posted_when_done_event_fires(self) -> None:
        from toad.acp.agent import watch_subagent_completion

        subagent = _fake_subagent()
        conductor = _fake_conductor()

        task = asyncio.create_task(
            watch_subagent_completion(
                subagent, conductor, "Strategy",
                summary_provider=lambda: "research complete",
            )
        )
        await asyncio.sleep(0)
        subagent.done_event.set()
        await asyncio.wait_for(task, timeout=1.0)

        conductor.send_prompt.assert_awaited_once_with(
            "[subagent Strategy completed: research complete]"
        )

    @pytest.mark.asyncio
    async def test_no_summary_provider_yields_empty_summary(self) -> None:
        from toad.acp.agent import watch_subagent_completion

        subagent = _fake_subagent()
        conductor = _fake_conductor()

        task = asyncio.create_task(
            watch_subagent_completion(subagent, conductor, "Strategy")
        )
        await asyncio.sleep(0)
        subagent.done_event.set()
        await asyncio.wait_for(task, timeout=1.0)

        (prompt,), _ = conductor.send_prompt.await_args
        assert prompt == "[subagent Strategy completed: ]"

    @pytest.mark.asyncio
    async def test_summary_provider_is_called_after_done(self) -> None:
        """Provider must run AFTER ``done_event`` — it typically reads the
        subagent's final transcript line, which only exists once the run
        has finished."""
        from toad.acp.agent import watch_subagent_completion

        subagent = _fake_subagent()
        conductor = _fake_conductor()
        call_order: list[str] = []

        def provider() -> str:
            call_order.append("provider")
            return "after-done"

        original_set = subagent.done_event.set

        def tagged_set() -> None:
            call_order.append("done")
            original_set()

        subagent.done_event.set = tagged_set  # type: ignore[method-assign]

        task = asyncio.create_task(
            watch_subagent_completion(
                subagent, conductor, "Strategy", summary_provider=provider
            )
        )
        await asyncio.sleep(0)
        subagent.done_event.set()
        await asyncio.wait_for(task, timeout=1.0)

        # "done" must appear before "provider" in the call order.
        assert call_order.index("done") < call_order.index("provider")

    @pytest.mark.asyncio
    async def test_multiple_watchers_fire_independently(self) -> None:
        from toad.acp.agent import watch_subagent_completion

        sub_a = _fake_subagent()
        sub_b = _fake_subagent()
        conductor = _fake_conductor()

        task_a = asyncio.create_task(
            watch_subagent_completion(sub_a, conductor, "Strategy",
                                      summary_provider=lambda: "A-done")
        )
        task_b = asyncio.create_task(
            watch_subagent_completion(sub_b, conductor, "CanonCLI",
                                      summary_provider=lambda: "B-done")
        )
        await asyncio.sleep(0)

        sub_b.done_event.set()
        await asyncio.wait_for(task_b, timeout=1.0)
        assert conductor.send_prompt.await_count == 1
        assert conductor.send_prompt.await_args.args[0] == (
            "[subagent CanonCLI completed: B-done]"
        )

        sub_a.done_event.set()
        await asyncio.wait_for(task_a, timeout=1.0)
        assert conductor.send_prompt.await_count == 2
        prompts = [c.args[0] for c in conductor.send_prompt.await_args_list]
        assert prompts == [
            "[subagent CanonCLI completed: B-done]",
            "[subagent Strategy completed: A-done]",
        ]


# ---------------------------------------------------------------------------
# Regression anchor: message shape is greppable
# ---------------------------------------------------------------------------


class TestMessageShape:
    """A plain-text anchor so the format can be grepped from logs."""

    @pytest.mark.asyncio
    async def test_prefix_is_fixed(self) -> None:
        from toad.acp.agent import inject_subagent_completion

        conductor = _fake_conductor()
        await inject_subagent_completion(conductor, "X", "y")
        prompt = conductor.send_prompt.await_args.args[0]
        assert prompt.startswith("[subagent ")
        assert " completed: " in prompt
        assert prompt.endswith("]")
