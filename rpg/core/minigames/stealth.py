"""Stealth: stay hidden from something that is hunting you until it moves on.

The silence meter (noise, 0-100) fills when you breathe, fumble or gasp, and drains while you're quiet.
At 100 you're discovered. The creature's attention cycles between *distant*, *near* and *listening*, and
every sound is multiplied by how closely it's paying attention. A warning comes before it listens.

* **Space** toggles holding your breath: no breathing noise, but your lungs drain. Run dry and you gasp.
* **Mishaps** (gravel shifts, a sleeve snags) flash an arrow key; press it in time or make a noise.
* Pressing anything else is fidgeting, which also makes noise.

Stealth (Agility, Dexterity, Wisdom) quiets your breathing, softens mishaps and widens their windows.
Vitality decides how long you can hold your breath. Traits: ``small_frame`` (quieter), ``heavy_step``
(louder mishaps), ``breathless`` (barely needs air), ``smoldering`` (smoky coughs), ``keen_senses``
(earlier warning).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rpg.core.events import Tone
from rpg.core.minigames.base import Minigame, MinigameKind, Outcome, countdown, key_label
from rpg.core.skills import Skill, SkillCheck

ATTENTION = {"distant": 0.3, "near": 1.0, "listening": 2.4}
BREATH_NOISE = 12.0  # per second while breathing, at attention 1.0
NOISE_DECAY = 4.0  # per second
HOLD_DRAIN = 14.0  # breath per second while holding it (at Vitality 10)
BREATH_RECOVER = 22.0
GASP_NOISE = 30.0
MISHAP_NOISE = 22.0
FIDGET_NOISE = 4.0
WARN_TIME = 1.2
MISHAP_KEYS = ("left", "right", "up", "down")
MISHAPS = (
    "Loose gravel shifts under your heel",
    "Your sleeve snags on a splinter",
    "Dust tickles the back of your throat",
    "A cramp knots in your calf",
    "Your scabbard starts to slide",
    "Something skitters across your hand",
)
COUGHS = ("Smoke curls up from your lungs", "An ember-cough rises in your chest")


@dataclass
class Mishap:
    text: str
    key: str
    window: float
    time_left: float

    @property
    def label(self) -> str:
        return key_label(self.key)


class Stealth(Minigame):
    kind = MinigameKind.STEALTH
    skill = Skill.STEALTH
    title = "Stealth"
    controls = "Space hold / release your breath · arrow keys when a mishap flashes · anything else is noise"

    def __init__(self, check: SkillCheck, rng: random.Random | None = None, *, duration: float = 22.0,
                 presence: float = 1.0, vitality: int = 10, creature: str = "It", time_scale: float = 1.0) -> None:
        super().__init__(check, rng)
        ease = check.ease()
        self.creature = creature
        self.duration = max(6.0, float(duration))
        self.presence = max(0.5, float(presence))
        self.loudness = (0.8 if check.has("small_frame") else 1.0) / ease
        self.decay = NOISE_DECAY * ease ** 0.5
        lungs = max(0.6, min(1.6, 10 / max(1, vitality)))
        self.drain = HOLD_DRAIN * lungs * (0.3 if check.has("breathless") else 1.0)
        self.mishap_window = max(0.6, 1.25 * ease) * time_scale
        self.mishap_loudness = MISHAP_NOISE * (1.3 if check.has("heavy_step") else 1.0)
        self.warn_time = WARN_TIME + (1.0 if check.has("keen_senses") else 0.0)
        self.noise = 0.0
        self.peak = 0.0
        self.breath = 100.0
        self.holding = False
        self.mishap: Mishap | None = None
        self.mishap_timer = self._next_mishap_delay() + 2.0
        self.schedule = self._build_schedule()

    # ------------------------------------------------------------ attention schedule
    def _build_schedule(self) -> list[tuple[float, str]]:
        """(start_time, phase) pairs covering the whole trial."""
        schedule, t = [(0.0, "distant")], self.rng.uniform(2.5, 4.0)
        cycle = ("near", "listening", "near", "distant")
        lengths = {"near": (2.0, 3.5), "listening": (1.8, 2.6), "distant": (2.5, 4.0)}
        i = 0
        while t < self.duration:
            phase = cycle[i % len(cycle)]
            schedule.append((t, phase))
            low, high = lengths[phase]
            t += self.rng.uniform(low, high) / (self.presence if phase != "distant" else 1.0)
            i += 1
        return schedule

    @property
    def attention(self) -> str:
        current = "distant"
        for start, phase in self.schedule:
            if start <= self.elapsed:
                current = phase
        return current

    @property
    def warning(self) -> bool:
        """True shortly before the creature starts listening."""
        for start, phase in self.schedule:
            if phase == "listening" and 0 < start - self.elapsed <= self.warn_time:
                return True
        return False

    @property
    def time_left(self) -> float:
        return max(0.0, self.duration - self.elapsed)

    def _next_mishap_delay(self) -> float:
        delay = self.rng.uniform(4.5, 7.5) / self.presence
        return delay / 1.35 if self.check.has("smoldering") else delay

    # ------------------------------------------------------------ rules
    def _noise(self, amount: float) -> None:
        self.noise = min(100.0, self.noise + amount * ATTENTION[self.attention] * self.presence)
        self.peak = max(self.peak, self.noise)

    def _tick(self, dt: float) -> None:
        if self.holding:
            self.breath = max(0.0, self.breath - self.drain * dt)
            if self.breath <= 0:
                self.holding = False
                self._noise(GASP_NOISE * self.loudness)
                self._flash("You can't hold it any longer — you gasp for air!", Tone.DAMAGE)
        else:
            self.breath = min(100.0, self.breath + BREATH_RECOVER * dt)
            self._noise(BREATH_NOISE * self.loudness * dt)
        self.noise = max(0.0, self.noise - self.decay * dt)

        if self.mishap:
            self.mishap.time_left = countdown(self.mishap.time_left, dt)
            if self.mishap.time_left <= 0:
                self._noise(self.mishap_loudness * self.loudness)
                self._flash(f"{self.mishap.text} — it makes a sound!", Tone.DAMAGE)
                self.mishap = None
        else:
            self.mishap_timer -= dt
            if self.mishap_timer <= 0 and self.time_left > 2.0:
                cough = self.check.has("smoldering") and self.rng.random() < 0.35
                text = self.rng.choice(COUGHS if cough else MISHAPS)
                self.mishap = Mishap(text, self.rng.choice(MISHAP_KEYS), self.mishap_window, self.mishap_window)
                self.mishap_timer = self._next_mishap_delay()

        if self.noise >= 100:
            self._finish(Outcome.FAILURE, 0.0, f"{self.creature} hears you. You've been discovered!")
        elif self.elapsed >= self.duration:
            score = 1.0 - self.peak / 100
            if self.peak < 70:
                self._finish(Outcome.SUCCESS, score, f"{self.creature} moves on without a second glance.")
            else:
                self._finish(Outcome.PARTIAL, score, f"{self.creature} lingers, suspicious, but finally moves on.")

    def _press(self, key: str) -> None:
        if key == "space":
            if self.holding:
                self.holding = False
            elif self.breath < 10:
                self._flash("You need air first!", Tone.WARNING)
            else:
                self.holding = True
            return
        if self.mishap and key == self.mishap.key:
            self._flash("You steady yourself without a sound.", Tone.PLAYER)
            self.mishap = None
            return
        self._noise(FIDGET_NOISE * self.loudness)
        self._flash("You shift — careful!", Tone.WARNING)
