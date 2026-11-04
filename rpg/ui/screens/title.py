"""Title screen."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from rpg.ui.menus import ARROW_BINDINGS, cycle_focus

TITLE_ART = r"""
███████╗██████╗ ██╗ ██████╗    ██████╗ ██████╗  ██████╗
██╔════╝██╔══██╗██║██╔════╝    ██╔══██╗██╔══██╗██╔════╝
█████╗  ██████╔╝██║██║         ██████╔╝██████╔╝██║  ███╗
██╔══╝  ██╔═══╝ ██║██║         ██╔══██╗██╔═══╝ ██║   ██║
███████╗██║     ██║╚██████╗    ██║  ██║██║     ╚██████╔╝
╚══════╝╚═╝     ╚═╝ ╚═════╝    ╚═╝  ╚═╝╚═╝      ╚═════╝
""".strip("\n")


class TitleScreen(Screen):
    BINDINGS = ARROW_BINDINGS + [Binding("n", "new", "New game"), Binding("l", "load", "Load"),
                                 Binding("o", "settings", "Settings"), Binding("q", "quit_game", "Quit")]

    def action_menu_move(self, step: int) -> None:
        cycle_focus(self, step)

    def compose(self) -> ComposeResult:
        with Vertical(id="title-root"):
            yield Static(Text(TITLE_ART, style="bold #E0A458"), id="title-art")
            yield Static("═══  A D V E N T U R E   A W A I T S  ═══", id="title-tagline")
            yield Static("Choose your race, master weapon and spell, and carve your legend through\n"
                         "goblin warrens, haunted graveyards and the lairs of ancient Titans.", id="title-blurb")
            with Center():
                with Vertical(id="title-menu"):
                    yield Button("New Game", variant="primary", id="new")
                    yield Button("Load Game", id="load")
                    yield Button("Settings", id="settings")
                    yield Button("Quit", id="quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#load", Button).disabled = not self.app.saves.any_saves()
        self.query_one("#new", Button).focus()

    def on_screen_resume(self) -> None:
        self.query_one("#load", Button).disabled = not self.app.saves.any_saves()

    @on(Button.Pressed, "#new")
    def action_new(self) -> None:
        from rpg.ui.screens.create_character import CreateCharacterScreen

        self.app.push_screen(CreateCharacterScreen())

    @on(Button.Pressed, "#load")
    def action_load(self) -> None:
        from rpg.ui.screens.save_load import SaveLoadScreen

        if self.app.saves.any_saves():
            self.app.push_screen(SaveLoadScreen("load"))

    @on(Button.Pressed, "#settings")
    def action_settings(self) -> None:
        from rpg.ui.screens.settings import SettingsScreen

        self.app.push_screen(SettingsScreen())

    @on(Button.Pressed, "#quit")
    def action_quit_game(self) -> None:
        self.app.exit()
