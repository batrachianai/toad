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
from collections.abc import Callable
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import TabbedContent

from toad.widgets.plan_execution_tab import PlanExecutionModel, PlanExecutionTab


__all__ = [
    "ModelFactory",
    "PlanExecutionSection",
]


log = logging.getLogger(__name__)


ModelFactory = Callable[[str], PlanExecutionModel | None]
"""Signature: ``factory(slug) -> PlanExecutionModel | None``.

Returning ``None`` tells the section to skip this slug (e.g. the plan
directory disappeared between detection and render).
"""


class PlanExecutionSection(Vertical):
    """TabbedContent section that hosts one tab per orchestrator plan."""

    SECTION_ID = "section-plan-execution"

    DEFAULT_CSS = """
    PlanExecutionSection {
        display: none;
        height: 1fr;
    }

    PlanExecutionSection TabbedContent {
        height: 1fr;
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

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield TabbedContent(id="plan-exec-tabs")

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
        tabs = self.query_one("#plan-exec-tabs", TabbedContent)
        tabs.add_pane(tab)
        self._open_slugs.add(slug)
        self.display = True
        self._activate(tab_id)
        return tab_id

    def close_tab(self, slug: str) -> None:
        """Close a plan tab. No-op if ``slug`` is unknown."""
        if slug not in self._open_slugs:
            return
        self._open_slugs.remove(slug)
        tabs = self.query_one("#plan-exec-tabs", TabbedContent)
        tabs.remove_pane(self._tab_id(slug))
        if not self._open_slugs:
            self.display = False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _activate(self, tab_id: str) -> None:
        tabs = self.query_one("#plan-exec-tabs", TabbedContent)
        tabs.active = tab_id

    @staticmethod
    def _tab_id(slug: str) -> str:
        safe = slug.replace(".", "-").replace("/", "-").replace(" ", "-")
        return f"plan-tab-{safe}"
