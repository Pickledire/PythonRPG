"""Victory rewards: XP, gold, loot, boss trophies and guaranteed drops."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from rpg import config
from rpg.core.catalog import ITEMS, LOOT_TABLE
from rpg.core.enemies import Enemy
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.inventory import InventoryFullError
from rpg.core.items import Item


@dataclass
class VictoryReport:
    enemy_name: str
    xp: int
    gold: int
    loot: list[tuple[Item, int]] = field(default_factory=list)
    trophy_choices: list[Item] = field(default_factory=list)
    levels_gained: int = 0
    events: list[LogEvent] = field(default_factory=list)


def xp_reward(enemy: Enemy, rng: random.Random) -> int:
    xp = rng.randint(config.MIN_XP_REWARD, config.MAX_XP_REWARD) * (1 + enemy.attributes.strength / 20)
    return int(xp * (config.BOSS_REWARD_MULTIPLIER if enemy.is_boss else 1))


def gold_reward(enemy: Enemy, rng: random.Random) -> int:
    gold = rng.randint(config.MIN_GOLD_REWARD, config.MAX_GOLD_REWARD) * (1 + enemy.attributes.strength / 30)
    return int(gold * (config.BOSS_REWARD_MULTIPLIER if enemy.is_boss else 1))


def roll_loot(enemy: Enemy, rng: random.Random) -> list[tuple[Item, int]]:
    drops: list[tuple[Item, int]] = [(ITEMS.create(tid), qty) for tid, qty in enemy.template.guaranteed_drops]
    if enemy.is_boss or rng.random() < config.LOOT_CHANCE:
        category = rng.choice(list(LOOT_TABLE))
        drops.append((ITEMS.create(rng.choice(LOOT_TABLE[category])), 1))
    return drops


def roll_victory(enemy: Enemy, rng: random.Random, multiplier: float = 1.0) -> VictoryReport:
    return VictoryReport(
        enemy_name=enemy.name,
        xp=int(xp_reward(enemy, rng) * multiplier),
        gold=int(gold_reward(enemy, rng) * multiplier),
        loot=roll_loot(enemy, rng),
        trophy_choices=[ITEMS.create(tid) for tid in enemy.template.reward_choices],
    )


def grant_item(player: Player, item: Item, quantity: int = 1) -> LogEvent:
    try:
        player.inventory.add(item, quantity)
    except InventoryFullError:
        return LogEvent(f"Your pack is full — you leave the {item.name} behind.", Tone.WARNING)
    suffix = f" ×{quantity}" if quantity > 1 else ""
    return LogEvent(f"Obtained {item.name}{suffix}.", Tone.LOOT)


def apply_victory(player: Player, report: VictoryReport) -> VictoryReport:
    """Grant XP, gold and loot (trophy choice is granted separately once the player picks)."""
    events = [
        LogEvent(f"+{report.xp} XP", Tone.XP),
        LogEvent(f"+{report.gold} gold", Tone.GOLD),
    ]
    player.add_gold(report.gold)
    player.kills += 1
    report.levels_gained = player.gain_xp(report.xp)
    for item, qty in report.loot:
        events.append(grant_item(player, item, qty))
    if report.levels_gained:
        events.append(LogEvent(f"Level up! You are now level {player.level}.", Tone.REWARD))
    report.events = events
    return report
