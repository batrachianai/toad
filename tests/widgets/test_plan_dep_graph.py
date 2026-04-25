"""Tests for the ``PlanDepGraph`` widget.

The dep graph is the main pane of a ``PlanExecutionTab``: it renders the
items of a running/completed plan with status-colored nodes and posts
``PlanDepGraph.ItemSelected`` when the user picks a node.

These tests drive:

- Rendering from a ``state.json`` fixture — one node per item.
- Status colors per state (queued/ready/running/done/failed/review).
- Selection posting ``PlanDepGraph.ItemSelected`` with the picked item id.

The widget is intentionally "dumb" — items are passed in directly, so no
file watching or direct I/O happens here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Tree

from toad.widgets.plan_dep_graph import (
    STATUS_COLORS,
    DepGraphItem,
    PlanDepGraph,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "plan_state.json"


def _load_fixture_items() -> list[DepGraphItem]:
    """Parse the fixture ``state.json`` into ``DepGraphItem`` records."""
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [
        DepGraphItem(
            id=entry["id"],
            description=entry["description"],
            status=entry["status"],
            deps=tuple(entry.get("deps", [])),
        )
        for entry in raw["items"]
    ]


class _Harness(App[None]):
    """Minimal app that mounts a single ``PlanDepGraph``."""

    def __init__(self, items: list[DepGraphItem]) -> None:
        super().__init__()
        self._items = items
        self.received: list[int] = []

    def compose(self) -> ComposeResult:
        yield PlanDepGraph(items=self._items, id="dep-graph")

    def on_plan_dep_graph_item_selected(
        self, event: PlanDepGraph.ItemSelected
    ) -> None:
        self.received.append(event.item_id)


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------


class TestRendering:
    """Dep graph renders one node per fixture item."""

    @pytest.mark.asyncio
    async def test_renders_one_node_per_item_from_fixture(self) -> None:
        items = _load_fixture_items()
        assert len(items) == 6  # fixture sanity check

        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            graph = app.query_one(PlanDepGraph)
            assert set(graph.node_ids()) == {i.id for i in items}

    @pytest.mark.asyncio
    async def test_set_items_replaces_existing_nodes(self) -> None:
        initial = [DepGraphItem(id=1, description="first", status="ready")]
        app = _Harness(initial)
        async with app.run_test() as pilot:
            await pilot.pause()
            graph = app.query_one(PlanDepGraph)
            assert set(graph.node_ids()) == {1}

            graph.set_items(
                [
                    DepGraphItem(id=7, description="later", status="running"),
                    DepGraphItem(
                        id=8, description="tail", status="queued", deps=(7,)
                    ),
                ]
            )
            await pilot.pause()
            assert set(graph.node_ids()) == {7, 8}


# ------------------------------------------------------------------
# Status colors
# ------------------------------------------------------------------


class TestStatusColors:
    """Each rendered node shows the color registered for its status."""

    @pytest.mark.asyncio
    async def test_each_status_paints_its_color(self) -> None:
        statuses = ["queued", "ready", "running", "done", "failed", "review"]
        items = [
            DepGraphItem(id=idx + 1, description=f"item-{s}", status=s)
            for idx, s in enumerate(statuses)
        ]
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            graph = app.query_one(PlanDepGraph)
            for item in items:
                label_text = graph.node_label_plain(item.id)
                assert item.description in label_text
                expected_color = STATUS_COLORS[item.status]
                assert graph.node_has_color(item.id, expected_color), (
                    f"item {item.id} ({item.status}) missing color "
                    f"{expected_color!r}"
                )

    @pytest.mark.asyncio
    async def test_unknown_status_falls_back_without_crashing(self) -> None:
        items = [
            DepGraphItem(id=1, description="wild", status="not-a-state")
        ]
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            graph = app.query_one(PlanDepGraph)
            assert 1 in graph.node_ids()


# ------------------------------------------------------------------
# Selection
# ------------------------------------------------------------------


class TestSelection:
    """Selecting a node posts ``ItemSelected`` with its item id."""

    @pytest.mark.asyncio
    async def test_selection_posts_item_selected(self) -> None:
        items = _load_fixture_items()
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            graph = app.query_one(PlanDepGraph)
            node = graph.node_for(3)
            graph.post_message(Tree.NodeSelected(node))
            await pilot.pause()
            assert app.received == [3]

    @pytest.mark.asyncio
    async def test_selection_is_per_node(self) -> None:
        items = _load_fixture_items()
        app = _Harness(items)
        async with app.run_test() as pilot:
            await pilot.pause()
            graph = app.query_one(PlanDepGraph)
            for target in (1, 4, 6):
                graph.post_message(Tree.NodeSelected(graph.node_for(target)))
            await pilot.pause()
            assert app.received == [1, 4, 6]
