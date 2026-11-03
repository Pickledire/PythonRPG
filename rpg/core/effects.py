"""Status effects: damage over time, buffs, debuffs and crowd control.

Timing rules (applied by ``rpg.core.combat``):
    * Start of the afflicted combatant's turn: damage-over-time and regeneration tick,
      each tick spends one turn of that effect.
    * If FROZEN at the start of their turn, the turn is skipped and one frozen turn is spent.
    * End of the combatant's own turn: SHIELD, BLIND, HASTE, WEAKEN, VULNERABLE and SILENCE count down.
    * HASTE: one extra action on each of the hasted combatant's turns.
    * WEAKEN: the afflicted deals ``potency`` less damage. VULNERABLE: takes ``potency`` more.
    * SILENCE: no spellcasting.
Re-applying an effect refreshes it to the longer duration and the stronger potency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class EffectKind(str, Enum):
    POISON = "poison"
    BURN = "burn"
    BLEED = "bleed"
    REGEN = "regen"
    SHIELD = "shield"
    BLIND = "blind"
    FROZEN = "frozen"
    HASTE = "haste"
    WEAKEN = "weaken"
    VULNERABLE = "vulnerable"
    SILENCE = "silence"


@dataclass(frozen=True)
class EffectInfo:
    label: str
    short: str
    harmful: bool
    description: str


EFFECT_INFO: dict[EffectKind, EffectInfo] = {
    EffectKind.POISON: EffectInfo("Poison", "PSN", True, "Takes {potency} damage at the start of each turn."),
    EffectKind.BURN: EffectInfo("Burn", "BRN", True, "Takes {potency} fire damage at the start of each turn."),
    EffectKind.BLEED: EffectInfo("Bleed", "BLD", True, "Loses {potency} HP at the start of each turn."),
    EffectKind.REGEN: EffectInfo("Regen", "RGN", False, "Recovers {potency} HP at the start of each turn."),
    EffectKind.SHIELD: EffectInfo("Ward", "WRD", False, "Incoming damage reduced by {pct}%."),
    EffectKind.BLIND: EffectInfo("Blind", "BLN", True, "Accuracy reduced by {pct}%."),
    EffectKind.FROZEN: EffectInfo("Frozen", "FRZ", True, "Cannot act."),
    EffectKind.HASTE: EffectInfo("Haste", "HST", False, "Acts twice each turn."),
    EffectKind.WEAKEN: EffectInfo("Weakened", "WKN", True, "Deals {pct}% less damage."),
    EffectKind.VULNERABLE: EffectInfo("Exposed", "EXP", True, "Takes {pct}% more damage."),
    EffectKind.SILENCE: EffectInfo("Silenced", "SIL", True, "Cannot cast spells."),
}

DAMAGE_OVER_TIME = (EffectKind.POISON, EffectKind.BURN, EffectKind.BLEED)
END_OF_TURN_DECAY = (EffectKind.SHIELD, EffectKind.BLIND, EffectKind.HASTE, EffectKind.WEAKEN, EffectKind.VULNERABLE,
                     EffectKind.SILENCE)
CLEANSABLE = (EffectKind.POISON, EffectKind.BURN, EffectKind.BLEED, EffectKind.BLIND, EffectKind.FROZEN,
              EffectKind.WEAKEN, EffectKind.VULNERABLE, EffectKind.SILENCE)
PERCENT_EFFECTS = (EffectKind.SHIELD, EffectKind.BLIND, EffectKind.WEAKEN, EffectKind.VULNERABLE)
DURATION_ONLY = (EffectKind.FROZEN, EffectKind.HASTE, EffectKind.SILENCE)


@dataclass
class StatusEffect:
    kind: EffectKind
    turns: int
    potency: float = 0.0  # damage/heal per tick, or a 0-1 fraction for shield/blind
    source: str = ""

    @property
    def info(self) -> EffectInfo:
        return EFFECT_INFO[self.kind]

    def describe(self) -> str:
        pct = int(round(self.potency * 100))
        text = self.info.description.format(potency=int(self.potency), pct=pct)
        return f"{self.info.label} ({self.turns} turn{'s' if self.turns != 1 else ''}): {text}"

    def badge(self) -> str:
        if self.kind in DAMAGE_OVER_TIME or self.kind == EffectKind.REGEN:
            return f"{self.info.label} {int(self.potency)}×{self.turns}"
        if self.kind in PERCENT_EFFECTS:
            return f"{self.info.label} {int(round(self.potency * 100))}% {self.turns}t"
        return f"{self.info.label} {self.turns}t"

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "turns": self.turns, "potency": self.potency, "source": self.source}

    @classmethod
    def from_dict(cls, data: dict) -> "StatusEffect":
        return cls(EffectKind(data["kind"]), int(data["turns"]), float(data.get("potency", 0)), data.get("source", ""))


@dataclass(frozen=True)
class EffectSpec:
    """A recipe for applying an effect, optionally with a proc chance (used by weapons, spells, enemies)."""

    kind: EffectKind
    potency: float
    turns: int
    chance: float = 1.0

    def roll(self, rng: random.Random) -> bool:
        return self.chance >= 1.0 or rng.random() < self.chance

    def create(self, source: str = "") -> StatusEffect:
        return StatusEffect(self.kind, self.turns, self.potency, source)

    def describe(self) -> str:
        info = EFFECT_INFO[self.kind]
        chance = "" if self.chance >= 1.0 else f"{int(self.chance * 100)}% chance: "
        if self.kind in PERCENT_EFFECTS:
            return f"{chance}{info.label} {int(self.potency * 100)}% for {self.turns} turns"
        if self.kind in DURATION_ONLY:
            return f"{chance}{info.label} for {self.turns} turn{'s' if self.turns != 1 else ''}"
        return f"{chance}{info.label} {int(self.potency)}/turn for {self.turns} turns"

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "potency": self.potency, "turns": self.turns, "chance": self.chance}

    @classmethod
    def from_dict(cls, data: dict | None) -> "EffectSpec | None":
        if not data:
            return None
        return cls(EffectKind(data["kind"]), float(data["potency"]), int(data["turns"]), float(data.get("chance", 1.0)))
