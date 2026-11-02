# Epic RPG Adventure

A turn-based fantasy RPG for the terminal, built with [Textual](https://textual.textualize.io/).
Create a hero, hunt monsters that scale with your level, face Titans and ancient story bosses,
follow branching quests, and build your character through gear, spells and attributes.

## Quick start

Python 3.10 or newer is required.

```bash
python -m pip install -r requirements.txt
```

```bash
python -m rpg
```

On Windows you can also double-click `run_game.bat`; on macOS/Linux run `./run_game.sh`. Both
create a virtual environment, install dependencies and launch the game.

For the best look use a modern terminal (Windows Terminal, iTerm2, kitty, WezTerm) at 120×40 or larger.

## How to play

| Where | Keys |
|---|---|
| Camp (hub) | `h` hunt · `q` quests · `r` rest · `i` inventory · `c` character · `s` shop · `ctrl+s` save · `l` load · `esc` title |
| Combat | `1` attack · `2` cast · `3` item · `4` flee |
| Dialogue | `1`–`9` choose · `esc` walk away |
| Inventory | `e` equip · `u` use · `d` discard |
| Shop | `b` buy / sell / repair · `esc` leave |
| Anywhere | `ctrl+q` quit · `ctrl+p` command palette (themes) |

Mouse clicks work everywhere too.

### Features
- **Ten races**: Human, Elf, Orc, Dwarf, Druid, Halfling, Gnome, Dragonkin, Beastkin and Revenant,
  each with their own attribute spread, HP/mana and starting kit.
- **Seven attributes** that all matter:

  | Attribute | Effect |
  |---|---|
  | Strength | melee damage, heavy weapons and armor |
  | Dexterity | accuracy, critical hits, bows and finesse weapons (daggers, claws, rapiers) |
  | Agility | dodge chance, flee chance, light armor |
  | Vitality | +5 max HP per point, less poison/burn/bleed damage |
  | Intelligence | spell damage, staves |
  | Wisdom | +5 max mana per point, healing power, chance to resist harmful effects |
  | Charisma | shop prices (discounts or markups, better sell prices), persuasion checks in quests |

  Many weapons, armor pieces and spells need **two** attributes, e.g. Mithril Armor needs Strength 14 and
  Dexterity 13.
- **Turn-based combat** with accuracy, critical hits, armor mitigation and armor penetration,
  weapon and armor durability, and a turn timer: hesitate and the enemy strikes.
- **Status effects** that tick each turn: poison, burn and bleed damage over time, regeneration,
  wards (damage shields), blindness (lower accuracy) and freezing (lose a turn).
  Weapons, spells and enemies can inflict them; antidotes cure them.
- **Spells**: damage, healing, wards, blinding, freezing, burning, poisoning and bleeding.
  Spell power scales with Intelligence.
- **Level-scaled hunts** with weighted enemy pools, risky hunts (stronger foes, +50% rewards) and
  random modifiers: *Enraged, Armored, Shielded, Swift, Venomous* and *Searing*.
- **Bosses**: a Titan at level 10, the Elder Dragon at 15, the Earth Eater Worm at 20 and the Rat King
  at 25, each with a cinematic intro and a choice of three legendary trophies. Story bosses appear in quests.
- **Progression**: XP, levels, +HP and +mana each level, and stat points you spend on Strength,
  Agility or Intelligence. Gear has attribute requirements.
- **Economy**: a rotating Merchant's Emporium (buy, sell, repair) and the Collegium Arcana spell stall
  reached through the Mages Academy questline.
- **Eight quest lines** written as JSON dialogue with conditions, effects, fights and rewards.
- **Campfire rest**: full recovery, time passes, and the night may bring ambushes, thieves, gifts
  or visitors.
- **The Ghost Horror**: linger too long at camp and something comes for you.
- **Three save slots** with atomic writes. Saves from the original version of the game are imported automatically.

## Project layout

```
rpg/
  config.py            Balance constants and paths (tune the game here)
  core/                Game rules. No UI imports; fully unit-tested
    attributes.py      Strength / Agility / Intelligence, equipment requirements
    effects.py         Status effects and their timing rules
    items.py           Weapon, Armor, Consumable, Spell, Curio models
    catalog.py         Item definitions + ItemFactory, shop pools and loot tables
    inventory.py       Stacking inventory and equipment slots
    entities.py        Combatant base class and Player
    enemies.py         Enemy templates, bosses, affixes, EnemyFactory
    formulas.py        Pure combat math (hit, crit, mitigation, spell power)
    combat.py          CombatSession state machine
    progression.py     XP, gold, loot and trophies
    shop.py            Rotating shops, selling, repairs
    campfire.py        Resting and night events
    dialogue.py        Data-driven dialogue engine
    world.py           Time of day and story flags
    session.py         GameSession: the single façade the UI uses
  services/
    persistence.py     Save slots, atomic writes, v1 save migration
  ui/
    app.py             RPGApp: navigation and multi-screen flows
    palette.py         Theme + text colors (re-skin here)
    styles.tcss        Layout and widget styles (re-skin here)
    widgets/           StatBar, PlayerPanel, CombatantCard, ItemTable, EventLog, VisualEffect
    screens/           Title, character creation, camp, encounter, combat, inventory,
                       character sheet, shop, quests, dialogue, campfire, save/load, game over, modals
dialogues/             Quest and encounter content (JSON)
saves/                 Save slots (slot1.json ... slot3.json)
tests/                 Unit tests for every core system + a headless UI test
```

### How it fits together
- The **UI never contains game rules**. Screens call `GameSession` methods (`create_hunt`,
  `begin_combat`, `rest`, `shop`, `equip`, ...) and render the `LogEvent`s they return.
- **Combat is a step-wise state machine** (`CombatSession.act()` / `enemy_turn()`), so the combat screen
  controls pacing and animation and tests can play whole fights without a terminal.
- **State changes are broadcast** with a reactive counter: screens call `app.touch()` and widgets that
  `watch(app, "revision")` (such as the player panel) redraw themselves.
- **Flows that span screens** (intro → combat → victory → trophy → level-up, or a quest fight that ends in
  game over) are `async` methods on `RPGApp` that run as workers and `await push_screen_wait(...)`.

## Extending the game

**Add an item**: one line in `rpg/core/catalog.py`:
```python
ITEMS.weapon("frost_brand", "Frost Brand", 34, 150, 260, "A blade rimed in frost.",
             on_hit=EffectSpec(EffectKind.FROZEN, 0, 1, 0.15),
             requirements=req(strength=13, wisdom=11))
```
Leave out `requirements` to use the default rule for the item type (melee → Strength, ranged/finesse →
Dexterity, staves and attack spells → Intelligence, heal/ward spells → Wisdom, light armor → Agility).
Then add its id to a shop pool or loot table, or hand it out from dialogue with `{"give_item": "frost_brand"}`.

**Add a race**: one `_race(...)` line in `rpg/config.py` with its seven attributes, base HP, blurb and
starting item ids.

**Add an enemy**: add an `EnemyTemplate` to `_TEMPLATES` in `rpg/core/enemies.py` (stats, spellbook,
on-hit effects, regeneration, intro text, trophy choices) and, for random hunts, to `LEVEL_POOLS`.
Dialogue can start a fight with `{"start_combat": "frost_giant"}` (by id or display name).

**Write a quest**: add JSON nodes under `dialogues/` and a `Quest` entry in `rpg/core/session.py`.
The schema (conditions and effects) is documented at the top of `rpg/core/dialogue.py`. Attribute checks
work in both directions: `{"min_stat": ["charisma", 12]}` as a condition for a persuasion choice, and
`{"stat_change": ["vitality", 1]}` or `{"set_wisdom": 15}` as effects. To check
content for broken links and unknown enemies or items:

```bash
python -c "from rpg.core.dialogue import DialogueRepository; from rpg.config import DIALOGUE_DIR; print('\n'.join(DialogueRepository(DIALOGUE_DIR).validate()) or 'OK')"
```

**Re-skin**: change the `EMBER_THEME` colors and `TONE_STYLES` in `rpg/ui/palette.py`, or any rule in
`rpg/ui/styles.tcss`. Run with `textual run --dev rpg.ui.app:RPGApp` (needs `textual-dev`) for live CSS reloading.

## Tests

```bash
python -m unittest discover -s tests -t .
```

The suite covers combat (including every status effect), items, inventory, progression, enemies, hunts,
shops, the campfire, dialogue (including a lint of all shipped dialogue), persistence and save migration,
plus an end-to-end UI run through Textual's headless pilot. It also runs under `pytest`.

## The original version

The first version of the game (`Main.py`, `GameEngine.py` and friends at the repository root) is still
here for reference and runs with `python Main.py`. The new game reads its dialogue files and imports its saves.

## Roadmap

Planned work (Aseprite sprites, combat effects, boss phases, timed events, minigames such as lockpicking,
Druid companions) is tracked in [TODO.md](TODO.md).
