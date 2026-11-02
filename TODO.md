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
- [ ] Telegraphed big attacks ("The Titan raises its fist...") one turn ahead, giving the player a chance
      to ward or dodge.
- [ ] Unique death animations per boss.

## 4. Pop-ups and timed events
- [ ] Styled toast cards (item pickup, level up, achievement) that slide in and fade.
- [ ] Timed dialogue choices: `"timeout": 5, "on_timeout": "node_id"` on a node, with a visible countdown.
- [ ] Quick-time events: "Press SPACE to dodge!" during boss attacks; success halves damage.
      Rules side: `QuickTimeRequest(key, window_seconds)`; result feeds back into the combat step.

## 5. Minigame framework
- [ ] `rpg/core/minigames/`: pure-rules minigames (state machine + difficulty + attribute modifiers), tested.
- [ ] Dialogue effect: `{"start_minigame": "lockpick", "difficulty": 3, "on_success": "id", "on_failure": "id"}`
      handled like `start_combat` (a request the UI fulfils, then the runner branches).
- [ ] **Lockpicking** (first): pin sweeps across a bar, press SPACE in the sweet spot; each tumbler faster and
      narrower; Dexterity widens the zone; failures can break lockpicks (new consumable sold in shops).
- [ ] Forge hammer timing for the blacksmith questline.
- [ ] Rune memory sequence for the mages' forbidden vault.
- [ ] Balance meter for the Mt. Aegis ice bridge.
- [ ] Tavern card game with unique NPC decks; rare cards drop from bosses/factions.

## 6. World and exploration
- [ ] Exploration mode (ASCII map): fog-of-war over zones, hazards, secrets; lightweight movement and
      discovery loops.
- [ ] Visual set-pieces as gameplay moments: mist, snowfall, torchlight cones, collapsing bridges.

## 7. Characters
- [ ] Druid companions: tame or befriend creatures (wolf, hawk, bear, sprite) that fight alongside you
      with their own card in combat and a simple AI; companion stats scale with Wisdom/Charisma.
- [ ] Racial traits (e.g. Revenant resists poison, Dragonkin resists burn, Halfling luck, Beastkin
      bleed-on-crit) as small passives on races.
- [ ] Use Charisma more in dialogue (`{"min_stat": ["charisma", 12]}` checks for persuasion branches).

## Content gaps
- [ ] Write `forest/woman_help_take_key`, `forest/woman_help_try_to_escape`, `forest/woman_help_wait_for_help`.
- [ ] Decide on orphaned nodes: `fighters/sand_oath_ending`, `forest/woman`, `tavern/rumors`, `tavern/work`.
