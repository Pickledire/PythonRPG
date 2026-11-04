"""Travel between regions: on foot (next door only, and the road may bring trouble) or by carriage
(anywhere, for a fare, and almost always safe). Numbers are in ``config`` under "travel"."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from rpg import config
from rpg.core.catalog import ITEMS
from rpg.core.enemies import ENEMIES, Enemy
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.progression import grant_item
from rpg.core.regions import Region, RegionMap
from rpg.core.world import WorldState


class TravelMode(str, Enum):
    WALK = "walk"
    CARRIAGE = "carriage"


@dataclass(frozen=True)
class TravelOption:
    """One destination as the travel screen shows it."""
    region: Region
    roads: int
    fare: int

    @property
    def walkable(self) -> bool:
        return self.roads == 1

    @property
    def walk_hours(self) -> int:
        return config.WALK_HOURS_PER_ROAD * self.roads

    @property
    def carriage_hours(self) -> int:
        return config.CARRIAGE_HOURS_PER_ROAD * self.roads


@dataclass
class TravelReport:
    events: list[LogEvent] = field(default_factory=list)
    ambush: Enemy | None = None  # a fight on the road, for the UI to run before ``arrival`` (you arrive either way)
    arrival: list[LogEvent] = field(default_factory=list)
    first_visit: bool = False


class TravelError(Exception):
    pass


def options(regions: RegionMap, world: WorldState) -> list[TravelOption]:
    """Every other region, nearest first."""
    roads = regions.roads(world.region)
    found = [TravelOption(regions.regions[r], n, regions.fare(world.region, r))
             for r, n in roads.items() if r != world.region]
    return sorted(found, key=lambda o: (o.roads, o.region.min_level, o.region.name))


def travel(player: Player, world: WorldState, regions: RegionMap, destination: str, mode: TravelMode,
           rng: random.Random) -> TravelReport:
    option = next((o for o in options(regions, world) if o.region.region_id == destination), None)
    if option is None:
        raise TravelError(f"No road leads to '{destination}'.")
    report = TravelReport()
    region = option.region
    if mode == TravelMode.WALK:
        if not option.walkable:
            raise TravelError(f"{region.name} is too far to walk. Only the regions next door are in reach on foot.")
        world.advance(option.walk_hours)
        report.events.append(LogEvent(f"You set out on foot for {region.name}.", Tone.INFO))
        _road(player, region, rng, report)
    else:
        if player.gold < option.fare:
            raise TravelError(f"The carriage to {region.name} costs {option.fare} gold.")
        player.add_gold(-option.fare)
        world.advance(option.carriage_hours)
        report.events.append(LogEvent(f"You pay the driver {option.fare} gold and take the carriage to {region.name}.",
                                      Tone.GOLD))
        if rng.random() < config.CARRIAGE_AMBUSH_CHANCE:
            report.ambush = ENEMIES.create("bandit", rng, max(region.min_level, player.level))
            report.events.append(LogEvent("Highwaymen stop the carriage! The driver dives under his seat.",
                                          Tone.DAMAGE))
    world.region = region.region_id
    report.first_visit = region.region_id not in world.regions_visited
    world.regions_visited.add(region.region_id)
    report.arrival.append(LogEvent(f"You arrive at {region.place}.", Tone.STORY))
    if report.first_visit and region.blurb:
        report.arrival.append(LogEvent(region.blurb, Tone.STORY))
    if region.min_level > player.level + 2:
        report.arrival.append(LogEvent(f"The creatures here are dangerous (level {region.min_level} and up).",
                                      Tone.WARNING))
    return report


def _road(player: Player, region: Region, rng: random.Random, report: TravelReport) -> None:
    """What happens on a walk: about a quarter of the time trouble, sometimes luck, mostly nothing."""
    say = report.events.append
    roll = rng.random()
    if roll < config.WALK_TROUBLE_CHANCE:
        trouble = rng.random()
        if trouble < 0.55:
            if rng.random() < 0.5:
                report.ambush = ENEMIES.create("bandit", rng, max(region.min_level, player.level))
                say(LogEvent("Bandits step out onto the road ahead of you.", Tone.DAMAGE))
            else:
                report.ambush = region.roll_enemy(player.level, rng)
                say(LogEvent(f"Something has been following you: {report.ambush.name}!", Tone.DAMAGE))
        elif trouble < 0.85:
            lost = min(player.gold, rng.randint(10, 40))
            player.add_gold(-lost)
            say(LogEvent(f"Somewhere on the road a cutpurse lightened your load: {lost} gold gone.", Tone.WARNING))
        else:
            dropped = list(player.inventory.consumables())
            if dropped:
                stack = rng.choice(dropped)
                player.inventory.remove(stack.item.uid, 1)
                say(LogEvent(f"A strap on your pack gave way somewhere on the road. You lost a {stack.item.name}.",
                             Tone.WARNING))
            else:
                say(LogEvent("A strap on your pack gives way, but there was nothing in that pocket anyway.",
                             Tone.INFO))
    elif roll < config.WALK_TROUBLE_CHANCE + config.WALK_FORTUNE_CHANCE:
        luck = rng.random()
        if luck < 0.4:
            found = rng.randint(10, 35)
            player.add_gold(found)
            say(LogEvent(f"You find a purse half-buried in the snow by the road: +{found} gold.", Tone.GOLD))
        elif luck < 0.7:
            say(grant_item(player, ITEMS.create("health_potion")))
            say(LogEvent("A carter heading the other way shares a potion and the news.", Tone.LOOT))
        else:
            xp = rng.randint(10, 30)
            player.gain_xp(xp)
            say(LogEvent(f"An old soldier walks with you for an hour and shows you a trick or two. +{xp} XP.",
                         Tone.XP))
    else:
        say(LogEvent("The road is cold and quiet.", Tone.INFO))

