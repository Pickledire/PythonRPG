"""The map: regions, the roads between them, and what you meet hunting in each.

Regions live in ``story/regions.yaml``. Roads go both ways. How many roads apart two regions are decides
where you can walk (one road) and what a carriage costs (see ``fare``).
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from rpg import config
from rpg.core.enemies import ENEMIES, Enemy, UnknownEnemyError
from rpg.core.storydata import StoryDataError, load_yaml

START_REGION = "hearthlands"


@dataclass(frozen=True)
class Region:
    region_id: str
    name: str
    place: str
    blurb: str = ""
    min_level: int = 1
    neighbors: tuple[str, ...] = ()
    hunt: tuple[tuple[str, int], ...] = ()

    def roll_enemy(self, player_level: int, rng: random.Random) -> Enemy:
        """A creature of this region at about your level, never below the region's starting level."""
        ids, weights = zip(*self.hunt)
        level = max(self.min_level, player_level + rng.choice((-1, 0, 0, 0, 1)), 1)
        return ENEMIES.create(rng.choices(ids, weights=weights, k=1)[0], rng, level)


class RegionMap:
    def __init__(self, regions: dict[str, Region] | None = None, errors: list[str] | None = None) -> None:
        self.regions = regions or {}
        self.errors = errors or []

    def __contains__(self, region_id: str) -> bool:
        return region_id in self.regions

    def get(self, region_id: str) -> Region | None:
        return self.regions.get(region_id)

    def roads(self, start: str) -> dict[str, int]:
        """How many roads it takes to reach every region from ``start``."""
        distance = {start: 0}
        queue = deque([start])
        while queue:
            here = queue.popleft()
            for there in self.regions[here].neighbors if here in self.regions else ():
                if there not in distance:
                    distance[there] = distance[here] + 1
                    queue.append(there)
        return distance

    def fare(self, start: str, destination: str) -> int:
        """Carriage fare: a base, a charge per road, and hazard pay for dangerous places; rounded to 5 gold."""
        roads = self.roads(start).get(destination, 0)
        region = self.regions[destination]
        raw = (config.CARRIAGE_BASE_FARE + config.CARRIAGE_FARE_PER_ROAD * roads
               + config.CARRIAGE_HAZARD_PER_LEVEL * region.min_level)
        return int(5 * math.floor(raw / 5 + 0.5))  # halves round up

    @classmethod
    def load(cls, path: Path) -> "RegionMap":
        if not Path(path).is_file():
            return cls()
        try:
            raw = load_yaml(Path(path)) or {}
        except StoryDataError as exc:
            return cls(errors=[str(exc)])
        regions, errors = {}, []
        for region_id, data in (raw if isinstance(raw, dict) else {}).items():
            try:
                hunt = tuple((str(k), int(v)) for k, v in (data.get("hunt") or {}).items())
                regions[str(region_id)] = Region(str(region_id), str(data["name"]), str(data.get("place") or data["name"]),
                                                 str(data.get("blurb") or ""), int(data.get("min_level", 1)),
                                                 tuple(str(n) for n in data.get("neighbors") or ()), hunt)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                errors.append(f"regions.yaml: region '{region_id}': {exc}")
        made = cls(regions, errors)
        made.errors += made.problems()
        return made

    def problems(self) -> list[str]:
        problems = []
        for region in self.regions.values():
            if not region.hunt:
                problems.append(f"regions.yaml: {region.region_id} has nothing to hunt")
            for enemy_id, _ in region.hunt:
                try:
                    ENEMIES.resolve(enemy_id)
                except UnknownEnemyError:
                    problems.append(f"regions.yaml: {region.region_id} hunts unknown enemy '{enemy_id}'")
            for other in region.neighbors:
                if other not in self.regions:
                    problems.append(f"regions.yaml: {region.region_id} has a road to unknown region '{other}'")
                elif region.region_id not in self.regions[other].neighbors:
                    problems.append(f"regions.yaml: the road {region.region_id} -> {other} doesn't go back")
        if self.regions and START_REGION not in self.regions:
            problems.append(f"regions.yaml: the starting region '{START_REGION}' is missing")
        if self.regions and START_REGION in self.regions and len(self.roads(START_REGION)) != len(self.regions):
            unreachable = sorted(set(self.regions) - set(self.roads(START_REGION)))
            problems.append(f"regions.yaml: no road reaches {', '.join(unreachable)}")
        return problems
