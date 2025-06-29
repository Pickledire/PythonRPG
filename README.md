# Brenden's Epic RPG Adventure

A comprehensive turn-based RPG game written in Python with improved mechanics, inventory system, gold economy, shop system, and **beautiful colorful interface**.

## 🚀 How to Run

### Easy Method (Recommended)
1. Double-click `run_game.bat` to automatically start the game with the virtual environment

### Manual Method
1. Make sure you have Python 3.6+ installed
2. Install colorama: `pip install colorama`
3. Navigate to the game directory
4. Run the game:
   ```bash
   python Main.py
   ```

### Virtual Environment Method
1. Activate the virtual environment:
   ```bash
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```
2. Run the game:
   ```bash
   python Main.py
   ```

## 🎨 Visual Features

### Color Scheme
- **🔴 Red**: Health, damage, enemies, warnings
- **🟢 Green**: XP, success messages, player actions
- **🔵 Blue**: Mana, armor, information
- **🟡 Yellow**: Gold, race selection, warnings
- **🟣 Magenta**: Combat actions, items
- **🔵 Cyan**: Weapons, titles, borders
- **⚪ White**: Menu options, general text

### Visual Elements
- **Health Bars**: Color-coded progress bars (green/yellow/red based on health %)
- **XP Bars**: Visual progress tracking for experience points
- **Borders**: Decorative borders and separators
- **Icons**: Emojis and symbols for better visual appeal
- **ASCII Art**: Enhanced title screen

## 🎯 How to Play

### Character Creation
1. Enter your character's name
2. Choose your race from the available options
3. Each race has different starting stats and equipment
4. You start with 100 gold

### Main Menu Options
- **🗡️ Find an enemy to fight**: Start a random combat encounter
- **📦 Check inventory**: Manage your items and equipment
- **📊 View character status**: See detailed character information with visual bars
- **🏪 Visit shop**: Buy and sell items at the Merchant's Emporium
- **💾 Save/Load game**: (Coming soon)

### Combat
1. **⚔️ Attack**: Use your equipped weapon to damage enemies
2. **🧪 Use item**: Consume health potions or other items
3. **🏃 Try to flee**: Attempt to escape from combat (70% success rate)
4. **🔮 Cast spell**: Attack using current spell
4. **🎉 Earn rewards**: Gain XP and gold from victories 

### Shopping System
- **Browse Categories**: View weapons, armor, or consumables separately
- **Buy Items**: Purchase equipment and consumables with gold
- **Sell Items**: Sell unwanted items for 50% of their value
- **Check Prices**: All items show their gold cost and stats

### Inventory Management
- **Equip weapons**: Change your active weapon
- **Equip armor**: Change your defensive equipment
- **Equip magic**: Change your current spell
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
├── Magic.py          # Base magic system
├── Inventory.py      # Inventory management system
├── Shop.py           # Shop system for buying/selling
├── config.py         # Game configuration and constants
├── run_game.bat      # Easy launcher for Windows
├── requirements.txt  # Python dependencies
├── .venv/            # Virtual environment
└── README.md         # This file
```

## 🎨 Testing Colors

Run the color demo to see all the visual enhancements:
```bash
python test_colors.py
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

- **Titan Boss**: Strongest enemy in the game - You should probably run

## 🔮 Future Enhancements

- **Save/Load System**: Persistent game progress
- **Quests**: Story-driven objectives
- **Multiple Areas**: Different locations to explore
- **Crafting System**: Create items from materials
- **More Shop Features**: Item repairs, special deals, rare items

## 🐛 Known Issues

- Save/Load functionality not yet implemented
- Limited enemy AI (basic attack only)
- Shop stock is unlimited for consumables

## 📝 Changelog

### Version (Current) - Visual Enhancement Update + Magic
- **NEW**: 🔮 New magic system for mages, and spells you can buy in shop
- **NEW**: 🎨 Complete colorama integration for beautiful terminal colors
- **NEW**: 📊 Visual health and XP progress bars
- **NEW**: 🖼️ ASCII art title screen with enhanced startup experience
- **NEW**: 🎯 Color-coded combat messages and status displays
- **NEW**: 🌈 Comprehensive color scheme for all game elements
- **NEW**: 📦 Virtual environment setup with requirements.txt
- **NEW**: 🚀 Easy launcher (run_game.bat) for Windows users
- **IMPROVED**: 📱 Fullscreen terminal optimization (120x40 characters)
- **IMPROVED**: 🎮 Enhanced user interface with borders and visual elements
- **IMPROVED**: 🎨 All menus, status screens, and combat displays now colorful
- **IMPROVED**: 📈 Character status display with visual progress indicators