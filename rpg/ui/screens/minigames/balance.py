"""Balance screen: a lean gauge, a wind sock and a little figure walking the beam."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

from rpg.core.minigames import BalanceBeam
from rpg.core.minigames.balance import SAFE_ZONE, WOBBLE_ZONE
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.minigames.base import MinigameScreen

GAUGE = 49
BEAM = 56
POSES = [  # by lean, far left to far right
    ("\\o ", " \\\\", "  |"),
    ("_o/", " | ", "/ \\"),
    (" o ", "/|\\", "/ \\"),
    ("\\o_", " | ", "/ \\"),
    (" o/", "// ", "|  "),
]


def pose_for(lean: float) -> tuple[str, str, str]:
    if lean <= -WOBBLE_ZONE:
        return POSES[0]
    if lean <= -SAFE_ZONE:
        return POSES[1]
    if lean < SAFE_ZONE:
        return POSES[2]
    if lean < WOBBLE_ZONE:
        return POSES[3]
    return POSES[4]


class BalanceScreen(MinigameScreen):
    kind_class = "-balance"
    game: BalanceBeam

    def render_stage(self) -> RenderableType:
        g = self.game
        # Wind
        strength = min(1.0, abs(g.gust) / max(0.01, g.gust_strength * 1.3))
        arrows = max(1, round(strength * 6)) if abs(g.gust) > 0.02 else 0
        wind = Text("wind  ", style=MUTED_STYLE)
        if arrows:
            wind.append(("<" * arrows).rjust(6) if g.gust < 0 else " " * 6, style="#9EDCF2")
            wind.append(" ≋ ", style="#9EDCF2")
            wind.append((">" * arrows).ljust(6) if g.gust > 0 else " " * 6, style="#9EDCF2")
        else:
            wind.append("       calm      ", style=MUTED_STYLE)

        # Lean gauge
        marker = round((max(-1.0, min(1.0, g.lean)) + 1) / 2 * (GAUGE - 1))
        gauge = Text()
        for i in range(GAUGE):
            x = abs(i / (GAUGE - 1) * 2 - 1)
            style = "#86B57F" if x < SAFE_ZONE else "#E3B85C" if x < WOBBLE_ZONE else "#E8604F"
            gauge.append("●" if i == marker else "─", style=f"bold {'#FFFFFF' if i == marker else style}")
        gauge = Text.assemble(("FALL ", "#E8604F"), ("<", "#E8604F"), gauge, (">", "#E8604F"), (" FALL", "#E8604F"))

        # The beam with the walker
        at = round(g.progress * (BEAM - 4))
        head, body, legs = pose_for(g.lean)
        figure_style = {"steady": "bold #EDE4D3", "wobbling": "bold #E3B85C", "falling": "bold #E8604F"}[g.zone]
        rows = [Text(" " * at + part, style=figure_style) for part in (head, body, legs)]
        beam = Text.assemble(("▐", "#9C7A54"), ("━" * at, "#C98A4B"), ("━" * (BEAM - at), "#6F5A44"), ("▌ far side", "#9C7A54"))
        abyss = Text("  ░  ▒ ░  ░ ▒   ░  ▒  ░   ▒ ░  ░ ▒  ░  ▒   ░ ▒  ░  ▒ ░  ", style="#3A322A")
        status = Text(f"{g.zone.upper()}   ·   {int(g.progress * 100)}% across", style=figure_style)
        return Group(Align.center(wind), Text(""), Align.center(gauge), Text(""),
                     Align.center(Group(*rows, beam, abyss)), Text(""), Align.center(status))
