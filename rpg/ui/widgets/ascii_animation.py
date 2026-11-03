"""Looping ASCII art animations: ASCII Motion exports (``tools/import_ascii_motion.py``) and the generated boss
portraits (``tools/make_boss_art.py``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from rich.text import Text
from textual.widgets import Static

ANIMATION_DIR = Path(__file__).resolve().parent.parent / "assets" / "animations"


def animation_exists(name: str) -> bool:
    return (ANIMATION_DIR / f"{name}.json").is_file()


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((ANIMATION_DIR / f"{name}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def load_frames(name: str, recolor: tuple[tuple[str, tuple[str, ...]], ...] = ()) -> tuple[float, tuple[Text, ...]]:
    """(fps, pre-rendered frames). ``recolor`` swaps a named color slot, e.g. (("glow", (...4 colors)),)."""
    data = _load(name)
    palette = dict(data["palette"])
    for slot, colors in recolor:
        for key, color in zip(data.get("slots", {}).get(slot, ()), colors):
            palette[key] = color
    frames = []
    for frame in data["frames"]:
        text = Text(no_wrap=True, overflow="crop")
        for row, (line, colors) in enumerate(zip(frame["lines"], frame["colors"])):
            if row:
                text.append("\n")
            start = 0
            for i in range(1, len(line) + 1):  # one span per run of the same color
                if i == len(line) or colors[i] != colors[start]:
                    key = colors[start]
                    text.append(line[start:i], style=palette.get(key, "") if key != " " else "")
                    start = i
        frames.append(text)
    return float(data.get("fps", 10)), tuple(frames)


class AsciiAnimation(Static):
    DEFAULT_CSS = """
    AsciiAnimation { width: auto; height: auto; }
    """

    def __init__(self, animation: str, fps: float | None = None, *, recolor: dict[str, tuple[str, ...]] | None = None,
                 id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self.animation = animation
        asset_fps, self.frames = load_frames(animation, tuple(sorted((recolor or {}).items())))
        self.fps = fps or asset_fps
        self.index = 0
        self._timer = None

    def on_mount(self) -> None:
        self.update(self.frames[0])
        self._timer = self.set_interval(1 / self.fps, self._advance)

    @property
    def _frozen(self) -> bool:
        settings = getattr(self.app, "settings", None)
        return bool(settings and settings.reduced_motion)

    def _advance(self) -> None:
        if self._frozen:
            return
        self.index = (self.index + 1) % len(self.frames)
        self.update(self.frames[self.index])

    def pause(self) -> None:
        if self._timer:
            self._timer.pause()

    def resume(self) -> None:
        if self._timer:
            self._timer.resume()
