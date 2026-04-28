"""Unix socket controller for external agent/script control of the TUI.

Starts an asyncio Unix socket server inside the Textual event loop.
Accepts JSON-line commands, dispatches to the app, returns JSON responses.

Socket path: /tmp/toad-{pid}.sock (auto-cleaned on shutdown).

Protocol (JSON lines, one request per connection):

    {"cmd": "snapshot"}
    {"cmd": "query", "selector": "Button"}
    {"cmd": "action", "name": "toggle_dark"}
    {"cmd": "update", "selector": "#status", "text": "new text"}
    {"cmd": "press", "key": "enter"}
    {"cmd": "focus", "selector": "#input"}
    {"cmd": "ping"}
"""

from __future__ import annotations

import atexit
import asyncio
import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

from textual.widget import Widget

if TYPE_CHECKING:
    from textual.app import App


SOCKET_DIR = Path("/tmp")

RESERVED_OBJECTIVE_KEYS = frozenset(
    {"objective", "output_format", "tool_scope", "boundary"}
)


def _validate_objective_payload(payload: Any) -> str | None:
    """Return an error string if ``payload`` is not a valid objective dict.

    v1 requires a string ``objective`` key. ``output_format``, ``tool_scope``,
    and ``boundary`` are accepted but not yet consumed. Unknown keys are
    rejected so typos surface early.
    """
    if not isinstance(payload, dict):
        return "objective payload must be a dict"
    if "objective" not in payload or not isinstance(payload["objective"], str):
        return "objective payload must contain a string 'objective'"
    extras = set(payload) - RESERVED_OBJECTIVE_KEYS
    if extras:
        return f"unknown objective keys: {sorted(extras)}"
    return None


def _socket_path() -> Path:
    return SOCKET_DIR / f"toad-{os.getpid()}.sock"


def _serialize_widget(widget: Widget) -> dict[str, Any]:
    """Serialize a widget to a plain dict."""
    text = ""
    if hasattr(widget, "renderable"):
        try:
            text = str(widget.renderable)
        except Exception:
            pass
    elif hasattr(widget, "label"):
        try:
            text = str(widget.label)
        except Exception:
            pass

    return {
        "id": widget.id,
        "type": type(widget).__name__,
        "classes": list(widget.classes),
        "text": text,
        "focused": widget.has_focus,
        "visible": widget.display,
    }


async def _handle_client(
    app: App,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Handle a single client connection."""
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        if not line:
            return
        request = json.loads(line.decode("utf-8").strip())
        response = await _dispatch(app, request)
    except asyncio.TimeoutError:
        response = {"error": "timeout"}
    except json.JSONDecodeError as exc:
        response = {"error": f"invalid json: {exc}"}
    except Exception as exc:
        response = {"error": str(exc)}

    writer.write(json.dumps(response).encode("utf-8") + b"\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def _dispatch(app: App, request: dict[str, Any]) -> dict[str, Any]:
    """Route a command to the appropriate handler."""
    cmd = request.get("cmd")
    if cmd is None:
        return {"error": "missing 'cmd' field"}

    if cmd == "ping":
        return {"ok": True, "pid": os.getpid()}

    if cmd == "snapshot":
        widgets = [_serialize_widget(w) for w in app.query("*")]
        return {"widgets": widgets}

    if cmd == "query":
        selector = request.get("selector")
        if not selector:
            return {"error": "missing 'selector'"}
        widgets = [_serialize_widget(w) for w in app.query(selector)]
        return {"widgets": widgets}

    if cmd == "action":
        name = request.get("name")
        if not name:
            return {"error": "missing 'name'"}
        # Strip the optional "screen." namespace so Conductor's agent can use
        # either bare (``open_subagent_tab``) or namespaced
        # (``screen.open_subagent_tab``) names.
        bare_name = name.split(".", 1)[1] if name.startswith("screen.") else name
        if bare_name in ("open_subagent_tab", "close_subagent_tab"):
            args = request.get("args")
            if not isinstance(args, dict):
                return {"error": f"'{bare_name}' requires 'args' object"}
            tab_name = args.get("name")
            if not isinstance(tab_name, str) or not tab_name:
                return {"error": f"'{bare_name}' requires 'args.name' string"}
            if bare_name == "open_subagent_tab":
                objective = args.get("objective")
                if objective is None:
                    return {"error": "'open_subagent_tab' requires 'args.objective'"}
                err = _validate_objective_payload(objective)
                if err is not None:
                    return {"error": err}
                await app.screen.action_open_subagent_tab(
                    name=tab_name, objective=objective
                )
            else:
                await app.screen.action_close_subagent_tab(name=tab_name)
            return {"ok": True}
        await app.run_action(name)
        return {"ok": True}

    if cmd == "subagent_status":
        status = app.screen.subagent_status()
        return {
            "ok": True,
            "tabs": list(status.get("tabs", [])),
            "count": int(status.get("count", 0)),
        }

    if cmd == "update":
        selector = request.get("selector")
        text = request.get("text")
        if not selector or text is None:
            return {"error": "missing 'selector' or 'text'"}
        try:
            widget = app.query_one(selector)
        except Exception as exc:
            return {"error": f"query failed: {exc}"}
        if hasattr(widget, "update"):
            widget.update(text)
            return {"ok": True}
        return {"error": f"widget {type(widget).__name__} has no update method"}

    if cmd == "press":
        key = request.get("key")
        if not key:
            return {"error": "missing 'key'"}
        await app._press_keys(key)
        return {"ok": True}

    if cmd == "focus":
        selector = request.get("selector")
        if not selector:
            return {"error": "missing 'selector'"}
        try:
            widget = app.query_one(selector)
        except Exception as exc:
            return {"error": f"query failed: {exc}"}
        widget.focus()
        return {"ok": True}

    return {"error": f"unknown cmd: {cmd}"}


async def start_socket_server(app: App) -> asyncio.AbstractServer:
    """Start the Unix socket server for external control.

    Returns the server instance (caller should keep a reference).
    """
    path = _socket_path()
    # Clean up stale socket from a previous crash
    path.unlink(missing_ok=True)

    server = await asyncio.start_unix_server(
        lambda r, w: _handle_client(app, r, w),
        path=str(path),
    )
    # Safety net: clean up socket file on interpreter exit (crash, SIGTERM)
    atexit.register(lambda p=path: p.unlink(missing_ok=True))
    app.log.info(f"Socket controller listening on {path}")
    return server


async def stop_socket_server(server: asyncio.AbstractServer) -> None:
    """Stop the server and clean up the socket file."""
    server.close()
    await server.wait_closed()
    _socket_path().unlink(missing_ok=True)
