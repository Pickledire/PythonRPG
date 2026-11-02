"""Test helpers: deterministic RNG and quick factories."""

from __future__ import annotations

import random

from rpg.core.enemies import ENEMIES, Enemy
from rpg.core.entities import Player


class ScriptedRandom(random.Random):
    """``random()`` returns scripted values in order, then ``default``. Other methods stay seeded."""

    def __init__(self, values=(), default: float = 0.5, seed: int = 0) -> None:
        super().__init__(seed)
        self.values = list(values)
        self.default = default

    def random(self) -> float:  # noqa: D401 - matches random.Random API
        return self.values.pop(0) if self.values else self.default

    def uniform(self, a: float, b: float) -> float:
        return (a + b) / 2  # no damage variance in tests


def make_player(race: str = "Human") -> Player:
    return Player.create("Tester", race)


def make_enemy(enemy_id: str = "goblin", **overrides) -> Enemy:
    enemy = ENEMIES.create(enemy_id, random.Random(1))
    for key, value in overrides.items():
        setattr(enemy, key, value)
    if "max_hp" in overrides and "hp" not in overrides:
        enemy.hp = enemy.max_hp
    return enemy
