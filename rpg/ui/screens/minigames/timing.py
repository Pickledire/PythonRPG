"""Precision screen: a sweeping needle over a bar with a marked zone."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

from rpg.core.minigames import TimingStrike
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.minigames.base import MinigameScreen

WIDTH = 64
GRADE_STYLES = {"perfect": "bold #FFB347", "good": "bold #9FD08F", "miss": "bold #E8604F"}


class TimingScreen(MinigameScreen):
    kind_class = "-timing"
    game: TimingStrike

    def render_stage(self) -> RenderableType:
        g = self.game
        needle = round(g.needle * (WIDTH - 1))
        bar = Text()
        for i in range(WIDTH):
            x = i / (WIDTH - 1)
            distance = abs(x - g.center)
            if distance <= g.perfect:
                char, style = "█", "#FFB347"
            elif distance <= g.zone:
                char, style = "▓", "#86B57F"
            else:
                char, style = "░", "#4A4036"
            if i == needle and not g.waiting:
                char, style = "┃", "bold #FFFFFF"
            bar.append(char, style=style)
        pointer = Text(" " * needle + ("▼" if not g.waiting else " "), style="bold #EDE4D3")
        frame = Text.assemble(("▕", "#9C7A54"), bar, ("▏", "#9C7A54"))

        tally = Text()
        for i in range(g.strikes):
            if i < len(g.grades):
                grade = g.grades[i]
                tally.append(f" {grade.upper():^9}", style=GRADE_STYLES[grade])
            else:
                tally.append(f" {'·':^9}", style=MUTED_STYLE)
        heading = Text(f"{g.action} {min(len(g.grades) + 1, g.strikes)} of {g.strikes}", style="bold #F2C46D")
        if g.waiting and not g.finished:
            heading.append("   steady...", style="italic " + MUTED_STYLE)
        return Group(Align.center(heading), Text(""), Align.center(Group(Text(" ") + pointer, frame)), Text(""),
                     Align.center(tally))
