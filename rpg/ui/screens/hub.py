"""The camp: the main hub between adventures."""

from __future__ import annotations

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from rpg import config
from rpg.core.events import LogEvent, Tone
from rpg.ui.widgets import EventLog, PlayerPanel

ACTIONS = [
    ("hunt", "Hunt", "Find an enemy to fight", "h"),
    ("quests", "Quests", "Seek adventure and story", "q"),
    ("rest", "Rest", "Rest at the campfire", "r"),
    ("inventory", "Inventory", "Equip gear, use items", "i"),
    ("character", "Character", "Stats and attributes", "c"),
    ("shop", "Shop", "Merchant's Emporium", "s"),
    ("save", "Save", "Save your progress", "ctrl+s"),
    ("load", "Load", "Load a saved game", "l"),
    ("settings", "Settings", "Theme, difficulty, pacing and more", "o"),
    ("title", "Title", "Return to the title screen", "escape"),
]


class HubScreen(Screen):
    BINDINGS = [Binding(key, f"do('{action}')", label) for action, label, _, key in ACTIONS]

    def __init__(self) -> None:
        super().__init__()
        self._idle = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="hub-root"):
            yield PlayerPanel(id="hub-player")
            with Vertical(id="hub-main"):
                yield Label("", id="hub-title", classes="screen-title")
                with Grid(id="hub-actions"):
                    for action, label, hint, _ in ACTIONS:
                        button = Button(label, id=f"act-{action}", classes="hub-button")
                        button.tooltip = hint
                        yield button
                yield EventLog(id="hub-log")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#hub-log", EventLog)
        log.border_title = "Journal"
        log.add(LogEvent("You make camp at the edge of town. Adventure waits in every direction.", Tone.STORY))
        self.watch(self.app, "revision", lambda *_: self._refresh_title(), init=True)
        self.set_interval(1.0, self._idle_tick)
        self.query_one("#act-hunt", Button).focus()

    def _refresh_title(self) -> None:
        session = self.app.session
        if session:
            self.query_one("#hub-title", Label).update(f"Camp · {session.world.time_label}")

    def journal(self, events: list[LogEvent] | LogEvent) -> None:
        self.query_one("#hub-log", EventLog).add(events)

    # ------------------------------------------------------------ the haunting (idle timer)
    def on_key(self, _: events.Key) -> None:
        self._idle = 0

    def on_mouse_move(self, _: events.MouseMove) -> None:
        self._idle = 0

    def on_screen_resume(self) -> None:
        self._idle = 0

    def _idle_tick(self) -> None:
        session = self.app.session
        if session is None or self.app.screen is not self or not session.ghost_horror_available():
            self._idle = 0
            return
        self._idle += 1
        if self._idle in config.HAUNT_MESSAGES:
            self.journal(LogEvent(config.HAUNT_MESSAGES[self._idle], Tone.WARNING))
        if self._idle >= config.HAUNT_TIMEOUT_SECONDS:
            self._idle = 0
            self.app.run_flow(self.app.ghost_horror_flow())

    # ------------------------------------------------------------ actions
    @on(Button.Pressed, ".hub-button")
    def button(self, event: Button.Pressed) -> None:
        self.action_do(event.button.id.removeprefix("act-"))

    def action_do(self, action: str) -> None:
        app = self.app
        self._idle = 0
        if action == "hunt":
            app.run_flow(app.hunt_flow())
        elif action == "quests":
            from rpg.ui.screens.quests import QuestBoardScreen

            app.push_screen(QuestBoardScreen())
        elif action == "rest":
            from rpg.ui.screens.campfire import CampfireScreen

            app.push_screen(CampfireScreen())
        elif action == "inventory":
            from rpg.ui.screens.inventory import InventoryScreen

            app.push_screen(InventoryScreen())
        elif action == "character":
            from rpg.ui.screens.character import CharacterScreen

            app.push_screen(CharacterScreen())
        elif action == "shop":
            from rpg.ui.screens.shop import ShopScreen

            app.push_screen(ShopScreen("general"))
        elif action == "save":
            from rpg.ui.screens.save_load import SaveLoadScreen

            app.push_screen(SaveLoadScreen("save"))
        elif action == "load":
            from rpg.ui.screens.save_load import SaveLoadScreen

            app.push_screen(SaveLoadScreen("load"))
        elif action == "settings":
            from rpg.ui.screens.settings import SettingsScreen

            app.push_screen(SettingsScreen())
        elif action == "title":
            app.run_flow(app.quit_to_title_flow())
