"""PlanWorkerLogPane — scrollable log tail for one plan item.

The worker log pane subscribes to a ``PlanExecutionModel`` (Phase B) via
``subscribe_log(item_id, callback)`` on mount, renders
``ItemLogAppended`` payloads addressed to the current item, and
unsubscribes when the user switches items or the tab unmounts.

The widget is "dumb": it does no file I/O. The callback handed to
``subscribe_log`` turns each streamed chunk into a
``PlanWorkerLogPane.ItemLogAppended`` message, which is the only path
through which text reaches the log.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from textual.message import Message
from textual.widgets import RichLog


__all__ = [
    "ItemLogSubscriber",
    "PlanWorkerLogPane",
]


@runtime_checkable
class ItemLogSubscriber(Protocol):
    """Protocol slice of ``PlanExecutionModel`` used by the log pane."""

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        """Subscribe ``callback`` to item ``item_id``'s log stream.

        Returns an unsubscribe callable. The log pane invokes it when the
        user switches items or the pane unmounts.
        """


class PlanWorkerLogPane(RichLog):
    """Tails one plan item's log by subscribing to the execution model."""

    DEFAULT_CSS = """
    PlanWorkerLogPane {
        height: 1fr;
        background: $surface;
        color: $text;
    }
    """

    class ItemLogAppended(Message):
        """A chunk of log output for a specific plan item."""

        def __init__(self, item_id: int, text: str) -> None:
            super().__init__()
            self.item_id = item_id
            self.text = text

    def __init__(
        self,
        model: ItemLogSubscriber | None = None,
        item_id: int | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            wrap=True,
            highlight=False,
            markup=False,
        )
        self._model = model
        self._item_id = item_id
        self._unsubscribe: Callable[[], None] | None = None
        self._appended: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_item_id(self, item_id: int | None) -> None:
        """Switch the pane to a new item (unsubscribes the previous one)."""
        if item_id == self._item_id:
            return
        self._teardown_subscription()
        self.clear()
        self._appended.clear()
        self._item_id = item_id
        self._setup_subscription()

    @property
    def item_id(self) -> int | None:
        return self._item_id

    def plain_text(self) -> str:
        """Plain text of the log contents — useful for assertions."""
        return "\n".join(self._appended)

    # ------------------------------------------------------------------
    # Textual lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._setup_subscription()

    def on_unmount(self) -> None:
        self._teardown_subscription()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def on_plan_worker_log_pane_item_log_appended(
        self, event: ItemLogAppended
    ) -> None:
        if event.item_id != self._item_id:
            return
        self._appended.append(event.text)
        self.write(event.text)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _setup_subscription(self) -> None:
        if self._model is None or self._item_id is None:
            return
        target = self._item_id

        def _callback(text: str) -> None:
            self.post_message(self.ItemLogAppended(target, text))

        self._unsubscribe = self._model.subscribe_log(target, _callback)

    def _teardown_subscription(self) -> None:
        if self._unsubscribe is None:
            return
        try:
            self._unsubscribe()
        finally:
            self._unsubscribe = None
