"""Lockpicking screen: a pin track with the marks of every probe, the pick, and its strain."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

from rpg.core.minigames import Lockpicking
from rpg.core.minigames.lockpick import TRACK
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.minigames.base import MinigameScreen, heat, meter

WIDTH = 60


def column(position: float) -> int:
    return max(0, min(WIDTH - 1, round(position / TRACK * (WIDTH - 1))))


def give_style(give: float) -> str:
    if give >= 1:
        return "bold #9FD08F"
    return "#E8604F" if give < 0.35 else "#E3B85C" if give < 0.75 else "#C9E07F"


class LockpickScreen(MinigameScreen):
    kind_class = "-lockpick"
    game: Lockpicking

    def render_stage(self) -> RenderableType:
        g = self.game
        pin = min(g.pin, g.pins - 1)

        # The lock face: set pins are raised.
        pins = Text(justify="center")
        for i in range(g.pins):
            if i < g.pin:
                pins.append(" ▀▀ ", style="bold #9FD08F")
            elif i == g.pin and not g.finished:
                pins.append(" ▄▄ ", style="bold #F2C46D")
            else:
                pins.append(" ▄▄ ", style=MUTED_STYLE)
        labels = Text(justify="center")
        for i in range(g.pins):
            labels.append(f" {i + 1:^2} ", style="bold #F2C46D" if i == g.pin else MUTED_STYLE)

        # The track: probe marks colored by how much the pin gave.
        cells = [Text("·", style="#4A4036") for _ in range(WIDTH)]
        for probe in g.probes[pin]:
            cells[column(probe.position)] = Text("▮" if probe.give >= 1 else "■", style=give_style(probe.give))
        track = Text.assemble(("┃", "#9C7A54"), *cells, ("┃", "#9C7A54"))
        pick = Text(" " * (column(g.position) + 1) + "▲", style="bold #EDE4D3")
        handle = Text(" " * (column(g.position) + 1) + "┃", style="#9C7A54")

        strain_ratio = g.strain / 100
        pick_name = g.current_pick.name if g.current_pick else "no pick"
        strain = Text.assemble(("Strain ", "bold"), meter(strain_ratio, 30, heat(strain_ratio)),
                               (f"  {int(g.strain):>3}%", heat(strain_ratio)))
        info = Text.assemble((f"Pin {pin + 1} of {g.pins}", "bold #F2C46D"), ("   ·   ", MUTED_STYLE),
                             (pick_name, "bold"), (f"  ({g.picks_left} left)", MUTED_STYLE))
        if g.time_left is not None:
            info.append(f"   ·   {g.time_left:4.1f}s", style="bold #E8604F" if g.time_left < 8 else "#E3B85C")
        legend = Text.assemble(("■", "#E8604F"), (" nothing  ", MUTED_STYLE), ("■", "#E3B85C"), (" shifts  ", MUTED_STYLE),
                               ("■", "#C9E07F"), (" so close  ", MUTED_STYLE), ("▮", "#9FD08F"), (" set", MUTED_STYLE))
        return Group(Align.center(pins), Align.center(labels), Text(""), Align.center(info), Text(""),
                     Align.center(Group(track, pick, handle)), Text(""), Align.center(strain), Align.center(legend))
