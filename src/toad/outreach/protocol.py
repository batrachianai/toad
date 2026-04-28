"""Public protocol for the Outreach right-pane panel.

Concrete implementations live in the private `toad.extensions.rpa_outreach`
submodule. The public repo only defines the data contract and the Protocol
that the registry looks up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ProspectsCard:
    """Totals for the Prospects card.

    Status enum in the source DB is only `scraped` and `messaged`, so the
    card splits into messaged vs pending (= scraped).
    """

    total: int
    messaged: int
    pending: int


@dataclass(frozen=True, slots=True)
class SendsCard:
    """Sends · 24h card payload — total plus a 24-slot hourly histogram."""

    total_24h: int
    hourly: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.hourly) != 24:
            raise ValueError(
                f"SendsCard.hourly must have 24 slots, got {len(self.hourly)}"
            )


@dataclass(frozen=True, slots=True)
class HackathonStat:
    """One row of the Hackathons (top 5) card."""

    name: str
    messaged: int
    total: int


@dataclass(frozen=True, slots=True)
class AccountStat:
    """One row of the Accounts card."""

    name: str
    online: bool
    sends_per_hour: float
    last_sent_relative: str


@dataclass(frozen=True, slots=True)
class OutreachSnapshot:
    """Complete payload rendered by the Outreach panel.

    `sends` and `accounts` are None when the `send_log` table is absent in
    the connected DB — the panel hides those cards instead of crashing.
    """

    prospects: ProspectsCard
    sends: SendsCard | None
    hackathons: list[HackathonStat]
    accounts: list[AccountStat] | None


@runtime_checkable
class OutreachInfoProvider(Protocol):
    """Data source for the Outreach panel.

    The registry discovers an implementation at startup; if none is found
    or the provider reports unavailable, the panel is not mounted.
    """

    async def available(self) -> bool:
        """Return True if the provider can currently serve a snapshot."""
        ...

    async def snapshot(self) -> OutreachSnapshot:
        """Fetch and return the current panel payload."""
        ...
