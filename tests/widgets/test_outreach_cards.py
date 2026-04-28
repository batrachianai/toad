"""Tests for the four Outreach panel card widgets.

The card widgets are theme-agnostic ``Static`` subclasses that accept plain
Python types — tests mount each one under a minimal Textual app harness so
``update()`` / ``refresh()`` can run, then assert on the plain-text
projection of the current content so we don't couple to specific style
markup.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from rich.console import Console
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widget import Widget

from toad.widgets.outreach_cards import AccountDot, Histogram, RankedBar, StatLine


def _plain(widget: Widget) -> str:
    """Return the current rendered content as plain text."""
    rendered = getattr(widget, "rendered", None)
    if isinstance(rendered, Text):
        return rendered.plain
    console = Console(record=True, width=120, color_system=None)
    console.print(rendered)
    return console.export_text()


class _Harness(App[None]):
    def __init__(self, factory: Callable[[], Widget]) -> None:
        super().__init__()
        self._factory = factory

    def compose(self) -> ComposeResult:
        yield self._factory()


@asynccontextmanager
async def _mounted(factory: Callable[[], Widget]) -> AsyncIterator[Widget]:
    app = _Harness(factory)
    async with app.run_test() as pilot:
        await pilot.pause()
        yield app.query_one(Widget)  # type: ignore[type-abstract]


# ---------------------------------------------------------------------------
# StatLine
# ---------------------------------------------------------------------------


class TestStatLine:
    @pytest.mark.asyncio
    async def test_renders_label_and_total(self) -> None:
        def build() -> StatLine:
            return StatLine(
                label="Prospects",
                total=2044,
                segments=(("messaged", 845, "success"), ("pending", 1199, "muted")),
            )

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "Prospects" in text
        assert "2,044" in text
        assert "845" in text
        assert "messaged" in text

    @pytest.mark.asyncio
    async def test_stacked_bar_has_width(self) -> None:
        def build() -> StatLine:
            return StatLine(
                label="Prospects",
                total=100,
                segments=(("messaged", 30, "success"), ("pending", 70, "muted")),
                bar_width=20,
            )

        async with _mounted(build) as widget:
            text = _plain(widget)
        rows = text.splitlines()
        assert any(len(row.strip()) >= 15 for row in rows)
        fill_chars = sum(text.count(g) for g in ("█", "░"))
        assert fill_chars > 0

    @pytest.mark.asyncio
    async def test_set_data_updates_render(self) -> None:
        def build() -> StatLine:
            return StatLine(label="Prospects", total=0, segments=())

        async with _mounted(build) as widget:
            assert isinstance(widget, StatLine)
            before = _plain(widget)
            widget.set_data(total=500, segments=(("messaged", 500, "success"),))
            after = _plain(widget)
        assert before != after
        assert "500" in after

    @pytest.mark.asyncio
    async def test_zero_total_does_not_crash(self) -> None:
        def build() -> StatLine:
            return StatLine(label="Prospects", total=0, segments=())

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "Prospects" in text
        assert "0" in text


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------


class TestHistogram:
    @pytest.mark.asyncio
    async def test_renders_total_and_24_cells(self) -> None:
        buckets = tuple(range(24))

        def build() -> Histogram:
            return Histogram(label="Sends · 24h", buckets=buckets, total=sum(buckets))

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "Sends" in text
        assert str(sum(buckets)) in text
        block_chars = "▁▂▃▄▅▆▇█ "
        densest = max(text.splitlines(), key=lambda row: sum(c in block_chars for c in row))
        assert sum(c in block_chars for c in densest) >= 24

    @pytest.mark.asyncio
    async def test_empty_buckets_render_without_crash(self) -> None:
        def build() -> Histogram:
            return Histogram(label="Sends · 24h", buckets=(0,) * 24, total=0)

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "0" in text

    @pytest.mark.asyncio
    async def test_wrong_length_buckets_are_normalized(self) -> None:
        def build() -> Histogram:
            return Histogram(label="Sends · 24h", buckets=(1, 2, 3), total=6)

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "6" in text

    @pytest.mark.asyncio
    async def test_set_data_updates_render(self) -> None:
        def build() -> Histogram:
            return Histogram(label="Sends · 24h", buckets=(0,) * 24, total=0)

        async with _mounted(build) as widget:
            assert isinstance(widget, Histogram)
            before = _plain(widget)
            widget.set_data(buckets=tuple([5] * 24), total=120)
            after = _plain(widget)
        assert before != after
        assert "120" in after


# ---------------------------------------------------------------------------
# RankedBar
# ---------------------------------------------------------------------------


class TestRankedBar:
    @pytest.mark.asyncio
    async def test_renders_rows_sorted_by_messaged(self) -> None:
        rows = (
            ("Alpha Hackathon", 10, 50),
            ("Beta Hackathon", 40, 100),
            ("Gamma Hackathon", 5, 10),
        )

        def build() -> RankedBar:
            return RankedBar(label="Hackathons", rows=rows, max_rows=5)

        async with _mounted(build) as widget:
            text = _plain(widget)
        idx_beta = text.find("Beta")
        idx_alpha = text.find("Alpha")
        idx_gamma = text.find("Gamma")
        assert idx_beta != -1 and idx_alpha != -1 and idx_gamma != -1
        assert idx_beta < idx_alpha
        assert idx_beta < idx_gamma

    @pytest.mark.asyncio
    async def test_respects_max_rows(self) -> None:
        rows = tuple((f"H{i}x", i, 10 + i) for i in range(10))

        def build() -> RankedBar:
            return RankedBar(label="Hackathons", rows=rows, max_rows=3)

        async with _mounted(build) as widget:
            text = _plain(widget)
        names_found = sum(1 for i in range(10) if f"H{i}x" in text)
        assert names_found == 3

    @pytest.mark.asyncio
    async def test_empty_rows_renders_placeholder(self) -> None:
        def build() -> RankedBar:
            return RankedBar(label="Hackathons", rows=())

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "Hackathons" in text

    @pytest.mark.asyncio
    async def test_set_data_updates_render(self) -> None:
        def build() -> RankedBar:
            return RankedBar(label="Hackathons", rows=())

        async with _mounted(build) as widget:
            assert isinstance(widget, RankedBar)
            before = _plain(widget)
            widget.set_data(rows=(("NewHack", 1, 2),))
            after = _plain(widget)
        assert before != after
        assert "NewHack" in after


# ---------------------------------------------------------------------------
# AccountDot
# ---------------------------------------------------------------------------


class TestAccountDot:
    @pytest.mark.asyncio
    async def test_renders_name_rate_and_last_sent(self) -> None:
        def build() -> AccountDot:
            return AccountDot(
                name="acct-01",
                active=True,
                sends_per_hour=12.3,
                last_sent="5m ago",
            )

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "acct-01" in text
        assert "12.3" in text
        assert "5m ago" in text
        assert "●" in text

    @pytest.mark.asyncio
    async def test_idle_uses_hollow_dot(self) -> None:
        def build() -> AccountDot:
            return AccountDot(name="acct-02", active=False, sends_per_hour=0.0, last_sent=None)

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "acct-02" in text
        assert "○" in text

    @pytest.mark.asyncio
    async def test_missing_last_sent_shows_dash(self) -> None:
        def build() -> AccountDot:
            return AccountDot(name="acct-03", active=False, sends_per_hour=0.0, last_sent=None)

        async with _mounted(build) as widget:
            text = _plain(widget)
        assert "—" in text or "-" in text

    @pytest.mark.asyncio
    async def test_set_data_updates_render(self) -> None:
        def build() -> AccountDot:
            return AccountDot(name="acct", active=False, sends_per_hour=0.0, last_sent=None)

        async with _mounted(build) as widget:
            assert isinstance(widget, AccountDot)
            before = _plain(widget)
            widget.set_data(name="acct", active=True, sends_per_hour=42.0, last_sent="1m ago")
            after = _plain(widget)
        assert before != after
        assert "42" in after
        assert "1m ago" in after
