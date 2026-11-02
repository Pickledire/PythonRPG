"""Combat math as small pure functions so it can be tuned, displayed and tested in isolation."""

from __future__ import annotations

from rpg.core.attributes import Attributes
from rpg.core.items import WeaponClass

BASE_ACCURACY = 0.85
ACCURACY_PER_AGILITY = 0.003
BLIND_TARGET_BONUS = 0.10
MIN_HIT, MAX_HIT = 0.05, 0.98


def hit_chance(agility: int, own_blind_penalty: float = 0.0, target_blinded: bool = False) -> float:
    chance = BASE_ACCURACY + agility * ACCURACY_PER_AGILITY - own_blind_penalty
    if target_blinded:
        chance += BLIND_TARGET_BONUS
    return max(MIN_HIT, min(MAX_HIT, chance))


def player_crit_chance(strength: int) -> float:
    return min(0.5, 0.10 + strength * 0.002)


def enemy_crit_chance(strength: int) -> float:
    return min(0.4, 0.08 + strength * 0.0015)


def weapon_attribute_bonus(attributes: Attributes, weapon_class: WeaponClass | None) -> float:
    """Each weapon class scales mainly with one attribute (unarmed counts as melee)."""
    s, a, i = attributes.strength, attributes.agility, attributes.intelligence
    if weapon_class == WeaponClass.RANGED:
        return a * 0.6 + s * 0.2
    if weapon_class == WeaponClass.MAGIC:
        return i * 0.6 + a * 0.2
    return s * 0.6 + a * 0.2


def armor_penetration(attacker_base_damage: int, attacker_strength: int, attacker_is_boss: bool) -> float:
    """Heavy hitters and bosses ignore part of the player's armor (max 50%)."""
    pen = 0.0
    if attacker_base_damage >= 40:
        pen += 0.25
    pen += min(0.15, attacker_strength * 0.01)
    if attacker_is_boss:
        pen += 0.10
    return min(0.5, max(0.0, pen))


def armor_mitigation(effective_defense: float) -> float:
    """Multiplier applied to incoming damage. Diminishing returns: 20 DEF -> 0.77, 40 DEF -> 0.63."""
    return 100.0 / (100.0 + effective_defense * 1.5)


def spell_power(base: int, intelligence: int) -> int:
    from rpg.config import SPELL_INT_SCALING

    return int(round(base * (1 + intelligence * SPELL_INT_SCALING)))


def heal_power(base: int, intelligence: int) -> int:
    from rpg.config import DEFAULT_HEAL_POTENCY, HEAL_INT_SCALING

    return (base if base > 0 else DEFAULT_HEAL_POTENCY) + intelligence * HEAL_INT_SCALING
