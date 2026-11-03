"""Minigames: quick-time events, lockpicking, precision timing, memory, balance and stealth.

Build one from data with ``MinigameSpec`` (the same dict dialogue JSON uses)::

    spec = MinigameSpec.from_dict({"type": "stealth", "dc": 12, "title": "Hide!", "duration": 20})
    game = session.start_minigame(spec)    # skill check from attributes, race, gear and primed tonics
    ... UI ticks and feeds input until game.finished ...
    session.finish_minigame(game)          # spends broken lockpicks, returns log events

To add a minigame: subclass ``Minigame`` (see ``base.py``), give it a ``kind`` and ``skill``, add it to
``MINIGAMES`` below and give it a screen in ``rpg/ui/screens/minigames``.
"""

from __future__ import annotations

import inspect
import random
from dataclasses import dataclass, field
from typing import Any

from rpg.core.minigames.balance import BalanceBeam
from rpg.core.minigames.base import Flash, Minigame, MinigameKind, MinigameResult, Outcome
from rpg.core.minigames.lockpick import Lockpicking
from rpg.core.minigames.memory import MemorySequence
from rpg.core.minigames.qte import QuickTimeEvent
from rpg.core.minigames.stealth import Stealth
from rpg.core.minigames.timing import TimingStrike
from rpg.core.skills import Skill, SkillCheck

MINIGAMES: dict[MinigameKind, type[Minigame]] = {
    MinigameKind.QTE: QuickTimeEvent,
    MinigameKind.LOCKPICK: Lockpicking,
    MinigameKind.TIMING: TimingStrike,
    MinigameKind.MEMORY: MemorySequence,
    MinigameKind.BALANCE: BalanceBeam,
    MinigameKind.STEALTH: Stealth,
}
KIND_ALIASES = {"quicktime": "qte", "quick_time": "qte", "lock": "lockpick", "lockpicking": "lockpick",
                "precision": "timing", "sequence": "memory", "hide": "stealth", "silence": "stealth"}
# Spec keys that describe the trial rather than tune the game.
SPEC_KEYS = {"type", "dc", "title", "intro", "success", "partial", "failure", "retreat", "flag", "skill"}
# Tuning keys supplied by the session from the player, never by content.
CONTEXT_KEYS = {"picks", "vitality", "time_scale"}


class MinigameSpecError(ValueError):
    pass


def tunable_params(kind: MinigameKind) -> set[str]:
    signature = inspect.signature(MINIGAMES[kind].__init__)
    return {name for name, p in signature.parameters.items() if p.kind == p.KEYWORD_ONLY} - CONTEXT_KEYS


@dataclass
class MinigameSpec:
    kind: MinigameKind
    dc: int = 12
    title: str = ""
    intro: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    skill: Skill | None = None  # override the kind's default skill (e.g. a Precision-based QTE)

    @property
    def game_class(self) -> type[Minigame]:
        return MINIGAMES[self.kind]

    @property
    def skill_used(self) -> Skill:
        return self.skill or self.game_class.skill

    @property
    def display_title(self) -> str:
        return self.title or self.game_class.title

    @classmethod
    def from_dict(cls, data: dict) -> "MinigameSpec":
        raw_kind = str(data.get("type", "")).lower()
        try:
            kind = MinigameKind(KIND_ALIASES.get(raw_kind, raw_kind))
        except ValueError:
            raise MinigameSpecError(f"Unknown minigame type '{data.get('type')}'") from None
        allowed = tunable_params(kind)
        params = {k: v for k, v in data.items() if k in allowed}
        params.update({k: v for k, v in (data.get("params") or {}).items() if k in allowed})
        skill = Skill(str(data["skill"]).lower()) if data.get("skill") else None
        return cls(kind, int(data.get("dc", 12)), str(data.get("title", "")), str(data.get("intro", "")), params, skill)

    @staticmethod
    def problems(data: dict) -> list[str]:
        """Content lint for a minigame dict (used by the dialogue validator)."""
        try:
            spec = MinigameSpec.from_dict(data)
        except (MinigameSpecError, ValueError, TypeError) as exc:
            return [str(exc)]
        allowed = tunable_params(spec.kind) | SPEC_KEYS | {"params"}
        return [f"unknown {spec.kind.value} setting '{key}'" for key in data if key not in allowed]


def build_minigame(spec: MinigameSpec, check: SkillCheck, rng: random.Random | None = None,
                   **context: Any) -> Minigame:
    cls = spec.game_class
    accepted = set(inspect.signature(cls.__init__).parameters)
    extra = {k: v for k, v in context.items() if k in accepted}
    return cls(check, rng, **spec.params, **extra)


__all__ = [
    "BalanceBeam", "Flash", "Lockpicking", "MINIGAMES", "MemorySequence", "Minigame", "MinigameKind",
    "MinigameResult", "MinigameSpec", "MinigameSpecError", "Outcome", "QuickTimeEvent", "Stealth", "TimingStrike",
    "build_minigame", "tunable_params",
]
