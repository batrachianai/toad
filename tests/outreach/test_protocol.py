"""Tests for the Outreach panel public protocol."""

from __future__ import annotations

import asyncio
import dataclasses
from typing import get_type_hints

import pytest

from toad.outreach.protocol import (
    AccountStat,
    HackathonStat,
    OutreachInfoProvider,
    OutreachSnapshot,
    ProspectsCard,
    SendsCard,
)


def test_prospects_card_fields() -> None:
    card = ProspectsCard(total=100, messaged=40, pending=60)
    assert card.total == 100
    assert card.messaged == 40
    assert card.pending == 60


def test_sends_card_histogram_has_24_slots() -> None:
    hist = [0] * 24
    card = SendsCard(total_24h=0, hourly=hist)
    assert len(card.hourly) == 24


def test_sends_card_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        SendsCard(total_24h=0, hourly=[0, 1, 2])


def test_hackathon_stat_fields() -> None:
    stat = HackathonStat(name="ETHGlobal", messaged=10, total=50)
    assert stat.name == "ETHGlobal"
    assert stat.messaged == 10
    assert stat.total == 50


def test_account_stat_fields() -> None:
    stat = AccountStat(
        name="alice",
        online=True,
        sends_per_hour=3.5,
        last_sent_relative="2m ago",
    )
    assert stat.name == "alice"
    assert stat.online is True
    assert stat.sends_per_hour == pytest.approx(3.5)
    assert stat.last_sent_relative == "2m ago"


def test_outreach_snapshot_holds_four_cards() -> None:
    snapshot = OutreachSnapshot(
        prospects=ProspectsCard(total=0, messaged=0, pending=0),
        sends=SendsCard(total_24h=0, hourly=[0] * 24),
        hackathons=[],
        accounts=[],
    )
    assert isinstance(snapshot.prospects, ProspectsCard)
    assert isinstance(snapshot.sends, SendsCard)
    assert snapshot.hackathons == []
    assert snapshot.accounts == []


def test_snapshot_allows_hidden_sends_and_accounts() -> None:
    """When send_log is absent, sends/accounts may be None."""
    snapshot = OutreachSnapshot(
        prospects=ProspectsCard(total=10, messaged=5, pending=5),
        sends=None,
        hackathons=[HackathonStat(name="X", messaged=1, total=2)],
        accounts=None,
    )
    assert snapshot.sends is None
    assert snapshot.accounts is None


def test_snapshot_is_dataclass() -> None:
    assert dataclasses.is_dataclass(OutreachSnapshot)


def test_provider_protocol_has_required_methods() -> None:
    """OutreachInfoProvider is a runtime-checkable Protocol with async methods."""

    class FakeProvider:
        async def available(self) -> bool:
            return True

        async def snapshot(self) -> OutreachSnapshot:
            return OutreachSnapshot(
                prospects=ProspectsCard(total=0, messaged=0, pending=0),
                sends=None,
                hackathons=[],
                accounts=None,
            )

    provider: OutreachInfoProvider = FakeProvider()
    assert asyncio.run(provider.available()) is True
    snap = asyncio.run(provider.snapshot())
    assert isinstance(snap, OutreachSnapshot)


def test_provider_protocol_runtime_checkable() -> None:
    class Good:
        async def available(self) -> bool:
            return False

        async def snapshot(self) -> OutreachSnapshot:
            raise NotImplementedError

    class Bad:
        pass

    assert isinstance(Good(), OutreachInfoProvider)
    assert not isinstance(Bad(), OutreachInfoProvider)


def test_protocol_method_annotations() -> None:
    hints = get_type_hints(OutreachInfoProvider.snapshot)
    assert hints["return"] is OutreachSnapshot
