"""Stealth screen: the hiding spot, the hunter's attention, the silence meter and your breath."""

from __future__ import annotations

import time

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

from rpg.core.minigames import Stealth
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.minigames.base import MinigameScreen, heat, meter

SCENE = 50
ATTENTION_TEXT = {
    "distant": ("◌ DISTANT", "#86B57F", "It is searching somewhere further off."),
    "near": ("◉ NEAR", "#E3B85C", "It prowls close to your hiding place."),
    "listening": ("◉ LISTENING", "#E8604F", "It has gone utterly still. It is listening."),
}
DISTANCE = {"distant": 0.9, "near": 0.45, "listening": 0.18}


class StealthScreen(MinigameScreen):
    kind_class = "-stealth"
    game: Stealth

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._hunter_x = DISTANCE["distant"]

    def render_stage(self) -> RenderableType:
        g = self.game
        label, color, line = ATTENTION_TEXT[g.attention]
        blink = int(time.monotonic() * 4) % 2 == 0

        # The scene: you behind cover on the left, the hunter drifting closer or further on the right.
        target = DISTANCE[g.attention]
        self._hunter_x += (target - self._hunter_x) * 0.08
        hunter_col = 6 + round(self._hunter_x * (SCENE - 10))
        words = [w for w in g.creature.split() if w.lower() not in ("the", "a", "an")]
        initial = (words[0][:1] if words else "?").upper()
        scene = Text()
        scene.append("▓▓", style="#6F5A44")
        scene.append("@", style="bold #EDE4D3" if not g.holding else "bold #9EDCF2")
        scene.append("▓▓", style="#6F5A44")
        scene.append(" " * (hunter_col - 5))
        scene.append(f"[{initial}]", style=f"bold {color}")
        if g.attention == "listening":
            scene.append(" ?", style=f"bold {color}")
        floor = Text("▀" * SCENE, style="#3A322A")

        attention = Text.assemble((label, f"bold {color}"), ("   " + line, MUTED_STYLE))
        warning = Text("!!  It's about to stop and listen  !!" if g.warning and blink else " ", style="bold #E8604F")

        noise_ratio = g.noise / 100
        noise = Text.assemble(("Noise   ", "bold"), meter(noise_ratio, 40, heat(noise_ratio)),
                              (f" {int(g.noise):>3}", heat(noise_ratio)))
        breath_style = "#7FA8E0" if g.breath > 30 else "#E8604F"
        breath = Text.assemble(("Breath  ", "bold"), meter(g.breath / 100, 40, breath_style),
                               ("  HOLDING" if g.holding else "  breathing", "bold #9EDCF2" if g.holding else MUTED_STYLE))

        if g.mishap:
            m = g.mishap
            mishap = Text.assemble(("! ", "bold #E3B85C"), (m.text + " — ", "#EDE4D3"), ("press ", MUTED_STYLE),
                                   (f" {m.label} ", "bold reverse #F2C46D"), ("  ", ""),
                                   meter(m.time_left / m.window, 12, heat(1 - m.time_left / m.window), char="━", rest="─"))
        else:
            mishap = Text(" ")
        clock = Text(f"Until it moves on: {g.time_left:4.1f}s", style="bold #F2C46D")
        return Group(Align.center(Group(scene, floor)), Text(""), Align.center(attention), Align.center(warning),
                     Text(""), Align.center(noise), Align.center(breath), Text(""), Align.center(mishap), Text(""),
                     Align.center(clock))
