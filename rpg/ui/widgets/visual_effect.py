"""Short ASCII set-pieces (quake, snowfall, glyphs...) played by dialogue ``visual`` effects."""

from __future__ import annotations

import asyncio
import random

from rich.text import Text
from textual.widgets import Static

FRAMES: dict[str, tuple[list[str], list[str]]] = {
    # name: (frames, colors)
    "quake": (["▓ ▓▓▓  ▓▓ ▓  ▓▓▓", " ▓▓  ▓▓▓  ▓ ▓ ▓▓", "▓  ▓▓  ▓▓▓  ▓▓ ", "  ▓▓▓ ▓  ▓ ▓▓▓ "], ["#E3B85C", "#C98A4B"]),
    "shadow_sweep": (["████████████████        ", "    ████████████████    ", "        ████████████████"], ["#4A4036"]),
    "glyphs": (["∆ ∴ ✧ ✦ ∵ ✩ ✪ ∆ ✧", "✦ ∵ ∆ ✩ ∴ ✧ ✪ ∵ ✦", "✩ ✧ ∴ ✪ ∆ ✦ ∵ ✩ ∴"], ["#C99BE8", "#7FA8E0"]),
    "candle": (["  )   (  ", "  (   )  ", "   ) (   "], ["#E3B85C", "#FFB347"]),
    "gears": (["(|) (/) (-) (\\)", "(/) (-) (\\) (|)", "(-) (\\) (|) (/)"], ["#7FA8E0", "#9C7A54"]),
    "banner": (["≈≈≈≈≈≈≈≈≈≈≈≈", "~~~~~~~~~~~~", "≋≋≋≋≋≋≋≋≋≋≋≋", "-~-~-~-~-~-~"], ["#F2C46D"]),
    "cold_breath": (["·  ·   ·", " · ·  ·  ", "   ·  · ·", "·   ·    "], ["#9EDCF2"]),
    "snow": (["*  ·  ✦   .  *   ·", " ·  *   .  ✦  ·  *", "✦   ·  *   ·   .  "], ["#EDE4D3", "#9EDCF2"]),
    "torch": (["  ^  ", " ^^^ ", "^^^^^", " ^^^ "], ["#FFB347", "#E8604F"]),
    "bridge_collapse": (["==== ==== ====", "== == == == ==", "=  ==  =  ==  ", "_   __    _   "], ["#E3B85C"]),
    "aurora": (["≈≈≈≈≈≈≈≈≈≈≈≈", "~~~~~~~~~~", "≋≋≋≋≋≋≋≋", "⋰⋱⋰⋱⋰⋱⋰⋱"], ["#7FD1A8", "#C99BE8", "#9EDCF2"]),
    "campfire": (["  (  )  (   ", " ) (  ) )  ", "(  ) (  ( ) ", " ^^ ^^^^ ^^ "], ["#FF8C42", "#E8604F", "#F2C46D"]),
}

ALIASES = {
    "tremor": "quake", "wings": "shadow_sweep", "arcane": "glyphs", "flicker": "candle", "clockwork": "gears",
    "coin_shimmer": "banner", "mist": "cold_breath", "snowfall": "snow", "torchlight": "torch", "bridge": "bridge_collapse",
    "collapse": "bridge_collapse", "lights": "aurora", "fire": "campfire",
}


class VisualEffect(Static):
    DEFAULT_CSS = """
    VisualEffect { height: auto; min-height: 1; content-align: center middle; text-align: center; }
    """

    async def play(self, name: str, duration: float = 1.2, rows: int = 3) -> None:
        key = ALIASES.get(name.lower(), name.lower())
        settings = getattr(self.app, "settings", None)
        if key not in FRAMES or (settings and settings.reduced_motion):
            return
        frames, colors = FRAMES[key]
        rng = random.Random()

        def draw() -> None:
            text = Text(justify="center")
            for row in range(rows):
                if row:
                    text.append("\n")
                text.append(rng.choice(frames), style=rng.choice(colors))
            self.update(text)

        draw()
        timer = self.set_interval(0.09, draw)
        try:
            await asyncio.sleep(max(0.2, duration))
        finally:
            timer.stop()
            self.update("")
