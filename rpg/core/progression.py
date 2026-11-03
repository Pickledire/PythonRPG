"""Victory rewards: XP, gold, loot, boss trophies and guaranteed drops."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from rpg import config
from rpg.core.catalog import ITEMS, LOOT_TABLE, LOOT_WEIGHTS
from rpg.core.enemies import Enemy
from rpg.core.formulas import threat
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


def enemy_threat(enemy: Enemy) -> float:
    damage = enemy.base_damage + enemy.attributes.strength * 0.3 + enemy.attributes.agility * 0.2
    return threat(enemy.max_hp, int(damage), enemy.defense)


def _variance(rng: random.Random) -> float:
    return 1 + rng.uniform(-config.REWARD_VARIANCE, config.REWARD_VARIANCE)


def xp_reward(enemy: Enemy, rng: random.Random, player_level: int | None = None) -> int:
    xp = enemy_threat(enemy) * config.XP_PER_THREAT * _variance(rng)
    if enemy.is_boss:
        xp *= config.BOSS_REWARD_MULTIPLIER
    if player_level is not None and enemy.level < player_level - 2:  # farming far weaker foes pays less
        xp *= max(0.25, 1 - config.UNDERLEVEL_PENALTY * (player_level - 2 - enemy.level))
    return max(1, int(xp))


def gold_reward(enemy: Enemy, rng: random.Random) -> int:
    gold = enemy_threat(enemy) * config.GOLD_PER_THREAT * _variance(rng)
    return max(1, int(gold * (config.BOSS_REWARD_MULTIPLIER if enemy.is_boss else 1)))


def loot_value_target(level: int) -> int:
    """Roughly what a dropped piece of gear is worth at this enemy level."""
    return 40 + level * 28


def roll_loot(enemy: Enemy, rng: random.Random) -> list[tuple[Item, int]]:
    """Guaranteed drops, plus (sometimes, always for bosses) one item from a loot pool at the enemy's tier."""
    drops: list[tuple[Item, int]] = [(ITEMS.create(tid), qty) for tid, qty in enemy.template.guaranteed_drops]
    if enemy.is_boss or rng.random() < config.LOOT_CHANCE:
        categories = list(LOOT_TABLE)
        category = rng.choices(categories, weights=[LOOT_WEIGHTS.get(c, 1) for c in categories], k=1)[0]
        candidates = [ITEMS.create(tid) for tid in LOOT_TABLE[category]]
        target = loot_value_target(enemy.level)
        in_band = [i for i in candidates if target * 0.45 <= i.value <= target * 1.5]
        pick = rng.choice(in_band) if in_band else min(candidates, key=lambda i: abs(i.value - target))
        drops.append((pick, 1))
    return drops


def roll_victory(enemy: Enemy, rng: random.Random, multiplier: float = 1.0,
                 player_level: int | None = None) -> VictoryReport:
    return VictoryReport(
        enemy_name=enemy.name,
        xp=int(xp_reward(enemy, rng, player_level) * multiplier),
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
    report.xp = int(report.xp * (1 + player.passive("xp_gain")))
    report.gold = int(report.gold * (1 + player.passive("gold_find")))
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
