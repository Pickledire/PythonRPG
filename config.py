# Game Configuration Constants

# Race Stats
RACE_STATS = {
    'Elf': {
        'strength': 8,
        'agility': 11,
        'intelligence': 15,
        'health': 80
    },
    'Orc': {
        'strength': 15,
        'agility': 10,
        'intelligence': 5,
        'health': 135
    },
    'Human': {
        'strength': 10,
        'agility': 8,
        'intelligence': 10,
        'health': 100
    },
    'Dwarf': {
        'strength': 12,
        'agility': 7,
        'intelligence': 11,
        'health': 120
    }
}

# Default stats for unknown races
DEFAULT_STATS = {
    'strength': 8,
    'agility': 8,
    'intelligence': 8,
    'health': 50
}

# Level progression
BASE_XP_REQUIREMENT = 100
XP_INCREASE_PER_LEVEL = 15
HEALTH_GAIN_PER_LEVEL = 10

# Combat
MIN_XP_REWARD = 25
MAX_XP_REWARD = 150
DAMAGE_VARIANCE = 0.50

# Gold system
STARTING_GOLD = 100
MIN_GOLD_REWARD = 10
MAX_GOLD_REWARD = 50

# Item types
ITEM_TYPES = ['weapon', 'armor', 'consumable', 'misc'] 