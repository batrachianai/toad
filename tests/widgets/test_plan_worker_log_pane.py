"""Tests for the ``PlanWorkerLogPane`` widget.

The worker log pane tails a single plan item's log inside a
``PlanExecutionTab``. It does not read files directly — it subscribes
to a ``PlanExecutionModel`` (Phase B) via ``subscribe_log(item_id,
callback)`` and renders ``ItemLogAppended`` payloads that either the
callback or the owning tab posts to it.

These tests drive:

- Subscribes on mount (calls ``model.subscribe_log`` with the item id).
- Unsubscribes on item switch (the returned unsubscribe is invoked and a
  fresh subscribe runs for the new id).
- Appends ``ItemLogAppended`` payloads addressed to the current item to
  the log, ignoring payloads for other items.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from textual.app import App, ComposeResult

from toad.widgets.plan_worker_log_pane import PlanWorkerLogPane


@dataclass
class _Subscription:
    item_id: int
    callback: Callable[[str], None]
    unsubscribed: bool = False


@dataclass
class _FakeModel:
    """Stand-in for ``PlanExecutionModel`` with ``subscribe_log`` only."""

    subscriptions: list[_Subscription] = field(default_factory=list)

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        sub = _Subscription(item_id=item_id, callback=callback)
        self.subscriptions.append(sub)

        def _unsubscribe() -> None:
            sub.unsubscribed = True

        return _unsubscribe

    def active(self) -> list[_Subscription]:
        return [s for s in self.subscriptions if not s.unsubscribed]


class _Harness(App[None]):
    def __init__(self, model: _FakeModel, item_id: int | None) -> None:
        super().__init__()
        self._model = model
        self._item_id = item_id

    def compose(self) -> ComposeResult:
        yield PlanWorkerLogPane(
            model=self._model, item_id=self._item_id, id="log"
        )


# ------------------------------------------------------------------
# Subscription lifecycle
# ------------------------------------------------------------------


class TestSubscription:
    @pytest.mark.asyncio
    async def test_subscribes_on_mount(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert len(model.subscriptions) == 1
            assert model.subscriptions[0].item_id == 3
            assert not model.subscriptions[0].unsubscribed

    @pytest.mark.asyncio
    async def test_no_subscription_when_item_id_is_none(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=None)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert model.subscriptions == []

    @pytest.mark.asyncio
    async def test_switch_item_unsubscribes_old_and_subscribes_new(
        self,
    ) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            pane.set_item_id(5)
            await pilot.pause()
            assert len(model.subscriptions) == 2
            assert model.subscriptions[0].item_id == 3
            assert model.subscriptions[0].unsubscribed is True
            assert model.subscriptions[1].item_id == 5
            assert model.subscriptions[1].unsubscribed is False

    @pytest.mark.asyncio
    async def test_setting_same_item_id_is_noop(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            pane.set_item_id(3)
            await pilot.pause()
            assert len(model.subscriptions) == 1
            assert model.subscriptions[0].unsubscribed is False

    @pytest.mark.asyncio
    async def test_unmount_unsubscribes(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert model.active()
        # After the app exits, the pane is unmounted.
        assert model.subscriptions[0].unsubscribed is True


# ------------------------------------------------------------------
# ItemLogAppended → log contents
# ------------------------------------------------------------------


class TestAppending:
    @pytest.mark.asyncio
    async def test_appends_payload_for_current_item(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            pane.post_message(
                PlanWorkerLogPane.ItemLogAppended(3, "hello world")
            )
            await pilot.pause()
            text = pane.plain_text()
            assert "hello world" in text

    @pytest.mark.asyncio
    async def test_multiple_appends_preserve_order(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            for line in ("first", "second", "third"):
                pane.post_message(
                    PlanWorkerLogPane.ItemLogAppended(3, line)
                )
            await pilot.pause()
            text = pane.plain_text()
            assert text.index("first") < text.index("second") < text.index(
                "third"
            )

    @pytest.mark.asyncio
    async def test_ignores_payloads_for_other_items(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            pane.post_message(
                PlanWorkerLogPane.ItemLogAppended(99, "noise")
            )
            pane.post_message(
                PlanWorkerLogPane.ItemLogAppended(3, "signal")
            )
            await pilot.pause()
            text = pane.plain_text()
            assert "signal" in text
            assert "noise" not in text

    @pytest.mark.asyncio
    async def test_switch_clears_old_lines(self) -> None:
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            pane.post_message(
                PlanWorkerLogPane.ItemLogAppended(3, "old-line")
            )
            await pilot.pause()
            assert "old-line" in pane.plain_text()

            pane.set_item_id(5)
            await pilot.pause()
            assert "old-line" not in pane.plain_text()

    @pytest.mark.asyncio
    async def test_subscribe_callback_drives_appending(self) -> None:
        """Callback handed to ``subscribe_log`` must append to the pane."""
        model = _FakeModel()
        app = _Harness(model, item_id=3)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(PlanWorkerLogPane)
            assert model.subscriptions
            model.subscriptions[0].callback("streamed-line")
            await pilot.pause()
            assert "streamed-line" in pane.plain_text()
