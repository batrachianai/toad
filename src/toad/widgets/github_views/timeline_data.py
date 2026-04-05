"""Timeline data models and transform layer.

Consumes provider-agnostic output from a ``TimelineProvider`` and
produces a normalized ``TimelineData`` structure ready for the Gantt
renderer.  All date arithmetic and grouping logic lives here so the
renderer never touches raw provider data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from toad.widgets.github_views.timeline_provider import (
    ItemStatus,
    Priority,
    ProviderItem,
    ProviderMilestone,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimelineItem:
    """A single renderable Gantt bar or gate marker.

    Attributes:
        id: Provider-specific identifier.
        title: Display label.
        status: Normalized status (todo / in_progress / done).
        start_day: Offset in days from the timeline start date.
        days: Duration in days (>= 1).
        is_gate: True for gate/checkpoint items (rendered as diamonds).
        priority: Optional priority level for styling.
        risk_labels: Risk labels for styling.
        effort: Effort estimate string.
        url: Link to the item in the provider's UI.
    """

    id: str
    title: str
    status: ItemStatus
    start_day: int
    days: int
    is_gate: bool = False
    priority: Priority | None = None
    risk_labels: list[str] = field(default_factory=list)
    effort: str | None = None
    url: str = ""


@dataclass(frozen=True)
class GateMarker:
    """A gate marker on the date axis.

    Attributes:
        label: Short display label (typically the issue title).
        day: Offset in days from the timeline start date.
    """

    label: str
    day: int


@dataclass(frozen=True)
class MilestoneGroup:
    """A group of timeline items under a single milestone.

    Attributes:
        title: Milestone display name.
        due_date: Optional due date for the milestone.
        items: Sorted list of timeline items in this group.
    """

    title: str
    due_date: date | None = None
    items: list[TimelineItem] = field(default_factory=list)


@dataclass(frozen=True)
class TimelineData:
    """Fully resolved timeline ready for rendering.

    Attributes:
        start_date: First date in the timeline range.
        total_days: Span of the timeline in days.
        groups: Milestone groups containing positioned items.
        gates: Gate markers for the date axis.
    """

    start_date: date
    total_days: int
    groups: list[MilestoneGroup] = field(default_factory=list)
    gates: list[GateMarker] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

_UNGROUPED_TITLE = "Ungrouped"


def _resolve_dates(
    item: ProviderItem,
    milestone_due: date | None,
    today: date,
) -> tuple[date, date]:
    """Resolve start and target dates with fallbacks.

    Fallback logic (from plan):
    - Start Date: use item start_date, else today.
    - Target Date: use item target_date, else milestone due date, else
      start + 1 day.
    """
    start = item.start_date or today
    target = item.target_date or milestone_due or start
    if target < start:
        target = start
    return start, target


def build_timeline(
    milestones: list[ProviderMilestone],
    items: list[ProviderItem],
    today: date | None = None,
) -> TimelineData:
    """Transform provider output into a renderable ``TimelineData``.

    Args:
        milestones: Milestones from the provider.
        items: Items from the provider (issues / tasks).
        today: Override for testing; defaults to ``date.today()``.

    Returns:
        A ``TimelineData`` with items grouped by milestone, positioned
        on a unified date axis, and gates extracted.
    """
    if today is None:
        today = date.today()

    if not items:
        return TimelineData(start_date=today, total_days=1)

    milestone_map: dict[str, ProviderMilestone] = {
        m.id: m for m in milestones
    }

    # --- Resolve dates for every item ---
    resolved: list[tuple[ProviderItem, date, date]] = []
    for item in items:
        ms_due = (
            milestone_map[item.milestone_id].due_date
            if item.milestone_id and item.milestone_id in milestone_map
            else None
        )
        start, target = _resolve_dates(item, ms_due, today)
        resolved.append((item, start, target))

    # --- Compute global date range ---
    all_starts = [s for _, s, _ in resolved]
    all_targets = [t for _, _, t in resolved]
    ms_dues = [
        m.due_date for m in milestones if m.due_date is not None
    ]
    global_start = min(all_starts + ms_dues)
    global_end = max(all_targets + ms_dues + [today])
    total_days = max((global_end - global_start).days, 1)

    # --- Build groups ---
    groups_map: dict[str | None, list[TimelineItem]] = {}
    gates: list[GateMarker] = []

    for item, start, target in resolved:
        start_day = (start - global_start).days
        duration = max((target - start).days, 1)

        ti = TimelineItem(
            id=item.id,
            title=item.title,
            status=item.status,
            start_day=start_day,
            days=duration,
            is_gate=item.is_gate,
            priority=item.priority,
            risk_labels=list(item.risk_labels),
            effort=item.effort,
            url=item.url,
        )

        groups_map.setdefault(item.milestone_id, []).append(ti)

        if item.is_gate:
            gates.append(GateMarker(label=item.title, day=start_day))

    # Sort gates by day
    gates.sort(key=lambda g: g.day)

    # Assemble MilestoneGroup objects in milestone order
    seen_ids: set[str | None] = set()
    ordered_groups: list[MilestoneGroup] = []

    for ms in milestones:
        seen_ids.add(ms.id)
        group_items = groups_map.get(ms.id, [])
        group_items.sort(key=lambda t: t.start_day)
        ordered_groups.append(
            MilestoneGroup(
                title=ms.title,
                due_date=ms.due_date,
                items=group_items,
            )
        )

    # Items without a milestone go into an "Ungrouped" group
    ungrouped_keys = [k for k in groups_map if k not in seen_ids]
    if ungrouped_keys:
        ungrouped_items: list[TimelineItem] = []
        for key in ungrouped_keys:
            ungrouped_items.extend(groups_map[key])
        ungrouped_items.sort(key=lambda t: t.start_day)
        ordered_groups.append(
            MilestoneGroup(title=_UNGROUPED_TITLE, items=ungrouped_items)
        )

    return TimelineData(
        start_date=global_start,
        total_days=total_days,
        groups=ordered_groups,
        gates=gates,
    )
