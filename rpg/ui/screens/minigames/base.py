"""Shared shell for minigame screens: the game clock, input routing, flashes and the result banner.

Subclasses implement ``render_stage()`` (a Rich renderable for the main area) and may override
``compose_stage()`` for interactive widgets (the memory grid) or ``game_key()`` to change input.
"""

from __future__ import annotations

import time

from rich.console import RenderableType
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from rpg.core.minigames import Minigame, MinigameResult, Outcome
from rpg.ui.palette import MUTED_STYLE, TONE_STYLES

TICK = 1 / 30
OUTCOME_BANNERS = {
    Outcome.SUCCESS: ("SUCCESS", "bold #9FD08F"),
    Outcome.PARTIAL: ("PARTIAL SUCCESS", "bold #E3B85C"),
    Outcome.FAILURE: ("FAILURE", "bold #E8604F"),
}


def meter(ratio: float, width: int, fill: str, empty: str = "#3A322A", char: str = "█", rest: str = "░") -> Text:
    ratio = max(0.0, min(1.0, ratio))
    filled = round(width * ratio)
    return Text.assemble((char * filled, fill), (rest * (width - filled), empty))


def heat(ratio: float) -> str:
    """Green -> amber -> red as ``ratio`` rises."""
    return "#86B57F" if ratio < 0.45 else "#E3B85C" if ratio < 0.75 else "#E8604F"


class MinigameScreen(ModalScreen[MinigameResult]):
    kind_class = ""

    def __init__(self, game: Minigame, heading: str = "", subtitle: str = "", auto_close: float | None = None) -> None:
        super().__init__()
        self.game = game
        self.heading = heading or game.title
        self.subtitle = subtitle
        self.auto_close = auto_close
        self._last = time.monotonic()
        self._flash_until = 0.0
        self._shown_result = False

    def compose(self) -> ComposeResult:
        with Vertical(classes=f"minigame-box {self.kind_class}"):
            yield Label(self.heading, classes="minigame-title")
            if self.subtitle:
                yield Static(self.subtitle, classes="minigame-subtitle")
            yield from self.compose_stage()
            yield Static(" ", id="mg-flash")
            yield Static(Text(self.game.controls, style=MUTED_STYLE), id="mg-controls")
            with Horizontal(id="mg-done"):
                yield Button("Continue", variant="primary", id="mg-continue")

    def compose_stage(self) -> ComposeResult:
        yield Static(id="mg-stage")

    def on_mount(self) -> None:
        self.query_one("#mg-done").display = False
        self._last = time.monotonic()
        self.set_interval(TICK, self._tick)
        self.refresh_stage()

    # ------------------------------------------------------------ clock
    def _tick(self) -> None:
        now = time.monotonic()
        dt, self._last = min(0.1, now - self._last), now
        if self.app.screen is not self:  # paused while something covers the trial
            return
        self.game.tick(dt)
        self._show_flashes()
        self.refresh_stage()
        if self.game.finished and not self._shown_result:
            self._show_result()

    def refresh_stage(self) -> None:
        stage = self.query("#mg-stage")
        if stage:
            stage.first(Static).update(self.render_stage())

    def render_stage(self) -> RenderableType:
        return Text("")

    def _show_flashes(self) -> None:
        flashes = self.game.take_flashes()
        flash = self.query_one("#mg-flash", Static)
        if flashes:
            last = flashes[-1]
            flash.update(Text(last.text, style=TONE_STYLES.get(last.tone, "")))
            self._flash_until = time.monotonic() + 1.4
        elif self._flash_until and time.monotonic() > self._flash_until and not self.game.finished:
            flash.update(" ")
            self._flash_until = 0.0

    def _show_result(self) -> None:
        self._shown_result = True
        result = self.game.result
        assert result is not None
        banner, style = OUTCOME_BANNERS[result.outcome]
        text = Text.assemble((f"{banner}  ", style), (result.summary, "#EDE4D3"))
        self.query_one("#mg-flash", Static).update(text)
        self.query_one("#mg-controls", Static).display = False
        self.query_one("#mg-done").display = True
        self.query_one("#mg-continue", Button).focus()
        if self.auto_close:
            self.set_timer(self.auto_close, self._close)

    # ------------------------------------------------------------ input
    def on_key(self, event: events.Key) -> None:
        if self.game.finished:
            return  # the Continue button handles Enter/Space
        event.stop()
        event.prevent_default()
        self.game_key(event.key)
        self._show_flashes()
        self.refresh_stage()

    def game_key(self, key: str) -> None:
        if key == "escape":
            self.game.abandon()
        else:
            self.game.press(key)

    @on(Button.Pressed, "#mg-continue")
    def _close(self) -> None:
        if self.app.screen is self and self.game.result is not None:
            self.dismiss(self.game.result)
