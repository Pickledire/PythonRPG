"""Character attributes and equipment requirements.

What each attribute does (formulas live in ``rpg.core.formulas``):
    Strength      melee damage, heavy weapons and armor
    Dexterity     accuracy, critical hits, bows and finesse weapons
    Agility       dodging attacks, escaping fights, light armor
    Vitality      maximum HP, resistance to poison/burn/bleed
    Intelligence  spell damage, staves
    Wisdom        maximum mana, healing power, resisting harmful status effects
    Charisma      shop prices, persuasion checks in dialogue
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import Enum


class Attribute(str, Enum):
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    AGILITY = "agility"
    VITALITY = "vitality"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"

    @property
    def short(self) -> str:
        return self.value[:3].upper()

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @property
    def description(self) -> str:
        return ATTRIBUTE_DESCRIPTIONS[self]


ATTRIBUTE_DESCRIPTIONS = {
    Attribute.STRENGTH: "melee damage, heavy weapons and armor",
    Attribute.DEXTERITY: "accuracy, critical hits, bows and finesse weapons",
    Attribute.AGILITY: "dodging, escaping fights, light armor",
    Attribute.VITALITY: "maximum HP, resisting poison, burn and bleed",
    Attribute.INTELLIGENCE: "spell damage and staves",
    Attribute.WISDOM: "maximum mana, healing, resisting harmful effects",
    Attribute.CHARISMA: "shop prices and persuasion",
}


@dataclass
class Attributes:
    strength: int = 8
    dexterity: int = 8
    agility: int = 8
    vitality: int = 8
    intelligence: int = 8
    wisdom: int = 8
    charisma: int = 8

    def get(self, attr: Attribute | str) -> int:
        return int(getattr(self, Attribute(attr).value))

    def set(self, attr: Attribute | str, value: int) -> None:
        setattr(self, Attribute(attr).value, max(0, int(value)))

    def add(self, attr: Attribute | str, delta: int) -> int:
        self.set(attr, self.get(attr) + int(delta))
        return self.get(attr)

    def items(self) -> list[tuple[Attribute, int]]:
        return [(attr, self.get(attr)) for attr in Attribute]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict, defaults: dict | None = None) -> "Attributes":
        """Missing attributes fall back to ``defaults`` (e.g. race stats) and then to 8."""
        defaults = defaults or {}
        return cls(**{a.value: int(data.get(a.value, defaults.get(a.value, 8))) for a in Attribute})


@dataclass(frozen=True)
class Requirement:
    attribute: Attribute
    minimum: int

    def met_by(self, attributes: Attributes) -> bool:
        return attributes.get(self.attribute) >= self.minimum

    def describe(self) -> str:
        return f"{self.attribute.label} {self.minimum}+"

    def short(self) -> str:
        return f"{self.attribute.short} {self.minimum}"

    def to_dict(self) -> dict:
        return {"attribute": self.attribute.value, "minimum": self.minimum}

    @classmethod
    def from_dict(cls, data: dict) -> "Requirement":
        return cls(Attribute(data["attribute"]), int(data["minimum"]))


Requirements = tuple[Requirement, ...]


def req(**minimums: int) -> Requirements:
    """Build requirements: ``req(strength=14, dexterity=13)``."""
    return tuple(Requirement(Attribute(name), int(value)) for name, value in minimums.items())


def unmet(requirements: Iterable[Requirement], attributes: Attributes) -> list[Requirement]:
    return [r for r in requirements if not r.met_by(attributes)]


def describe_requirements(requirements: Iterable[Requirement]) -> str:
    return ", ".join(r.describe() for r in requirements)
