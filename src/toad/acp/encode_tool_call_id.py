def encode_tool_call_id(tool_call_id: str) -> str:
    """Encode the tool call id so that it fits within a TCSS id.

    Args:
        tool_call_id: Raw tool call id.

    Returns:
        Tool call usable as widget id.
    """
    hex_tool_call_id = "".join(f"{ord(character):2X}" for character in tool_call_id)
    encoded_tool_call_id = f"tool-call-{hex_tool_call_id}"
    print(f"{tool_call_id} -> {encoded_tool_call_id}")
    return encoded_tool_call_id
