"""Quick-time event: hit the key on screen before its window closes.

Used by boss telegraphs in combat and by story moments ("the bridge gives way!"). Reflexes widen each
window; ``keen_senses`` and ``quickened`` stretch it further.
"""

from __future__ import annotations

import random

from rpg.core.events import Tone
from rpg.core.minigames.base import Minigame, MinigameKind, Outcome, countdown, key_label, parse_key_pool
from rpg.core.skills import Skill, SkillCheck

READY_TIME = 1.0  # "get ready" before the first prompt
GAP_TIME = 0.3  # pause between prompts
MIN_WINDOW = 0.55


class QuickTimeEvent(Minigame):
    kind = MinigameKind.QTE
    skill = Skill.REFLEXES
    title = "Quick-Time Event"
    controls = "Press the key shown before the bar runs out. Wrong keys count as misses."

    def __init__(self, check: SkillCheck, rng: random.Random | None = None, *, prompts: int = 4,
                 window: float = 1.5, keys: str = "", success_score: float = 1.0, partial_score: float = 0.5,
                 heading: str = "", time_scale: float = 1.0) -> None:
        super().__init__(check, rng)
        self.heading = heading
        self.success_score, self.partial_score = success_score, partial_score
        pool = parse_key_pool(keys or "WASDQE")
        self.sequence: list[str] = []
        for _ in range(max(1, int(prompts))):
            options = [k for k in pool if not self.sequence or k != self.sequence[-1]] or pool
            self.sequence.append(self.rng.choice(options))
        stretch = check.ease()
        if check.has("keen_senses"):
            stretch *= 1.15
        if check.has("quickened"):
            stretch *= 1.2
        self.window = max(MIN_WINDOW, float(window) * stretch) * time_scale
        self.index = 0
        self.results: list[bool] = []
        self.ready = READY_TIME
        self.gap = 0.0
        self.time_left = self.window

    # ------------------------------------------------------------ state for the UI
    @property
    def current_key(self) -> str | None:
        if self.ready > 0 or self.gap > 0 or self.index >= len(self.sequence):
            return None
        return self.sequence[self.index]

    @property
    def current_label(self) -> str:
        key = self.current_key
        return key_label(key) if key else ""

    @property
    def time_ratio(self) -> float:
        return self.time_left / self.window if self.window else 0.0

    # ------------------------------------------------------------ rules
    def _tick(self, dt: float) -> None:
        if self.ready > 0:
            self.ready = countdown(self.ready, dt)
            return
        if self.gap > 0:
            self.gap = countdown(self.gap, dt)
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self._resolve(False, "Too slow!")

    def _press(self, key: str) -> None:
        expected = self.current_key
        if expected is None:
            return
        if key == expected:
            self._resolve(True, "Hit!")
        else:
            self._resolve(False, f"Wrong key ({key_label(key)})!")

    def _resolve(self, hit: bool, text: str) -> None:
        self.results.append(hit)
        self._flash(text, Tone.PLAYER if hit else Tone.DAMAGE)
        self.index += 1
        if self.index >= len(self.sequence):
            self._conclude()
        else:
            self.gap = GAP_TIME
            self.time_left = self.window

    def _conclude(self) -> None:
        hits = sum(self.results)
        score = hits / len(self.sequence)
        if score >= self.success_score:
            self._finish(Outcome.SUCCESS, score, f"Flawless — {hits}/{len(self.sequence)} prompts.")
        elif score >= self.partial_score:
            self._finish(Outcome.PARTIAL, score, f"Close — {hits}/{len(self.sequence)} prompts.")
        else:
            self._finish(Outcome.FAILURE, score, f"Too slow — {hits}/{len(self.sequence)} prompts.")
