"""Tests for the ``PlanStatusRail`` widget.

The status rail is the footer of a ``PlanExecutionTab``: a compact strip
showing one status glyph per plan item plus an overall verdict badge
(running / SHIP / REVISE).

These tests drive:

- One glyph per item in render order.
- Verdict badge reflects overall plan state.
- Rail updates when ``ItemStatusChanged`` messages are posted.

The widget is intentionally "dumb" — items come in directly; no file I/O.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from toad.widgets.plan_status_rail import (
    STATUS_COLORS,
    STATUS_GLYPHS,
    VERDICT_COLORS,
    PlanStatusRail,
    RailItem,
)


def _fixture_items() -> list[RailItem]:
    return [
        RailItem(id=1, status="done"),
        RailItem(id=2, status="running"),
        RailItem(id=3, status="ready"),
        RailItem(id=4, status="queued"),
        RailItem(id=5, status="failed"),
        RailItem(id=6, status="review"),
    ]


class _Harness(App[None]):
    """Mounts a single ``PlanStatusRail``."""

    def __init__(
        self,
        items: list[RailItem],
        verdict: str = "running",
    ) -> None:
        super().__init__()
        self._items = items
        self._verdict = verdict

    def compose(self) -> ComposeResult:
        yield PlanStatusRail(
            items=self._items, verdict=self._verdict, id="rail"
        )


# ------------------------------------------------------------------
# Glyph rendering
# ------------------------------------------------------------------


class TestGlyphs:
    """One glyph per item, in the given order, with status color."""

    @pytest.mark.asyncio
    async def test_one_glyph_per_item(self) -> None:
        items = _fixture_items()
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            glyphs = rail.glyphs_plain()
            assert len(glyphs) == len(items)
            for rendered, item in zip(glyphs, items, strict=True):
                assert rendered == STATUS_GLYPHS[item.status]

    @pytest.mark.asyncio
    async def test_each_glyph_uses_status_color(self) -> None:
        items = _fixture_items()
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            for item in items:
                assert rail.has_color_for(item.id, STATUS_COLORS[item.status])

    @pytest.mark.asyncio
    async def test_set_items_replaces_glyphs(self) -> None:
        initial = [RailItem(id=1, status="queued")]
        app = _Harness(initial)
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            assert rail.glyphs_plain() == [STATUS_GLYPHS["queued"]]

            rail.set_items(
                [
                    RailItem(id=7, status="running"),
                    RailItem(id=8, status="done"),
                ]
            )
            await pilot.pause()
            assert rail.glyphs_plain() == [
                STATUS_GLYPHS["running"],
                STATUS_GLYPHS["done"],
            ]


# ------------------------------------------------------------------
# Verdict badge
# ------------------------------------------------------------------


class TestVerdictBadge:
    """Badge on the right shows running / SHIP / REVISE with proper color."""

    @pytest.mark.asyncio
    async def test_running_badge(self) -> None:
        app = _Harness(_fixture_items(), verdict="running")
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            assert rail.verdict_label() == "running"
            assert rail.verdict_has_color(VERDICT_COLORS["running"])

    @pytest.mark.asyncio
    async def test_ship_badge(self) -> None:
        app = _Harness(_fixture_items(), verdict="SHIP")
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            assert rail.verdict_label() == "SHIP"
            assert rail.verdict_has_color(VERDICT_COLORS["SHIP"])

    @pytest.mark.asyncio
    async def test_revise_badge(self) -> None:
        app = _Harness(_fixture_items(), verdict="REVISE")
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            assert rail.verdict_label() == "REVISE"
            assert rail.verdict_has_color(VERDICT_COLORS["REVISE"])

    @pytest.mark.asyncio
    async def test_set_verdict_updates_badge(self) -> None:
        app = _Harness(_fixture_items(), verdict="running")
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            rail.set_verdict("SHIP")
            await pilot.pause()
            assert rail.verdict_label() == "SHIP"
            assert rail.verdict_has_color(VERDICT_COLORS["SHIP"])


# ------------------------------------------------------------------
# ItemStatusChanged updates
# ------------------------------------------------------------------


class TestItemStatusChanged:
    """Posting ``ItemStatusChanged`` updates the matching glyph in place."""

    @pytest.mark.asyncio
    async def test_message_updates_single_glyph(self) -> None:
        items = _fixture_items()
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            # item 3 starts as "ready"; flip to "done".
            rail.post_message(PlanStatusRail.ItemStatusChanged(3, "done"))
            await pilot.pause()
            glyphs = rail.glyphs_plain()
            # position of id=3 in original list is index 2
            assert glyphs[2] == STATUS_GLYPHS["done"]
            # neighbours unchanged
            assert glyphs[1] == STATUS_GLYPHS["running"]
            assert glyphs[3] == STATUS_GLYPHS["queued"]

    @pytest.mark.asyncio
    async def test_unknown_item_id_is_ignored(self) -> None:
        items = _fixture_items()
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            rail = app.query_one(PlanStatusRail)
            before = rail.glyphs_plain()
            rail.post_message(PlanStatusRail.ItemStatusChanged(999, "done"))
            await pilot.pause()
            assert rail.glyphs_plain() == before
