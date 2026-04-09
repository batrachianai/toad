# Async Phase Runner — `/canon-start` in Conductor

Design for running `/canon-start` as a phased background process from the
Conductor TUI, with user feedback between phases.

## Problem

`/canon-start` is a multi-phase prompt (init, scaffold, strategy, develop, run)
that today runs inside the main agent session. It blocks the conversation and
hijacks the agent. When run inside the Conductor TUI, we want:

1. The main chat agent stays responsive (not blocked).
2. Long-running phases (scaffold, develop, ralph-loop) run in the background.
3. Phases that need user input (strategy selection in step 5, risk review)
   pause and surface the question to the user through the conductor.
4. The process is resumable — if the user closes the TUI or the agent crashes,
   re-running picks up where it left off.

## Current architecture

- `canon.sh` launches a tmux session with the agent + dashboard.
- `/canon-start` is a `.claude/commands/canon-start.md` prompt fetched from
  GitHub during scaffold. It runs as a single long prompt inside one agent.
- The command uses `AskUserQuestion` (Claude's built-in tool) when it needs
  user input (e.g. strategy selection in phase 5).
- State is already tracked in `.canon/state.json` with phase, status, logs,
  and metrics.

## Design: checkpoint-based phase runner

Break `/canon-start` into discrete phases. Each phase runs as a background
command. When a phase completes or needs input, it exits. The conductor
reads the exit state and either launches the next phase or asks the user.

### State file contract

`.canon/state.json` already tracks phase and status. Extend it with a
`conductor` block:

```json
{
  "phase": "strategy",
  "status": "waiting_for_input",
  "conductor": {
    "question": {
      "text": "Which strategy approach do you want to use?",
      "header": "Strategy",
      "options": [
        {
          "id": "template-nba-momentum",
          "label": "Use template: NBA Momentum",
          "description": "Includes bootstrapped code and pre-filled plan"
        },
        {
          "id": "discover",
          "label": "Run /discover",
          "description": "Scan markets and generate a strategy spec"
        },
        {
          "id": "provide",
          "label": "Provide a spec",
          "description": "Point to an existing strategy document"
        }
      ]
    },
    "answer": null
  }
}
```

When `status` is `waiting_for_input` and `conductor.question` is populated,
the conductor surfaces the question. When the user answers, the conductor
writes `conductor.answer` and sets `status` back to `ready`.

### Phase definitions

Each phase is a self-contained prompt or script that:

1. Reads `.canon/state.json` to determine current state.
2. Does its work (scaffold, develop, etc.).
3. Exits with one of three outcomes:
   - **done** — phase complete, next phase can start.
   - **waiting_for_input** — wrote a question to state file, needs answer.
   - **error** — something broke, error in state file.

| Phase | Runs as | Needs input? | Exit condition |
|-------|---------|-------------|----------------|
| detect | inline (fast) | no | Determines phase, writes to state |
| init | background bash (`canon-scaffold.sh`) | no | Script exits 0 or error |
| scaffold | background bash (`canon-scaffold.sh --force`) | no | Script exits 0 or error |
| strategy | background agent prompt | **yes** — strategy selection | Writes question, exits with `waiting_for_input` |
| develop | background agent prompt | maybe — design decisions | Writes question or runs to completion |
| run | background bash (`canon-runner.sh`) | no | Long-running, fire-and-forget |

### Conductor flow

```
User types /canon-start
  │
  ├─ Conductor reads .canon/state.json (or creates it)
  ├─ Runs detect phase inline → determines current phase
  │
  ├─ Launches phase script/prompt in background
  │   └─ run_in_background: true
  │
  ├─ Background process completes (conductor gets notified)
  │   ├─ Reads .canon/state.json
  │   │
  │   ├─ status == "waiting_for_input"?
  │   │   ├─ Read conductor.question from state file
  │   │   ├─ Call AskUserQuestion with the question
  │   │   ├─ Write conductor.answer to state file
  │   │   ├─ Set status = "ready"
  │   │   └─ Re-launch same phase in background
  │   │
  │   ├─ status == "done" or phase advanced?
  │   │   ├─ Log completion to user
  │   │   └─ Launch next phase in background
  │   │
  │   └─ status == "error"?
  │       └─ Show error to user, ask whether to retry or abort
  │
  └─ Repeat until phase == "run" (fire-and-forget)
```

### How each phase runs

**Phases that are shell scripts** (init, scaffold, run):
Run via `Bash` tool with `run_in_background: true`. These already update
`.canon/state.json` via `terminal-ui-write.sh`. No changes needed.

**Phases that are agent prompts** (strategy, develop):
These are the tricky ones. Options:

**Option A — Headless agent subprocess:**
Spawn a second `claude` process in headless mode with a scoped prompt:
```bash
claude --dangerously-skip-permissions -p "Read .canon/state.json. \
  You are in the 'strategy' phase. <phase-specific instructions>. \
  When you need user input, write the question to .canon/state.json \
  under conductor.question, set status to waiting_for_input, and exit."
```
The conductor runs this in the background and gets notified on exit.

**Option B — Phased prompts in conductor itself:**
Don't spawn a sub-agent. Instead, the conductor reads the phase-specific
instructions from a prompt file and executes them directly. When it hits
an `AskUserQuestion` moment, it just... asks. No serialization needed.
The prompt is designed so each phase is a self-contained set of
instructions that the conductor can execute in sequence.

**Recommendation: Option B for phases that need input, Option A for
phases that don't.** Strategy selection (needs input) runs in the
conductor. Develop/ralph-loop (long-running, autonomous) runs as a
background subprocess.

### Splitting the canon-start.md command

Today: one monolithic prompt with steps 1-7.

Proposed: split into phase files in `.claude/commands/`:

```
.claude/commands/
  canon-start.md          ← conductor entrypoint (phase router)
  _canon-phase-detect.md  ← inline: detect and write phase
  _canon-phase-init.md    ← background: run scaffold script
  _canon-phase-strategy.md ← conductor: ask user, write spec
  _canon-phase-develop.md  ← background: headless agent
  _canon-phase-run.md      ← background: launch runner
```

The `canon-start.md` becomes a thin router:

```
Read .canon/state.json. Based on the current phase:
- If no state or phase=="init": run _canon-phase-init.md instructions
- If phase=="scaffold": verify scaffold, advance to strategy
- If phase=="strategy": run _canon-phase-strategy.md instructions
  (this phase uses AskUserQuestion — run it inline, not background)
- If phase=="develop": launch _canon-phase-develop.md in background
- If phase=="run": launch canon-runner.sh in background
```

### What changes where

| Component | Change | Scope |
|-----------|--------|-------|
| `canon-start.md` (core repo) | Split into phase router + phase files | Medium — restructure existing prompt |
| `.canon/state.json` | Add `conductor` block with question/answer | Small — extend existing schema |
| `terminal-ui-write.sh` (core repo) | Support writing `conductor.*` fields | Small |
| Conductor TUI | Nothing — conductor is just a Claude agent | None |
| Canon TUI (`conductor-view`) | Optional: watch state file for question events | Nice-to-have |

### Resumability

Because state is in `.canon/state.json`, the process is inherently resumable:

- User closes TUI mid-develop → state says `phase=develop, status=running`
- User re-runs `/canon-start` → detect reads state, sees develop phase,
  re-launches develop from where the code left off
- Background agent crashed → state says `status=error` with error message
- User re-runs → conductor sees error, asks retry or abort

### Open questions

1. **Headless agent auth**: Does `claude --dangerously-skip-permissions`
   work reliably for the develop phase? The agent needs to write files,
   run tests, iterate. If permissions are needed, we're back to needing
   interactive input from a background process.

2. **State file polling vs notification**: Should the conductor poll
   `.canon/state.json` while a background phase runs, or just wait for
   the process exit notification? Polling gives live progress updates
   but adds complexity.

3. **Develop phase granularity**: The develop phase can be long (multiple
   ralph-loop iterations). Should it be further split into sub-phases,
   or is one background run sufficient?

4. **TUI integration**: Should the Canon TUI's `CanonStateWidget` (which
   already watches `.canon/state.json`) gain the ability to render
   `conductor.question` as a UI prompt? This would let the question
   appear in the right pane without the conductor agent needing to
   relay it.
