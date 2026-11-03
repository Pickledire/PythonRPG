"""The minigame contract shared by every trial.

A minigame is a pure, real-time state machine. The UI calls ``tick(dt)`` on a timer, forwards input with
``press(key)`` (Textual key names: ``"left"``, ``"space"``, ``"w"``...) or ``click(index)``, renders from the
public state, and reads ``result`` once ``finished`` is set. No UI imports, so tests drive games directly
with a seeded RNG and fake time.

Difficulty comes from a ``SkillCheck`` (rating vs dc, plus traits). Each game turns ``check.ease()`` into
wider windows, slower needles, gentler gusts and so on, so attributes, race, gear and tonics all matter
without any game knowing where the numbers came from.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from rpg.core.events import Tone
from rpg.core.skills import Skill, SkillCheck


class MinigameKind(str, Enum):
    QTE = "qte"
    LOCKPICK = "lockpick"
    TIMING = "timing"
    MEMORY = "memory"
    BALANCE = "balance"
    STEALTH = "stealth"


class Outcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass
class MinigameResult:
    kind: MinigameKind
    outcome: Outcome
    score: float  # 0..1, how well it went
    summary: str
    abandoned: bool = False
    spent: list[Any] = field(default_factory=list)  # consumables used up (broken lockpicks)

    @property
    def succeeded(self) -> bool:
        return self.outcome != Outcome.FAILURE


@dataclass(frozen=True)
class Flash:
    """A short message the UI shows as feedback ("The pin sets!")."""

    text: str
    tone: Tone = Tone.INFO


class Minigame:
    kind: ClassVar[MinigameKind]
    skill: ClassVar[Skill]
    title: ClassVar[str] = "Trial"
    controls: ClassVar[str] = ""
    can_abandon: ClassVar[bool] = False

    def __init__(self, check: SkillCheck, rng: random.Random | None = None) -> None:
        self.check = check
        self.rng = rng or random.Random()
        self.elapsed = 0.0
        self.result: MinigameResult | None = None
        self.flashes: list[Flash] = []

    # ------------------------------------------------------------ driving the game
    @property
    def finished(self) -> bool:
        return self.result is not None

    def tick(self, dt: float) -> None:
        if self.finished or dt <= 0:
            return
        self.elapsed += dt
        self._tick(dt)

    def press(self, key: str) -> None:
        if not self.finished:
            self._press(key)

    def click(self, index: int) -> None:
        if not self.finished:
            self._click(index)

    def abandon(self) -> None:
        if self.can_abandon and not self.finished:
            self._finish(Outcome.FAILURE, 0.0, "You give up.", abandoned=True)

    def take_flashes(self) -> list[Flash]:
        flashes, self.flashes = self.flashes, []
        return flashes

    # ------------------------------------------------------------ for subclasses
    def _tick(self, dt: float) -> None:
        pass

    def _press(self, key: str) -> None:
        pass

    def _click(self, index: int) -> None:
        pass

    def _flash(self, text: str, tone: Tone = Tone.INFO) -> None:
        self.flashes.append(Flash(text, tone))

    def _finish(self, outcome: Outcome, score: float, summary: str, **extra: Any) -> None:
        self.result = MinigameResult(self.kind, outcome, max(0.0, min(1.0, score)), summary, **extra)


def countdown(value: float, dt: float) -> float:
    return max(0.0, value - dt)


# Keys a prompt can ask for, and how to draw them.
KEY_GLYPHS = {"left": "←", "right": "→", "up": "↑", "down": "↓", "space": "SPACE"}
GLYPH_KEYS = {glyph: key for key, glyph in KEY_GLYPHS.items()}


def parse_key_pool(pool: str) -> list[str]:
    """``"WASD"`` -> ["w", "a", "s", "d"]; ``"←→↑↓"`` -> ["left", "right", "up", "down"]."""
    keys = []
    for char in pool:
        if char in GLYPH_KEYS:
            keys.append(GLYPH_KEYS[char])
        elif char.isalnum():
            keys.append(char.lower())
    return keys or ["w", "a", "s", "d"]


def key_label(key: str) -> str:
    return KEY_GLYPHS.get(key, key.upper())
