from __future__ import annotations


import asyncio
from functools import lru_cache
from operator import itemgetter
import os
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
from textual.actions import SkipAction

from textual.reactive import var, Initialize
from textual.content import Content, Span
from textual.strip import Strip
from textual.widget import Widget
from textual import widgets
from textual.widgets import OptionList, Input, DirectoryTree
from textual.widgets.option_list import Option


from toad import directory
from toad.fuzzy import FuzzySearch
from toad.messages import Dismiss, InsertPath, PromptSuggestion
from toad.path_filter import PathFilter
from toad.widgets.project_directory_tree import ProjectDirectoryTree


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


class FuzzyInput(Input):
    """Adds a Content placeholder to fuzzy input.

    TODO: Add this ability to Textual.
    """

    HELP = """\
## Fuzzy search

Type a few characters from the file you are searching for.

The search is *fuzzy*, and will match characters that aren't neccesarily next to each other—only the order matters.
"""

    def render_line(self, y: int) -> Strip:
        if y == 0 and not self.value:
            placeholder = Content.from_markup(self.placeholder).expand_tabs()
            placeholder = placeholder.stylize(self.visual_style)
            placeholder = placeholder.stylize(
                self.get_visual_style("input--placeholder")
            )
            if self.has_focus:
                cursor_style = self.get_visual_style("input--cursor")
                if self._cursor_visible:
                    # If the placeholder is empty, there's no characters to stylise
                    # to make the cursor flash, so use a single space character
                    if len(placeholder) == 0:
                        placeholder = Content(" ")
                    placeholder = placeholder.stylize(cursor_style, 0, 1)

            strip = Strip(placeholder.render_segments())
            return strip

        return super().render_line(y)


class PathSearch(containers.VerticalGroup):

    BINDING_GROUP_TITLE = "Path search"

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
        Binding("enter", "submit", "Insert path", priority=True, show=False),
        Binding("escape", "dismiss", "Dismiss", priority=True, show=False),
        Binding("tab", "switch_picker", "Switch picker", priority=True, show=False),
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
    show_tree_picker: var[bool] = var(False)

    option_list = getters.query_one(OptionList)
    tree_view = getters.query_one(ProjectDirectoryTree)
    input = getters.query_one(Input)

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    def compose(self) -> ComposeResult:
        with widgets.ContentSwitcher(initial="path-search-fuzzy"):
            with containers.VerticalGroup(id="path-search-fuzzy"):
                yield FuzzyInput(
                    compact=True, placeholder="fuzzy search \t[r]▌tab▐[/r] tree view"
                )
                yield OptionList()
            with containers.VerticalGroup(id="path-search-tree"):
                yield widgets.Static(
                    Content.from_markup(
                        "tree view \t[r]▌tab▐[/] fuzzy search"
                    ).expand_tabs(),
                    classes="message",
                )
                yield ProjectDirectoryTree(self.root).data_bind(path=PathSearch.root)

    def on_mount(self) -> None:
        tree = self.tree_view
        tree.guide_depth = 2
        tree.center_scroll = True

    def watch_show_tree_picker(self, show_tree_picker: bool) -> None:
        content_switcher = self.query_one(widgets.ContentSwitcher)
        content_switcher.current = (
            "path-search-tree" if show_tree_picker else "path-search-fuzzy"
        )
        if show_tree_picker:
            self.tree_view.focus()

        else:
            self.input.focus()

    def action_switch_picker(self) -> None:
        self.show_tree_picker = not self.show_tree_picker

    async def search(self, search: str) -> None:
        if not search:
            self.option_list.set_options(
                [
                    Option(highlighted_path, highlighted_path.plain)
                    for highlighted_path in self.highlighted_paths[:100]
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
        with self.option_list.prevent(OptionList.OptionHighlighted):
            self.option_list.highlighted = 0
        self.post_message(PromptSuggestion(""))

    def action_cursor_down(self) -> None:
        if self.show_tree_picker:
            self.tree_view.action_cursor_down()
        else:
            self.option_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.show_tree_picker:
            self.tree_view.action_cursor_up()
        else:
            self.option_list.action_cursor_up()

    def action_dismiss(self) -> None:
        self.post_message(Dismiss(self))

    def on_show(self) -> None:
        self.focus()

    def focus(self, scroll_visible: bool = False) -> Self:
        if self.show_tree_picker:
            return self.tree_view.focus(scroll_visible=scroll_visible)
        else:
            return self.input.focus(scroll_visible=scroll_visible)

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        if self.show_tree_picker:
            if event.widget == self.tree_view:
                self.post_message(Dismiss(self))
        else:
            if event.widget == self.input:
                self.post_message(Dismiss(self))

    @on(DirectoryTree.NodeHighlighted)
    def on_node_highlighted(self, event: DirectoryTree.NodeHighlighted) -> None:
        event.stop()

        dir_entry = event.node.data
        if dir_entry is not None:
            try:
                path = Path(dir_entry.path).resolve().relative_to(self.root.resolve())
            except ValueError:
                # Being defensive here, shouldn't occur
                return
            tree_path = str(path)
            self.post_message(PromptSuggestion(tree_path))

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()

        dir_entry = event.node.data
        if dir_entry is not None:
            try:
                path = Path(dir_entry.path).resolve().relative_to(self.root.resolve())
            except ValueError:
                return
            tree_path = str(path)
            self.post_message(InsertPath(tree_path))
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
        if self.show_tree_picker:
            raise SkipAction()

        elif (highlighted := self.option_list.highlighted) is not None:
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
            self.tree_view.path_filter = path_filter
            self.tree_view.clear()
            await self.tree_view.reload()
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
        content = Content.styled(path, "dim $text")
        if os.path.split(path)[-1].startswith("."):
            return content
        content = content.highlight_regex("[^/]*?$", style="not dim $text-primary")
        content = content.highlight_regex(r"\.[^/]*$", style="italic")
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
            ][:100]
        )
        with self.option_list.prevent(OptionList.OptionHighlighted):
            self.option_list.highlighted = 0
        self.post_message(PromptSuggestion(""))
