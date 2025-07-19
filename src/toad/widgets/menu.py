from dataclasses import dataclass

from typing import NamedTuple

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup
from textual.widgets import ListView, ListItem, Label
from textual.reactive import var

from textual._partition import partition


class MenuOption(ListItem):
    ALLOW_SELECT = False

    def __init__(self, action: str, description: str, key: str | None) -> None:
        self._action = action
        self._description = description
        self._key = key
        super().__init__(classes="-has-key" if key else "-no_key")

    def compose(self) -> ComposeResult:
        yield Label(self._key or " ", id="key")
        yield Label(self._description, id="description")
        # if self._key is not None:


class Menu(ListView):
    DEFAULT_CSS = """
    Menu {
        margin: 1 2;
        width: auto;
        height: auto;
        expand: optimal;
        max-width: 100%;
        overlay: screen;  
        color: $foreground;
        background: $panel-darken-1;
        border: heavy black;
   
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
                expand: optimal;            
            }
            #key {                
                padding-right: 1;
                
                text-style: bold;
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

    class Item(NamedTuple):
        action: str
        description: str
        key: str | None = None

    def __init__(self, options: list[Item]) -> None:
        self._options = options
        super().__init__()

    def _insert_options(self) -> None:
        with_keys, without_keys = partition(
            lambda option: option.key is None, self._options
        )
        self.extend(
            [
                MenuOption(action, description, key)
                for action, description, key in with_keys
            ]
        )
        self.extend(
            [
                MenuOption(action, description, key)
                for action, description, key in without_keys
            ]
        )

    def on_mount(self) -> None:
        self._insert_options()
