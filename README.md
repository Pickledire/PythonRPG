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
| Camp (hub) | `h` hunt · `q` quests · `t` travel · `r` rest · `b` bestiary · `i` inventory · `c` character · `s` shop · `ctrl+s` save · `l` load · `o` settings · `esc` title |
| Combat | `1` attack · `2` cast · `3` item · `4` flee |
| Dialogue | `1`–`9` choose · `esc` walk away |
| Trials | see each trial's briefing; the memory trial is mouse-only |
| Inventory | `e` equip / remove · `u` use · `d` discard |
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

  Many weapons, armor pieces and spells need **two** attributes, e.g. Mithril Armor needs Strength 15 and
  Dexterity 15. Weapons gain +3.5% damage per point of their main attribute above 10.
- **Turn-based combat** with accuracy, critical hits, armor mitigation and armor penetration,
  weapon and armor durability, and a turn timer: hesitate and the enemy strikes.
- **Status effects** that tick each turn: poison, burn and bleed (different kinds stack), regeneration,
  wards, blindness, freezing, **haste** (act twice), **weaken** (deal less), **expose** (take more) and
  **silence** (no spells). Weapons, spells and enemies inflict them; antidotes and Purify cure them.
  Fire stops regeneration.
- **Spells** (about 50): damage, drains, damage-over-time, debuffs, haste, wards, and a healing line from Mend
  to Divine Light. Intelligence adds +3% spell damage per point above 10, Wisdom +4% healing. The Collegium
  Arcana sells the strongest.
- **Regions and travel**: twelve regions on a map of roads (`story/regions.yaml`). You hunt the creatures
  of the region you're in, never weaker than its starting level. Walk to the regions next door (the road
  can bring bandits, thieves or luck) or pay for a carriage to anywhere (30-90 gold, almost always safe).
  The quest board lists what's on offer where you are.
- **160 creatures**: every region has its own (ten new per region, built in `rpg/core/creatures.py` from a
  stat curve fitted to the original roster, plus variants like the Bandit Cutthroat and the Feral Frost Bear).
- **The Bestiary** (`b`): every creature you've met, by region, with what it can do in plain words (weak to
  spells, can freeze you, heals itself...), how tough it is at your level, and its lore once you've beaten one.
- **A calendar**: days and a seven-day Harrowfolk week (Kindlemorn to Hearthsday); the title shows where you
  are and when.
- **Level-scaled hunts**: enemies are built at your level from designed stat ranges. Some resist physical or magic damage or are immune to effects. Elites carry modifiers
  (*Enraged, Armored, Shielded, Swift, Venomous, Searing, Vampiric, Thorned, Frenzied, Regenerating,
  Hulking, Ethereal, Hexing*), and from level 15 they can carry two.
- **Bosses**: a Titan at level 10 (one of eight elements, immune to its own), the Elder Dragon at 15, the
  Earth Eater Worm at 20 and the Rat King at 25. Each has a cinematic intro, telegraphed quick-time attacks
  and a choice of three legendary trophies. Story bosses appear in quests.
- **Progression**: XP and gold come from how dangerous a foe is (no XP farming far below your level).
  You get HP and mana each level, a stat point per level and a bonus point every fifth level.
- **Equipment**: weapon, armor, a readied spell, an **amulet**, a **ring** and **three trinkets**. Gear
  carries attribute bonuses and passives (regeneration, lifesteal, thorns, immunities, resistances, spell
  power, crit, execute, opening ward or haste, gold and XP find...) that apply while worn. About 50 weapons,
  50 armors and 30 rings and amulets.
- **Trials (minigames)**: stealth, lockpicking, quick-time events, precision timing, rune memory and balance,
  started from dialogue, plus boss quick-time events mid-combat. See [Trials](#trials-minigames).
- **Economy**: a rotating Merchant's Emporium that stocks gear for your level (buy, sell, repair) and the
  Collegium's stall (spells, staves, robes and jewelry, on the quest board for now). Every
  item is priced from its power.
- **Balance**: tuned with bot playthroughs. See [docs/BALANCE_AUDIT.md](docs/BALANCE_AUDIT.md) and
  `tools/balance_sim.py`.
- **A story engine**: scenes written in YAML (many per file), a story memory of flags, numbers, visits and
  quest stages, lines that change with your race and past choices, greyed-out choices that say what they
  need, rewards that pay once, quests listed in the camp's journal box, and endings that close the run. See
  [docs/STORY_ENGINE.md](docs/STORY_ENGINE.md).
- **The Banked Fire**: Emberwick's inn, its innkeeper's odd jobs, and a secret ending.
- **The Sunken Vault**: a test quest that uses every trial (for development).
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
charms** are trinkets: equip up to three. Weapons, armor and jewelry work while equipped.

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
    passives.py        Equipment passives (regeneration, lifesteal, immunities...)
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
    dialogue.py        The story engine: scenes, conditions, effects, the runner
    storydata.py       Loading YAML story files
    quests.py          Journal quests and the quest board (data)
    endings.py         Endings and their epilogues (data)
    storycheck.py      Whole-story checks (broken links, typos, dead scenes)
    regions.py         The map: regions, roads, fares, what lives where
    travel.py          Travel on foot and by carriage, and the road's surprises
    creatures.py       The creatures of each region (new species and variants)
    bestiary.py        What you've met, and its traits in plain words
    world.py           Time of day and the story's memory (flags, numbers, visits, quest stages)
    minigames/         Trials as pure state machines (qte, lockpick, timing, memory, balance, stealth)
    session.py         GameSession: the single façade the UI uses
  services/
    persistence.py     Save slots, atomic writes, v1 save migration
    settings.py        Player settings (options are data; the settings screen is built from them)
    profile.py         The meta profile across runs (endings found)
  ui/
    app.py             RPGApp: navigation and multi-screen flows
    palette.py         Themes + text colors (re-skin here)
    assets/animations/ ASCII animations: the campfire and the boss portraits (JSON)
    styles.tcss        Layout and widget styles (re-skin here)
    widgets/           StatBar, PlayerPanel, CombatantCard, ItemTable, EventLog, VisualEffect
    screens/           Title, character creation, camp, encounter, combat, inventory,
                       character sheet, shop, quests, dialogue, campfire, save/load, game over, modals
      minigames/       One screen per trial + the briefing
dialogues/             Scenes: new content in YAML (emberwick/), older quests in JSON
story/                 board.yaml (the quest board), quests/ (journal quests), endings.yaml, regions.yaml
                       (the map), bestiary.yaml (creature lore)
tools/                 story_check.py (checks the whole story), balance_sim.py (bot playthroughs for
                       balancing), import_ascii_motion.py (ASCII Motion
                       exports), make_boss_art.py (boss portraits)
docs/                  BALANCE_AUDIT.md (balance findings, targets and how to keep it balanced),
                       STORY_ENGINE.md (how to write story content), story/ (the story bible)
saves/                 Save slots (slot1.json ... slot3.json), autosave.json, profile.json
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
ITEMS.weapon("frost_brand", "Frost Brand", 34, "A blade rimed in frost.",
             on_hit=EffectSpec(EffectKind.FROZEN, 0, 1, 0.15),
             requirements=req(strength=15, wisdom=11), passives={"immune_frozen": 1})
ITEMS.jewelry("ring_of_embers", "Ring of Embers", RING, "Warm, always.",
              attributes={"strength": 1}, passives={"dot_power": 0.15, "immune_burn": 1})
```
Leave out `value` and the item is priced from its power. Keep damage, defense and requirements inside the tier
table at the top of `catalog.py`. `passives` keys are listed in `rpg/core/passives.py`. Add
`skills={"stealth": 2}` or `traits=("keen_senses",)` to make gear matter in trials (`ITEMS.curio(...)`
makes an equippable trinket). Leave out `requirements` to use the default rule for the item type (melee → Strength, ranged/finesse →
Dexterity, staves and attack spells → Intelligence, heal/ward spells → Wisdom, light armor → Agility).
Then add its id to a shop pool or loot table, or hand it out from dialogue with `{"give_item": "frost_brand"}`.

**Add a race**: one `_race(...)` line in `rpg/config.py` with its seven attributes, base HP, blurb and
starting item ids, plus optional trial bonuses in `RACE_SKILLS` and traits in `RACE_TRAITS`.

**Add an enemy**: for a region creature, add a `creature(...)` (new species, numbers from a role and a
level) or a `variant(...)` (a twist on an existing one) in `rpg/core/creatures.py`, put it in a region's
`hunt` list and give it a line of lore in `story/bestiary.yaml`. For a special one (a boss, a story
enemy), add an `EnemyTemplate` to `_TEMPLATES` in `rpg/core/enemies.py` (stats, spellbook,
on-hit effects, regeneration, intro text, trophy choices) and, for hunting, to a region's `hunt` list in
`story/regions.yaml`.
Dialogue can start a fight with `{"start_combat": "frost_giant"}` (by id or display name).

**Write a quest**: write scenes in a YAML file under `dialogues/`, define the quest in `story/quests/`, and
add a board entry to `story/board.yaml` if it starts from the hub. The guide is
[docs/STORY_ENGINE.md](docs/STORY_ENGINE.md); the full list of conditions and effects is at the top of
`rpg/core/dialogue.py`. Then check the whole story for broken links, typos and unreachable scenes:

```bash
python tools/story_check.py
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
