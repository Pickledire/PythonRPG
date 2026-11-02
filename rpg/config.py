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
# health is the starting max HP; the rest are attributes.
RACES: dict[str, dict] = {
    "Human": {
        "strength": 10, "agility": 8, "intelligence": 10, "health": 100,
        "blurb": "Adaptable and steady. A reliable blade and a level head.",
        "starting_items": ["iron_sword"],
        "equip": ["iron_sword"],
    },
    "Elf": {
        "strength": 8, "agility": 11, "intelligence": 15, "health": 80,
        "blurb": "Graceful archers with a natural gift for the arcane.",
        "starting_items": ["elven_bow", "elven_blast"],
        "equip": ["elven_bow", "elven_blast"],
    },
    "Orc": {
        "strength": 15, "agility": 10, "intelligence": 5, "health": 135,
        "blurb": "Brutal and tireless. Hits hard, takes harder.",
        "starting_items": ["orcish_axe"],
        "equip": ["orcish_axe"],
    },
    "Dwarf": {
        "strength": 12, "agility": 7, "intelligence": 11, "health": 120,
        "blurb": "Stubborn as stone, with a war cry that shakes mountains.",
        "starting_items": ["dwarven_hammer", "dwarven_scream"],
        "equip": ["dwarven_hammer", "dwarven_scream"],
    },
}
STARTING_CONSUMABLES = {"health_potion": 3}
STARTING_GOLD = 100
STARTING_MANA = 100

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
HEAL_INT_SCALING = 2  # flat bonus HP per intelligence point
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
