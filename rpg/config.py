"""Game balance constants and paths.

Everything a designer may want to tune lives here so rules modules stay free of magic numbers.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RPG_DATA_DIR", PROJECT_ROOT))
DIALOGUE_DIR = DATA_DIR / "dialogues"
SAVE_DIR = Path(os.environ.get("RPG_SAVE_DIR", PROJECT_ROOT / "saves"))
SAVE_SLOTS = 3
SAVE_VERSION = 2

# --------------------------------------------------------------------------- races
# Max HP  = base_hp + vitality × HP_PER_VITALITY
# Max mana = BASE_MANA + wisdom × MANA_PER_WISDOM
HP_PER_VITALITY = 5
BASE_MANA = 50
MANA_PER_WISDOM = 5


def _race(stats: str, base_hp: int, blurb: str, kit: list[str], equip: list[str] | None = None) -> dict:
    """``stats`` is "STR DEX AGI VIT INT WIS CHA"."""
    keys = ("strength", "dexterity", "agility", "vitality", "intelligence", "wisdom", "charisma")
    return {**dict(zip(keys, map(int, stats.split()))), "base_hp": base_hp, "blurb": blurb,
            "starting_items": kit, "equip": kit if equip is None else equip}


RACES: dict[str, dict] = {
    #                    STR DEX AGI VIT INT WIS CHA
    "Human": _race("10 10  9 10 10 10 12", 55, "Adaptable and steady. A reliable blade and a silver tongue.",
                   ["iron_sword"]),
    "Elf": _race(" 8 12 11  8 15 12 10", 40, "Graceful archers with a natural gift for the arcane.",
                 ["elven_bow", "elven_blast"]),
    "Orc": _race("15  8 10 14  5  6  7", 65, "Brutal and tireless. Hits hard, takes harder.",
                 ["orcish_axe"]),
    "Dwarf": _race("12  9  7 13 11 10  8", 55, "Stubborn as stone, with a war cry that shakes mountains.",
                   ["dwarven_hammer", "dwarven_scream"]),
    "Druid": _race(" 9  9 10 11 11 15 10", 45, "Grove-born keepers of the wild. Thorns answer their call, and "
                   "one day the beasts will too.", ["thornwood_staff", "thorn_lash"]),
    "Halfling": _race(" 7 14 14  9  9 10 13", 45, "Small, quick and impossibly lucky. Hard to hit, harder to "
                      "haggle with.", ["halfling_dagger"]),
    "Gnome": _race(" 6 12 11  9 15 12 11", 45, "Tinkerers and spark-casters with a crossbow for every problem.",
                   ["clockwork_crossbow", "arc_spark"]),
    "Dragonkin": _race("14  8  7 13  9  9 11", 60, "Scaled descendants of wyrms who carry fire in their lungs.",
                       ["dragonkin_glaive", "ember_breath"]),
    "Beastkin": _race("12 11 14 12  6  9  7", 55, "Feral hunters with claws for blades and senses for maps.",
                      ["bone_claws"]),
    "Revenant": _race("11 10  8 12 10 13  5", 50, "Risen from the grave with unfinished business. People "
                      "tend to stare.", ["grave_blade", "wither"]),
}
STARTING_CONSUMABLES = {"health_potion": 3}
STARTING_GOLD = 100

# --------------------------------------------------------------------------- progression
BASE_XP_REQUIREMENT = 100
XP_INCREASE_PER_LEVEL = 15
HEALTH_GAIN_PER_LEVEL = 10
MANA_GAIN_PER_LEVEL = 10
STAT_POINTS_PER_LEVEL = 1

MIN_XP_REWARD = 25
MAX_XP_REWARD = 150
MIN_GOLD_REWARD = 10
MAX_GOLD_REWARD = 50
BOSS_REWARD_MULTIPLIER = 2.0
LOOT_CHANCE = 0.5

# --------------------------------------------------------------------------- combat
PLAYER_DAMAGE_VARIANCE = 0.50
ENEMY_DAMAGE_VARIANCE = 0.30
CRIT_MULTIPLIER = 1.5
FLEE_CHANCE = 0.70
BOSS_FLEE_CHANCE = 0.25
UNARMED_DAMAGE = 4
SPELL_INT_SCALING = 0.01  # +1% spell power per point of intelligence
HEAL_WIS_SCALING = 2  # flat bonus HP per wisdom point
DEFAULT_HEAL_POTENCY = 60
ENEMY_SPELL_CHANCE = 0.35

# Seconds the player has to act before hesitating (0 disables the timer).
TURN_TIMER_SECONDS = 20

# --------------------------------------------------------------------------- hunts & scaling
RISKY_HUNT_ENEMY_SCALE = 1.2
RISKY_HUNT_REWARD_MULTIPLIER = 1.5
AFFIX_CHANCE = 0.40
LEVEL_HP_SCALING = 0.05  # enemy HP +5% per player level above 1 (non-bosses)
LEVEL_DAMAGE_SCALING = 0.03  # enemy damage +3% per player level above 1 (non-bosses)

# Story bosses forced on the next hunt once the player reaches the level (checked highest first).
MILESTONE_BOSSES: list[tuple[int, str]] = [
    (25, "rat_king"),
    (20, "earth_eater_worm"),
    (15, "elder_dragon"),
    (10, "titan"),
]

# --------------------------------------------------------------------------- world
START_BELL = 8  # world time 0-23
REST_HOURS = 8

# Idle haunting on the camp screen: milestone whispers, then the Ghost Horror (once per run).
HAUNT_TIMEOUT_SECONDS = 30
HAUNT_MESSAGES = {
    10: "The air grows cold...",
    20: "Whispers echo from the darkness...",
    28: "A presence gathers just beyond your sight...",
}

INVENTORY_SIZE = 50
SELL_RATIO = 0.5
REPAIR_COST_RATIO = 0.5  # fraction of item value to fully repair from 0 durability
