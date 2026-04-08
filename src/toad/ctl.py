"""canon-ctl — send commands to a running Canon TUI via Unix socket."""

from __future__ import annotations

import glob
import json
import os
import socket
import sys


def find_socket() -> str:
    """Find a live Canon/Toad socket in /tmp/.

    Tries each matching socket, removes stale ones (no listener),
    and returns the first that accepts a connection.
    """
    socks = sorted(glob.glob("/tmp/toad-*.sock"))
    if not socks:
        print("error: no canon socket found in /tmp/", file=sys.stderr)
        sys.exit(1)

    for path in socks:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                probe.settimeout(2)
                probe.connect(path)
            return path
        except (ConnectionRefusedError, OSError):
            # Stale socket — remove it
            try:
                os.unlink(path)
            except OSError:
                pass

    print("error: no live canon socket found in /tmp/", file=sys.stderr)
    sys.exit(1)


def build_payload(args: list[str]) -> str:
    """Build JSON payload from CLI arguments."""
    if not args:
        print(
            "usage: canon-ctl <command> [args...]\n"
            "commands: ping, snapshot, action, query, "
            "update, press, focus, raw",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = args[0]
    rest = args[1:]

    match cmd:
        case "ping":
            return json.dumps({"cmd": "ping"})
        case "snapshot":
            return json.dumps({"cmd": "snapshot"})
        case "action":
            return json.dumps({"cmd": "action", "name": rest[0]})
        case "query":
            return json.dumps({"cmd": "query", "selector": rest[0]})
        case "update":
            return json.dumps(
                {"cmd": "update", "selector": rest[0], "text": rest[1]}
            )
        case "press":
            return json.dumps({"cmd": "press", "key": rest[0]})
        case "focus":
            return json.dumps({"cmd": "focus", "selector": rest[0]})
        case "raw":
            return rest[0]
        case _:
            print(f"error: unknown command '{cmd}'", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    sock_path = os.environ.get("TOAD_SOCKET") or find_socket()
    payload = build_payload(sys.argv[1:])

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(sock_path)
        s.sendall(payload.encode() + b"\n")
        response = s.recv(65536)
        if response:
            print(response.decode())


if __name__ == "__main__":
    main()
