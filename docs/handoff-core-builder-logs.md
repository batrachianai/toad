# Hand-off to `claude-code-config` — Builder/Run log wording

The Canon TUI's **State view → Builder log** renders whatever the
running strategy template writes into `.canon/state.json`. The log
text surfaces in the user-facing panel verbatim. One thing in there
reads as engineer jargon and should be fixed in the engine /
strategy bundle, not the TUI.

## Where this is read in canon-tui (reference only)

| File | Role |
|------|------|
| `src/toad/widgets/canon_state.py` | Parses `.canon/state.json` into `CanonState(logs, metrics, …)` |
| `src/toad/widgets/builder_view.py` | Renders status bar, metrics, logs |

No canon-tui changes needed for this hand-off — only the strings in
the log lines.

## What to fix

### Replace "Cycle N — …" log wording

Today's State log includes lines like:

```
Cycle 2 — fetching NBA futures...
```

"Cycle" reads as engineer jargon to anyone who isn't in the loop. The
strategy template that emits these lines should use a verb that
matches what the cycle actually did. Suggested replacements:

| Old | New |
|-----|-----|
| `Cycle 1 — fetching NBA futures...` | `Round 1: refreshing odds for NBA futures…` |
| `Cycle 2 — fetching NBA futures...` | `Round 2: refreshing odds for NBA futures…` |
| `Cycle N — <action>...` | `Round N: <action>…` |

If "round" doesn't fit, alternatives that read naturally:

- `Sweep N: …`
- `Pass N: …`
- `Pull N: …` (when the action is a fetch)

The literal verb depends on what the cycle does — fetching odds is a
"refresh", running a model pass is an "evaluation", placing trades is
a "trade pass". Pick the verb at the strategy level so each line
tells the user what was *done*, not which iteration counter ticked.

## What does NOT need a core change

- **Metric labels (Runs, Opportunities, Games, Markets, Errors,
  Mode).** The TUI now applies these names at render time via an
  alias map in `src/toad/widgets/builder_view.py::METRIC_LABEL_ALIASES`
  (canon-tui ≥ 0.7.10). Core can keep writing `cycles` / `signals`
  in `state.metrics` — the panel reads clean either way.

  Optional polish: if you do rename the keys in `state.metrics` for
  consistency on the engine side, drop the matching entries from
  `METRIC_LABEL_ALIASES` afterwards. Not blocking.

- **Log levels.** The TUI colours each log line by `level` (`info` /
  `warn` / `error` / `debug`); no core change needed. If you ever
  want explicit `[ERROR]` / `[WARN]` text tags inline, that's a TUI
  change — file an issue on canon-tui.

## Summary checklist for core

- [ ] Strategy templates replace `Cycle N — <verb>…` log wording
      with action-led phrasing (Round / Pass / Sweep / Pull / etc.).

That's it. After this lands, the State view in canon-tui reflects it
automatically.
