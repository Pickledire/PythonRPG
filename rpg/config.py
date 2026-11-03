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
# Racial skill bonuses and traits for minigames (see rpg/core/skills.py for what each skill and trait does).
_ALL_SKILLS = ("stealth", "lockpicking", "reflexes", "focus", "balance", "precision")
RACE_SKILLS: dict[str, dict[str, int]] = {
    "Human": {skill: 1 for skill in _ALL_SKILLS},  # adaptable: a little better at everything
    "Elf": {"balance": 2, "focus": 2, "precision": 1},
    "Orc": {"reflexes": 1, "stealth": -2, "lockpicking": -1},
    "Dwarf": {"lockpicking": 2, "balance": 2, "stealth": -1},
    "Druid": {"stealth": 2, "focus": 1},
    "Halfling": {"stealth": 5, "balance": 1, "lockpicking": 1},  # small, quiet, overlooked
    "Gnome": {"lockpicking": 4, "precision": 2, "focus": 1},
    "Dragonkin": {"stealth": -3, "balance": -1, "reflexes": 1},
    "Beastkin": {"reflexes": 3, "balance": 2, "stealth": 1},
    "Revenant": {"stealth": 2, "focus": 1, "reflexes": -1},  # no heartbeat, stiff joints
}
RACE_TRAITS: dict[str, tuple[str, ...]] = {
    "Elf": ("keen_senses",),
    "Orc": ("heavy_step",),
    "Dwarf": ("stoneborn",),
    "Halfling": ("small_frame",),
    "Gnome": ("small_frame", "tinker"),
    "Dragonkin": ("smoldering",),
    "Beastkin": ("keen_senses",),
    "Revenant": ("breathless",),
}

STARTING_CONSUMABLES = {"health_potion": 3}
STARTING_GOLD = 100

# --------------------------------------------------------------------------- progression
# XP to go from level L to L+1 = BASE_XP_REQUIREMENT * L ** XP_EXPONENT
BASE_XP_REQUIREMENT = 100
XP_EXPONENT = 1.15
HEALTH_GAIN_PER_LEVEL = 10
MANA_GAIN_PER_LEVEL = 6
STAT_POINTS_PER_LEVEL = 1
BONUS_STAT_POINT_EVERY = 5  # an extra point at levels 5, 10, 15...

# Rewards come from an enemy's threat (rpg.core.formulas.threat): sqrt(effective HP x damage).
XP_PER_THREAT = 3.5
GOLD_PER_THREAT = 0.6
REWARD_VARIANCE = 0.15
BOSS_REWARD_MULTIPLIER = 3.0
UNDERLEVEL_PENALTY = 0.12  # -12% XP per level the enemy is more than 2 levels below you (min 25%)
LOOT_CHANCE = 0.45

# --------------------------------------------------------------------------- combat
PLAYER_DAMAGE_VARIANCE = 0.35
ENEMY_DAMAGE_VARIANCE = 0.30
CRIT_MULTIPLIER = 1.5
FLEE_CHANCE = 0.70
BOSS_FLEE_CHANCE = 0.25
UNARMED_DAMAGE = 4
SPELL_INT_SCALING = 0.03  # +3% spell damage (and spell DoT strength) per point of Intelligence above 10
HEAL_WIS_SCALING = 0.04  # +4% healing per point of Wisdom above 10
DEFAULT_HEAL_POTENCY = 60
ENEMY_SPELL_GROWTH = 0.06  # enemy spells +6% per enemy level
ENEMY_SPELL_CHANCE = 0.35

# Seconds the player has to act before hesitating (0 disables the timer).
TURN_TIMER_SECONDS = 20

# --------------------------------------------------------------------------- difficulty (settings screen)
# Applied to every enemy when it is created, to combat rewards and to trial difficulty (dc).
DIFFICULTIES: dict[str, dict] = {
    "story": {"label": "Story", "blurb": "Gentler foes and easier trials. For the tale, not the struggle.",
              "enemy_hp": 0.7, "enemy_damage": 0.7, "rewards": 1.0, "trial_dc": -2},
    "normal": {"label": "Normal", "blurb": "The intended balance.",
               "enemy_hp": 1.0, "enemy_damage": 1.0, "rewards": 1.0, "trial_dc": 0},
    "hard": {"label": "Hard", "blurb": "Tougher, harder-hitting foes and stricter trials, for 30% more rewards.",
             "enemy_hp": 1.3, "enemy_damage": 1.2, "rewards": 1.3, "trial_dc": 2},
}

# --------------------------------------------------------------------------- hunts & scaling
RISKY_HUNT_ENEMY_SCALE = 1.2
RISKY_HUNT_REWARD_MULTIPLIER = 1.5
AFFIX_CHANCE = 0.25  # +1% per enemy level, up to 50%
DOUBLE_AFFIX_CHANCE = 0.3  # level 15+ elites may roll a second affix

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

# --------------------------------------------------------------------------- minigames
# Each point of skill above (below) a minigame's difficulty widens (narrows) its windows by this much.
SKILL_EASE_PER_POINT = 0.06
# Boss quick-time events: share of max HP lost on a failed prompt sequence (partial success halves it).
QTE_FAIL_DAMAGE = 0.22
