"""World state shared by quests, shops and encounters: time of day and story flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rpg import config

TIME_OF_DAY = [
    (4, "Night"), (7, "Dawn"), (11, "Morning"), (16, "Afternoon"), (19, "Dusk"), (23, "Evening"),
]


def time_of_day(bell: int) -> str:
    for last_bell, label in TIME_OF_DAY:
        if bell <= last_bell:
            return label
    return "Night"


@dataclass
class WorldState:
    bell: int = config.START_BELL  # 0-23
    flags: dict[str, Any] = field(default_factory=dict)
    shop_unlocks: set[str] = field(default_factory=set)
    bosses_defeated: set[str] = field(default_factory=set)
    ghost_horror_seen: bool = False

    def advance(self, hours: int = 1) -> None:
        self.bell = (self.bell + int(hours)) % 24

    def set_time(self, bell: int) -> None:
        self.bell = int(bell) % 24

    @property
    def time_label(self) -> str:
        return f"Bell {self.bell} · {time_of_day(self.bell)}"

    def to_dict(self) -> dict:
        return {
            "bell": self.bell,
            "flags": self.flags,
            "shop_unlocks": sorted(self.shop_unlocks),
            "bosses_defeated": sorted(self.bosses_defeated),
            "ghost_horror_seen": self.ghost_horror_seen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        return cls(
            bell=int(data.get("bell", config.START_BELL)) % 24,
            flags=dict(data.get("flags", {})),
            shop_unlocks=set(data.get("shop_unlocks", [])),
            bosses_defeated=set(data.get("bosses_defeated", [])),
            ghost_horror_seen=bool(data.get("ghost_horror_seen", False)),
        )
