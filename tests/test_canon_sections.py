"""Tests for canon state widget, builder view, and automation view.

Verifies:
- CanonState dataclass and _parse_state with mock .canon/state.json data
- Phase transitions: build phases, run phase, develop→run switch
- Error state handling (status=error, error message)
- Log rendering with level-based color coding
- BuilderView phase badge and iteration rendering
- AutomationView status badge, metrics grid, error banner
- Graceful empty state when no data
"""

from __future__ import annotations

import json

import pytest

from toad.widgets.canon_state import (
    ALL_PHASES,
    BUILD_PHASES,
    RUN_PHASES,
    CanonState,
    CanonStateWidget,
    LogEntry,
    _parse_state,
)


# ------------------------------------------------------------------
# Fixtures — mock state.json payloads
# ------------------------------------------------------------------


def _build_state(
    *,
    phase: str = "develop",
    status: str = "active",
    iteration: int = 3,
    error: str | None = None,
    logs: list[dict] | None = None,
    metrics: dict | None = None,
) -> dict:
    """Build a raw state.json dict."""
    payload: dict = {
        "phase": phase,
        "status": status,
        "iteration": iteration,
    }
    if error is not None:
        payload["error"] = error
    if logs is not None:
        payload["logs"] = logs
    if metrics is not None:
        payload["metrics"] = metrics
    return payload


# ------------------------------------------------------------------
# CanonState / _parse_state tests
# ------------------------------------------------------------------


class TestCanonStateDataclass:
    """CanonState properties and defaults."""

    def test_defaults(self):
        s = CanonState()
        assert s.phase == ""
        assert s.status == ""
        assert s.iteration == 0
        assert s.error is None
        assert s.logs == ()
        assert s.metrics == ()

    @pytest.mark.parametrize("phase", sorted(BUILD_PHASES))
    def test_is_build_phase(self, phase: str):
        s = CanonState(phase=phase)
        assert s.is_build_phase is True
        assert s.is_run_phase is False

    def test_is_run_phase(self):
        s = CanonState(phase="run")
        assert s.is_run_phase is True
        assert s.is_build_phase is False

    def test_unknown_phase_is_neither(self):
        s = CanonState(phase="unknown")
        assert s.is_build_phase is False
        assert s.is_run_phase is False

    def test_phase_sets_are_disjoint(self):
        assert BUILD_PHASES & RUN_PHASES == set()
        assert BUILD_PHASES | RUN_PHASES == ALL_PHASES


class TestParseState:
    """_parse_state correctly maps raw JSON dicts to CanonState."""

    def test_minimal_payload(self):
        state = _parse_state({})
        assert state.phase == ""
        assert state.status == ""
        assert state.iteration == 0
        assert state.error is None
        assert state.logs == ()
        assert state.metrics == ()

    def test_full_build_payload(self):
        raw = _build_state(
            phase="scaffold",
            status="active",
            iteration=2,
            logs=[
                {
                    "level": "info",
                    "message": "Starting scaffold",
                    "timestamp": "2026-03-30T10:00:00Z",
                },
                {
                    "level": "warn",
                    "message": "Slow network",
                    "timestamp": "2026-03-30T10:00:01Z",
                },
            ],
        )
        state = _parse_state(raw)
        assert state.phase == "scaffold"
        assert state.status == "active"
        assert state.iteration == 2
        assert state.is_build_phase is True
        assert len(state.logs) == 2
        assert state.logs[0].level == "info"
        assert state.logs[1].message == "Slow network"

    def test_run_phase_with_metrics(self):
        raw = _build_state(
            phase="run",
            status="running",
            iteration=1,
            metrics={"requests": "142", "errors": "3", "p99_ms": "87"},
        )
        state = _parse_state(raw)
        assert state.is_run_phase is True
        assert len(state.metrics) == 3
        assert ("requests", "142") in state.metrics
        assert ("errors", "3") in state.metrics
        assert ("p99_ms", "87") in state.metrics

    def test_error_state(self):
        raw = _build_state(
            phase="develop",
            status="error",
            error="Build failed: missing dependency",
        )
        state = _parse_state(raw)
        assert state.status == "error"
        assert state.error == "Build failed: missing dependency"

    def test_logs_missing_fields_default(self):
        raw = _build_state(logs=[{"message": "bare log"}])
        state = _parse_state(raw)
        assert state.logs[0].level == "info"
        assert state.logs[0].timestamp == ""
        assert state.logs[0].message == "bare log"

    def test_metrics_values_coerced_to_str(self):
        raw = _build_state(
            phase="run",
            status="running",
            metrics={"count": 42, "rate": 3.14},
        )
        state = _parse_state(raw)
        assert ("count", "42") in state.metrics
        assert ("rate", "3.14") in state.metrics

    def test_roundtrip_through_json(self):
        """Ensure _parse_state works on json.loads output."""
        raw = _build_state(
            phase="init",
            status="active",
            iteration=1,
            logs=[{"level": "debug", "message": "boot"}],
        )
        text = json.dumps(raw)
        state = _parse_state(json.loads(text))
        assert state.phase == "init"
        assert state.logs[0].level == "debug"


# ------------------------------------------------------------------
# Phase transition tests
# ------------------------------------------------------------------


class TestPhaseTransitions:
    """Verify phase classification across all transitions."""

    @pytest.mark.parametrize(
        ("from_phase", "to_phase", "expect_build", "expect_run"),
        [
            ("init", "scaffold", True, False),
            ("scaffold", "strategy", True, False),
            ("strategy", "develop", True, False),
            ("develop", "run", False, True),
        ],
    )
    def test_transition(
        self,
        from_phase: str,
        to_phase: str,
        expect_build: bool,
        expect_run: bool,
    ):
        old = CanonState(phase=from_phase)
        new = CanonState(phase=to_phase)
        # Old state should be build-phase for first 3 transitions
        if from_phase != "develop" or to_phase != "run":
            assert old.is_build_phase is True
        # New state classification
        assert new.is_build_phase is expect_build
        assert new.is_run_phase is expect_run

    def test_develop_to_run_switches_section(self):
        """The critical develop→run transition should flip is_build→is_run."""
        old = CanonState(phase="develop")
        new = CanonState(phase="run")
        assert old.is_build_phase is True
        assert old.is_run_phase is False
        assert new.is_build_phase is False
        assert new.is_run_phase is True


# ------------------------------------------------------------------
# Log rendering tests
# ------------------------------------------------------------------


class TestBuilderLogRendering:
    """builder_view._render_log produces correct Rich markup."""

    def test_info_log(self):
        from toad.widgets.builder_view import _render_log

        entry = LogEntry(level="info", message="hello", timestamp="10:00")
        rendered = _render_log(entry)
        assert "hello" in rendered
        assert "INFO" in rendered
        assert "10:00" in rendered

    def test_error_log_color(self):
        from toad.widgets.builder_view import _render_log

        entry = LogEntry(level="error", message="fail")
        rendered = _render_log(entry)
        assert "[red bold]" in rendered
        assert "ERROR" in rendered

    def test_warn_log_color(self):
        from toad.widgets.builder_view import _render_log

        entry = LogEntry(level="warn", message="caution")
        rendered = _render_log(entry)
        assert "[yellow]" in rendered
        assert "WARN" in rendered

    def test_debug_log_color(self):
        from toad.widgets.builder_view import _render_log

        entry = LogEntry(level="debug", message="trace")
        rendered = _render_log(entry)
        assert "[dim]" in rendered
        assert "DEBUG" in rendered

    def test_no_timestamp(self):
        from toad.widgets.builder_view import _render_log

        entry = LogEntry(level="info", message="no ts")
        rendered = _render_log(entry)
        # Should not have an empty timestamp prefix
        assert rendered.strip().startswith("[")

    def test_unknown_level_defaults_white(self):
        from toad.widgets.builder_view import _render_log

        entry = LogEntry(level="custom", message="msg")
        rendered = _render_log(entry)
        assert "[white]" in rendered


class TestAutomationLogRendering:
    """automation_view._render_log produces correct Rich markup."""

    def test_info_log(self):
        from toad.widgets.automation_view import _render_log

        entry = LogEntry(level="info", message="running")
        rendered = _render_log(entry)
        assert "running" in rendered
        assert "INFO" in rendered

    def test_error_log(self):
        from toad.widgets.automation_view import _render_log

        entry = LogEntry(level="error", message="crash")
        rendered = _render_log(entry)
        assert "[red bold]" in rendered

    def test_warning_alias(self):
        from toad.widgets.automation_view import _render_log

        entry = LogEntry(level="warning", message="heads up")
        rendered = _render_log(entry)
        assert "[yellow]" in rendered
        assert "WARNING" in rendered


# ------------------------------------------------------------------
# Builder/Automation view helper tests
# ------------------------------------------------------------------


class TestBuilderViewHelpers:
    """Phase badge and related helpers."""

    def test_phase_badge_colors(self):
        from toad.widgets.builder_view import PHASE_COLORS, _phase_badge

        for phase, color in PHASE_COLORS.items():
            badge = _phase_badge(phase)
            assert f"[{color}]" in badge
            assert phase.upper() in badge

    def test_phase_badge_unknown_uses_dim(self):
        from toad.widgets.builder_view import _phase_badge

        badge = _phase_badge("unknown")
        assert "[dim]" in badge


class TestAutomationViewHelpers:
    """Status badge and metric rendering."""

    def test_status_badge_colors(self):
        from toad.widgets.automation_view import STATUS_COLORS, _status_badge

        for status, color in STATUS_COLORS.items():
            badge = _status_badge(status)
            assert f"[{color}]" in badge
            assert status.upper() in badge

    def test_render_metric(self):
        from toad.widgets.automation_view import _render_metric

        line = _render_metric("requests", "142")
        assert "[bold]requests[/]" in line
        assert "142" in line


# ------------------------------------------------------------------
# Error state tests
# ------------------------------------------------------------------


class TestErrorState:
    """Error conditions are properly surfaced."""

    def test_error_state_from_json(self):
        raw = _build_state(
            phase="develop",
            status="error",
            error="Compilation failed",
            logs=[{"level": "error", "message": "exit code 1"}],
        )
        state = _parse_state(raw)
        assert state.status == "error"
        assert state.error == "Compilation failed"
        assert state.logs[0].level == "error"

    def test_error_none_when_absent(self):
        raw = _build_state(phase="run", status="running")
        state = _parse_state(raw)
        assert state.error is None

    def test_error_in_run_phase(self):
        raw = _build_state(
            phase="run",
            status="error",
            error="Agent timeout",
        )
        state = _parse_state(raw)
        assert state.is_run_phase is True
        assert state.error == "Agent timeout"


# ------------------------------------------------------------------
# CanonStateWidget message types
# ------------------------------------------------------------------


class TestCanonStateWidgetMessages:
    """Message classes exist with correct interfaces."""

    def test_detected_message_is_message(self):
        from textual.message import Message

        msg = CanonStateWidget.CanonStateDetected()
        assert isinstance(msg, Message)

    def test_updated_message_carries_state(self):
        state = CanonState(phase="run", status="running")
        msg = CanonStateWidget.CanonStateUpdated(state)
        assert msg.state is state
        assert msg.state.phase == "run"

    def test_updated_message_is_message(self):
        from textual.message import Message

        state = CanonState()
        msg = CanonStateWidget.CanonStateUpdated(state)
        assert isinstance(msg, Message)


# ------------------------------------------------------------------
# MainScreen auto-show handler existence
# ------------------------------------------------------------------


class TestMainScreenCanonHandlers:
    """MainScreen has canon state event handlers."""

    def test_canon_detected_handler_exists(self):
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "_on_canon_detected")

    def test_canon_updated_handler_exists(self):
        from toad.screens.main import MainScreen

        assert hasattr(MainScreen, "_on_canon_updated")


# ------------------------------------------------------------------
# ProjectStatePane section registration
# ------------------------------------------------------------------


class TestProjectStatePaneSections:
    """Builder and Automation sections are registered."""

    def test_builder_section_registered(self):
        import inspect

        from toad.widgets.project_state_pane import ProjectStatePane

        source = inspect.getsource(ProjectStatePane)
        assert "Builder" in source or "builder" in source

    def test_automation_section_registered(self):
        import inspect

        from toad.widgets.project_state_pane import ProjectStatePane

        source = inspect.getsource(ProjectStatePane)
        assert "Automation" in source or "automation" in source

    def test_canon_state_widget_mounted(self):
        import inspect

        from toad.widgets.project_state_pane import ProjectStatePane

        source = inspect.getsource(ProjectStatePane)
        assert "CanonStateWidget" in source


# ------------------------------------------------------------------
# Graceful empty state
# ------------------------------------------------------------------


class TestGracefulEmptyState:
    """Absent .canon/state.json → empty / default CanonState."""

    def test_empty_parse(self):
        state = _parse_state({})
        assert state == CanonState()

    def test_empty_state_is_neither_build_nor_run(self):
        state = CanonState()
        assert state.is_build_phase is False
        assert state.is_run_phase is False
