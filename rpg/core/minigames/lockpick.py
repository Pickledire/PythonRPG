"""Lockpicking: find each pin's sweet spot by feel before the pick snaps.

This one is deliberately calm. Slide the pick along the pin (left/right) and apply tension (space/up).
Each probe tells you how close you were and leaves a mark on the track. Missing strains the pick, and
the further off you are, the more strain. Lockpicks are consumables: a pick snaps at 100 strain and the
next one in your pack takes over. Pins already set stay set.

Lockpicking (mostly Dexterity) widens the sweet spot and lowers strain. Better picks (potency 2-3) and
the ``tinker`` trait lower strain further.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rpg.core.events import Tone
from rpg.core.minigames.base import Minigame, MinigameKind, Outcome
from rpg.core.skills import Skill, SkillCheck

TRACK = 100
STEP = 2
BIG_STEP = 6
BASE_HALF_WIDTH = 6.0
FEEL_RANGE = 30.0  # how far from the sweet spot a probe still "gives"
QUALITY_STRAIN = {1: 1.0, 2: 0.65, 3: 0.4}


@dataclass
class Probe:
    position: int
    give: float  # 0..1, how much the pin moved


class Lockpicking(Minigame):
    kind = MinigameKind.LOCKPICK
    skill = Skill.LOCKPICKING
    title = "Lockpicking"
    controls = "←/→ slide the pick (shift for big steps) · Space or ↑ apply tension · Esc give up"
    can_abandon = True

    def __init__(self, check: SkillCheck, rng: random.Random | None = None, *, pins: int | None = None,
                 picks: list | None = None, time_limit: float = 0.0, time_scale: float = 1.0) -> None:
        super().__init__(check, rng)
        count = pins if pins is not None else 2 + check.dc // 5
        self.pins = max(1, min(6, int(count)))
        self.sweet = [self.rng.randint(10, TRACK - 10) for _ in range(self.pins)]
        self.half_width = max(2.5, min(12.0, BASE_HALF_WIDTH * check.ease()))
        self.picks = list(picks or [])  # consumable items, best first; each has .potency
        self.spent: list = []
        self.pin = 0
        self.position = TRACK // 2
        self.strain = 0.0
        self.probes: list[list[Probe]] = [[] for _ in range(self.pins)]
        self.time_limit = float(time_limit) * time_scale
        if not self.picks:
            self._finish(Outcome.FAILURE, 0.0, "You have no lockpicks.")

    # ------------------------------------------------------------ state for the UI
    @property
    def current_pick(self):
        return self.picks[0] if self.picks else None

    @property
    def picks_left(self) -> int:
        return len(self.picks)

    @property
    def time_left(self) -> float | None:
        return max(0.0, self.time_limit - self.elapsed) if self.time_limit else None

    def strain_per_miss(self, give: float) -> float:
        quality = QUALITY_STRAIN.get(getattr(self.current_pick, "potency", 1), 0.4)
        multiplier = quality / self.check.ease() ** 1.5
        if self.check.has("tinker"):
            multiplier *= 0.7
        return (6 + 22 * (1 - give)) * multiplier

    # ------------------------------------------------------------ rules
    def _tick(self, dt: float) -> None:
        if self.time_limit and self.elapsed >= self.time_limit:
            self._end(False, "Footsteps! You pull the pick out before anyone sees you.")

    def _press(self, key: str) -> None:
        if key in ("left", "a"):
            self.position = max(0, self.position - STEP)
        elif key in ("right", "d"):
            self.position = min(TRACK, self.position + STEP)
        elif key == "shift+left":
            self.position = max(0, self.position - BIG_STEP)
        elif key == "shift+right":
            self.position = min(TRACK, self.position + BIG_STEP)
        elif key in ("space", "up", "w"):
            self._probe()
        elif key == "escape":
            self.abandon()

    def _probe(self) -> None:
        distance = abs(self.position - self.sweet[self.pin])
        if distance <= self.half_width:
            self.probes[self.pin].append(Probe(self.position, 1.0))
            self.pin += 1
            self.strain = max(0.0, self.strain - 20)
            if self.pin >= self.pins:
                self._end(True, "The last pin sets. The lock turns with a soft click.")
                return
            self._flash(f"Click! Pin {self.pin} of {self.pins} sets.", Tone.PLAYER)
            self.position = TRACK // 2
            return
        give = max(0.0, 1.0 - (distance - self.half_width) / FEEL_RANGE)
        self.probes[self.pin].append(Probe(self.position, give))
        self.strain += self.strain_per_miss(give)
        if give > 0.75:
            self._flash("So close — the pin almost gives.", Tone.WARNING)
        elif give > 0.4:
            self._flash("The pin shifts a little.", Tone.INFO)
        elif give > 0:
            self._flash("A faint give.", Tone.MISS)
        else:
            self._flash("Nothing. Dead metal.", Tone.MISS)
        if self.strain >= 100:
            broken = self.picks.pop(0)
            self.spent.append(broken)
            self.strain = 0.0
            if not self.picks:
                self._end(False, f"Your {broken.name.lower()} snaps — and it was your last one.")
                return
            self._flash(f"SNAP! Your {broken.name.lower()} breaks. {len(self.picks)} left.", Tone.DAMAGE)

    def abandon(self) -> None:
        if not self.finished:
            self._end(False, "You ease the pick out and leave the lock be.", abandoned=True)

    def _end(self, opened: bool, summary: str, abandoned: bool = False) -> None:
        broken = len(self.spent)
        if opened:
            outcome = Outcome.SUCCESS if broken <= 1 else Outcome.PARTIAL
            score = max(0.25, 1.0 - 0.25 * broken)
        else:
            outcome, score = Outcome.FAILURE, self.pin / self.pins * 0.5
        self._finish(outcome, score, summary, abandoned=abandoned, spent=list(self.spent))
