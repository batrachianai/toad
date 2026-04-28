"""PlanDepGraph — selectable dependency graph for a single plan.

Rendered as a Textual ``Tree`` laid out by dependency depth: items with
no deps appear first, then items whose deps resolve at depth 0, and so on.
Each node shows a status glyph and the item id + truncated description,
colored by item status.

The widget is "dumb": the owning ``PlanExecutionTab`` passes in the
parsed item list and replaces it via :meth:`set_items` when the
``PlanExecutionModel`` emits updates. No file I/O happens here.

Selecting a node posts :class:`PlanDepGraph.ItemSelected` with the
picked item id so the owning tab can route the worker-log pane.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode


__all__ = [
    "STATUS_COLORS",
    "STATUS_GLYPHS",
    "DepGraphItem",
    "PlanDepGraph",
]


STATUS_COLORS: dict[str, str] = {
    "queued": "grey50",
    "ready": "cyan",
    "running": "yellow",
    "done": "green",
    "failed": "red",
    "review": "magenta",
}

STATUS_GLYPHS: dict[str, str] = {
    "queued": "○",
    "ready": "◐",
    "running": "◉",
    "done": "✓",
    "failed": "✗",
    "review": "?",
}

_FALLBACK_COLOR = "white"
_FALLBACK_GLYPH = "•"
_LABEL_MAX = 80


@dataclass(frozen=True)
class DepGraphItem:
    """A single plan item rendered as a node in the graph."""

    id: int
    description: str
    status: str
    deps: tuple[int, ...] = field(default_factory=tuple)


class PlanDepGraph(Tree[int]):
    """Depth-grouped dependency graph of plan items.

    The tree root is hidden; each plan item becomes a single leaf whose
    data payload is the item id.
    """

    DEFAULT_CSS = """
    PlanDepGraph {
        height: 1fr;
        background: $surface;
    }
    """

    class ItemSelected(Message):
        """Posted when the user selects an item node in the graph."""

        def __init__(self, item_id: int) -> None:
            super().__init__()
            self.item_id = item_id

    def __init__(
        self,
        items: list[DepGraphItem] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("Plan", name=name, id=id, classes=classes)
        self.show_root = False
        self.guide_depth = 2
        self._items: list[DepGraphItem] = []
        self._nodes_by_id: dict[int, TreeNode[int]] = {}
        if items:
            self.set_items(items)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_items(self, items: list[DepGraphItem]) -> None:
        """Replace the current nodes with ``items`` in dep-depth order."""
        self._items = list(items)
        self.root.remove_children()
        self._nodes_by_id.clear()

        depth_by_id = _compute_depths(self._items)
        ordered = sorted(
            self._items,
            key=lambda i: (depth_by_id.get(i.id, 0), i.id),
        )
        for item in ordered:
            node = self.root.add_leaf(
                _format_label(item),
                data=item.id,
            )
            self._nodes_by_id[item.id] = node
        self.root.expand()

    def node_for(self, item_id: int) -> TreeNode[int]:
        """Return the tree node for ``item_id`` (raises ``KeyError``)."""
        return self._nodes_by_id[item_id]

    def node_ids(self) -> list[int]:
        """Return the list of item ids currently rendered."""
        return list(self._nodes_by_id.keys())

    def node_label_plain(self, item_id: int) -> str:
        """Plain-text label for ``item_id`` — useful for assertions."""
        label = self._nodes_by_id[item_id].label
        return label.plain if isinstance(label, Text) else str(label)

    def node_has_color(self, item_id: int, color: str) -> bool:
        """Whether the node label for ``item_id`` paints ``color`` anywhere."""
        label = self._nodes_by_id[item_id].label
        if not isinstance(label, Text):
            return False
        for span in label.spans:
            if color in str(span.style):
                return True
        return False

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_tree_node_selected(self, event: Tree.NodeSelected[int]) -> None:
        """Forward ``Tree.NodeSelected`` as our typed ``ItemSelected``."""
        item_id = event.node.data
        if item_id is None:
            return
        self.post_message(self.ItemSelected(int(item_id)))


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _compute_depths(items: list[DepGraphItem]) -> dict[int, int]:
    """Return a dep-depth (longest path to a root) per item id."""
    by_id = {item.id: item for item in items}
    depth: dict[int, int] = {}

    def resolve(item_id: int, stack: frozenset[int]) -> int:
        if item_id in depth:
            return depth[item_id]
        if item_id in stack:
            # Cycle guard — treat cycle nodes as depth 0 so rendering
            # stays deterministic even with a malformed plan.
            depth[item_id] = 0
            return 0
        item = by_id.get(item_id)
        if item is None or not item.deps:
            depth[item_id] = 0
            return 0
        next_stack = stack | {item_id}
        resolved = [resolve(dep, next_stack) for dep in item.deps if dep in by_id]
        d = 1 + max(resolved) if resolved else 0
        depth[item_id] = d
        return d

    for item in items:
        resolve(item.id, frozenset())
    return depth


def _format_label(item: DepGraphItem) -> Text:
    """Render a Rich ``Text`` label for ``item`` with status color + glyph."""
    glyph = STATUS_GLYPHS.get(item.status, _FALLBACK_GLYPH)
    color = STATUS_COLORS.get(item.status, _FALLBACK_COLOR)
    description = item.description
    if len(description) > _LABEL_MAX:
        description = description[: _LABEL_MAX - 1] + "…"

    label = Text()
    label.append(f"{glyph} ", style=color)
    label.append(f"{item.id}. ", style=f"bold {color}")
    label.append(description, style=color)
    return label
