"""Unit tests for OrchestratorStateWidget helpers — no Textual app needed.

Covers:

- ``is_stale`` — running plans whose updatedAt is older than the
  threshold are flagged; non-running and recently-updated ones are not.
- ``_patch_plan_status`` and ``_drop_plan`` — JSON mutators used by the
  zombie cleanup buttons.
- Baseline capture and filter contract — exercised at the widget level
  in :mod:`tests.widgets.test_project_state_pane_orch`; here we cover
  the pure helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from toad.widgets.orchestrator_state import (
    PlanProgress,
    PlanSummary,
    STALE_THRESHOLD_SECONDS,
    _drop_plan,
    _patch_plan_status,
    is_stale,
)


def _summary(
    *,
    slug: str = "demo",
    status: str = "running",
    updated_at: str = "",
) -> PlanSummary:
    return PlanSummary(
        slug=slug,
        status=status,
        state_path="",
        started_at="",
        updated_at=updated_at,
        progress=PlanProgress(),
    )


# ----------------------------------------------------------------------
# is_stale
# ----------------------------------------------------------------------


class TestIsStale:
    def _now(self) -> datetime:
        return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)

    def test_non_running_is_never_stale(self) -> None:
        plan = _summary(status="completed", updated_at="2026-01-01T00:00:00Z")
        assert is_stale(plan, now=self._now()) is False

    def test_recent_running_is_not_stale(self) -> None:
        recent = (self._now() - timedelta(seconds=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        plan = _summary(status="running", updated_at=recent)
        assert is_stale(plan, now=self._now()) is False

    def test_old_running_is_stale(self) -> None:
        old = (
            self._now() - timedelta(seconds=STALE_THRESHOLD_SECONDS + 30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = _summary(status="running", updated_at=old)
        assert is_stale(plan, now=self._now()) is True

    def test_malformed_timestamp_on_running_is_stale(self) -> None:
        plan = _summary(status="running", updated_at="not-a-date")
        assert is_stale(plan, now=self._now()) is True

    def test_threshold_is_overridable(self) -> None:
        """Tests can dial the threshold down for fast feedback."""
        old = (self._now() - timedelta(seconds=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        plan = _summary(status="running", updated_at=old)
        assert is_stale(plan, now=self._now(), threshold_seconds=1) is True
        assert is_stale(plan, now=self._now(), threshold_seconds=10) is False


# ----------------------------------------------------------------------
# _patch_plan_status / _drop_plan
# ----------------------------------------------------------------------


class TestMasterMutators:
    def _data(self) -> dict:
        return {
            "plans": [
                {"slug": "alpha", "status": "running"},
                {"slug": "beta", "status": "running"},
            ]
        }

    def test_patch_status_returns_true_and_mutates(self) -> None:
        data = self._data()
        assert _patch_plan_status(data, "alpha", "crashed") is True
        statuses = {p["slug"]: p["status"] for p in data["plans"]}
        assert statuses == {"alpha": "crashed", "beta": "running"}

    def test_patch_status_records_updatedAt(self) -> None:
        data = self._data()
        _patch_plan_status(data, "alpha", "crashed")
        entry = next(p for p in data["plans"] if p["slug"] == "alpha")
        # ISO-8601 with trailing Z, e.g. 2026-04-27T12:34:56Z
        assert entry["updatedAt"].endswith("Z")
        assert "T" in entry["updatedAt"]

    def test_patch_status_returns_false_on_unknown_slug(self) -> None:
        data = self._data()
        assert _patch_plan_status(data, "ghost", "crashed") is False
        assert all(p["status"] == "running" for p in data["plans"])

    def test_drop_plan_removes_entry(self) -> None:
        data = self._data()
        assert _drop_plan(data, "beta") is True
        assert [p["slug"] for p in data["plans"]] == ["alpha"]

    def test_drop_plan_returns_false_on_unknown_slug(self) -> None:
        data = self._data()
        assert _drop_plan(data, "ghost") is False
        assert len(data["plans"]) == 2

    def test_drop_plan_handles_missing_plans_key(self) -> None:
        assert _drop_plan({}, "alpha") is False
        assert _patch_plan_status({}, "alpha", "crashed") is False


# ----------------------------------------------------------------------
# Round-trip through a real master.json — used by the widget mutators
# ----------------------------------------------------------------------


def test_master_json_mutation_round_trip(tmp_path: Path) -> None:
    """Mark crashed + drop, both round-trip cleanly through JSON."""
    master = tmp_path / "master.json"
    master.write_text(
        json.dumps(
            {
                "plans": [
                    {"slug": "alpha", "status": "running"},
                    {"slug": "beta", "status": "running"},
                    {"slug": "gamma", "status": "completed"},
                ]
            }
        ),
        encoding="utf-8",
    )

    data = json.loads(master.read_text(encoding="utf-8"))
    assert _patch_plan_status(data, "alpha", "crashed") is True
    assert _drop_plan(data, "beta") is True
    master.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )

    reloaded = json.loads(master.read_text(encoding="utf-8"))
    statuses = {p["slug"]: p["status"] for p in reloaded["plans"]}
    assert statuses == {"alpha": "crashed", "gamma": "completed"}
