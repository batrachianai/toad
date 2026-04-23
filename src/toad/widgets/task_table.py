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
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 60)),
        ("Milestone", lambda t: t.milestone_title),
        ("Priority", lambda t: _format_priority(t.priority)),
        ("Assignee", lambda t: _format_assignees(t.assignees)),
    ),
    "plan": (
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 50)),
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
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 55)),
        ("Priority", lambda t: _format_priority(t.priority)),
        ("Assignee", lambda t: _format_assignees(t.assignees)),
        ("Age", lambda t: _format_age(t.created_at)),
    ),
    "feature": (
        ("Status", lambda t: _format_status(t.status)),
        ("Title", lambda t: _truncate(t.title, 55)),
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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(zebra_stripes=True, **kwargs)
        self.cursor_type = "row"
        self._tasks: dict[str, TaskItem] = {}
        self._task_order: list[str] = []
        self._column_set: str = "all"

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
        self._tasks = {t.id: t for t in tasks}
        self._task_order = [t.id for t in tasks]
        if not self.columns:
            self.set_column_set(self._column_set)
            return
        self._rerender_rows()

    def _rerender_rows(self) -> None:
        self.clear()
        formatters = COLUMN_SETS[self._column_set]
        for task_id in self._task_order:
            task = self._tasks.get(task_id)
            if task is None:
                continue
            self.add_row(*(fmt(task) for _, fmt in formatters), key=task.id)

    def get_task(self, task_id: str) -> TaskItem | None:
        """Return the ``TaskItem`` previously set for ``task_id``."""
        return self._tasks.get(task_id)
