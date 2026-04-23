"""FilterToolbar — status/milestone/priority selects + refresh button.

Posts a :class:`FilterToolbar.FiltersChanged` message whenever a selection
changes, and :class:`FilterToolbar.RefreshRequested` when the refresh
button is pressed.

Also exposes a module-level :func:`filter_tasks` predicate used both by the
Tasks pane and by unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Button, Input, Select

from toad.widgets.github_views.task_provider import TaskItem
from toad.widgets.github_views.timeline_provider import ItemStatus, Priority

_ANY = "__any__"
_ACTIVE = "__active__"  # Active = Todo + In progress (default, excludes Done)

_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Active (default)", _ACTIVE),
    ("All statuses", _ANY),
    ("Todo", ItemStatus.TODO.value),
    ("In progress", ItemStatus.IN_PROGRESS.value),
    ("Done", ItemStatus.DONE.value),
)

_PRIORITY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("All priorities", _ANY),
    ("P1", "1"),
    ("P2", "2"),
    ("P3", "3"),
    ("P4", "4"),
)


def filter_tasks(
    tasks: Iterable[TaskItem],
    *,
    status: ItemStatus | None = None,
    milestone_id: str | None = None,
    priority: Priority | None = None,
    title_query: str | None = None,
    type_filter: str | None = None,
    exclude_done: bool = False,
) -> list[TaskItem]:
    """Return the subset of ``tasks`` matching all non-None filters.

    ``type_filter`` matches against labels of the form ``type:<value>``
    (case-insensitive). Pass ``"plan"`` to return only tasks labelled
    ``type:plan``. The special value ``"all"`` or ``None`` disables the
    type filter.

    ``exclude_done`` drops DONE tasks when no explicit status is set.
    Ignored when ``status`` is provided (explicit wins).
    """
    query = (title_query or "").strip().lower() or None
    type_needle = _normalize_type(type_filter)
    result: list[TaskItem] = []
    for task in tasks:
        if status is not None:
            if task.status is not status:
                continue
        elif exclude_done and task.status is ItemStatus.DONE:
            continue
        if milestone_id is not None and task.milestone_id != milestone_id:
            continue
        if priority is not None and task.priority is not priority:
            continue
        if query is not None and query not in task.title.lower():
            continue
        if type_needle is not None and not _task_has_type(task, type_needle):
            continue
        result.append(task)
    return result


def _normalize_type(raw: str | None) -> str | None:
    if not raw:
        return None
    lower = raw.strip().lower()
    if lower in ("", "all"):
        return None
    return lower


def _task_has_type(task: TaskItem, needle: str) -> bool:
    # "pr" is special — it matches the is_pr flag rather than a label.
    if needle == "pr":
        return task.is_pr
    # For all other types, issues only (exclude PRs unless asked for them).
    if task.is_pr:
        return False
    prefix = f"type:{needle}"
    return any(lbl.lower() == prefix for lbl in task.labels)


@dataclass(frozen=True)
class FilterState:
    """Snapshot of the toolbar's current filter selections."""

    status: ItemStatus | None = None
    milestone_id: str | None = None
    priority: Priority | None = None
    title_query: str | None = None
    type_filter: str | None = None
    exclude_done: bool = True  # Default: hide Done tasks


class FilterToolbar(Vertical):
    """Two-row filter toolbar: primary controls on top, type chips below."""

    DEFAULT_CSS = """
    FilterToolbar {
        height: auto;
        padding: 0 1;
    }
    FilterToolbar #filter-primary-row {
        height: auto;
    }
    FilterToolbar #filter-primary-row > Select {
        width: 1fr;
        margin-right: 1;
    }
    FilterToolbar #filter-primary-row > Input {
        width: 1fr;
        margin-right: 1;
    }
    FilterToolbar #filter-primary-row > Button {
        width: auto;
    }
    FilterToolbar #filter-chip-row {
        height: auto;
        padding: 0 0 0 0;
    }
    FilterToolbar #filter-chip-row > Button {
        min-width: 10;
        height: 1;
        margin-right: 1;
        border: none;
        background: $surface;
        color: $text-muted;
    }
    FilterToolbar #filter-chip-row > Button.active {
        background: $primary 30%;
        color: $text;
        text-style: bold;
    }
    """

    _TYPE_CHIPS: tuple[tuple[str, str], ...] = (
        ("All", "all"),
        ("Plans", "plan"),
        ("PRs", "pr"),
        ("Bugs", "bug"),
        ("Features", "feature"),
    )

    class FiltersChanged(Message):
        """Emitted when any select value changes."""

        def __init__(self, state: FilterState) -> None:
            super().__init__()
            self.state = state

    class RefreshRequested(Message):
        """Emitted when the refresh button is pressed."""

    def __init__(
        self,
        milestones: Iterable[tuple[str, str]] = (),
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._milestones: list[tuple[str, str]] = list(milestones)

    def compose(self) -> ComposeResult:
        with Horizontal(id="filter-primary-row"):
            yield Select(
                options=list(_STATUS_OPTIONS),
                value=_ACTIVE,
                allow_blank=False,
                id="filter-status",
            )
            yield Select(
                options=self._milestone_options(),
                value=_ANY,
                allow_blank=False,
                id="filter-milestone",
            )
            yield Select(
                options=list(_PRIORITY_OPTIONS),
                value=_ANY,
                allow_blank=False,
                id="filter-priority",
            )
            yield Input(
                placeholder="Filter title… (press / to focus)",
                id="filter-title",
            )
            yield Button("Refresh", id="filter-refresh", variant="primary")
        with Horizontal(id="filter-chip-row"):
            for label, value in self._TYPE_CHIPS:
                btn = Button(label, id=f"chip-type-{value}")
                if value == "all":
                    btn.add_class("active")
                yield btn

    def set_milestones(self, milestones: Iterable[tuple[str, str]]) -> None:
        """Replace the milestone dropdown's options while preserving selection.

        Suppresses ``Select.Changed`` during the swap so programmatic option
        resets don't masquerade as user input.
        """
        self._milestones = list(milestones)
        try:
            select = self.query_one("#filter-milestone", Select)
        except NoMatches:
            return
        current = select.value
        with self.prevent(Select.Changed):
            select.set_options(self._milestone_options())
            if current != Select.BLANK and current in {
                v for _, v in self._milestone_options()
            }:
                select.value = current
            else:
                select.value = _ANY

    def focus_title_input(self) -> None:
        """Move focus to the title-query input (called by ``/`` binding)."""
        try:
            self.query_one("#filter-title", Input).focus()
        except NoMatches:
            return

    def current_state(self) -> FilterState:
        """Read the current filter selections."""
        raw_status = self._value("#filter-status")
        status, exclude_done = _to_status_and_flag(raw_status)
        return FilterState(
            status=status,
            milestone_id=_to_milestone(self._value("#filter-milestone")),
            priority=_to_priority(self._value("#filter-priority")),
            title_query=self._title_query(),
            type_filter=self._active_type_chip(),
            exclude_done=exclude_done,
        )

    def _active_type_chip(self) -> str | None:
        """Return the value of the currently-active type chip."""
        for _, value in self._TYPE_CHIPS:
            try:
                btn = self.query_one(f"#chip-type-{value}", Button)
            except NoMatches:
                continue
            if "active" in btn.classes:
                return None if value == "all" else value
        return None

    def set_active_type(self, value: str) -> None:
        """Activate the chip matching ``value`` (e.g. 'plan', 'all')."""
        normalized = value.lower() if value else "all"
        for _, v in self._TYPE_CHIPS:
            try:
                btn = self.query_one(f"#chip-type-{v}", Button)
            except NoMatches:
                continue
            if v == normalized:
                btn.add_class("active")
            else:
                btn.remove_class("active")

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        self.post_message(self.FiltersChanged(self.current_state()))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "filter-title":
            return
        event.stop()
        self.post_message(self.FiltersChanged(self.current_state()))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "filter-refresh":
            event.stop()
            self.post_message(self.RefreshRequested())
            return
        if btn_id.startswith("chip-type-"):
            event.stop()
            value = btn_id.removeprefix("chip-type-")
            self.set_active_type(value)
            self.post_message(self.FiltersChanged(self.current_state()))

    def _milestone_options(self) -> list[tuple[str, str]]:
        return [("All milestones", _ANY), *self._milestones]

    def _value(self, selector: str) -> str | None:
        try:
            select = self.query_one(selector, Select)
        except NoMatches:
            return None
        value = select.value
        if value == Select.BLANK:
            return None
        return str(value)

    def _title_query(self) -> str | None:
        try:
            query = self.query_one("#filter-title", Input).value
        except NoMatches:
            return None
        query = query.strip()
        return query or None


def _to_status_and_flag(raw: str | None) -> tuple[ItemStatus | None, bool]:
    """Parse the status Select value into (status, exclude_done).

    - ``__active__`` → (None, True)   # Todo + In progress
    - ``__any__``    → (None, False)  # include Done
    - specific value → (ItemStatus.X, False)
    - unknown        → (None, True)   # fall back to Active default
    """
    if raw is None or raw == _ACTIVE:
        return (None, True)
    if raw == _ANY:
        return (None, False)
    try:
        return (ItemStatus(raw), False)
    except ValueError:
        return (None, True)


def _to_status(raw: str | None) -> ItemStatus | None:
    """Legacy helper — still used elsewhere. Returns only the status."""
    return _to_status_and_flag(raw)[0]


def _to_priority(raw: str | None) -> Priority | None:
    if raw is None or raw == _ANY:
        return None
    try:
        return Priority(int(raw))
    except (ValueError, TypeError):
        return None


def _to_milestone(raw: str | None) -> str | None:
    if raw is None or raw == _ANY:
        return None
    return raw
