"""Settings: built from ``rpg.services.settings.OPTIONS``. Changes apply and save immediately."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from rpg.services.settings import OPTIONS, Settings
from rpg.ui.palette import MUTED_STYLE


class SettingsScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        settings = self.app.settings
        with Vertical(id="settings-root"):
            yield Label("Settings", classes="screen-title")
            with VerticalScroll(id="settings-scroll"):
                group = None
                for info in OPTIONS:
                    if info.group != group:
                        group = info.group
                        yield Label(group, classes="settings-group")
                    with Horizontal(classes="settings-row"):
                        with Vertical(classes="settings-text"):
                            yield Label(info.label, classes="settings-label")
                            yield Static(Text(info.description, style=MUTED_STYLE), classes="settings-description")
                            yield Static("", id=f"blurb-{info.key}", classes="settings-blurb")
                        yield Select([(o.label, i) for i, o in enumerate(info.options)], allow_blank=False,
                                     value=self._index(settings, info.key), id=f"set-{info.key}",
                                     classes="settings-select")
            with Horizontal(classes="button-row"):
                yield Button("Back", variant="primary", id="back")
                yield Button("Reset to defaults", id="reset")
        yield Footer()

    @staticmethod
    def _index(settings: Settings, key: str) -> int:
        options = settings.options_for(key)
        value = getattr(settings, key)
        return next((i for i, o in enumerate(options) if o.value == value), 0)

    def on_mount(self) -> None:
        for info in OPTIONS:
            self._show_blurb(info.key)
        self.query_one("#back", Button).focus()

    def _show_blurb(self, key: str) -> None:
        settings = self.app.settings
        option = settings.options_for(key)[self._index(settings, key)]
        self.query_one(f"#blurb-{key}", Static).update(Text(option.blurb, style="italic #C9BFAE") if option.blurb else "")

    @on(Select.Changed, ".settings-select")
    def changed(self, event: Select.Changed) -> None:
        key = event.select.id.removeprefix("set-")
        if event.value is Select.BLANK:
            return
        option = self.app.settings.options_for(key)[int(event.value)]
        if getattr(self.app.settings, key) == option.value:
            return
        self.app.change_setting(key, option.value)
        self._show_blurb(key)

    @on(Button.Pressed, "#reset")
    def reset(self) -> None:
        defaults = Settings()
        for info in OPTIONS:
            self.query_one(f"#set-{info.key}", Select).value = self._index(defaults, info.key)
        self.notify("Settings reset to defaults.")

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()
