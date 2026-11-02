"""Character attributes and equipment requirements."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class Attribute(str, Enum):
    STRENGTH = "strength"
    AGILITY = "agility"
    INTELLIGENCE = "intelligence"

    @property
    def short(self) -> str:
        return {"strength": "STR", "agility": "AGI", "intelligence": "INT"}[self.value]

    @property
    def label(self) -> str:
        return self.value.capitalize()


@dataclass
class Attributes:
    strength: int = 8
    agility: int = 8
    intelligence: int = 8

    def get(self, attr: Attribute | str) -> int:
        return int(getattr(self, Attribute(attr).value))

    def set(self, attr: Attribute | str, value: int) -> None:
        setattr(self, Attribute(attr).value, int(value))

    def add(self, attr: Attribute | str, delta: int) -> int:
        new = max(0, self.get(attr) + int(delta))
        self.set(attr, new)
        return new

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Attributes":
        return cls(
            strength=int(data.get("strength", 8)),
            agility=int(data.get("agility", 8)),
            intelligence=int(data.get("intelligence", 8)),
        )


@dataclass(frozen=True)
class Requirement:
    attribute: Attribute
    minimum: int

    def met_by(self, attributes: Attributes) -> bool:
        return attributes.get(self.attribute) >= self.minimum

    def describe(self) -> str:
        return f"{self.attribute.label} {self.minimum}+"

    def to_dict(self) -> dict:
        return {"attribute": self.attribute.value, "minimum": self.minimum}

    @classmethod
    def from_dict(cls, data: dict | None) -> "Requirement | None":
        if not data:
            return None
        return cls(Attribute(data["attribute"]), int(data["minimum"]))
