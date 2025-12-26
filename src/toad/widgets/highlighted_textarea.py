from __future__ import annotations
from dataclasses import dataclass
import re2 as re
from typing import Sequence

from rich.text import Text

from textual import on
from textual.reactive import reactive
from textual.content import Content
from textual.highlight import highlight, HighlightTheme, TokenType
from textual.message import Message
from textual.widgets import TextArea
from textual.widgets.text_area import Selection

from pygments.token import Token


RE_MATCH_FILE_PROMPT = re.compile(r"(@\S+)|@\"(.*)\"")
RE_SLASH_COMMAND = re.compile(r"(\/\S*)(\W.*)?$")


class TextualHighlightTheme(HighlightTheme):
    """Contains the style definition for user with the highlight method."""

    STYLES: dict[TokenType, str] = {
        Token.Comment: "$text 60%",
        Token.Error: "$text-error on $error-muted",
        Token.Generic.Strong: "bold",
        Token.Generic.Emph: "italic",
        Token.Generic.Error: "$text-error on $error-muted",
        Token.Generic.Heading: "$text-primary underline",
        Token.Generic.Subheading: "$text-primary",
        Token.Keyword: "$text-accent",
        Token.Keyword.Constant: "bold $text-success 80%",
        Token.Keyword.Namespace: "$text-error",
        Token.Keyword.Type: "bold",
        Token.Literal.Number: "$text-warning",
        Token.Literal.String.Backtick: "$text 60%",
        Token.Literal.String: "$text-success 90%",
        Token.Literal.String.Doc: "$text-success 80% italic",
        Token.Literal.String.Double: "$text-success 90%",
        Token.Name: "$text-primary",
        Token.Name.Attribute: "$text-warning",
        Token.Name.Builtin: "$text-accent",
        Token.Name.Builtin.Pseudo: "italic",
        Token.Name.Class: "$text-warning bold",
        Token.Name.Constant: "$text-error",
        Token.Name.Decorator: "$text-primary bold",
        Token.Name.Entity: "$text",
        Token.Name.Function: "$text-warning underline",
        Token.Name.Function.Magic: "$text-warning underline",
        Token.Name.Tag: "$text-primary bold",
        Token.Name.Variable: "$text-secondary",
        Token.Number: "$text-warning",
        Token.Operator: "bold",
        Token.Operator.Word: "bold $text-error",
        Token.String: "$text-success",
        Token.Whitespace: "",
    }


class HighlightedTextArea(TextArea):
    highlight_language = reactive("markdown")

    @dataclass
    class CursorMove(Message):
        selection: Selection

    def __init__(
        self,
        text: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        placeholder: str | Content = "",
    ):
        self._text_cache: dict[int, Text] = {}
        self._highlight_lines: list[Content] | None = None
        super().__init__(
            text,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            highlight_cursor_line=False,
            placeholder=placeholder,
        )
        self.compact = True

    def _clear_caches(self) -> None:
        self._highlight_lines = None
        self._text_cache.clear()

    def notify_style_update(self) -> None:
        self._clear_caches()
        return super().notify_style_update()

    def _watch_selection(
        self, previous_selection: Selection, selection: Selection
    ) -> None:
        self.post_message(self.CursorMove(selection))
        super()._watch_selection(previous_selection, selection)

    @property
    def highlight_lines(self) -> Sequence[Content]:
        if self._highlight_lines is None:
            text = self.text
            if text.startswith("/") and "\n" not in text:
                content = self.highlight_slash_command(text)
                self._highlight_lines = [content]
                return self._highlight_lines

            language = self.highlight_language
            if language == "markdown":
                content = self.highlight_markdown(text)
                content_lines = content.split("\n", allow_blank=True)[:-1]
                self._highlight_lines = content_lines
            elif language == "shell":
                content = self.highlight_shell(text)
                content_lines = content.split("\n", allow_blank=True)
                self._highlight_lines = content_lines
            else:
                raise ValueError("highlight_language must be `markdown` or `shell`")
        return self._highlight_lines

    def highlight_slash_command(self, text: str) -> Content:
        return Content.styled(text, "$text-success")

    def highlight_markdown(self, text: str) -> Content:
        """Highlight markdown content.

        Args:
            text: Text containing Markdown.

        Returns:
            Highlighted content.
        """
        content = highlight(
            text + "\n```",
            language="markdown",
            theme=TextualHighlightTheme,
        )
        content = content.highlight_regex(RE_MATCH_FILE_PROMPT, style="$primary")
        return content

    def highlight_shell(self, text: str) -> Content:
        """Highlight text with a bash shell command.

        Args:
            text: Text containing shell command.

        Returns:
            Highlighted content.
        """
        content = highlight(text, language="sh")
        return content

    @on(TextArea.Changed)
    def _on_changed(self) -> None:
        self._highlight_lines = None
        self._text_cache.clear()

    def get_line(self, line_index: int) -> Text:
        if (cached_line := self._text_cache.get(line_index)) is not None:
            return cached_line.copy()
        try:
            line = self.highlight_lines[line_index]
        except IndexError:
            return Text("", end="", no_wrap=True)
        rendered_line = list(line.render_segments(self.visual_style))
        text = Text.assemble(
            *[(text, style) for text, style, _ in rendered_line],
            end="",
            no_wrap=True,
        )
        self._text_cache[line_index] = text.copy()
        return text
