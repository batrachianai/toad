"""TaskTable — DataTable master listing project-board items.

Subclasses ``DataTable`` with ``cursor_type="row"``. Row keys are the
``TaskItem.id`` string so selection events round-trip back to the
owning task via ``event.row_key.value``.

Columns are **contextual** — the caller picks a ``ColumnSet`` that
matches the active type-chip filter (All, Plans, PRs, Bugs, Features).
Switching the column set on the fly clears the existing columns and
re-renders the rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rich.text import Text
from textual.widgets import DataTable

from toad.widgets.github_views.task_provider import TaskItem
from toad.widgets.github_views.timeline_provider import ItemStatus, Priority

_STATUS_LABELS: dict[ItemStatus, str] = {
    ItemStatus.TODO: "Todo",
    ItemStatus.IN_PROGRESS: "In Progress",
    ItemStatus.DONE: "Done",
}

_PRIORITY_LABELS: dict[Priority, str] = {
    Priority.P1: "P1",
    Priority.P2: "P2",
    Priority.P3: "P3",
    Priority.P4: "P4",
}


# Named column sets per active chip. Keys match the chip values in
# FilterToolbar._TYPE_CHIPS. The first entry in each tuple is the column
# header; the second is a lambda (task) → cell string.
COLUMN_SETS: dict[str, tuple[tuple[str, Any], ...]] = {
    "all": (
        ("#", lambda t: f"#{t.number}"),
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 55)),
        ("Milestone", lambda t: t.milestone_title),
        ("Priority", lambda t: _format_priority(t.priority)),
        ("Assignee", lambda t: _format_assignees(t.assignees)),
    ),
    "plan": (
        ("#", lambda t: f"#{t.number}"),
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 45)),
        ("Progress", lambda t: _format_progress(t.progress_pct)),
        ("Milestone", lambda t: t.milestone_title),
        ("Priority", lambda t: _format_priority(t.priority)),
    ),
    "pr": (
        ("#", lambda t: f"#{t.number}"),
        ("Title", lambda t: _truncate(t.title, 45)),
        ("Review", lambda t: _format_review(t.review_state)),
        ("CI", lambda t: _format_ci(t.ci_state)),
        ("Age", lambda t: _format_age(t.created_at)),
        ("Author", lambda t: t.author or ""),
    ),
    "bug": (
        ("#", lambda t: f"#{t.number}"),
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 50)),
        ("Priority", lambda t: _format_priority(t.priority)),
        ("Assignee", lambda t: _format_assignees(t.assignees)),
        ("Age", lambda t: _format_age(t.created_at)),
    ),
    "feature": (
        ("#", lambda t: f"#{t.number}"),
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 50)),
        ("Milestone", lambda t: t.milestone_title),
        ("Priority", lambda t: _format_priority(t.priority)),
        ("Assignee", lambda t: _format_assignees(t.assignees)),
    ),
}


def _format_status(status: ItemStatus) -> str:
    return _STATUS_LABELS.get(status, status.value)


def _format_priority(priority: Priority | None) -> str:
    if priority is None:
        return ""
    return _PRIORITY_LABELS.get(priority, "")


def _format_assignees(assignees: list[str]) -> str:
    if not assignees:
        return ""
    if len(assignees) == 1:
        return assignees[0]
    return f"{assignees[0]} +{len(assignees) - 1}"


def _format_progress(pct: int | None) -> str:
    if pct is None:
        return "—"
    filled = round(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{bar} {pct:>3}%"


def _format_review(state: str | None) -> str:
    if not state:
        return ""
    mapping = {
        "APPROVED": "✓ approved",
        "CHANGES_REQUESTED": "✗ changes",
        "REVIEW_REQUIRED": "… needed",
        "COMMENTED": "· comment",
    }
    return mapping.get(state, state.lower())


def _format_ci(state: str | None) -> str:
    if not state:
        return ""
    mapping = {
        "SUCCESS": "✓ pass",
        "FAILURE": "✗ fail",
        "PENDING": "… run",
        "NONE": "",
    }
    return mapping.get(state, state.lower())


def _format_age(created: datetime | None) -> str:
    if created is None:
        return ""
    now = datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = now - created
    days = delta.days
    if days < 1:
        hours = delta.seconds // 3600
        return f"{hours}h"
    if days < 30:
        return f"{days}d"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


class TaskTable(DataTable[str]):
    """DataTable listing ``TaskItem`` rows keyed by issue id.

    Column layout is chosen via :meth:`set_column_set`. Call it before
    :meth:`set_tasks` (or in any order — the table re-renders).
    """

    DEFAULT_CSS = """
    TaskTable {
        height: 1fr;
    }
    """

    # Cells whose value changed between two ``set_tasks`` calls render
    # with this background style for ``_FLASH_SECONDS`` so the eye
    # catches the diff. Tuned to be visible on both light and dark
    # themes without screaming.
    _FLASH_STYLE = "on rgb(60,60,20)"
    _FLASH_SECONDS = 1.5

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(zebra_stripes=True, **kwargs)
        self.cursor_type = "row"
        self._tasks: dict[str, TaskItem] = {}
        self._task_order: list[str] = []
        self._column_set: str = "all"
        self._previous_cells: dict[str, list[str]] = {}
        self._flash_cells: set[tuple[str, int]] = set()
        self._flash_timer: Any = None

    def set_column_set(self, name: str) -> None:
        """Switch the visible columns to ``COLUMN_SETS[name]`` and re-render."""
        if name not in COLUMN_SETS:
            name = "all"
        if name == self._column_set and self.columns:
            return
        self._column_set = name
        self.clear(columns=True)
        headers = tuple(h for h, _ in COLUMN_SETS[name])
        self.add_columns(*headers)
        if self._tasks:
            self._rerender_rows()

    def set_tasks(self, tasks: list[TaskItem]) -> None:
        """Replace all rows with ``tasks``. Row keys = ``task.id``."""
        formatters = COLUMN_SETS[self._column_set]
        new_cells = {t.id: [fmt(t) for _, fmt in formatters] for t in tasks}

        # Flash only when we have a previous snapshot to diff against.
        # The first ``set_tasks`` call after mount/column-switch
        # populates the baseline silently — flashing every cell on
        # initial load would be useless noise.
        flash: set[tuple[str, int]] = set()
        if self._previous_cells:
            for task_id, cells in new_cells.items():
                prev = self._previous_cells.get(task_id)
                if prev is None:
                    continue  # newly-added rows aren't a "change"
                for col, (old, new) in enumerate(zip(prev, cells, strict=False)):
                    if old != new:
                        flash.add((task_id, col))

        self._tasks = {t.id: t for t in tasks}
        self._task_order = [t.id for t in tasks]
        self._previous_cells = new_cells
        self._flash_cells = flash

        if not self.columns:
            self.set_column_set(self._column_set)
            return
        self._rerender_rows()
        self._schedule_flash_clear()

    def _rerender_rows(self) -> None:
        self.clear()
        formatters = COLUMN_SETS[self._column_set]
        for task_id in self._task_order:
            task = self._tasks.get(task_id)
            if task is None:
                continue
            cells: list[Any] = []
            for col, (_, fmt) in enumerate(formatters):
                value = fmt(task)
                if (task_id, col) in self._flash_cells:
                    cells.append(Text(str(value), style=self._FLASH_STYLE))
                else:
                    cells.append(value)
            self.add_row(*cells, key=task.id)

    def _schedule_flash_clear(self) -> None:
        if not self._flash_cells:
            return
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self._flash_timer = self.set_timer(
            self._FLASH_SECONDS, self._clear_flash
        )

    def _clear_flash(self) -> None:
        if not self._flash_cells:
            return
        self._flash_cells.clear()
        self._flash_timer = None
        if self.columns:
            self._rerender_rows()

    def get_task(self, task_id: str) -> TaskItem | None:
        """Return the ``TaskItem`` previously set for ``task_id``."""
        return self._tasks.get(task_id)
