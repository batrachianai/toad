from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import ListView, ListItem, Label
from textual._partition import partition
from textual import events
from textual.widget import Widget

from toad.menus import MenuItem


class NonSelectableLabel(Label):
    ALLOW_SELECT = False


class MenuOption(ListItem):
    ALLOW_SELECT = False

    def __init__(self, action: str | None, description: str, key: str | None) -> None:
        self._action = action
        self._description = description
        self._key = key
        super().__init__(classes="-has-key" if key else "-no_key")

    def compose(self) -> ComposeResult:
        yield NonSelectableLabel(self._key or " ", id="key")
        yield NonSelectableLabel(self._description, id="description")


class Menu(ListView, can_focus=True):
    BINDINGS = [Binding("escape", "dismiss", "Dismiss")]

    DEFAULT_CSS = """
    Menu {
        margin: 1 1;
        width: auto;
        height: auto;        
        max-width: 100%;
        overlay: screen;  
        position: absolute;
        color: $foreground;
        background: $panel;
        border: block $panel;
        constrain: inside inside;
   
        & > MenuOption {         
            
            layout: horizontal;            
            width: 1fr;            
            padding: 0 1;
            height: auto !important;
            overflow: auto;
            expand: optimal;            
            #description {                        
                color: $text 80%;
                width: 1fr;                    
            }
            #key {                
                padding-right: 1;                
                text-style: bold;
            }                            
           
        }

        &:blur {
            background-tint: transparent;
            & > ListItem.-highlight {
                color: $block-cursor-blurred-foreground;
                background: $block-cursor-blurred-background 30%;
                text-style: $block-cursor-blurred-text-style;
            }
        }
        
        &:focus {
            background-tint: transparent;
            & > ListItem.-highlight {
                color: $block-cursor-blurred-foreground;
                background: $block-cursor-blurred-background;
                text-style: $block-cursor-blurred-text-style;
            }
        }
    }
    """

    @dataclass
    class OptionSelected(Message):
        """The user selected on of the options."""

        menu: Menu
        owner: Widget
        action: str | None

    @dataclass
    class Dismissed(Message):
        """Menu was dismissed."""

        menu: Menu

    def __init__(self, owner: Widget, options: list[MenuItem], *args, **kwargs) -> None:
        self._owner = owner
        self._options = options
        super().__init__(*args, **kwargs)

    def _insert_options(self) -> None:
        with_keys, without_keys = partition(
            lambda option: option.key is None, self._options
        )
        self.extend(
            MenuOption(menu_item.action, menu_item.description, menu_item.key)
            for menu_item in with_keys
        )
        self.extend(
            MenuOption(menu_item.action, menu_item.description, menu_item.key)
            for menu_item in without_keys
        )

    def on_mount(self) -> None:
        self._insert_options()

    async def activate_index(self, index: int) -> None:
        action = self._options[index].action
        self.post_message(self.OptionSelected(self, self._owner, action))

    async def action_dismiss(self) -> None:
        self.post_message(self.Dismissed(self))

    async def on_blur(self) -> None:
        self.post_message(self.Dismissed(self))

    @on(events.Key)
    async def on_key(self, event: events.Key) -> None:
        for index, option in enumerate(self._options):
            if event.key == option.key:
                self.index = index
                event.stop()
                await self.activate_index(index)
                break

    @on(ListView.Selected)
    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        await self.activate_index(event.index)
