"""Memory sequence: watch the runes light up, then click them back in order. Mouse only.

Rounds grow one rune longer each time. A wrong rune costs a *glance* (a retry of that round with a new
sequence); run out and the trial fails. Focus (Intelligence and Wisdom) keeps runes lit longer and earns
an extra glance; ``eidetic`` lingers longer still and adds another glance.
"""

from __future__ import annotations

import random

from rpg.core.events import Tone
from rpg.core.minigames.base import Minigame, MinigameKind, Outcome, countdown
from rpg.core.skills import Skill, SkillCheck

RUNES = 9  # a 3×3 grid
SHOW_TIME = 0.65
GAP_TIME = 0.22
FEEDBACK_TIME = 0.9
LEAD_IN = 0.8


class MemorySequence(Minigame):
    kind = MinigameKind.MEMORY
    skill = Skill.FOCUS
    title = "Memory"
    controls = "Watch the sequence, then click the runes in the same order. Mouse only."

    def __init__(self, check: SkillCheck, rng: random.Random | None = None, *, rounds: int = 3,
                 start_length: int | None = None, time_scale: float = 1.0) -> None:
        super().__init__(check, rng)
        self.rounds = max(1, int(rounds))
        self.start_length = max(2, int(start_length if start_length is not None else check.dc // 4))
        linger = 1.3 if check.has("eidetic") else 1.0
        self.show_time = max(0.3, SHOW_TIME * check.ease() * linger) * time_scale
        self.glances = 1 + (1 if check.edge >= 3 else 0) + (1 if check.has("eidetic") else 0)
        self.max_glances = self.glances
        self.round = 0
        self.sequence: list[int] = []
        self.entered: list[int] = []
        self.state = "lead_in"
        self.timer = LEAD_IN
        self.show_index = -1  # index into sequence currently lit while showing
        self.lit: int | None = None
        self.last_click: tuple[int, bool] | None = None  # (rune, correct) for the click flash
        self._new_sequence()

    @property
    def length(self) -> int:
        return self.start_length + self.round

    def _new_sequence(self) -> None:
        sequence: list[int] = []
        for _ in range(self.length):
            options = [r for r in range(RUNES) if not sequence or r != sequence[-1]]
            sequence.append(self.rng.choice(options))
        self.sequence = sequence
        self.entered = []

    # ------------------------------------------------------------ rules
    def _tick(self, dt: float) -> None:
        if self.state == "input":
            return
        self.timer = countdown(self.timer, dt)
        if self.timer > 0:
            return
        if self.state in ("lead_in", "gap"):
            self.show_index += 1
            if self.show_index >= len(self.sequence):
                self.state, self.lit = "input", None
                self._flash("Your turn.", Tone.INFO)
                return
            self.state, self.lit, self.timer = "showing", self.sequence[self.show_index], self.show_time
        elif self.state == "showing":
            self.state, self.lit, self.timer = "gap", None, GAP_TIME
        elif self.state == "feedback":
            self._replay()

    def _replay(self) -> None:
        self.state, self.timer, self.show_index, self.lit = "lead_in", LEAD_IN, -1, None
        self.last_click = None

    def _click(self, index: int) -> None:
        if self.state != "input" or not 0 <= index < RUNES:
            return
        expected = self.sequence[len(self.entered)]
        correct = index == expected
        self.last_click = (index, correct)
        if not correct:
            self.glances -= 1
            if self.glances <= 0:
                self._finish(Outcome.FAILURE, self.round / self.rounds, "The runes go dark. The pattern is lost.")
                return
            self._flash(f"Wrong rune! {self.glances} glance(s) left — watch again.", Tone.DAMAGE)
            self._new_sequence()
            self.state, self.timer = "feedback", FEEDBACK_TIME
            return
        self.entered.append(index)
        if len(self.entered) < len(self.sequence):
            return
        self.round += 1
        if self.round >= self.rounds:
            if self.glances == self.max_glances:
                self._finish(Outcome.SUCCESS, 1.0, "Every rune blazes. The pattern is complete.")
            else:
                self._finish(Outcome.PARTIAL, 0.75, "The pattern holds, though not on your first try.")
            return
        self._flash(f"Sequence {self.round} of {self.rounds} complete!", Tone.PLAYER)
        self._new_sequence()
        self.state, self.timer = "feedback", FEEDBACK_TIME
