"""Memory screen: a 3×3 grid of runes you click with the mouse. The keyboard does nothing here."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Grid
from textual.widgets import Static

from rpg.core.minigames import MemorySequence
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.minigames.base import MinigameScreen

RUNES = [  # glyph, name, color
    ("☼", "Sun", "#F2C46D"), ("☾", "Moon", "#9EDCF2"), ("✦", "Star", "#EDE4D3"),
    ("▲", "Peak", "#C98A4B"), ("◆", "Gem", "#C99BE8"), ("≈", "Tide", "#7FA8E0"),
    ("✚", "Hearth", "#E8604F"), ("◐", "Dusk", "#A99FBF"), ("❦", "Root", "#86B57F"),
]


class RuneTile(Static):
    """Clickable but never focusable, so the trial is mouse-only."""

    can_focus = False

    def __init__(self, index: int) -> None:
        super().__init__(id=f"rune-{index}", classes="rune-tile")
        self.index = index

    def show(self, state: str) -> None:
        glyph, name, color = RUNES[self.index]
        style = {"lit": f"bold {color}", "right": "bold #9FD08F", "wrong": "bold #E8604F"}.get(state, MUTED_STYLE)
        self.update(Text.assemble((glyph, style), "\n", (name, style if state != "idle" else "#6F665A"),
                                  justify="center"))
        for cls in ("-lit", "-right", "-wrong"):
            self.set_class(state == cls[1:], cls)

    def on_click(self, event: events.Click) -> None:
        screen = self.screen
        if isinstance(screen, MemoryScreen):
            screen.click_rune(self.index)


class MemoryScreen(MinigameScreen):
    kind_class = "-memory"
    game: MemorySequence

    def compose_stage(self) -> ComposeResult:
        yield Static(id="mg-stage")
        with Grid(id="rune-grid"):
            for i in range(len(RUNES)):
                yield RuneTile(i)

    def game_key(self, key: str) -> None:
        pass  # mouse only

    def click_rune(self, index: int) -> None:
        if not self.game.finished:
            self.game.click(index)
            self._show_flashes()
            self.refresh_stage()

    def refresh_stage(self) -> None:
        g = self.game
        state = g.state
        if g.finished:
            status = Text("")
        elif state in ("lead_in", "showing", "gap"):
            status = Text.assemble(("Watch closely...", "bold #E3B85C"))
        elif state == "input":
            status = Text.assemble(("Your turn  ", "bold #9FD08F"), (f"{len(g.entered)}/{len(g.sequence)}", "bold"))
        else:
            status = Text(" ")
        glances = Text.assemble(("   glances ", MUTED_STYLE), ("◆" * g.glances, "bold #C99BE8"),
                                ("◇" * (g.max_glances - g.glances), MUTED_STYLE))
        rounds = Text(f"Sequence {min(g.round + 1, g.rounds)} of {g.rounds} · {g.length} runes   ", style="bold #F2C46D")
        line = Text.assemble(rounds, status, glances, justify="center")
        self.query_one("#mg-stage", Static).update(line)

        click = g.last_click if state in ("input", "feedback") else None
        for tile in self.query(RuneTile):
            if g.lit == tile.index:
                tile.show("lit")
            elif click and click[0] == tile.index:
                tile.show("right" if click[1] else "wrong")
            else:
                tile.show("idle")
