"""Quick-time event screen: one big key at a time and a draining bar. Hands on the keyboard."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

from rpg.core.minigames import QuickTimeEvent
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.minigames.base import MinigameScreen, heat, meter

BOX_WIDTH = 15


def key_box(label: str, style: str) -> Text:
    inner = BOX_WIDTH - 2
    text = Text(justify="center")
    text.append("╔" + "═" * inner + "╗\n", style=style)
    text.append("║" + " " * inner + "║\n", style=style)
    text.append("║", style=style)
    text.append(label.center(inner), style=f"bold {style}")
    text.append("║\n", style=style)
    text.append("║" + " " * inner + "║\n", style=style)
    text.append("╚" + "═" * inner + "╝", style=style)
    return text


class QTEScreen(MinigameScreen):
    kind_class = "-qte"
    game: QuickTimeEvent

    def render_stage(self) -> RenderableType:
        g = self.game
        if g.ready > 0:
            box = key_box("READY", "#E3B85C")
            bar = Text("Hands on the keys...", style="italic #E3B85C")
        elif g.current_key is None:
            last = g.results[-1] if g.results else None
            box = key_box("✓" if last else "✗" if last is not None else "", "#9FD08F" if last else "#E8604F")
            bar = Text(" ")
        else:
            urgency = 1 - g.time_ratio
            style = heat(urgency)
            box = key_box(g.current_label, "#F2C46D" if urgency < 0.6 else style)
            bar = meter(g.time_ratio, 40, style, char="━", rest="─")

        pips = Text()
        for i in range(len(g.sequence)):
            if i < len(g.results):
                pips.append("● " if g.results[i] else "✗ ", style="bold #9FD08F" if g.results[i] else "bold #E8604F")
            elif i == g.index:
                pips.append("◉ ", style="bold #F2C46D")
            else:
                pips.append("○ ", style=MUTED_STYLE)
        return Group(Align.center(box), Text(""), Align.center(bar), Text(""), Align.center(pips))
