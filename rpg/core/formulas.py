"""Combat and economy math as small pure functions, so it can be tuned, displayed and tested in isolation."""

from __future__ import annotations

from rpg import config
from rpg.core.attributes import Attributes
from rpg.core.items import Weapon, WeaponClass

BASE_ACCURACY = 0.85
ACCURACY_PER_DEXTERITY = 0.003
BLIND_TARGET_BONUS = 0.10
MIN_HIT, MAX_HIT = 0.05, 0.98


# ------------------------------------------------------------------ offense
def hit_chance(dexterity: int, own_blind_penalty: float = 0.0, target_blinded: bool = False) -> float:
    """Chance to land an attack. Player accuracy uses Dexterity; enemies pass their agility."""
    chance = BASE_ACCURACY + dexterity * ACCURACY_PER_DEXTERITY - own_blind_penalty
    if target_blinded:
        chance += BLIND_TARGET_BONUS
    return max(MIN_HIT, min(MAX_HIT, chance))


def player_crit_chance(attributes: Attributes) -> float:
    """Dexterity is the main crit stat; Strength adds a little."""
    return min(0.5, 0.08 + attributes.dexterity * 0.003 + attributes.strength * 0.001)


def enemy_crit_chance(strength: int) -> float:
    return min(0.4, 0.08 + strength * 0.0015)


WEAPON_SCALING = 0.035  # +3.5% weapon damage per point of the weapon's main attribute above 10


def weapon_attribute_bonus(attributes: Attributes, weapon: Weapon | None) -> float:
    """Damage an attribute adds to a weapon hit: a small flat part plus a share of the weapon's own damage.

    Melee uses Strength, finesse blades and bows use Dexterity, staves use Intelligence (unarmed = melee).
    """
    a = attributes
    damage = weapon.effective_damage if weapon else config.UNARMED_DAMAGE
    if weapon is None or weapon.weapon_class == WeaponClass.MELEE and not weapon.finesse:
        primary, flat = a.strength, a.strength * 0.35 + a.dexterity * 0.05 + a.agility * 0.05
    elif weapon.finesse:
        primary, flat = a.dexterity, a.dexterity * 0.4 + a.agility * 0.2
    elif weapon.weapon_class == WeaponClass.RANGED:
        primary, flat = a.dexterity, a.dexterity * 0.45 + a.strength * 0.1
    else:  # staves
        primary, flat = a.intelligence, a.intelligence * 0.35 + a.wisdom * 0.1
    return flat + damage * max(-0.3, (primary - 10) * WEAPON_SCALING)


def spell_multiplier(intelligence: int) -> float:
    """Spell damage and spell damage-over-time scale with Intelligence above 10 (and shrink a little below)."""
    return max(0.6, 1 + (intelligence - 10) * config.SPELL_INT_SCALING)


def spell_power(base: int, intelligence: int) -> int:
    return int(round(base * spell_multiplier(intelligence)))


def heal_multiplier(wisdom: int) -> float:
    return max(0.6, 1 + (wisdom - 10) * config.HEAL_WIS_SCALING)


def heal_power(base: int, wisdom: int) -> int:
    return int(round((base if base > 0 else config.DEFAULT_HEAL_POTENCY) * heal_multiplier(wisdom)))


def enemy_spell_multiplier(level: int) -> float:
    """Enemies have no Intelligence; their spells grow with their level instead."""
    return 1 + max(0, level - 1) * config.ENEMY_SPELL_GROWTH


# ------------------------------------------------------------------ defense
def dodge_chance(agility: int) -> float:
    """Chance to completely avoid a weapon attack."""
    return min(0.25, agility * 0.006)


def dot_resistance(vitality: int) -> float:
    """Fraction of poison/burn/bleed damage shrugged off."""
    return min(0.4, vitality * 0.01)


def status_resist_chance(wisdom: int) -> float:
    """Chance to resist a harmful status effect (poison, burn, bleed, blind, freeze) entirely."""
    return min(0.35, wisdom * 0.01)


def flee_chance(agility: int, against_boss: bool) -> float:
    base = config.BOSS_FLEE_CHANCE if against_boss else config.FLEE_CHANCE
    return max(0.05, min(0.95, base + (agility - 10) * 0.01))


def armor_penetration(attacker_level: int, attacker_is_boss: bool) -> float:
    """Stronger enemies ignore part of the player's armor: 1% per level, +10% for bosses (max 40%)."""
    return min(0.4, max(0.0, attacker_level * 0.01 + (0.10 if attacker_is_boss else 0.0)))


def armor_mitigation(effective_defense: float) -> float:
    """Multiplier applied to incoming damage. Diminishing returns: 20 DEF -> 0.77, 40 DEF -> 0.63."""
    return 100.0 / (100.0 + effective_defense * 1.5)


# ------------------------------------------------------------------ economy
def buy_price_multiplier(charisma: int) -> float:
    """Charismatic heroes haggle prices down (max 25% off); uncharismatic ones pay a little more."""
    if charisma >= 10:
        return 1.0 - min(0.25, (charisma - 10) * 0.02)
    return 1.0 + (10 - charisma) * 0.02


def sell_ratio(charisma: int) -> float:
    """Fraction of an item's value a merchant pays (50% at 10 CHA, up to 65%)."""
    return max(0.35, min(0.65, config.SELL_RATIO + (charisma - 10) * 0.01))


def threat(max_hp: int, damage: int, defense: float = 0.0) -> float:
    """How dangerous an enemy is: the geometric mean of its staying power and its punch. Drives XP and gold."""
    staying = max_hp / armor_mitigation(defense)
    return (max(1.0, staying) * max(1.0, damage)) ** 0.5


def xp_to_next(level: int) -> int:
    """XP needed to go from ``level`` to ``level + 1``."""
    return int(round(config.BASE_XP_REQUIREMENT * level ** config.XP_EXPONENT))


def max_hp_for(base_hp: int, vitality: int) -> int:
    return base_hp + vitality * config.HP_PER_VITALITY


def max_mana_for(wisdom: int) -> int:
    return config.BASE_MANA + wisdom * config.MANA_PER_WISDOM
