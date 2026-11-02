"""Shown when the hero falls."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from rpg.ui.palette import MUTED_STYLE


class GameOverScreen(Screen[None]):
    def __init__(self, name: str, level: int, kills: int, killer: str) -> None:
        super().__init__()
        self.summary = (name, level, kills, killer)

    def compose(self) -> ComposeResult:
        name, level, kills, killer = self.summary
        with Vertical(id="gameover-root"):
            yield Static(Text("☠  YOU HAVE FALLEN  ☠", style="bold #E8604F"), id="gameover-title")
            yield Static(Text.assemble((f"{name}", "bold"), (f", level {level}, was slain by {killer}.\n", ""),
                                       (f"{kills} foes fell before the end.\n\n", MUTED_STYLE),
                                       ("Better luck next time, adventurer...", "italic #C9BFAE"),
                                       justify="center"), id="gameover-body")
            with Center():
                with Vertical(id="gameover-menu"):
                    yield Button("Load a save", variant="primary", id="load")
                    yield Button("New character", id="new")
                    yield Button("Title screen", id="title")
        yield Footer()

    def on_mount(self) -> None:
        load = self.query_one("#load", Button)
        load.disabled = not self.app.saves.any_saves()
        (self.query_one("#new", Button) if load.disabled else load).focus()

    @on(Button.Pressed, "#load")
    def load(self) -> None:
        from rpg.ui.screens.save_load import SaveLoadScreen

        self.app.push_screen(SaveLoadScreen("load"))

    @on(Button.Pressed, "#new")
    def new(self) -> None:
        from rpg.ui.screens.create_character import CreateCharacterScreen

        self.app.push_screen(CreateCharacterScreen())

    @on(Button.Pressed, "#title")
    def title(self) -> None:
        from rpg.ui.screens.title import TitleScreen

        self.app.run_flow(self.app.reset_to(TitleScreen()))
