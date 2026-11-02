"""Save / load slot picker."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from rpg.services.persistence import SaveError
from rpg.ui.screens.modals import ConfirmModal


class SaveLoadScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, mode: str) -> None:
        super().__init__()
        if mode not in ("save", "load"):
            raise ValueError(mode)
        self.mode = mode

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="slots-root"):
            yield Label("Save your progress" if self.mode == "save" else "Load a saved game", classes="screen-title")
            yield OptionList(id="slot-list")
            yield Label("Enter to choose · Esc to go back", classes="muted")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_slots()
        self.query_one(OptionList).focus()

    def refresh_slots(self) -> None:
        options = self.query_one(OptionList)
        options.clear_options()
        first_enabled = None
        for index, info in enumerate(self.app.saves.list_slots()):
            disabled = self.mode == "load" and (not info.exists or bool(info.error))
            options.add_option(Option(info.label, id=f"slot{info.slot}", disabled=disabled))
            if not disabled and first_enabled is None:
                first_enabled = index
        if first_enabled is not None:
            options.highlighted = first_enabled

    @on(OptionList.OptionSelected, "#slot-list")
    def picked(self, event: OptionList.OptionSelected) -> None:
        self._handle(int(event.option_id.removeprefix("slot")))

    @work
    async def _handle(self, slot: int) -> None:
        app = self.app
        info = app.saves.slot_info(slot)
        if self.mode == "save":
            if info.exists and not await app.push_screen_wait(
                    ConfirmModal(f"Overwrite {info.label}?", "Overwrite", "Cancel")):
                return
            try:
                app.saves.save(app.session, slot)
            except OSError as exc:
                app.notify(f"Save failed: {exc}", severity="error")
                return
            app.notify(f"Saved to slot {slot}.")
            self.dismiss(None)
        else:
            if app.session is not None and not await app.push_screen_wait(
                    ConfirmModal("Load this save? Unsaved progress will be lost.", "Load", "Cancel")):
                return
            try:
                session = app.saves.load(slot)
            except SaveError as exc:
                app.notify(str(exc), severity="error")
                return
            session.rng = app.make_rng()
            app.start_session(session)
            app.notify(f"Welcome back, {session.player.name}.")
