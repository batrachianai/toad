# Hand-off to `claude-code-config` — Builder/Run log content

The Canon TUI's **State view → Builder log** renders whatever the
running strategy template writes into `.canon/state.json`. The log
text and the metric keys/values surface in the user-facing panel
verbatim. Two things in there are jargon-y or unclear and should be
fixed in the engine / strategy bundle, not the TUI.

## Where this is read in canon-tui

For reference only — no changes needed on the TUI side:

| File | Role |
|------|------|
| `src/toad/widgets/canon_state.py` | Parses `.canon/state.json` into `CanonState(logs, metrics, …)` |
| `src/toad/widgets/builder_view.py` | Renders status bar, logs, metrics |

## What to fix in core / strategy templates

### 1. Replace "Cycle N — …" log wording

Today's State log includes lines like:

```
Cycle 2 — fetching NBA futures...
```

"Cycle" reads as engineer jargon to anyone who isn't in the loop. The
strategy template that emits these lines should use a more concrete
verb that matches what it just did. Suggested replacements:

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
"refresh", running a model pass is a "evaluation", placing trades is a
"trade pass". Pick the verb at the strategy level so each line tells
the user what was *done*, not which iteration counter ticked.

### 2. Rename the metric keys

Today's State view bottom row:

```
mode: dry-run        cycles: 0
signals: 18          errors: 0
games: 0             markets: 0
```

`cycles` and `signals` are template-internal terminology. Agreed
user-facing names — natural language, no underscores:

| Current key | New key       |
|-------------|---------------|
| `cycles`    | `runs`        |
| `signals`   | `opportunities` |
| `games`     | `games` (keep) |
| `markets`   | `markets` (keep) |
| `errors`    | `errors` (keep) |
| `mode`      | `mode` (keep) |

Keys are written to `state.metrics` as a flat dict by the strategy
runner. Renaming is a one-line change wherever the metric is bumped
(e.g. `state.metrics.cycles += 1` → `state.metrics.runs += 1`).

**TUI-side stopgap already shipped (canon-tui ≥ 0.7.10).** Until core
lands, the TUI renders the labels via an alias map in
`src/toad/widgets/builder_view.py::METRIC_LABEL_ALIASES`. So the
panel reads "Runs / Opportunities / Games / Markets / Errors / Mode"
even if `state.metrics` still uses the old keys. Once core renames
the keys, drop the obsolete entries from the alias map.

### 3. Optional: log levels

Today entries are coloured by `level` (`info` / `warn` / `error` /
`debug`). The level text itself is **not** displayed — only the colour
varies. If you want explicit `WARN` / `ERROR` tags in the line, that
would be a TUI change (in `_render_log`). Mention it if so.

## Summary checklist for core

- [ ] Strategy templates replace "Cycle N — <verb>…" log wording
      with action-led phrasing (Round / Pass / Sweep / Pull / etc.).
- [ ] `state.metrics` keys renamed (`cycles`, `signals`, `markets` at
      minimum) to user-facing nouns.
- [ ] Decide whether log levels should appear inline as text tags;
      if yes, file a follow-up on canon-tui.

After these land, the State view in canon-tui will reflect them
automatically — no canon-tui changes required.
