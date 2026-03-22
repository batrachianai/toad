#!/usr/bin/env bash
set -euo pipefail

# toad-ctl — send commands to a running Toad TUI via Unix socket.
#
# Usage:
#   toad-ctl ping
#   toad-ctl snapshot
#   toad-ctl action toggle_dark
#   toad-ctl query "Button"
#   toad-ctl update "#status" "new text"
#   toad-ctl press enter
#   toad-ctl focus "#input"
#
# Finds the socket automatically (first /tmp/toad-*.sock found).

find_socket() {
  local sock
  sock=$(ls /tmp/toad-*.sock 2>/dev/null | head -1)
  if [[ -z "$sock" ]]; then
    echo "error: no toad socket found in /tmp/" >&2
    exit 1
  fi
  echo "$sock"
}

SOCK="${TOAD_SOCKET:-$(find_socket)}"
CMD="${1:?usage: toad-ctl <command> [args...]}"
shift

case "$CMD" in
  ping)
    PAYLOAD='{"cmd":"ping"}'
    ;;
  snapshot)
    PAYLOAD='{"cmd":"snapshot"}'
    ;;
  action)
    PAYLOAD="{\"cmd\":\"action\",\"name\":\"$1\"}"
    ;;
  query)
    PAYLOAD="{\"cmd\":\"query\",\"selector\":\"$1\"}"
    ;;
  update)
    PAYLOAD="{\"cmd\":\"update\",\"selector\":\"$1\",\"text\":\"$2\"}"
    ;;
  press)
    PAYLOAD="{\"cmd\":\"press\",\"key\":\"$1\"}"
    ;;
  focus)
    PAYLOAD="{\"cmd\":\"focus\",\"selector\":\"$1\"}"
    ;;
  raw)
    PAYLOAD="$1"
    ;;
  *)
    echo "error: unknown command '$CMD'" >&2
    echo "commands: ping, snapshot, action, query, update, press, focus, raw" >&2
    exit 1
    ;;
esac

echo "$PAYLOAD" | socat - "UNIX-CONNECT:$SOCK"
