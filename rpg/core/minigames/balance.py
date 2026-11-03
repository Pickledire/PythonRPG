"""Balance: keep your footing while you cross a beam, a ledge or a pitching deck.

Your lean ``x`` runs from -1 (falling left) to +1 (falling right). Leaning feeds on itself, like a real
balance, and gusts push you around. Tap ←/→ (or A/D) to shift your weight. Reach the far side to succeed.
Balance (Agility, Vitality, Dexterity) softens the gusts and the sway; ``stoneborn`` softens them further.
"""

from __future__ import annotations

import random

from rpg.core.events import Tone
from rpg.core.minigames.base import Minigame, MinigameKind, Outcome
from rpg.core.skills import Skill, SkillCheck

INSTABILITY = 1.35  # how quickly a lean grows on its own
DAMPING = 0.7
NUDGE = 0.32
SAFE_ZONE = 0.35
WOBBLE_ZONE = 0.7


class BalanceBeam(Minigame):
    kind = MinigameKind.BALANCE
    skill = Skill.BALANCE
    title = "Balance"
    controls = "Tap ← / → (or A / D) to shift your weight against the sway. Don't overcorrect."

    def __init__(self, check: SkillCheck, rng: random.Random | None = None, *, duration: float = 16.0,
                 gust: float = 0.7, time_scale: float = 1.0) -> None:
        super().__init__(check, rng)
        ease = check.ease()
        self.duration = max(4.0, float(duration))
        self.gust_strength = gust / ease ** 1.3 * (0.8 if check.has("stoneborn") else 1.0)
        self.instability = INSTABILITY / ease ** 0.5 / time_scale ** 0.5
        self.lean = 0.0
        self.velocity = 0.0
        self.gust = 0.0
        self.gust_timer = 1.2
        self.centered_time = 0.0
        self._warned = False

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def zone(self) -> str:
        lean = abs(self.lean)
        return "steady" if lean < SAFE_ZONE else "wobbling" if lean < WOBBLE_ZONE else "falling"

    def _tick(self, dt: float) -> None:
        self.gust_timer -= dt
        if self.gust_timer <= 0:
            # Gusts get a little stronger the further out you are.
            strength = self.gust_strength * (0.7 + 0.6 * self.progress)
            self.gust = self.rng.uniform(-strength, strength)
            self.gust_timer = self.rng.uniform(0.6, 1.5)
        accel = self.instability * self.lean + self.gust
        self.velocity += accel * dt
        self.velocity *= max(0.0, 1.0 - DAMPING * dt)
        self.lean += self.velocity * dt
        if abs(self.lean) < SAFE_ZONE:
            self.centered_time += dt
        if abs(self.lean) >= WOBBLE_ZONE and not self._warned:
            self._flash("You teeter!", Tone.WARNING)
            self._warned = True
        elif abs(self.lean) < SAFE_ZONE:
            self._warned = False
        if abs(self.lean) >= 1.0:
            side = "left" if self.lean < 0 else "right"
            self._finish(Outcome.FAILURE, self.progress * 0.5, f"You lose your footing and topple to the {side}!")
        elif self.elapsed >= self.duration:
            steadiness = self.centered_time / self.elapsed
            if steadiness >= 0.5:
                self._finish(Outcome.SUCCESS, steadiness, "You reach the far side, steady as stone.")
            else:
                self._finish(Outcome.PARTIAL, steadiness, "You stagger the last stretch and make it across.")

    def _press(self, key: str) -> None:
        if key in ("left", "a"):
            self.velocity -= NUDGE
        elif key in ("right", "d"):
            self.velocity += NUDGE
