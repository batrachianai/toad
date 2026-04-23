"""TaskDetail widget — ContentSwitcher between an empty state and task detail.

Master-detail partner of :class:`toad.widgets.task_table.TaskTable`. The
table calls :meth:`TaskDetail.show_task` on row selection to render the
selected task's metadata immediately; body + comments are populated via
:meth:`TaskDetail.show_details` once the async fetch completes.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Collapsible, ContentSwitcher, Markdown, Static

from toad.widgets.github_views.task_provider import TaskDetailData, TaskItem

_EMPTY_ID = "empty"
_DETAIL_ID = "detail"


class TaskDetail(Container):
    """Detail pane for the Tasks widget.

    Holds a :class:`ContentSwitcher` with two children:

    * an empty-state placeholder shown before any row is selected,
    * a detail view with the task title, rendered Markdown body, and a
      :class:`Collapsible` metadata panel exposing labels, dates, linked
      PRs, and a "View comments" button that pushes the drill-down
      screen.
    """

    DEFAULT_CSS = """
    TaskDetail {
        height: 1fr;
        width: 1fr;
    }
    TaskDetail ContentSwitcher {
        height: 1fr;
    }
    TaskDetail #detail {
        padding: 1 2;
    }
    TaskDetail .task-detail-title {
        text-style: bold;
        padding-bottom: 1;
    }
    TaskDetail .task-detail-empty {
        content-align: center middle;
        color: $text-muted;
        height: 1fr;
    }
    TaskDetail Button {
        margin-top: 1;
    }
    """

    class DrillDownRequested(Message):
        """Emitted when the user activates "View comments"."""

        def __init__(self, task: TaskItem) -> None:
            super().__init__()
            self.task = task

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._task_item: TaskItem | None = None
        self._details: TaskDetailData | None = None

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial=_EMPTY_ID):
            yield Static(
                "Select a task to see details.",
                id=_EMPTY_ID,
                classes="task-detail-empty",
            )
            with VerticalScroll(id=_DETAIL_ID):
                yield Static("", id="task-detail-title", classes="task-detail-title")
                yield Static("", id="task-detail-summary")
                yield Markdown("", id="task-detail-body")
                with Collapsible(title="Metadata", id="task-detail-meta"):
                    yield Static("", id="task-detail-meta-body")
                yield Button(
                    "View comments",
                    id="task-detail-view-comments",
                    variant="primary",
                )

    def show_task(self, task: TaskItem) -> None:
        """Render immediate task metadata and switch to the detail view."""
        self._task_item = task
        self._details = None
        self.query_one("#task-detail-title", Static).update(
            f"#{task.number} — {task.title}"
        )
        self.query_one("#task-detail-summary", Static).update(
            _render_summary(task)
        )
        self.query_one("#task-detail-body", Markdown).update(
            "_Loading body…_"
        )
        self.query_one("#task-detail-meta-body", Static).update(
            _render_meta(task, None)
        )
        self.query_one(ContentSwitcher).current = _DETAIL_ID

    def show_details(self, details: TaskDetailData) -> None:
        """Render the lazy-loaded body + linked PRs once available."""
        self._details = details
        self.query_one("#task-detail-body", Markdown).update(
            details.body or "_(no description)_"
        )
        self.query_one("#task-detail-meta-body", Static).update(
            _render_meta(self._task_item, details)
        )

    def clear(self) -> None:
        """Reset back to the empty state."""
        self._task_item = None
        self._details = None
        self.query_one(ContentSwitcher).current = _EMPTY_ID

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Drill into the full-screen detail view on "View comments"."""
        if event.button.id != "task-detail-view-comments":
            return
        if self._task_item is None:
            return
        event.stop()
        self.post_message(self.DrillDownRequested(self._task_item))


def _render_summary(task: TaskItem) -> str:
    """Short one-line metadata summary shown above the body."""
    parts: list[str] = [f"status: {task.status.value}"]
    if task.milestone_title:
        parts.append(f"milestone: {task.milestone_title}")
    if task.priority is not None:
        parts.append(f"priority: {task.priority.value}")
    if task.assignees:
        parts.append(f"assignees: {', '.join(task.assignees)}")
    if task.effort:
        parts.append(f"effort: {task.effort}")
    return "  ·  ".join(parts)


def _render_meta(
    task: TaskItem | None, details: TaskDetailData | None
) -> str:
    """Multi-line metadata block for the Collapsible panel."""
    if task is None:
        return ""
    lines: list[str] = []
    if task.labels:
        lines.append(f"labels: {', '.join(task.labels)}")
    if task.start_date:
        lines.append(f"start: {task.start_date.isoformat()}")
    if task.target_date:
        lines.append(f"target: {task.target_date.isoformat()}")
    if task.created_at:
        lines.append(f"created: {task.created_at.date().isoformat()}")
    if task.updated_at:
        lines.append(f"updated: {task.updated_at.date().isoformat()}")
    comments = details.comments_count if details else task.comments_count
    lines.append(f"comments: {comments}")
    if details and details.linked_prs:
        pr_refs = ", ".join(
            f"#{pr.get('number')}" for pr in details.linked_prs if pr.get("number")
        )
        lines.append(f"linked PRs: {pr_refs}")
    if task.url:
        lines.append(f"url: {task.url}")
    return "\n".join(lines)
