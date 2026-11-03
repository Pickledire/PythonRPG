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
| Title | `n` new game · `l` load · `o` settings · `q` quit |
| Camp (hub) | `h` hunt · `q` quests · `r` rest · `i` inventory · `c` character · `s` shop · `ctrl+s` save · `l` load · `o` settings · `esc` title |
| Combat | `1` attack · `2` cast · `3` item · `4` flee |
| Dialogue | `1`–`9` choose · `esc` walk away |
| Trials | see each trial's briefing; the memory trial is mouse-only |
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
- **Progression**: XP, levels, +HP and +mana each level, and stat points you spend on any attribute.
  Gear has attribute requirements.
- **Trials (minigames)**: stealth, lockpicking, quick-time events, precision timing, rune memory and balance,
  started from dialogue, plus boss quick-time events mid-combat. See [Trials](#trials-minigames).
- **Economy**: a rotating Merchant's Emporium (buy, sell, repair) and the Collegium Arcana spell stall
  reached through the Mages Academy questline.
- **Eight quest lines** written as JSON dialogue with conditions, effects, fights and rewards.
- **Campfire rest**: full recovery, time passes, and the night may bring ambushes, thieves, gifts
  or visitors.
- **The Ghost Horror**: linger too long at camp and something comes for you.
- **Three save slots** with atomic writes. Saves from the original version of the game are imported automatically.
- **Settings** (title screen or camp, `o`): theme (Ember, Frost, Verdant, Grave, High contrast), difficulty
  (Story / Normal / Hard: enemy health and damage, rewards, trial difficulty), turn timer, trial reaction time,
  combat and boss-intro speed, skip intros, reduced motion. Stored in `saves/settings.json`, separate from saves.
- **Animated art**: a looping campfire while you rest, and a portrait for every boss intro (the Titan's glow
  matches its element).

## Trials (minigames)

Every trial is rolled against a **skill**. A skill is a weighted mix of attributes, plus your race, your
gear and any tonic you drank beforehand. The briefing before each trial shows your rating against the
difficulty and where every point comes from.

| Trial | Skill (attributes) | How it plays | Helped by |
|---|---|---|---|
| Stealth | Stealth (AGI 50%, DEX 30%, WIS 20%) | Hide until the hunter moves on. `space` holds your breath, arrow keys answer mishaps, anything else is noise. Fill the silence meter and you're discovered and ambushed. | Halflings (+5, *small frame*), Revenants (*breathless*), Vitality (longer breath), Shadow Leathers, Whisperweave Garb, Muffling Salve. Heavy armor is loud. |
| Lockpicking | Lockpicking (DEX 60%, INT 30%, WIS 10%) | Slide the pick (`←/→`, shift for big steps), apply tension (`space`). Each probe shows how close you were. Misses strain the pick until it snaps. | Gnomes (+4, *tinker*), Dwarves, Thieves' Tools, Tinker's Loupe, better picks, Steadyhand Tonic |
| Quick-time event | Reflexes (AGI 40%, DEX 40%, WIS 20%) | Hit the key on screen before the bar empties. Bosses telegraph big moves this way. | Beastkin (+3), *keen senses* (Elves, Beastkin), Hourglass Pendant (*quickened*), Quicksilver Draught |
| Precision | Precision (DEX 60%, STR 20%, WIS 20%) | Press `space` while the sweeping needle is in the mark; dead center is perfect. | Gnomes, Elven Bow, Long Bow, Sentinel Core (*steady hands*), Hawkeye Drops |
| Memory | Focus (INT 60%, WIS 40%) | Watch the runes light up, then **click** them in order (mouse only). Mistakes cost a glance. | Elves, Gnomes, Mage Robes, Memory Stone (*eidetic*), Sage Tea |
| Balance | Balance (AGI 50%, VIT 30%, DEX 20%) | Tap `←/→` against the sway and the gusts until you reach the far side. | Elves, Dwarves (*stoneborn*), Beastkin, Acrobat's Harness, Climber's Chalk, Catfoot Draught |

**Tonics** (Muffling Salve, Steadyhand Tonic, Quicksilver Draught, Sage Tea, Catfoot Draught, Hawkeye
Drops) prime a skill by +3 for your next trial of that kind. Drink one from the inventory, in combat or on
the briefing screen. **Lockpicks** come in three qualities and are spent as they break. **Tools and
charms** work while carried. Weapons and armor work while equipped.

Try them all in the temporary quest *The Sunken Vault (trial run)*. Its practice hall lets you replay
any single trial.

**Adding a trial to a quest:**
```json
{"text": "Hide behind the crates.", "effects": [{"minigame": {
  "type": "stealth", "dc": 12, "title": "Hide!", "intro": "Boots on the stairs...",
  "success": "camp/overheard", "partial": "camp/half_heard", "failure": "camp/discovered",
  "retreat": "camp/cellar", "flag": "camp_hide", "creature": "The captain", "duration": 20}}]}
```
`partial` falls back to `success` and `retreat` lets the player back out at the briefing. `flag` stores
`success` / `partial` / `failure` / `retreat` for later checks with `{"flag_is": ["camp_hide", "success"]}`.
A discovered player usually meets `{"start_combat": "captain", "ambush": true}`, and a successful
sneak can open with `{"start_combat": "captain", "opener": 0.25}`. Tuning keys for each type are the
keyword arguments of its class in `rpg/core/minigames/`:

| Type | Keys |
|---|---|
| `qte` | `prompts`, `window`, `keys` (e.g. `"WASD"` or `"←→↑↓"`) |
| `lockpick` | `pins`, `time_limit` |
| `timing` | `strikes`, `speed`, `zone`, `action` |
| `memory` | `rounds`, `start_length` |
| `balance` | `duration`, `gust` |
| `stealth` | `duration`, `presence`, `creature` |

**Boss quick-time events** are `QTETrigger`s on an `EnemyTemplate`. One fires once at an HP threshold and
replaces the boss's action that turn. Success dodges (and can stagger or counter), partial halves the
damage, failure deals a share of your max HP plus an optional effect.

## Project layout

```
rpg/
  config.py            Balance constants and paths (tune the game here)
  core/                Game rules. No UI imports; fully unit-tested
    attributes.py      The seven attributes and equipment requirements
    skills.py          Skills, traits and skill checks for trials
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
    minigames/         Trials as pure state machines (qte, lockpick, timing, memory, balance, stealth)
    session.py         GameSession: the single façade the UI uses
  services/
    persistence.py     Save slots, atomic writes, v1 save migration
    settings.py        Player settings (options are data; the settings screen is built from them)
  ui/
    app.py             RPGApp: navigation and multi-screen flows
    palette.py         Themes + text colors (re-skin here)
    assets/animations/ ASCII animations: the campfire and the boss portraits (JSON)
    styles.tcss        Layout and widget styles (re-skin here)
    widgets/           StatBar, PlayerPanel, CombatantCard, ItemTable, EventLog, VisualEffect
    screens/           Title, character creation, camp, encounter, combat, inventory,
                       character sheet, shop, quests, dialogue, campfire, save/load, game over, modals
      minigames/       One screen per trial + the briefing
dialogues/             Quest and encounter content (JSON)
tools/                 import_ascii_motion.py (bring in ASCII Motion exports), make_boss_art.py (boss portraits)
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
Add `skills={"stealth": 2}` or `traits=("keen_senses",)` to make gear matter in trials (`ITEMS.curio(...)`
makes a carried tool or charm). Leave out `requirements` to use the default rule for the item type (melee → Strength, ranged/finesse →
Dexterity, staves and attack spells → Intelligence, heal/ward spells → Wisdom, light armor → Agility).
Then add its id to a shop pool or loot table, or hand it out from dialogue with `{"give_item": "frost_brand"}`.

**Add a race**: one `_race(...)` line in `rpg/config.py` with its seven attributes, base HP, blurb and
starting item ids, plus optional trial bonuses in `RACE_SKILLS` and traits in `RACE_TRAITS`.

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

**Animations**: export from [ASCII Motion](https://ascii-motion.app) as a TUI component (`.tsx`) and run
```bash
python tools/import_ascii_motion.py path/to/export.tsx campfire --fps 10
```
then show it anywhere with `AsciiAnimation("campfire")`. Boss portraits are generated from shapes in
`tools/make_boss_art.py` (`python tools/make_boss_art.py titan`); the encounter screen picks up
`boss_<enemy id>.json` automatically, so a new boss only needs a scene function there.

**Re-skin**: add or change a theme in `THEMES` and the `TONE_STYLES` in `rpg/ui/palette.py` (list new themes in
`rpg/services/settings.py` to offer them on the settings screen), or change any rule in
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

Planned work (Aseprite sprites, combat effects, boss phases, timed events, the card game, clothing slots,
Druid companions) is tracked in [TODO.md](TODO.md).
