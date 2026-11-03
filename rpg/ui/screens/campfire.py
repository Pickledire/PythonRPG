"""Rest at the campfire: animation, recovery and a random night event."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from rpg.core.campfire import CampfireReport
from rpg.core.combat import Phase
from rpg.core.session import Encounter
from rpg.ui.widgets import AsciiAnimation, EventLog

REST_SECONDS = 2.5


class CampfireScreen(Screen[None]):
    BINDINGS = [Binding("escape", "leave", "Back to camp")]

    def __init__(self) -> None:
        super().__init__()
        self.report: CampfireReport | None = None
        self._done = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="campfire-root"):
            yield Label("You set up a small camp and rest by the fire...", classes="screen-title")
            with Horizontal(id="campfire-scene"):
                yield AsciiAnimation("campfire", id="campfire-art")
                yield EventLog(id="campfire-log")
            with Center():
                with Horizontal(id="campfire-buttons"):
                    yield Button("Fight!", variant="error", id="fight")
                    yield Button("Approach", variant="primary", id="approach")
                    yield Button("Back to camp", id="leave")
        yield Footer()

    def on_mount(self) -> None:
        for button_id in ("fight", "approach", "leave"):
            self.query_one(f"#{button_id}", Button).display = False
        self.run_worker(self._rest())

    async def _rest(self) -> None:
        log = self.query_one("#campfire-log", EventLog)
        log.add_text(Text("You feed the fire and settle in for the night...", style="#C9BFAE"))
        await asyncio.sleep(REST_SECONDS)
        log.add_text(Text("Warmth seeps into your bones...", style="#E3B85C"))
        await asyncio.sleep(0.3)
        self.report = self.app.session.rest()
        self.app.touch()
        log.add(self.report.events)
        await self.app.resolve_level_ups()
        if self.report.ambush:
            self.query_one("#fight", Button).display = True
            self.query_one("#fight", Button).focus()
        elif self.report.dialogue_category:
            self.query_one("#approach", Button).display = True
            self.query_one("#leave", Button).display = True
            self.query_one("#leave", Button).label = "Ignore them"
            self.query_one("#approach", Button).focus()
        else:
            self._show_leave()

    def _show_leave(self) -> None:
        self._done = True
        leave = self.query_one("#leave", Button)
        leave.label = "Back to camp"
        leave.display = True
        leave.focus()

    @on(Button.Pressed, "#fight")
    def fight(self) -> None:
        self.query_one("#fight", Button).display = False
        self.app.run_flow(self._ambush())

    async def _ambush(self) -> None:
        assert self.report and self.report.ambush
        phase = await self.app.run_encounter(Encounter(self.report.ambush))
        if phase == Phase.DEFEAT:
            return
        self.query_one("#campfire-log", EventLog).add_text("The night falls quiet again.")
        self._show_leave()

    @on(Button.Pressed, "#approach")
    def approach(self) -> None:
        from rpg.ui.screens.dialogue import DialogueScreen

        assert self.report and self.report.dialogue_category
        dialogue_id = self.app.session.random_dialogue(self.report.dialogue_category)
        self.query_one("#approach", Button).display = False
        self._show_leave()
        if dialogue_id:
            self.app.push_screen(DialogueScreen(self.app.session.dialogue(dialogue_id), title="A visitor in the night"))
        else:
            self.query_one("#campfire-log", EventLog).add_text("...but they melt back into the dark.")

    @on(Button.Pressed, "#leave")
    def action_leave(self) -> None:
        if self.report is None or (self.report.ambush and not self._done):
            return  # still resting, or an ambush must be faced
        self.dismiss(None)
