# State.json Contract — Canon TUI ↔ Orchestrator Engine

The plan-execution panel renders entirely from local files written by the
orchestrator engine in `claude-code-config`. The TUI does **not** call
GitHub. This doc pins the fields the TUI reads and where they get
written, so cross-repo schema drift is easy to spot.

## Source files

Per plan, under `.orchestrator/plans/<slug>/`:

| File | Reader | Writer |
|------|--------|--------|
| `state.json` | `src/toad/data/plan_execution_model.py` | `claude-code-config/scripts/orch-engine.sh`, `orch-review.sh`, `orch-verify.sh`, `orch-watchdog.sh` |
| `logs/<id>.log` | `PlanExecutionModel._scan_logs` | worker shells |

Plus `master.json` at the orchestrator root, read by
`src/toad/widgets/orchestrator_state.py`.

## Fields the TUI consumes

```jsonc
{
  "plan": "20260428-stop-hook-agent-bump",      // slug
  "issueNumber": 258,
  "status": "running"                            // running | verifying | completed | failed | aborted
                                                 // — terminal trigger #1
  "startedAt": "2026-04-28T20:14:03Z",
  "updatedAt": "2026-04-28T20:30:21Z",           // elapsed = updated - started

  "items": [
    { "id": 1, "description": "...",
      "deps": [], "status": "done" }             // queued | ready | running | done | failed | review
  ],

  "finalReview": {
    "status": "done",                            // pending | running | done
    "result": "SHIP",                            // SHIP | REVISE — terminal trigger #2
    "reworkItems": [],                           // ints; len() = items_reworked
    "prUrl": null,                               // ★ engine TODO — see "Open gaps" below
    "prNumber": null                             // ★ engine TODO
  },

  "verification": {
    "status": "passed",                          // passed | failed | (absent if not run)
    "unchecked": []                              // list or int — both accepted
  },

  "reviewIterations": 7                          // optional — engine TODO, used in summary line
}
```

The TUI tolerates absent fields; presence drives the completion banner.

## Terminal-state detection

`PlanExecutionModel._is_terminal()` in
`src/toad/data/plan_execution_model.py` fires `PlanFinished` when **any**
of these are true:

- `state.status` ∈ `{completed, failed, aborted}`
- `state.finalReview.result` ∈ `{SHIP, REVISE}`

Both paths matter — engine bailouts (budget exhausted, watchdog kill)
reach `status: failed` without ever populating `finalReview.result`,
and we want the panel to flip terminal anyway.

## Open gaps (engine side)

The engine has the data; it just doesn't persist it. Each gap below
degrades the completion banner gracefully — TUI handles missing fields
without crashing — but the banner is more useful when they're present.

### 1. `finalReview.prUrl` / `finalReview.prNumber` ★

`scripts/orch-engine.sh` already has `PR_URL` in scope at the
`gh-push-and-pr.sh` invocation (~line 875). The success branch logs it
but never writes it to state. Fix: in the `if [[ "${rc}" -eq 0 ]]` block,
patch `state.json` with
`.finalReview.prUrl = $url | .finalReview.prNumber = $num` before the
`status: "completed"` write at ~line 917. Spec:
`claude-code-config/docs/specs/canon-tui-plan-completion.md`,
"Engine-side requirement".

### 2. `reviewIterations` (top-level int)

Used to render `Reviews: N total iterations` on the summary line. Nice
to have. Increment in `scripts/orch-review.sh` whenever a review pass
runs.

## When changing the schema

If you add or rename a field on the engine side, update **both**:

1. `_initial_parse` / `_scan_state` / `_build_terminal_info` in
   `src/toad/data/plan_execution_model.py`.
2. The header / terminal-line render in
   `src/toad/widgets/plan_execution_tab.py::_format_terminal_line`.

Tests fixtures live in `tests/data/test_plan_execution_model.py` and
`tests/widgets/test_plan_execution_tab.py` — keep the fixture payload
matching the real engine schema (e.g. `finalReview.result`, not
`.verdict`). Drift here is silent: a wrong field name returns `None`,
the panel never reaches terminal, and no test fails.

## History note

A previous version of the model read `finalReview.verdict` — a phantom
field that never existed in any engine version. The terminal banner
silently never fired. See commit `52a6528` ("Plan completion: terminal
state, phase header, progress gauge") for the fix.
