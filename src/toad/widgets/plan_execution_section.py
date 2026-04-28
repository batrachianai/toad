"""PlanExecutionSection — dedicated tabbed section for plan execution tabs.

This widget is a sibling of :class:`SubagentTabSection`: it owns a
``TabbedContent`` that hosts one :class:`PlanExecutionTab` per plan
discovered in ``.orchestrator/master.json``. Tabs persist after their
plan finishes — the user closes them manually.

The section is deliberately minimal: it holds a dedupe set keyed by plan
slug, and an injected ``model_factory`` callable that Phase B (or a
test) supplies to build the per-tab :class:`PlanExecutionModel`. When
no factory is registered the section still mounts but :meth:`open_tab`
is a silent no-op — this lets the view ship before the Phase B model
lands without crashing on live ``master.json`` updates.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static, TabbedContent, TabPane

from toad.widgets.orchestrator_state import PlanSummary, is_stale
from toad.widgets.plan_execution_tab import PlanExecutionModel, PlanExecutionTab


__all__ = [
    "EMPTY_PANE_ID",
    "ModelFactory",
    "PlanExecutionSection",
]


EMPTY_PANE_ID = "plan-exec-empty"
_EMPTY_PANE_TITLE = "Plans"
_EMPTY_PLACEHOLDER_TEXT = (
    "No plan running.\n\n"
    "Start one with:  bash ~/.claude/scripts/orch-run.sh <slug>"
)
_BTN_OPEN_PREFIX = "plan-open-"
_BTN_CRASH_PREFIX = "plan-crash-"
_BTN_REMOVE_PREFIX = "plan-remove-"


log = logging.getLogger(__name__)


ModelFactory = Callable[[str], PlanExecutionModel | None]
"""Signature: ``factory(slug) -> PlanExecutionModel | None``.

Returning ``None`` tells the section to skip this slug (e.g. the plan
directory disappeared between detection and render).
"""


class PlanExecutionSection(Vertical):
    """TabbedContent section that hosts one tab per orchestrator plan."""

    SECTION_ID = "section-plan-execution"

    class PlanCrashRequested(Message):
        """User clicked Mark-crashed on the running-plans list."""

        def __init__(self, slug: str) -> None:
            super().__init__()
            self.slug = slug

    class PlanRemoveRequested(Message):
        """User clicked Remove-from-list on the running-plans list."""

        def __init__(self, slug: str) -> None:
            super().__init__()
            self.slug = slug

    DEFAULT_CSS = """
    PlanExecutionSection {
        display: none;
        height: 1fr;
    }

    PlanExecutionSection TabbedContent {
        height: 1fr;
    }

    PlanExecutionSection .empty-state {
        padding: 1 2;
        color: $text-muted;
    }

    PlanExecutionSection .plan-list-header {
        padding: 1 2 0 2;
        color: $text;
        text-style: bold;
    }

    PlanExecutionSection .plan-list-row {
        height: 1;
        padding: 0 2;
    }

    PlanExecutionSection .plan-list-row Button {
        height: 1;
        min-width: 6;
        margin-right: 1;
        border: none;
        background: $surface;
        color: $text;
    }

    PlanExecutionSection .plan-list-row .plan-status {
        width: 9;
        color: $success;
    }

    PlanExecutionSection .plan-list-row .plan-status.zombie {
        color: $warning;
    }

    PlanExecutionSection .plan-list-row .plan-status.crashed {
        color: $error;
    }
    """

    def __init__(
        self,
        *,
        model_factory: ModelFactory | None = None,
        get_current_agent: Callable[[], str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_factory = model_factory
        self._get_current_agent = get_current_agent
        # Dedupe set keyed by plan slug — prevents duplicate tabs when
        # master.json updates replay the same slug across polls.
        self._open_slugs: set[str] = set()
        # Plans surfaced in the empty-state list (running + zombie only).
        self._listed_plans: list[PlanSummary] = []

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with TabbedContent(id="plan-exec-tabs"):
            yield self._build_empty_pane(self._listed_plans)

    @classmethod
    def _build_empty_pane(
        cls, plans: list[PlanSummary]
    ) -> TabPane:
        body = Vertical(
            *cls._empty_body_widgets(plans),
            id="plan-exec-empty-body",
        )
        return TabPane(_EMPTY_PANE_TITLE, body, id=EMPTY_PANE_ID)

    @classmethod
    def _empty_body_widgets(
        cls, plans: list[PlanSummary]
    ) -> list[Any]:
        listed = [
            p for p in plans
            if p.status == "running"  # zombies are still status=running
        ]
        if not listed:
            return [Static(_EMPTY_PLACEHOLDER_TEXT, classes="empty-state")]
        children: list[Any] = [
            Static("Active plans", classes="plan-list-header")
        ]
        for plan in listed:
            children.append(cls._build_plan_row(plan))
        return children

    @staticmethod
    def _build_plan_row(plan: PlanSummary) -> Horizontal:
        zombie = is_stale(plan)
        status_label = "ZOMBIE" if zombie else "RUNNING"
        status_classes = "plan-status zombie" if zombie else "plan-status"
        row_widgets: list[Any] = [
            Static(status_label, classes=status_classes),
            Button(
                plan.slug,
                id=f"{_BTN_OPEN_PREFIX}{_safe(plan.slug)}",
                tooltip="Open this plan's tab",
            ),
        ]
        if zombie:
            row_widgets.extend(
                [
                    Button(
                        "Mark crashed",
                        id=f"{_BTN_CRASH_PREFIX}{_safe(plan.slug)}",
                        tooltip="Mark as crashed in master.json",
                    ),
                    Button(
                        "Remove",
                        id=f"{_BTN_REMOVE_PREFIX}{_safe(plan.slug)}",
                        tooltip="Remove from master.json (keeps logs on disk)",
                    ),
                ]
            )
        return Horizontal(*row_widgets, classes="plan-list-row")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def open_slugs(self) -> frozenset[str]:
        """Read-only snapshot of currently-open plan slugs."""
        return frozenset(self._open_slugs)

    def set_model_factory(self, factory: ModelFactory | None) -> None:
        """Register (or clear) the model factory.

        Useful when Phase B's factory becomes available after the section
        has already been mounted.
        """
        self._model_factory = factory

    def set_plan_summaries(
        self, plans: Iterable[PlanSummary]
    ) -> None:
        """Update the running-plans list shown in the empty-state pane.

        Filtered to plans with ``status == "running"`` (zombies included
        — they're still nominally running). Has no effect on plans that
        already have an open tab.
        """
        self._listed_plans = list(plans)
        self._refresh_empty_pane()

    def _refresh_empty_pane(self) -> None:
        # Replace the empty pane's body in place rather than removing
        # and re-adding the TabPane (Textual's TabbedContent generates
        # an internal --content-tab-<id> widget that races with re-adds
        # of the same pane id).
        try:
            body = self.query_one(
                "#plan-exec-empty-body", Vertical
            )
        except Exception:
            return
        body.remove_children()
        body.mount(*self._empty_body_widgets(self._listed_plans))

    def open_tab(self, slug: str) -> str | None:
        """Open a plan tab for ``slug``. Idempotent on the slug.

        Returns the tab's widget id, or ``None`` if no tab was mounted
        (duplicate slug or no model factory available).
        """
        if slug in self._open_slugs:
            tab_id = self._tab_id(slug)
            self._activate(tab_id)
            return tab_id
        if self._model_factory is None:
            log.debug("PlanExecutionSection: no model factory; skipping %s", slug)
            return None
        model = self._model_factory(slug)
        if model is None:
            log.debug("PlanExecutionSection: factory returned None for %s", slug)
            return None
        tab_id = self._tab_id(slug)
        tab = PlanExecutionTab(
            model=model,
            get_current_agent=self._get_current_agent,
            id=tab_id,
        )
        # Re-point the model's message sink at the tab now that it exists.
        # The factory built the model with a placeholder pane target so
        # ItemStatusChanged / PlanFinished bubble through the correct tab
        # handler instead of dying on the pane (which has no handler).
        if hasattr(model, "set_target"):
            model.set_target(tab)
        tabs = self.query_one("#plan-exec-tabs", TabbedContent)
        if not self._open_slugs:
            self._remove_empty_pane(tabs)
        tabs.add_pane(tab)
        self._open_slugs.add(slug)
        self.display = True
        self._activate(tab_id)
        return tab_id

    def close_tab(self, slug: str) -> None:
        """Close a plan tab. No-op if ``slug`` is unknown.

        ``master.json`` dropping a slug is *not* a close trigger — finished
        runs keep their tab mounted. The user (or test) calls this method
        explicitly.
        """
        if slug not in self._open_slugs:
            return
        self._open_slugs.remove(slug)
        tabs = self.query_one("#plan-exec-tabs", TabbedContent)
        tabs.remove_pane(self._tab_id(slug))
        if not self._open_slugs:
            tabs.add_pane(self._build_empty_pane(self._listed_plans))

    # ------------------------------------------------------------------
    # Empty-state list — open / mark-crashed / remove buttons
    # ------------------------------------------------------------------

    @on(Button.Pressed)
    def _on_plan_list_button(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        slug: str | None = None
        action: str | None = None
        for prefix, name in (
            (_BTN_OPEN_PREFIX, "open"),
            (_BTN_CRASH_PREFIX, "crash"),
            (_BTN_REMOVE_PREFIX, "remove"),
        ):
            if btn_id.startswith(prefix):
                action = name
                safe = btn_id.removeprefix(prefix)
                slug = self._lookup_slug(safe)
                break
        if action is None or slug is None:
            return
        event.stop()
        if action == "open":
            self.open_tab(slug)
        elif action == "crash":
            self.post_message(self.PlanCrashRequested(slug))
        elif action == "remove":
            self.post_message(self.PlanRemoveRequested(slug))

    def _lookup_slug(self, safe: str) -> str | None:
        for plan in self._listed_plans:
            if _safe(plan.slug) == safe:
                return plan.slug
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _activate(self, tab_id: str) -> None:
        tabs = self.query_one("#plan-exec-tabs", TabbedContent)
        tabs.active = tab_id

    @staticmethod
    def _remove_empty_pane(tabs: TabbedContent) -> None:
        try:
            tabs.query_one(f"#{EMPTY_PANE_ID}", TabPane)
        except Exception:
            return
        tabs.remove_pane(EMPTY_PANE_ID)

    @staticmethod
    def _tab_id(slug: str) -> str:
        return f"plan-tab-{_safe(slug)}"


def _safe(slug: str) -> str:
    return slug.replace(".", "-").replace("/", "-").replace(" ", "-")
