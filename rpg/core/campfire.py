"""Resting at the campfire: full recovery, time passes, and the night may bring company."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

from rpg import config
from rpg.core.catalog import ITEMS
from rpg.core.enemies import ENEMIES, Enemy
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.progression import grant_item
from rpg.core.world import WorldState


@dataclass
class CampfireReport:
    events: list[LogEvent] = field(default_factory=list)
    ambush: Enemy | None = None
    dialogue_category: str | None = None  # "good" or "bad" random encounter
    levels_gained: int = 0


def rest(player: Player, world: WorldState, rng: random.Random,
         ambusher: Callable[[], Enemy] | None = None) -> CampfireReport:
    """``ambusher`` makes the creature for a night ambush (the region's creatures); default: any at your level."""
    report = CampfireReport()
    player.full_restore()
    player.cleanse()
    world.advance(config.REST_HOURS)
    report.events.append(LogEvent("You feel refreshed. Health and mana fully restored.", Tone.HEAL))

    roll = rng.random()
    if roll < 0.35:  # bad night
        bad = rng.random()
        if bad < 0.40:
            report.ambush = ambusher() if ambusher else ENEMIES.random_for_level(player.level, rng)
            report.events.append(LogEvent(f"You are ambushed in the night by {report.ambush.name}!", Tone.DAMAGE))
        elif bad < 0.70:
            report.dialogue_category = "bad"
            report.events.append(LogEvent("A shadow steps from the treeline...", Tone.WARNING))
        elif bad < 0.85:
            lost = min(player.gold, rng.randint(10, 40))
            player.add_gold(-lost)
            report.events.append(LogEvent(f"Thieves slip through the dark — you lose {lost} gold.", Tone.WARNING))
        else:
            drain = int(player.max_mana * 0.25)
            player.mana = max(0, player.mana - drain)
            report.events.append(LogEvent(f"A chilling presence saps {drain} mana.", Tone.MANA))
    elif roll < 0.70:  # good night
        good = rng.random()
        if good < 0.35:
            found = rng.randint(20, 60)
            player.add_gold(found)
            report.events.append(LogEvent(f"You find a hidden pouch: +{found} gold.", Tone.GOLD))
        elif good < 0.70:
            report.dialogue_category = "good"
            report.events.append(LogEvent("A friendly traveler approaches your fire...", Tone.INFO))
        elif good < 0.85:
            xp = rng.randint(10, 30)
            report.levels_gained = player.gain_xp(xp)
            report.events.append(LogEvent(f"A restful insight grants you {xp} XP.", Tone.XP))
        else:
            report.events.append(grant_item(player, ITEMS.create("health_potion")))
            report.events.append(LogEvent("You discover a forgotten potion near the embers.", Tone.LOOT))
    else:
        report.events.append(LogEvent("The night passes quietly.", Tone.INFO))
    return report
