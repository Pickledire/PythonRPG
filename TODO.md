# Roadmap

Planned work for the Textual version (`rpg/`). Rules go in `rpg/core/` with tests; drawing goes in `rpg/ui/`.
UI-only effects are triggered the same way dialogue `visual` effects already are: the rules emit a
request, the UI fulfils it.

## 1. Pixel art from Aseprite (sprite pipeline)
- [ ] `assets/sprites/` folder; export from Aseprite with **File → Export Sprite Sheet** + "JSON Data"
      (array or hash) so frame rectangles, durations and animation tags come along.
- [ ] Add Pillow to `requirements.txt` (PNG loading).
- [ ] `rpg/ui/sprites.py`: load an Aseprite sheet + JSON, slice frames, convert each frame to half-block
      (`▀`) cells once (2 pixels per cell, true color, transparent pixels keep the background), cache the result.
- [ ] `Sprite` widget: plays an animation tag (`idle`, `attack`, `hurt`, `death`, `enraged`) using the
      frame durations from Aseprite; loop vs. play-once; emits a message when a one-shot finishes.
- [ ] Optional `sprite` field on `EnemyTemplate` (and on races for player portraits); falls back to text
      when missing.
- [ ] Show sprites on: combat cards, boss intro, encounter card, title screen, camp scene, race preview
      on character creation, small item icons in shop/inventory.
- [ ] Size guidance in the README: 32×32 = 32 cols × 16 rows, 48×48 = 48 × 24, 64×64 for full-screen bosses.
- [ ] Optional high-resolution path via `textual-image` (Kitty / Sixel / iTerm2 protocols) with half-block
      fallback.

- [ ] Replace the generated boss portraits (`tools/make_boss_art.py`) with Aseprite sprites as they're drawn;
      keep the generated ones as fallbacks.

## 2. Combat feel
- [ ] Screen shake on big hits/crits (animate the arena's `offset`).
- [ ] Hit flash: sprite briefly tinted white/red (auto-generated tinted frames, no extra art needed).
- [ ] Floating damage numbers over the target (overlay layer, drift up and fade); crits bigger/gold,
      heals green, DoT ticks in the effect's color.
- [ ] Status overlays: flames on burning cards, bubbles for poison, drips for bleed, frost creeping
      over frozen cards, shimmer for wards.
- [ ] Turn-change transitions (enemy card pulses during its turn).

## 3. Boss presentation
- [ ] Cinematic intros: sprite fades in from black while story text types out, then the name slams in.
- [ ] Boss phases in the rules (`EnemyTemplate.phases`): at HP thresholds switch animation tag, gain moves
      or affixes, change music-less "mood" (border color, effects); log line + screen shake on transition.
- [x] Telegraphed big attacks answered with quick-time events (`QTETrigger` on `EnemyTemplate`): the Titan,
      Elder Dragon, Earth Eater Worm, Rat King and the Stone Sentinel each have two.
- [ ] Telegraph one turn *ahead* as an alternative (time to ward or drink a Quicksilver Draught first).
- [ ] Unique death animations per boss.

## 4. Pop-ups and timed events
- [ ] Styled toast cards (item pickup, level up, achievement) that slide in and fade.
- [ ] Timed dialogue choices: `"timeout": 5, "on_timeout": "node_id"` on a node, with a visible countdown.
- [x] Quick-time events during boss attacks (`CombatSession.pending_qte` / `resolve_qte`) and in dialogue
      (`{"minigame": {"type": "qte", ...}}`).

## 5. Minigame framework
- [x] `rpg/core/minigames/`: pure state machines, tested, driven by a `SkillCheck` (attributes + race + gear +
      primed tonics, plus traits). Six kinds: quick-time event, lockpicking, precision timing, memory (mouse
      only), balance, stealth (silence meter).
- [x] Dialogue effect `{"minigame": {...}}` with success / partial / failure / retreat routing and a story flag.
- [x] Skills, race bonuses and traits (`rpg/core/skills.py`, `RACE_SKILLS` / `RACE_TRAITS` in config).
- [x] Gear and items: lockpicks (3 qualities), skill tonics, carried tools and charms, stealthy and
      acrobatic armor, loud heavy armor.
- [x] Briefing screen (odds, where every point comes from, drink a tonic first) and a test quest
      (*The Sunken Vault (trial run)* with a practice hall).
- [ ] Replace the trial run with real placements: lockpicking in Valoria, rune memory for the mages'
      forbidden vault, balance on the Mt. Aegis ice bridge, stealth in the graveyard, precision for the
      fighters' archery contest.
- [ ] Clothing / accessory slots (cloak, boots, gloves, ring): add a `Slot` and an item class; skill bonuses
      and traits already apply to anything in `inventory.equipped`.
- [ ] Minigame sprites once the Aseprite pipeline exists (lock face, rune tiles, the hunter in stealth).
- [ ] Tavern card game with unique NPC decks; rare cards drop from bosses/factions (needs deck rules).

## 6. World and exploration
- [ ] Exploration mode (ASCII map): fog-of-war over zones, hazards, secrets; lightweight movement and
      discovery loops.
- [ ] Visual set-pieces as gameplay moments: mist, snowfall, torchlight cones, collapsing bridges.

## 7. Characters
- [ ] Druid companions: tame or befriend creatures (wolf, hawk, bear, sprite) that fight alongside you
      with their own card in combat and a simple AI; companion stats scale with Wisdom/Charisma.
- [x] Racial minigame traits (Halfling small frame, Revenant breathless, Gnome tinker, Dwarf stoneborn...).
- [ ] Racial *combat* passives (e.g. Revenant resists poison, Dragonkin resists burn, Halfling luck,
      Beastkin bleed-on-crit), using the same trait channel.
- [ ] Use Charisma more in dialogue (`{"min_stat": ["charisma", 12]}` checks for persuasion branches).

## 8. Presentation and settings
- [x] Settings screen: themes, difficulty, turn timer, trial reaction time, pacing, skip intros, reduced motion.
- [ ] Font size and style: ship a Windows Terminal profile fragment (font, size, colors, maybe a background
      image) and have `run_game.bat` launch the game with it.
- [ ] Ironman difficulty (save deleted on death), autosave after resting or finishing a quest, key remapping
      for trials (arrows vs WASD), a colorblind-safe palette for stat colors and meters.
- [ ] Rework the stealth trial (feedback: "slightly iffy").

## 9. Balance follow-ups (see docs/BALANCE_AUDIT.md)
- [x] Threat-based XP/gold, steeper XP curve, level-aware shops, priced-by-power items, durability softened.
- [x] Designed enemy stats, 10 new hunt enemies, 13 affixes, resistances/immunities, boss retune.
- [x] Amulet, ring and 3 trinket slots with passives; 25 weapons, 25 armors, 25 spells, 30 jewelry.
- [ ] Martial abilities (stamina techniques: cleave, shield bash, aimed shot) so non-casters have a toolkit
      as deep as spells. Bots show mages are still the strongest build.
- [ ] Late-game gold sinks: enchanting/upgrading gear, Collegium tuition, rare merchant stock.
- [ ] More level 25+ hunt enemies as the story adds regions.
- [ ] Teach the simulator to visit the Collegium and use quests, then re-run the sweep.

## Content gaps
- [ ] Write `forest/woman_help_take_key`, `forest/woman_help_try_to_escape`, `forest/woman_help_wait_for_help`.
- [ ] Decide on orphaned nodes: `fighters/sand_oath_ending`, `forest/woman`, `tavern/rumors`, `tavern/work`.
