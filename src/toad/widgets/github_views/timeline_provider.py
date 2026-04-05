"""TimelineProvider protocol and provider-agnostic data models.

Defines the contract that any timeline data source (GitHub, Bitbucket,
Linear, etc.) must implement, plus the typed dataclasses that flow
between providers, the transform layer, and the rendering layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Protocol, runtime_checkable


class ItemStatus(Enum):
    """Normalized status for a timeline item."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Priority(Enum):
    """Priority levels derived from p1–p4 labels."""

    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4


@dataclass(frozen=True)
class ProviderMilestone:
    """A milestone that groups timeline items.

    Attributes:
        id: Provider-specific identifier (e.g. GitHub milestone number).
        title: Human-readable milestone name.
        due_date: Optional due date for the milestone.
        description: Optional description text.
    """

    id: str
    title: str
    due_date: date | None = None
    description: str = ""


@dataclass(frozen=True)
class ProviderItem:
    """A single timeline item (issue, task, etc.).

    Attributes:
        id: Provider-specific identifier (e.g. issue number).
        title: Item title.
        status: Normalized status.
        start_date: When work begins (None if unset).
        target_date: When work should complete (None if unset).
        milestone_id: ID of the parent milestone (None if unassigned).
        labels: All labels attached to the item.
        is_gate: Whether this item is a gate/checkpoint.
        priority: Priority level from p1–p4 labels (None if unset).
        risk_labels: Risk labels (e.g. "risk:dependency").
        effort: Effort estimate from project board (None if unset).
        url: Link back to the item in the provider's UI.
    """

    id: str
    title: str
    status: ItemStatus
    start_date: date | None = None
    target_date: date | None = None
    milestone_id: str | None = None
    labels: list[str] = field(default_factory=list)
    is_gate: bool = False
    priority: Priority | None = None
    risk_labels: list[str] = field(default_factory=list)
    effort: str | None = None
    url: str = ""


@dataclass(frozen=True)
class ProviderField:
    """Metadata for a project board custom field.

    Used to map provider-specific field IDs to semantic names so the
    transform layer knows which fields carry Start Date, Target Date,
    Status, and Effort values.

    Attributes:
        id: Provider-specific field identifier.
        name: Human-readable field name.
        field_type: Type hint (e.g. "date", "single_select", "number").
        options: For select fields, the allowed option values.
    """

    id: str
    name: str
    field_type: str = ""
    options: list[str] = field(default_factory=list)


@runtime_checkable
class TimelineProvider(Protocol):
    """Protocol for fetching timeline data from any project management tool.

    Implementations must provide three async methods that return
    provider-agnostic dataclasses. The transform layer consumes these
    outputs to build the unified `TimelineData` model.
    """

    async def fetch_milestones(self) -> list[ProviderMilestone]:
        """Fetch all milestones for the configured project.

        Returns:
            List of milestones with titles and optional due dates.
        """
        ...

    async def fetch_items(self) -> list[ProviderItem]:
        """Fetch all timeline items (issues, tasks) with project board data.

        Items should have their status, dates, labels, and milestone
        associations resolved. Gate items (label ``gate``) must have
        ``is_gate=True``. Priority and risk labels should be parsed
        from the provider's label system.

        Returns:
            List of items with normalized fields.
        """
        ...

    async def fetch_fields(self) -> list[ProviderField]:
        """Fetch project board field metadata.

        Returns field definitions so the caller can understand which
        custom fields are available and what options they support.
        Implementations may cache this per session since field
        definitions rarely change.

        Returns:
            List of field metadata objects.
        """
        ...
