# Socket Controller — External TUI Control

The socket controller lets external processes (AI agents, scripts, orchestrators)
read and manipulate the Toad TUI at runtime via a Unix domain socket.

## How it works

When Toad starts, it opens an asyncio Unix socket server at
`/tmp/toad-{pid}.sock`. Any process can connect, send a JSON-line command,
and receive a JSON-line response. The server runs in the same asyncio event
loop as Textual — no threads, no locking.

The socket is automatically cleaned up when Toad exits.

## Protocol

One JSON object per connection (newline-terminated). The server responds with
one JSON object and closes the connection.

### Commands

#### `ping` — check the TUI is alive

```json
→ {"cmd": "ping"}
← {"ok": true, "pid": 12345}
```

#### `snapshot` — get the full widget tree

```json
→ {"cmd": "snapshot"}
← {"widgets": [{"id": "header", "type": "Header", "classes": [], "text": "...", "focused": false, "visible": true}, ...]}
```

#### `query` — CSS-selector query on widgets

```json
→ {"cmd": "query", "selector": "Button"}
← {"widgets": [...]}
```

#### `action` — invoke a Textual action method

```json
→ {"cmd": "action", "name": "toggle_dark"}
← {"ok": true}
```

Actions correspond to `action_*` methods on App, Screen, or Widget. For
example, `toggle_dark` calls `action_toggle_dark()`.

#### `update` — update a widget's content

```json
→ {"cmd": "update", "selector": "#status", "text": "new content"}
← {"ok": true}
```

Only works on widgets with an `update()` method (Label, Static, etc.).

#### `press` — synthesize a keypress

```json
→ {"cmd": "press", "key": "enter"}
← {"ok": true}
```

#### `focus` — move focus to a widget

```json
→ {"cmd": "focus", "selector": "#input"}
← {"ok": true}
```

## CLI client

`tools/toad-ctl.sh` wraps the protocol for shell use. Requires `socat`.

```bash
# Auto-discovers the socket in /tmp/
toad-ctl.sh ping
toad-ctl.sh snapshot
toad-ctl.sh action toggle_dark
toad-ctl.sh query "Button"
toad-ctl.sh update "#status" "hello"
toad-ctl.sh press enter
toad-ctl.sh focus "#input"

# Override socket path
TOAD_SOCKET=/tmp/toad-12345.sock toad-ctl.sh ping

# Send raw JSON
toad-ctl.sh raw '{"cmd":"ping"}'
```

## Python client example

```python
import json
import socket

def toad_cmd(cmd: dict, sock_path: str = "/tmp/toad-*.sock") -> dict:
    """Send a command to the Toad socket controller."""
    from glob import glob
    path = glob(sock_path)[0]
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    s.sendall(json.dumps(cmd).encode() + b"\n")
    response = s.makefile().readline()
    s.close()
    return json.loads(response)

# Usage
toad_cmd({"cmd": "ping"})
toad_cmd({"cmd": "action", "name": "toggle_dark"})
```

## Architecture

```
External process              Toad TUI process
     │                              │
     │  JSON line over socket ────► │ asyncio.start_unix_server
     │  ◄──── JSON response         │   └─ _handle_client()
     │                              │        └─ _dispatch()
     │                              │             ├─ app.run_action()
     │                              │             ├─ app.query()
     │                              │             └─ widget.update()
```

The server shares the Textual asyncio loop. Commands execute as coroutines
interleaved with UI event processing — cooperative, single-threaded.

## Files

| File | Purpose |
|------|---------|
| `src/toad/socket_controller.py` | Server implementation |
| `src/toad/app.py` | Startup/shutdown hooks (on_mount/on_unmount) |
| `tools/toad-ctl.sh` | Shell client |
