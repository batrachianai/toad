"""Data layer for the Canon TUI.

Currently re-exports :class:`PlanExecutionModel`, the watcher that turns
an orchestrator plan directory (``.orchestrator/plans/<slug>/``) into
the Textual messages the plan-execution widgets already handle.
"""

from __future__ import annotations

from toad.data.plan_execution_model import PlanExecutionModel


__all__ = ["PlanExecutionModel"]
