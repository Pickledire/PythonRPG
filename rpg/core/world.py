"""World state shared by quests, shops and encounters: time of day and the story's memory.

The story's memory (the "Ledger"):

- ``flags``: named facts (``saw_crowned_rat: true``, ``oswin: persuaded``).
- ``vars``: numbers (reputation, counters): ``rep.brannoc: 3``. Missing numbers read as 0.
- ``visits``: how many times each scene has been entered.
- ``claimed``: which scenes and choices have already paid out their rewards (rewards pay once).
- ``quests``: each started quest's current stage (``done`` and ``failed`` are final).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rpg import config

TIME_OF_DAY = [
    (4, "Night"), (7, "Dawn"), (11, "Morning"), (16, "Afternoon"), (19, "Dusk"), (23, "Evening"),
]


def weekday(day: int) -> str:
    """Day 1 is a Kindlemorn."""
    return config.WEEKDAYS[(day - 1) % len(config.WEEKDAYS)]


def time_of_day(bell: int) -> str:
    for last_bell, label in TIME_OF_DAY:
        if bell <= last_bell:
            return label
    return "Night"


@dataclass
class WorldState:
    bell: int = config.START_BELL  # the hour, 0-23
    day: int = 1  # days since the story began (day 1 is a Kindlemorn)
    region: str = "hearthlands"
    regions_visited: set[str] = field(default_factory=lambda: {"hearthlands"})
    flags: dict[str, Any] = field(default_factory=dict)
    shop_unlocks: set[str] = field(default_factory=set)
    bosses_defeated: set[str] = field(default_factory=set)
    ghost_horror_seen: bool = False
    vars: dict[str, float] = field(default_factory=dict)
    visits: dict[str, int] = field(default_factory=dict)
    claimed: set[str] = field(default_factory=set)
    quests: dict[str, str] = field(default_factory=dict)
    bestiary: dict[str, dict[str, int]] = field(default_factory=dict)  # creature id -> {"seen": n, "defeated": n}

    def var(self, key: str) -> float:
        return self.vars.get(key, 0)

    def advance(self, hours: int = 1) -> None:
        total = self.bell + int(hours)
        self.day += total // 24
        self.bell = total % 24

    def set_time(self, bell: int) -> None:
        """Move forward to the next time it is ``bell`` o'clock (tomorrow, if that hour has passed)."""
        bell = int(bell) % 24
        if bell <= self.bell:
            self.day += 1
        self.bell = bell

    @property
    def weekday(self) -> str:
        return weekday(self.day)

    @property
    def time_label(self) -> str:
        """``Stonesday, Afternoon``."""
        return f"{self.weekday}, {time_of_day(self.bell)}"

    @property
    def date_label(self) -> str:
        """``Day 3: Stonesday, Afternoon``."""
        return f"Day {self.day}: {self.time_label}"

    def to_dict(self) -> dict:
        return {
            "bell": self.bell,
            "day": self.day,
            "region": self.region,
            "regions_visited": sorted(self.regions_visited),
            "flags": self.flags,
            "shop_unlocks": sorted(self.shop_unlocks),
            "bosses_defeated": sorted(self.bosses_defeated),
            "ghost_horror_seen": self.ghost_horror_seen,
            "vars": self.vars,
            "visits": self.visits,
            "claimed": sorted(self.claimed),
            "quests": self.quests,
            "bestiary": self.bestiary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        return cls(
            bell=int(data.get("bell", config.START_BELL)) % 24,
            day=max(1, int(data.get("day", 1))),
            region=str(data.get("region") or "hearthlands"),
            regions_visited=set(data.get("regions_visited") or ["hearthlands"]) | {str(data.get("region") or "hearthlands")},
            flags=dict(data.get("flags", {})),
            shop_unlocks=set(data.get("shop_unlocks", [])),
            bosses_defeated=set(data.get("bosses_defeated", [])),
            ghost_horror_seen=bool(data.get("ghost_horror_seen", False)),
            vars={str(k): v for k, v in (data.get("vars") or {}).items() if isinstance(v, (int, float))},
            visits={str(k): int(v) for k, v in (data.get("visits") or {}).items()},
            claimed=set(data.get("claimed") or []),
            quests={str(k): str(v) for k, v in (data.get("quests") or {}).items()},
            bestiary={str(k): {"seen": int(v.get("seen", 0)), "defeated": int(v.get("defeated", 0))}
                      for k, v in (data.get("bestiary") or {}).items() if isinstance(v, dict)},
        )
