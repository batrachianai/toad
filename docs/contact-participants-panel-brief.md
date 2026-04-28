# Contact-Participants Panel Brief

A right-pane section for Canon TUI that surfaces live state of the RPA
outreach pipeline (hackathon contact-participants bot) directly beside the
agent conversation.

## Goal

Give operators a glance-level read of the outreach workflow without leaving
the TUI: how many prospects are in each status, what the last 24h of sends
look like, which hackathons are pulling weight, and which sender accounts
are active.

## Constraints

- **Public repo ships zero private code.** The Canon TUI is open-source;
  the outreach pipeline code and credentials are not. The panel must be
  absent (section not mounted, no routes active) unless the operator has
  the private submodule checked out *and* `CANON_RPA_OUTREACH_DATABASE_URL`
  set in their environment *and* a probe query succeeds.
- **Read-only.** No writes, no `subprocess`, no shell-outs. A TUI that
  could mutate the outreach DB is out of scope.
- **Narrow column.** The right pane is ~60–80 cols; wide tables are out.
  Visuals carry proportion-at-a-glance better than truncated columns.
- **Canon palette only.** Tokens from `src/toad/theme.py` — no ad-hoc
  colors.

## Shipped design

The panel ships as four visual-first cards composed inside a new
**Outreach** section in `ProjectStatePane`. No tables, no dense grids.

| Card | Data | Visual |
|------|------|--------|
| **Prospects** | total + count by status | stacked horizontal bar (`messaged / pending`) — the `prospects.status` enum only has `scraped` and `messaged`, so there is no `failed` segment |
| **Sends · 24h** | total sends in the last 24h + per-hour count | single-row 24-slot hourly histogram |
| **Hackathons (top 5)** | per-`source_hackathon` messaged/total | ranked horizontal bars, labeled with `hackathons.name` (LEFT JOIN on `hackathons.url = prospects.source_hackathon`; falls back to URL on miss). `participation_rate` intentionally skipped — source unclear. |
| **Accounts** | per-sender account | colored dot + sends/hr + last-sent relative time |

Refresh cadence is **30 seconds**, owned by `ProjectStatePane`'s existing
timer pattern.

### Graceful degradation

`send_log` may not exist on older or alternate DBs. The provider runs
`SELECT to_regclass('send_log')` first; if it returns null, the Sends and
Accounts cards are hidden (`display = False`) and the panel never crashes.

### Discovery + gating

The public repo defines only the contract. The implementation lives in the
private submodule.

```
src/toad/outreach/protocol.py     OutreachSnapshot, OutreachInfoProvider
src/toad/outreach/registry.py     discover() → provider | None
src/toad/widgets/outreach_cards.py StatLine, Histogram, RankedBar, AccountDot
src/toad/extensions/rpa_outreach/  (git submodule → DEGAorg/rpa-outreach-view)
```

`discover()` returns `None` — and therefore the section never mounts —
when any of these fails:

1. `import toad.extensions.rpa_outreach` raises `ImportError`
2. `CANON_RPA_OUTREACH_DATABASE_URL` is unset
3. The provider's `available()` probe returns False

### Panel wiring

- `SECTION_OUTREACH` + `OUTREACH_REFRESH_INTERVAL = 30` in
  `project_state_pane.py`
- `PANEL_ROUTES["outreach"]` registered unconditionally so chat intents
  resolve even when the section is absent (silently no-ops)
- Chat intents: `show me outreach`, `open the outreach panel`,
  `close the outreach panel`, etc., parsed by the existing
  `_PANEL_KEYWORDS` registry in `conversation.py`
- `tools/verify-tui.py --widget outreach` mounts synthetic card data and
  asserts `discover()` returns `None` when the env var is unset

### Install UX

- `.gitmodules` lists the submodule URL; the submodule init is opt-in
- `install.sh` runs `git submodule update --init --recursive || true` and
  `uv sync --extra outreach || true` — both non-fatal so external users
  install cleanly without the private code
- `psycopg[binary]>=3.2` ships as the `outreach` optional extra in
  `pyproject.toml`

## Out of scope

- Token-based auth. The TUI runs locally; credentials live in the
  operator's env already.
- Writes or bot-control actions from the TUI.
- Porting the Vercel dashboard's table views 1:1.
- Surfacing `participation_rate` — the source field's provenance is
  unclear and it would mislead more than inform.
