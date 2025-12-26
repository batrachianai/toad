from __future__ import annotations


import asyncio
from functools import lru_cache
from operator import itemgetter
from pathlib import Path
import re2 as re
from typing import Sequence


from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual import work
from textual import getters
from textual import containers
from textual import events
from textual.reactive import var, Initialize
from textual.content import Content, Span
from textual.widget import Widget
from textual.widgets import OptionList, Input
from textual.widgets.option_list import Option


from toad import directory
from toad.fuzzy import FuzzySearch
from toad.messages import Dismiss, InsertPath, PromptSuggestion
from toad.path_filter import PathFilter


class PathFuzzySearch(FuzzySearch):
    @classmethod
    @lru_cache(maxsize=1024)
    def get_first_letters(cls, candidate: str) -> frozenset[int]:
        return frozenset(
            {
                0,
                *[match.start() + 1 for match in re.finditer(r"/", candidate)],
            }
        )

    def score(self, candidate: str, positions: Sequence[int]) -> float:
        """Score a search.

        Args:
            search: Search object.

        Returns:
            Score.
        """
        first_letters = self.get_first_letters(candidate)
        # This is a heuristic, and can be tweaked for better results
        # Boost first letter matches
        offset_count = len(positions)
        score: float = offset_count + len(first_letters.intersection(positions))

        # if 0 in first_letters:
        #     score += 1

        groups = 1
        last_offset, *offsets = positions
        for offset in offsets:
            if offset != last_offset + 1:
                groups += 1
            last_offset = offset

        # Boost to favor less groups
        normalized_groups = (offset_count - (groups - 1)) / offset_count
        score *= 1 + (normalized_groups * normalized_groups)
        return score


class PathSearch(containers.VerticalGroup):
    CURSOR_BINDING_GROUP = Binding.Group(description="Move selection")
    BINDINGS = [
        Binding(
            "up", "cursor_up", "Cursor up", group=CURSOR_BINDING_GROUP, priority=True
        ),
        Binding(
            "down",
            "cursor_down",
            "Cursor down",
            group=CURSOR_BINDING_GROUP,
            priority=True,
        ),
        Binding("enter", "submit", "Insert path", priority=True),
        Binding("escape", "dismiss", "Dismiss", priority=True),
    ]

    def get_fuzzy_search(self) -> FuzzySearch:
        return PathFuzzySearch(case_sensitive=False)

    root: var[Path] = var(Path("./"))
    paths: var[list[Path]] = var(list)
    highlighted_paths: var[list[Content]] = var(list)
    filtered_path_indices: var[list[int]] = var(list)
    loaded = var(False)
    filter = var("")
    fuzzy_search: var[FuzzySearch] = var(Initialize(get_fuzzy_search))

    option_list = getters.query_one(OptionList)
    input = getters.query_one(Input)

    def compose(self) -> ComposeResult:
        yield Input(compact=True, placeholder="fuzzy search")
        yield OptionList()

    async def search(self, search: str) -> None:
        if not search:
            self.option_list.set_options(
                [
                    Option(highlighted_path, highlighted_path.plain)
                    for highlighted_path in self.highlighted_paths
                ],
            )
            return

        fuzzy_search = self.fuzzy_search
        fuzzy_search.cache.grow(len(self.paths))
        scores: list[tuple[float, Sequence[int], Content]] = [
            (
                *fuzzy_search.match(search, highlighted_path.plain),
                highlighted_path,
            )
            for highlighted_path in self.highlighted_paths
        ]

        scores = sorted(
            [score for score in scores if score[0]], key=itemgetter(0), reverse=True
        )
        scores = scores[:20]

        def highlight_offsets(path: Content, offsets: Sequence[int]) -> Content:
            return path.add_spans(
                [Span(offset, offset + 1, "underline") for offset in offsets]
            )

        self.option_list.set_options(
            [
                Option(
                    highlight_offsets(path, offsets) if index < 20 else path,
                    id=path.plain,
                )
                for index, (score, offsets, path) in enumerate(scores)
            ]
        )
        self.option_list.highlighted = 0
        self.post_message(PromptSuggestion(""))

    def action_cursor_down(self) -> None:
        self.option_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        self.option_list.action_cursor_up()

    def action_dismiss(self) -> None:
        self.post_message(Dismiss(self))

    def focus(self, scroll_visible: bool = False) -> Self:
        return self.input.focus(scroll_visible=scroll_visible)

    def on_descendant_blur(self) -> None:
        self.post_message(Dismiss(self))

    @on(Input.Changed)
    async def on_input_changed(self, event: Input.Changed):
        await self.search(event.value)

    @on(OptionList.OptionHighlighted)
    async def on_option_list_changed(self, event: OptionList.OptionHighlighted):
        event.stop()
        if event.option:
            self.post_message(PromptSuggestion(event.option.id))

    @on(OptionList.OptionSelected)
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.action_submit()

    def action_submit(self):
        if (highlighted := self.option_list.highlighted) is not None:
            option = self.option_list.options[highlighted]
            if option.id:
                self.post_message(InsertPath(option.id))
                self.post_message(Dismiss(self))

    def get_path_filter(self, project_path: Path) -> PathFilter:
        """Get a PathFilter insance for the give project path.

        Args:
            project_path: Project path.

        Returns:
            `PathFilter` object.
        """
        path_filter = PathFilter.from_git_root(project_path)
        return path_filter

    def reset(self) -> None:
        """Reset and focus input."""
        self.input.clear()
        self.input.focus()

    @work(exclusive=True)
    async def refresh_paths(self):
        self.loading = True
        root = self.root
        try:
            path_filter = await asyncio.to_thread(self.get_path_filter, root)
            paths = await directory.scan(
                root, path_filter=path_filter, add_directories=True
            )

            paths = [path.absolute() for path in paths]
            self.root = root
            self.paths = paths
        finally:
            self.loading = False

    def get_loading_widget(self) -> Widget:
        from textual.widgets import LoadingIndicator

        return LoadingIndicator()

    def highlight_path(self, path: str) -> Content:
        content = Content.styled(path, "dim")
        if path.startswith("."):
            return content
        if not path.endswith("/"):
            if "/" in path:
                content = content.stylize("$text-success", path.rfind("/") + 1)
            else:
                content = content.stylize("$text-success dim")
        if (match := re.search(r"\.(.*$)", content.plain)) is not None:
            content = content.stylize("not dim", match.start(1), match.end(1))
        return content

    def watch_paths(self, paths: list[Path]) -> None:
        self.option_list.highlighted = None

        def path_display(path: Path) -> str:
            try:
                is_directory = path.is_dir()
            except OSError:
                is_directory = False
            if is_directory:
                return str(path.relative_to(self.root)) + "/"
            else:
                return str(path.relative_to(self.root))

        display_paths = sorted(map(path_display, paths), key=str.lower)
        self.highlighted_paths = [self.highlight_path(path) for path in display_paths]
        self.option_list.set_options(
            [
                Option(highlighted_path, id=highlighted_path.plain)
                for highlighted_path in self.highlighted_paths
            ][:20]
        )
        self.option_list.highlighted = 0
        self.post_message(PromptSuggestion(""))
