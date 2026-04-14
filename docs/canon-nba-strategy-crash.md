# Canon crash on nba-strategy: DuplicateIds in PipelineView

## Error

Running `canon .` in `/Users/cerratoa/dega/nba-strategy` crashes with:

```
DuplicateIds: Tried to insert a widget with ID 'pipeline-placeholder',
but a widget already exists with that ID
```

## Root cause

`PipelineView.render_flow()` calls `row.remove_children()` followed immediately by `row.mount(Static(..., id="pipeline-placeholder"))`. In Textual, `remove_children()` is **async** — it schedules removal but doesn't complete it synchronously. When `mount()` runs on the next line, the old `pipeline-placeholder` widget is still in the DOM, causing a duplicate ID collision.

The same pattern existed in `BuilderView._render_state()` for the log scroll container.

### Call chain

```
MainScreen._on_canon_updated()
  → _forward_canon_state(state)
    → BuilderView._render_state(state)
      → PipelineView.render_flow(state.flow)   # flow=None for nba-strategy
        → row.remove_children()                 # async, not awaited!
        → row.mount(Static(id="pipeline-placeholder"))  # BOOM: old one still exists
```

## Why nba-strategy triggers it

The nba-strategy canon state has `flow=None` (no pipeline flow data defined), so `render_flow` always hits the "no flow" placeholder branch. Other projects that define a flow in their `canon.yaml` might not hit this path.

## Fix applied

Made the entire render chain async:

| File | Change |
|------|--------|
| `src/toad/widgets/pipeline_view.py` | `render_flow` → `async`, `await remove_children()` and `await mount()` |
| `src/toad/widgets/builder_view.py` | `_render_state` and its event handler → `async`, `await` all child mutations |
| `src/toad/screens/main.py` | `_forward_canon_state` and `_on_canon_updated` → `async` |

Also batched individual `mount()` calls into `mount_all()` to reduce layout passes.

## Verification

- `uv run python tools/verify-tui.py --widget imports` passes
- `canon .` in nba-strategy renders without crash (tested with reinstall via `install.sh`)
