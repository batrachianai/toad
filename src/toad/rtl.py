"""RTL (Right-to-Left) text support for Hebrew, Arabic, and other BiDi languages.

This module provides utilities for properly displaying RTL text in terminals.
Terminals render characters left-to-right, so we use the Unicode BiDi algorithm
to reorder characters for correct visual display.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from bidi.algorithm import get_display
from rich.text import Text


# Unicode BiDi character classes that indicate RTL text
RTL_BIDI_TYPES = {"R", "AL", "RLE", "RLO", "RLI"}


@lru_cache(maxsize=256)
def contains_rtl(text: str) -> bool:
    """Check if text contains any RTL (Right-to-Left) characters.

    Args:
        text: The text to check.

    Returns:
        True if the text contains Hebrew, Arabic, or other RTL characters.
    """
    for char in text:
        try:
            bidi_class = unicodedata.bidirectional(char)
            if bidi_class in RTL_BIDI_TYPES:
                return True
        except ValueError:
            continue
    return False


def apply_bidi(text: str) -> str:
    """Apply the Unicode BiDi algorithm to reorder text for display.

    This transforms RTL text so it displays correctly in LTR terminals.
    LTR-only text is returned unchanged for performance.

    Args:
        text: The text to transform.

    Returns:
        Text reordered for correct visual display in a terminal.
    """
    if not text or not contains_rtl(text):
        return text
    return get_display(text)


def apply_bidi_to_rich_text(rich_text: Text) -> Text:
    """Apply BiDi algorithm to a Rich Text object while preserving styles.

    This handles styled text by processing each span individually and
    maintaining the style information through the transformation.

    Args:
        rich_text: A Rich Text object potentially containing RTL text.

    Returns:
        A new Text object with RTL characters reordered for display.
    """
    plain = rich_text.plain
    if not contains_rtl(plain):
        return rich_text

    # For styled text, we need to handle each line separately
    # to maintain proper BiDi context per line
    lines = plain.split("\n")
    result_parts: list[tuple[str, str]] = []

    current_pos = 0
    for i, line in enumerate(lines):
        if i > 0:
            result_parts.append(("\n", ""))
            current_pos += 1

        if not line:
            continue

        # Get the style at the start of this line
        line_start = current_pos
        line_end = current_pos + len(line)

        # Apply BiDi to the line
        display_line = apply_bidi(line)

        # For simplicity with styled text, we take the dominant style
        # This preserves most styling while ensuring correct RTL display
        if rich_text._spans:
            # Find spans that overlap with this line
            for span in rich_text._spans:
                if span.start < line_end and span.end > line_start:
                    result_parts.append((display_line, span.style or ""))
                    break
            else:
                result_parts.append((display_line, rich_text.style or ""))
        else:
            result_parts.append((display_line, rich_text.style or ""))

        current_pos = line_end

    return Text.assemble(*result_parts, end=rich_text.end, no_wrap=rich_text.no_wrap)


def apply_bidi_to_lines(lines: list[str]) -> list[str]:
    """Apply BiDi algorithm to a list of lines.

    Args:
        lines: List of text lines.

    Returns:
        List of lines with RTL characters reordered for display.
    """
    return [apply_bidi(line) for line in lines]


def apply_bidi_to_markdown(markdown: str) -> str:
    """Apply BiDi algorithm to markdown text, preserving code blocks.

    This processes markdown line by line, skipping code blocks (fenced and indented)
    to prevent breaking code syntax while properly displaying RTL text content.

    Args:
        markdown: Markdown text potentially containing RTL content.

    Returns:
        Markdown with RTL text reordered for correct visual display.
    """
    if not markdown or not contains_rtl(markdown):
        return markdown

    lines = markdown.split("\n")
    result_lines: list[str] = []
    in_code_block = False

    for line in lines:
        # Check for fenced code block markers (``` or ~~~)
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            result_lines.append(line)
            continue

        # Skip processing for code blocks and indented code (4+ spaces)
        if in_code_block or line.startswith("    ") or line.startswith("\t"):
            result_lines.append(line)
            continue

        # Apply BiDi to regular text lines
        result_lines.append(apply_bidi(line))

    return "\n".join(result_lines)
