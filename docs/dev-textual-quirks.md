# Textual Quirks & Local Patches

Things upstream Textual gets subtly wrong that we work around in
Canon. Each entry says **what's wrong**, **why our fix exists**, and
**how to remove the workaround** if upstream eventually fixes it.

## 1. `alt+<multichar-key>` is dropped on legacy xterm input

**Symptom.** `option+enter` in macOS Terminal.app and iTerm2 (default
config, no Kitty keyboard protocol) arrives as a plain `enter` event.
Widgets cannot tell it apart from Return, so option+enter ends up
sending the prompt instead of inserting a newline.

**Cause.** `textual._xterm_parser.XTermParser._sequence_to_key_events`
only prepends `alt+` to **single-character** key names:

```python
# textual/_xterm_parser.py, around line 394
if len(name) == 1 and alt:
    name = f"alt+{name}"
```

When iTerm2 sends `ESC + CR` for option+enter, the parser correctly
flags `alt=True` but skips the prefix because `name == "enter"` is
5 chars. The Key event arrives with `key="enter"`, alt info lost. Same
problem for any multi-char key: `tab`, `space`, `home`, etc.

**Workaround.** `src/toad/_textual_key_patch.py` wraps
`_sequence_to_key_events` and re-emits the event with the `alt+` prefix
when `alt=True` was passed but the key string came back without a
modifier prefix. The patch is loaded eagerly from `src/toad/__init__.py`
so it applies before the driver starts reading keys. Idempotent.

**Removal criteria.** If a future Textual release removes the
`len(name) == 1` gate (e.g. by always prepending modifiers when the
parser detected them), drop `_textual_key_patch.py` and the import in
`__init__.py`. Smoke-test by pressing option+enter on a stock macOS
Terminal — it should arrive as `alt+enter` without the patch.

**Also affects.** Anywhere we want to bind `alt+<word>`. If a binding
seems silently dead after upgrading Textual, this is the first thing to
check.

## 2. Two bindings on the same chord don't fall through

**Symptom.** In an earlier version of `prompt.py` we had two bindings
on `shift+enter` — one for `newline`, one for `multiline_submit` —
gated by `check_action`. Once `multi_line` flipped to True, **both**
keys went dead: enter ran the now-disabled `submit`, shift+enter ran
the now-disabled `newline`, and the second binding for the same chord
was never tried.

**Cause.** Textual stops at the first binding match for a key; if
`check_action` returns False, the key is consumed but no action runs.
There is no fall-through to the next binding for the same chord.

**Workaround.** Don't share chords. Use one binding per chord and
branch inside the action. See `src/toad/widgets/prompt.py`:
`action_enter_pressed` / `action_shift_enter_pressed`.

**Note.** This is a Textual design choice, not a bug. Don't try to
"fix" it — just write your bindings to avoid the pattern.

## 3. Circles render badly in terminals

**Symptom.** Terminal cells are roughly 2:1 (height:width); any
attempt at a "donut" or "pie" chart drawn from cell positions looks
oblong, lopsided, or chunky depending on font and zoom.

**Workaround.** Don't draw circles. The plan-execution header uses a
flat 2-row gauge (`PlanDonut` widget — name kept for import stability
even though the visual is now horizontal): segmented bar above,
percentage below. Reads cleanly at any size.

**Lesson for new widgets.** Prefer rectangular composition (bars,
sparklines, stacked blocks) over rotational shapes. Half-block
characters (`▀ ▄ ▌ ▐`) give 2× vertical resolution if you need finer
detail.

## 4. `Static` with Rich `Text` doesn't auto-expand

This one is in the project CLAUDE.md but worth repeating because it
keeps biting:

> `Static` with Rich Text does not auto-expand width — set
> `styles.min_width` explicitly to enable horizontal scroll.
> `ScrollableContainer` handles both axes; don't nest
> `VerticalScroll` inside `HorizontalScroll`.
> `height: auto` on a scroll container collapses it — use `height: 1fr`.

If a widget mysteriously renders truncated or won't scroll, check sizing
before anything else.
