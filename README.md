# Epic RPG Adventure

A comprehensive turn-based RPG game written in Python with improved mechanics, inventory system, gold economy, and shop system.

## 🎮 Features

### Character System
- **Multiple Races**: Choose from Elf, Orc, Human, or Dwarf
- **Unique Stats**: Each race has different starting stats and health
- **Leveling System**: Gain XP to level up and increase stats
- **Character Progression**: Stats increase automatically on level up
- **Gold System**: Earn and spend gold for equipment and items

### Combat System
- **Turn-based Combat**: Strategic turn-based battles
- **Weapon Durability**: Weapons degrade with use and affect damage
- **Armor Defense**: Armor reduces incoming damage
- **Flee Option**: Attempt to escape from difficult battles
- **Random Encounters**: Fight various enemy types
- **Gold Rewards**: Earn gold from defeating enemies

### Economy & Shopping
- **Gold Currency**: Earn gold from combat and spend it in shops
- **Merchant's Emporium**: Fully functional shop system
- **Buy Items**: Purchase weapons, armor, and consumables
- **Sell Items**: Sell unwanted items for gold (50% of original value)
- **Item Categories**: Browse by weapon type, armor, or consumables
- **Dynamic Pricing**: Items have realistic values based on their power

### Inventory Management
- **Equipment System**: Equip weapons and armor
- **Consumables**: Use health potions and other items
- **Item Stacking**: Multiple quantities of the same item
- **Inventory Limits**: Maximum inventory size management

### Items & Equipment
- **Weapons**: Various weapon types (melee, ranged, magic) with different damage and durability
- **Armor**: Defensive equipment with durability system
- **Consumables**: Health potions of different strengths
- **Loot System**: Random loot drops after combat

### Game Features
- **User-friendly Interface**: Clear menus and status displays
- **Race-specific Starting Equipment**: Each race starts with appropriate gear
- **Enemy Variety**: Different enemy types with unique stats
- **Save/Load System**: (Coming soon)

## 🚀 How to Run

1. Make sure you have Python 3.6+ installed
2. Navigate to the game directory
3. Run the game:
   ```bash
   python Main.py
   ```

## 🎯 How to Play

### Character Creation
1. Enter your character's name
2. Choose your race from the available options
3. Each race has different starting stats and equipment
4. You start with 100 gold

### Main Menu Options
- **Find an enemy to fight**: Start a random combat encounter
- **Check inventory**: Manage your items and equipment
- **View character status**: See detailed character information
- **Visit shop**: Buy and sell items at the Merchant's Emporium
- **Save/Load game**: (Coming soon)

### Combat
1. **Attack**: Use your equipped weapon to damage enemies
2. **Use item**: Consume health potions or other items
3. **Try to flee**: Attempt to escape from combat (70% success rate)
4. **Earn rewards**: Gain XP and gold from victories

### Shopping System
- **Browse Categories**: View weapons, armor, or consumables separately
- **Buy Items**: Purchase equipment and consumables with gold
- **Sell Items**: Sell unwanted items for 50% of their value
- **Check Prices**: All items show their gold cost and stats

### Inventory Management
- **Equip weapons**: Change your active weapon
- **Equip armor**: Change your defensive equipment
- **Use items**: Consume potions and other usable items

## 📁 File Structure

```
RPG Game/
├── Main.py           # Main entry point
├── GameEngine.py     # Game loop and UI management
├── Character.py      # Player character class
├── Enemy.py          # Enemy classes and factory
├── Weapon.py         # Weapon class with durability
├── Item.py           # Base item classes (Item, Consumable, Armor)
├── Inventory.py      # Inventory management system
├── Shop.py           # Shop system for buying/selling
├── config.py         # Game configuration and constants
└── README.md         # This file
```

## 💰 Gold System

### Earning Gold
- **Combat Victories**: Earn 10-50+ gold per enemy defeated
- **Stronger Enemies**: Tougher enemies give more gold
- **Random Amounts**: Gold rewards vary for excitement

### Spending Gold
- **Weapons**: 80-400+ gold for various weapon types
- **Armor**: 30-600+ gold for different armor pieces
- **Consumables**: 25-200 gold for health potions
- **Selling**: Get 50% value when selling items

## 🛍️ Shop Items

### Weapons Available
- **Melee Weapons**: Bronze Sword, Steel Sword, Silver Sword, Enchanted Blade, War Hammer, Battle Axe
- **Ranged Weapons**: Short Bow, Long Bow, Crossbow
- **Magic Weapons**: Oak Staff, Crystal Staff, Arcane Staff

### Armor Available
- **Light Armor**: Cloth Robes, Leather Armor, Studded Leather
- **Medium Armor**: Chain Mail, Scale Mail, Enchanted Robes
- **Heavy Armor**: Plate Armor, Dragon Scale

### Consumables Available
- **Health Potion**: Restores 50 HP (25 gold)
- **Greater Health Potion**: Restores 100 HP (50 gold)
- **Superior Health Potion**: Restores 200 HP (100 gold)
- **Mega Health Potion**: Restores 500 HP (200 gold)

## 🎲 Race Statistics

| Race  | Strength | Agility | Intelligence | Health | Starting Gold |
|-------|----------|---------|--------------|--------|---------------|
| Elf   | 8        | 11      | 15           | 80     | 100           |
| Orc   | 15       | 10      | 5            | 135    | 100           |
| Human | 10       | 8       | 10           | 100    | 100           |
| Dwarf | 12       | 7       | 11           | 120    | 100           |

## 🗡️ Starting Equipment

- **Elf**: Elven Bow (12 damage, ranged) + 3 Health Potions
- **Orc**: Orcish Axe (18 damage, melee) + 3 Health Potions
- **Human**: Iron Sword (15 damage, melee) + 3 Health Potions
- **Dwarf**: Dwarven Hammer (16 damage, melee) + 3 Health Potions

## 🐉 Enemy Types

- **Goblin**: Weak but quick (40 HP, 8 damage) - Low gold reward
- **Orc Warrior**: Balanced fighter (80 HP, 15 damage) - Medium gold reward
- **Skeleton**: Undead creature (35 HP, 10 damage) - Low gold reward
- **Cave Troll**: Strong and tough (120 HP, 20 damage) - High gold reward
- **Young Dragon**: Powerful boss-type (200 HP, 35 damage) - Very high gold reward

## 🔮 Future Enhancements

- **Save/Load System**: Persistent game progress
- **Magic System**: Spells and mana
- **Quests**: Story-driven objectives
- **Multiple Areas**: Different locations to explore
- **Crafting System**: Create items from materials
- **Multiplayer**: Online or local multiplayer support
- **More Shop Features**: Item repairs, special deals, rare items

## 🐛 Known Issues

- Save/Load functionality not yet implemented
- Limited enemy AI (basic attack only)
- Shop stock is unlimited for consumables

## 📝 Changelog

### Version 2.1 (Current)
- **NEW**: Gold system with earning and spending mechanics
- **NEW**: Complete shop system with buying and selling
- **NEW**: Expanded weapon, armor, and consumable selection
- **NEW**: Dynamic pricing based on item power
- **NEW**: Gold rewards from combat victories
- **IMPROVED**: Main menu now shows gold amount
- **IMPROVED**: Character status displays gold
- **IMPROVED**: Combat rewards include both XP and gold

### Version 2.0
- Complete rewrite of the game engine
- Added inventory management system
- Implemented equipment system
- Added multiple races with unique stats
- Improved combat mechanics
- Added durability system for weapons and armor
- Enhanced user interface
- Added random loot system
- Implemented proper game loop

### Version 1.0 (Original)
- Basic character and enemy classes
- Simple combat system
- Minimal functionality

---

Enjoy your epic adventure and happy shopping! 🗡️⚔️🛡️💰 