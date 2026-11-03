"""Skills: what the seven attributes, your race and your gear add up to outside of combat.

Minigames (stealth, lockpicking, quick-time events, ...) never read attributes directly. They ask for a
``SkillCheck``: one number (the *rating*) built from several sources, compared with a difficulty (*dc*):

    rating = weighted attributes            e.g. Stealth = 50% Agility + 30% Dexterity + 20% Wisdom
           + race bonus                     Halflings are hard to spot (+5 Stealth)
           + gear bonuses                   equipped weapon/armor/spell, carried tools and charms
           + a primed boost                 a Muffling Salve rubbed on your boots before you hide

Traits change *how* a minigame plays rather than the rating (a Revenant barely needs to breathe while
hiding, a Gnome's lockpicks snap less often). Races, items and future sources (enchanted clothing,
companions, blessings) all feed the same two channels, so new content only has to declare
``skill_bonuses`` and ``traits``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from rpg import config
from rpg.core.attributes import Attribute

if TYPE_CHECKING:
    from rpg.core.entities import Player


class Skill(str, Enum):
    STEALTH = "stealth"
    LOCKPICKING = "lockpicking"
    REFLEXES = "reflexes"
    FOCUS = "focus"
    BALANCE = "balance"
    PRECISION = "precision"

    @property
    def label(self) -> str:
        return SKILL_INFO[self].label

    @property
    def description(self) -> str:
        return SKILL_INFO[self].description


@dataclass(frozen=True)
class SkillInfo:
    label: str
    description: str
    weights: dict[Attribute, float]


A = Attribute
SKILL_INFO: dict[Skill, SkillInfo] = {
    Skill.STEALTH: SkillInfo("Stealth", "Staying unheard and unseen while hiding.",
                             {A.AGILITY: 0.5, A.DEXTERITY: 0.3, A.WISDOM: 0.2}),
    Skill.LOCKPICKING: SkillInfo("Lockpicking", "Finding the sweet spot of a pin before the pick snaps.",
                                 {A.DEXTERITY: 0.6, A.INTELLIGENCE: 0.3, A.WISDOM: 0.1}),
    Skill.REFLEXES: SkillInfo("Reflexes", "Reacting in time when something comes at you.",
                              {A.AGILITY: 0.4, A.DEXTERITY: 0.4, A.WISDOM: 0.2}),
    Skill.FOCUS: SkillInfo("Focus", "Memorising patterns, runes and sequences.",
                           {A.INTELLIGENCE: 0.6, A.WISDOM: 0.4}),
    Skill.BALANCE: SkillInfo("Balance", "Keeping your footing on beams, ledges and decks.",
                             {A.AGILITY: 0.5, A.VITALITY: 0.3, A.DEXTERITY: 0.2}),
    Skill.PRECISION: SkillInfo("Precision", "Striking or shooting at exactly the right moment.",
                               {A.DEXTERITY: 0.6, A.STRENGTH: 0.2, A.WISDOM: 0.2}),
}


# ------------------------------------------------------------------ traits
@dataclass(frozen=True)
class TraitInfo:
    label: str
    description: str


TRAITS: dict[str, TraitInfo] = {
    "small_frame": TraitInfo("Small frame", "Fits into tighter hiding spots: makes less noise while hiding."),
    "heavy_step": TraitInfo("Heavy step", "Slips and stumbles while hiding are louder."),
    "breathless": TraitInfo("Breathless", "Barely needs air: holding your breath drains it far more slowly."),
    "smoldering": TraitInfo("Smoldering", "Embers in your lungs: an occasional smoky cough while hiding."),
    "keen_senses": TraitInfo("Keen senses", "Hear danger coming: extra time on quick-time prompts and earlier "
                             "warnings while hiding."),
    "tinker": TraitInfo("Tinker", "Gentle with mechanisms: lockpicks take less strain."),
    "stoneborn": TraitInfo("Stoneborn", "Low and steady: less sway on beams and ledges."),
    "eidetic": TraitInfo("Eidetic memory", "Sequences linger: runes stay lit longer in memory trials."),
    "steady_hands": TraitInfo("Steady hands", "The needle slows in precision trials."),
    "quickened": TraitInfo("Quickened", "Time seems to slow when danger strikes: longer quick-time windows."),
}


# ------------------------------------------------------------------ the check
@dataclass(frozen=True)
class SkillSource:
    label: str
    amount: int


@dataclass
class SkillCheck:
    """A skill rating against a difficulty, with every source that went into it (for the briefing UI)."""

    skill: Skill
    dc: int
    base: int
    sources: list[SkillSource] = field(default_factory=list)
    traits: frozenset[str] = frozenset()

    @property
    def rating(self) -> int:
        return max(0, self.base + sum(s.amount for s in self.sources))

    @property
    def edge(self) -> int:
        """How far the rating is above (+) or below (-) the difficulty, capped at ±10."""
        return max(-10, min(10, self.rating - self.dc))

    def ease(self, per_point: float = config.SKILL_EASE_PER_POINT, low: float = 0.45, high: float = 1.8) -> float:
        """Multiplier > 1 when the check favors you. Minigames scale windows, speeds and drift with it."""
        return max(low, min(high, 1.0 + self.edge * per_point))

    def has(self, trait: str) -> bool:
        return trait in self.traits

    @property
    def odds_label(self) -> str:
        edge = self.edge
        if edge >= 6:
            return "Trivial"
        if edge >= 3:
            return "Favorable"
        if edge >= 0:
            return "Even"
        if edge >= -3:
            return "Risky"
        return "Dire"


def base_rating(player: "Player", skill: Skill) -> int:
    weights = SKILL_INFO[skill].weights
    return int(round(sum(player.attributes.get(attr) * w for attr, w in weights.items())))


def skill_sources(player: "Player", skill: Skill) -> list[SkillSource]:
    """Race, gear and primed boosts that modify ``skill`` (zero entries are left out)."""
    sources: list[SkillSource] = []
    race_bonus = config.RACE_SKILLS.get(player.race, {}).get(skill.value, 0)
    if race_bonus:
        sources.append(SkillSource(player.race, race_bonus))
    for item in player.skill_items():
        amount = item.skill_bonuses.get(skill.value, 0)
        if amount:
            sources.append(SkillSource(item.name, amount))
    primed = player.skill_primes.get(skill.value, 0)
    if primed:
        sources.append(SkillSource("Primed", primed))
    return sources


def player_traits(player: "Player") -> frozenset[str]:
    traits = set(config.RACE_TRAITS.get(player.race, ()))
    for item in player.skill_items():
        traits.update(item.traits)
    return frozenset(traits)


def skill_check(player: "Player", skill: Skill | str, dc: int) -> SkillCheck:
    skill = Skill(skill)
    return SkillCheck(skill, int(dc), base_rating(player, skill), skill_sources(player, skill), player_traits(player))


def skill_rating(player: "Player", skill: Skill | str) -> int:
    return skill_check(player, skill, 0).rating
