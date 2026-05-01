"""Make Textual surface ``alt+<multichar-key>`` events on legacy xterm input.

Textual's xterm parser only prepends the ``alt+`` modifier to **single
character** key names (see ``_xterm_parser.py``: ``if len(name) == 1 and
alt:``). On terminals that don't speak the Kitty keyboard protocol —
which still includes most stock macOS Terminal.app and iTerm2 setups
even with "Use Option as Meta" / "Esc+" enabled — pressing
``option+enter`` arrives as the byte sequence ``ESC + CR``. The parser
correctly detects ``alt=True`` but skips the ``alt+`` prefix because the
key name is ``"enter"`` (5 chars), so widgets receive a plain ``enter``
event with no way to tell it apart from a regular Return.

We patch ``XTermParser._sequence_to_key_events`` to wrap its output and
re-emit a properly-prefixed event whenever ``alt`` was set but the
resulting key string lacks the modifier. The patch is import-time and
idempotent — calling it twice is a no-op. It is loaded from
``toad/__init__.py`` so every Canon entry point picks it up before the
app driver starts reading keys.
"""

from __future__ import annotations

from textual import events
from textual._xterm_parser import XTermParser


_PATCH_FLAG = "_canon_alt_key_patch_applied"
_KNOWN_MODIFIERS = ("alt+", "shift+", "ctrl+", "meta+", "super+", "hyper+")


def apply() -> None:
    """Install the alt-prefix backfill. Safe to call multiple times."""
    if getattr(XTermParser, _PATCH_FLAG, False):
        return

    original = XTermParser._sequence_to_key_events

    def patched(self, sequence: str, alt: bool = False):  # type: ignore[no-untyped-def]
        for event in original(self, sequence, alt):
            if alt and event.key and not event.key.startswith(_KNOWN_MODIFIERS):
                yield events.Key(f"alt+{event.key}", event.character)
            else:
                yield event

    XTermParser._sequence_to_key_events = patched  # type: ignore[method-assign]
    setattr(XTermParser, _PATCH_FLAG, True)
