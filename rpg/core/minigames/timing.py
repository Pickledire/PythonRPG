"""Precision timing: strike when the sweeping needle crosses the mark.

A first-person "moment of truth": loose an arrow at a swinging rope, drive a spike into a crack, leap at
the top of a swing. Each strike scores perfect / good / miss and the needle speeds up after every strike.
Precision widens the zone and slows the needle; ``steady_hands`` slows it further.
"""

from __future__ import annotations

import random

from rpg.core.events import Tone
from rpg.core.minigames.base import Minigame, MinigameKind, Outcome, countdown
from rpg.core.skills import Skill, SkillCheck

PAUSE = 0.7  # between strikes
IDLE_LIMIT = 6.0  # a strike you never take counts as a miss
PERFECT_SHARE = 0.35  # perfect band as a share of the zone
SCORES = {"perfect": 1.0, "good": 0.6, "miss": 0.0}


class TimingStrike(Minigame):
    kind = MinigameKind.TIMING
    skill = Skill.PRECISION
    title = "Precision"
    controls = "Space (or Enter) when the needle is inside the mark. Dead center is perfect."

    def __init__(self, check: SkillCheck, rng: random.Random | None = None, *, strikes: int = 3,
                 speed: float = 0.9, zone: float = 0.09, success_score: float = 0.6,
                 partial_score: float = 0.3, action: str = "Strike", time_scale: float = 1.0) -> None:
        super().__init__(check, rng)
        self.action = action
        self.strikes = max(1, int(strikes))
        ease = check.ease()
        self.zone = max(0.025, min(0.2, zone * ease))
        self.speed = speed / ease ** 0.5 * (0.85 if check.has("steady_hands") else 1.0) / time_scale  # bars/second
        self.success_score, self.partial_score = success_score, partial_score
        self.needle = 0.0
        self.direction = 1
        self.center = self._new_center()
        self.grades: list[str] = []
        self.pause = 0.6
        self.idle = 0.0

    def _new_center(self) -> float:
        return self.rng.uniform(0.2, 0.8)

    @property
    def perfect(self) -> float:
        return self.zone * PERFECT_SHARE

    @property
    def waiting(self) -> bool:
        return self.pause > 0

    def _tick(self, dt: float) -> None:
        if self.pause > 0:
            self.pause = countdown(self.pause, dt)
            return
        self.needle += self.direction * self.speed * dt
        while not 0.0 <= self.needle <= 1.0:  # bounce off the ends
            if self.needle > 1.0:
                self.needle, self.direction = 2.0 - self.needle, -1
            else:
                self.needle, self.direction = -self.needle, 1
        self.idle += dt
        if self.idle >= IDLE_LIMIT:
            self._grade("miss", "You hesitate and the moment passes.")

    def _press(self, key: str) -> None:
        if key not in ("space", "enter") or self.pause > 0:
            return
        distance = abs(self.needle - self.center)
        if distance <= self.perfect:
            self._grade("perfect", "PERFECT!")
        elif distance <= self.zone:
            self._grade("good", "Good.")
        else:
            self._grade("miss", "Missed!")

    def _grade(self, grade: str, text: str) -> None:
        self.grades.append(grade)
        self._flash(text, {"perfect": Tone.CRIT, "good": Tone.PLAYER, "miss": Tone.MISS}[grade])
        self.idle = 0.0
        if len(self.grades) >= self.strikes:
            score = sum(SCORES[g] for g in self.grades) / self.strikes
            tally = ", ".join(self.grades)
            if score >= self.success_score:
                self._finish(Outcome.SUCCESS, score, f"Clean work ({tally}).")
            elif score >= self.partial_score:
                self._finish(Outcome.PARTIAL, score, f"Rough, but it holds ({tally}).")
            else:
                self._finish(Outcome.FAILURE, score, f"It goes wrong ({tally}).")
            return
        self.pause = PAUSE
        self.speed *= 1.12
        self.center = self._new_center()
