"""
ACP v2 (draft) translation helpers.

ACP v2 reports session state as upserts, patches, and chunks keyed by stable ids
(messages, tool calls, terminals, plans). Toad's UI was built around v1, so the helpers
here keep the v2 state and translate it into the v1-shaped structures the widgets
already render.

These follow the draft release named in `SCHEMA_RELEASE`; see `toad.acp.session_v2`
for how to update to a newer draft.

https://agentclientprotocol.com/protocol/v2/migration
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from typing import Any, NamedTuple

PROTOCOL_VERSION = 2
"""The ACP v2 protocol version number."""

SCHEMA_RELEASE = "schema-v2.0.0-beta.3"
"""The ACP v2 draft release (a tag in the agent-client-protocol repository) that Toad's
v2 support is built against. See `toad.acp.session_v2` for details."""

MAX_TERMINAL_DISPLAY = 64 * 1024
"""Maximum number of bytes of terminal output to show in a tool call."""

# v1 widgets only know these tool call statuses. Unknown statuses mean in progress.
_TOOL_STATUS = {
    "pending": "pending",
    "in_progress": "in_progress",
    "paused": "in_progress",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "failed",
}

_TOOL_KINDS = {
    "read",
    "edit",
    "delete",
    "move",
    "search",
    "execute",
    "think",
    "fetch",
    "switch_mode",
    "other",
}

_PLAN_STATUS = {"pending", "in_progress", "completed"}
_PLAN_PRIORITY = {"high", "medium", "low"}

# Patch defaults when a field is set to `null`
_TOOL_DEFAULTS: dict[str, Any] = {"status": "pending", "kind": "other"}
_TOOL_COLLECTIONS = {"content", "locations"}


def patch_meta(current: dict | None, patch: dict | None) -> dict | None:
    """Apply a v2 `_meta` patch (null clears, keys set to null are removed)."""
    if patch is None:
        return None
    meta = dict(current or {})
    for key, value in patch.items():
        if value is None:
            meta.pop(key, None)
        else:
            meta[key] = value
    return meta


def patch_tool_call(current: dict | None, update: dict) -> dict:
    """Apply a `tool_call_update` to the stored tool call (or create it).

    Omitted fields are unchanged, `null` clears (or resets to the default), and
    values (including arrays) replace.

    Args:
        current: The current tool call state, or `None` if the id is new.
        update: The `tool_call_update` payload.

    Returns:
        New tool call state.
    """
    if current is None:
        tool_call: dict[str, Any] = {
            "toolCallId": update["toolCallId"],
            **_TOOL_DEFAULTS,
        }
    else:
        tool_call = dict(current)
    for key, value in update.items():
        if key in ("sessionUpdate", "toolCallId"):
            continue
        if key == "_meta":
            if (meta := patch_meta(tool_call.get("_meta"), value)) is None:
                tool_call.pop("_meta", None)
            else:
                tool_call["_meta"] = meta
        elif value is None:
            if key in _TOOL_DEFAULTS:
                tool_call[key] = _TOOL_DEFAULTS[key]
            elif key in _TOOL_COLLECTIONS:
                tool_call[key] = []
            else:
                tool_call.pop(key, None)
        else:
            tool_call[key] = value
    return tool_call


def append_tool_call_content(
    current: dict | None, tool_call_id: str, item: dict
) -> dict:
    """Apply a `tool_call_content_chunk` (appends one content item)."""
    tool_call = patch_tool_call(current, {"toolCallId": tool_call_id})
    tool_call["content"] = [*(tool_call.get("content") or []), item]
    return tool_call


@dataclass
class Terminal:
    """Display state of an agent-owned terminal."""

    terminal_id: str
    command: str | None = None
    cwd: str | None = None
    output: bytearray = field(default_factory=bytearray)
    exit_status: dict | None = None

    def apply_update(self, update: dict) -> None:
        """Apply a `terminal_update` patch."""
        if "command" in update:
            self.command = update["command"]
        if "cwd" in update:
            self.cwd = update["cwd"]
        if "exitStatus" in update:
            self.exit_status = update["exitStatus"]
        if "output" in update:
            output = update["output"]
            self.output = bytearray(
                decode_base64(output.get("data", "")) if output else b""
            )

    def append(self, data: str) -> None:
        """Apply a `terminal_output_chunk`."""
        self.output += decode_base64(data)

    @property
    def text(self) -> str:
        """The terminal rendered as text for display in a tool call."""
        lines: list[str] = []
        if self.command:
            lines.append(f"$ {self.command}")
        output = bytes(self.output[-MAX_TERMINAL_DISPLAY:])
        if output_text := output.decode("utf-8", "replace").rstrip():
            lines.append(output_text)
        if (exit_status := self.exit_status) is not None:
            if (signal := exit_status.get("signal")) is not None:
                lines.append(f"[killed by {signal}]")
            elif (exit_code := exit_status.get("exitCode")) not in (None, 0):
                lines.append(f"[exit code {exit_code}]")
        return "\n".join(lines)


def decode_base64(data: str) -> bytes:
    try:
        return base64.b64decode(data)
    except binascii.Error, ValueError:
        return b""


def diff_to_markdown(diff: dict) -> str:
    """Render a v2 structured diff (changes + optional git patch) as text."""
    patch = diff.get("patch")
    patch_text = ""
    # Unknown patch formats are treated as if the patch were omitted
    if isinstance(patch, dict) and patch.get("format") == "git_patch":
        patch_text = str(patch.get("text") or "").rstrip()

    def code(path: str) -> str:
        return f"`{path}`" if patch_text else path

    lines: list[str] = []
    for change in diff.get("changes") or []:
        operation = change.get("operation", "change")
        path = change.get("path", "")
        if operation in ("move", "copy"):
            line = f"{operation} {code(change.get('oldPath', ''))} → {code(path)}"
        else:
            line = f"{operation} {code(path)}"
        if (file_type := change.get("fileType")) not in (None, "text"):
            line += f" ({file_type})"
        lines.append(f"- {line}")

    if patch_text:
        longest_fence = max(
            (len(match) for match in re.findall(r"`{3,}", patch_text)), default=2
        )
        fence = "`" * (longest_fence + 1)
        lines.append(f"\n{fence}diff\n{patch_text}\n{fence}")
    return "\n".join(lines)


def _text_block(text: str) -> dict:
    return {"type": "content", "content": {"type": "text", "text": text}}


def to_v1_content(item: dict, terminals: dict[str, Terminal]) -> dict | None:
    """Convert v2 tool call content into something the v1 widgets render."""
    match item:
        case {"type": "content", "content": _}:
            return item
        case {"type": "diff"}:
            return _text_block(diff_to_markdown(item))
        case {"type": "terminal", "terminalId": terminal_id}:
            if (terminal := terminals.get(terminal_id)) is not None and (
                text := terminal.text
            ):
                return _text_block(text)
            return None
        case {"type": "session", "sessionId": session_id}:
            return _text_block(f"Subagent session {session_id}")
    # Unknown content types are ignored
    return None


def to_v1_tool_call(tool_call: dict, terminals: dict[str, Terminal]) -> dict:
    """Convert stored v2 tool call state into a v1 `ToolCall` for the UI."""
    v1_tool_call = {key: value for key, value in tool_call.items() if key != "content"}
    v1_tool_call["sessionUpdate"] = "tool_call"
    v1_tool_call["title"] = (
        tool_call.get("title") or tool_call.get("name") or "Tool call"
    )
    v1_tool_call["status"] = _TOOL_STATUS.get(
        tool_call.get("status") or "pending", "in_progress"
    )
    if tool_call.get("kind") not in _TOOL_KINDS:
        v1_tool_call["kind"] = "other"
    v1_tool_call["content"] = [
        converted
        for item in tool_call.get("content") or []
        if isinstance(item, dict)
        and (converted := to_v1_content(item, terminals)) is not None
    ]
    return v1_tool_call


def tool_call_terminals(tool_call: dict) -> set[str]:
    """Get the ids of terminals referenced by a tool call."""
    return {
        item["terminalId"]
        for item in tool_call.get("content") or []
        if isinstance(item, dict)
        and item.get("type") == "terminal"
        and isinstance(item.get("terminalId"), str)
    }


def blocks_text(blocks: list | None) -> str:
    """Concatenate the text of content blocks."""
    return "".join(
        block.get("text", "")
        for block in blocks or []
        if isinstance(block, dict) and block.get("type") == "text"
    )


class MessageText:
    """Tracks the text of streamed messages, so upserts can be turned in to appends.

    Messages are keyed by kind and id: an agent message and an agent thought may share
    a `messageId` but are separate entities.
    """

    def __init__(self) -> None:
        self._text: dict[tuple[str, str], str] = {}

    @staticmethod
    def _key(kind: str, message_id: str) -> tuple[str, str]:
        # "agent_message_chunk" and "agent_message" update the same entity
        return (kind.removesuffix("_chunk"), message_id)

    def chunk(self, kind: str, message_id: str, block: dict) -> str:
        """Append a chunk, and return the new text."""
        key = self._key(kind, message_id)
        text = blocks_text([block])
        self._text[key] = self._text.get(key, "") + text
        return text

    def upsert(self, kind: str, message_id: str, content: list | None) -> str | None:
        """Replace a message's content.

        Returns:
            The text to append, or `None` if earlier text was rewritten (which can't be
            shown by appending).
        """
        key = self._key(kind, message_id)
        new_text = blocks_text(content)
        old_text = self._text.get(key, "")
        self._text[key] = new_text
        if new_text.startswith(old_text):
            return new_text[len(old_text) :]
        return None


_CHECKBOX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX~-])\]\s+(.*)$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def plan_entries(plan: dict) -> list[dict]:
    """Convert a v2 plan (items or markdown) into v1 plan entries."""
    match plan:
        case {"type": "items", "entries": entries}:
            return [
                {
                    "content": entry.get("content", ""),
                    "priority": (
                        priority
                        if (priority := entry.get("priority")) in _PLAN_PRIORITY
                        else "medium"
                    ),
                    "status": (
                        status
                        if (status := entry.get("status")) in _PLAN_STATUS
                        else "pending"
                    ),
                }
                for entry in entries or []
            ]
        case {"type": "markdown", "content": content}:
            markdown_entries: list[dict] = []
            for line in str(content).splitlines():
                if match := _CHECKBOX.match(line):
                    mark, text = match.groups()
                    status = "completed" if mark in "xX" else "pending"
                    markdown_entries.append(
                        {"content": text, "priority": "medium", "status": status}
                    )
                elif match := _LIST_ITEM.match(line):
                    markdown_entries.append(
                        {
                            "content": match.group(1),
                            "priority": "medium",
                            "status": "pending",
                        }
                    )
            if not markdown_entries and (text := str(content).strip()):
                markdown_entries.append(
                    {"content": text, "priority": "medium", "status": "pending"}
                )
            return markdown_entries
    return []


class ModeOption(NamedTuple):
    """A session config option of category 'mode', presented as Toad modes."""

    config_id: str
    current: str
    modes: list[tuple[str, str, str | None]]
    """(id, name, description) for each mode."""


def find_mode_option(config_options: list | None) -> ModeOption | None:
    """Find the 'mode' select in a list of v2 session config options."""
    for option in config_options or []:
        if not isinstance(option, dict):
            continue
        if option.get("category") != "mode" or option.get("type") != "select":
            continue
        modes: list[tuple[str, str, str | None]] = []
        for choice in option.get("options") or []:
            # Options may be grouped
            choices = (
                choice.get("options", [choice]) if isinstance(choice, dict) else []
            )
            for value in choices:
                if isinstance(value, dict) and "value" in value:
                    modes.append(
                        (
                            str(value["value"]),
                            str(value.get("name", value["value"])),
                            value.get("description"),
                        )
                    )
        if modes:
            return ModeOption(option["configId"], option.get("currentValue", ""), modes)
    return None


def available_commands(commands: list | None) -> list[dict]:
    """Filter v2 available commands to those Toad can show as slash commands."""
    result: list[dict] = []
    for command in commands or []:
        if not isinstance(command, dict) or command.get("type", "command") != "command":
            continue
        command = dict(command)
        match command.get("input"):
            case {"type": "text", **_rest}:
                pass
            case None:
                pass
            case _:
                # Unknown input types are plain text
                command["input"] = None
        result.append(command)
    return result
