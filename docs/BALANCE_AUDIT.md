# Balance audit

Quests were excluded, as requested. Everything below comes from bots playing the real rules engine through
`tools/balance_sim.py`, which is in the repo so every future change can be re-measured the same way.

## How it was measured

| Experiment | Volume | What it shows |
|---|---|---|
| Progression, permadeath | 10 races × 4 builds × 25 seeds = 1,000 full runs | How far a hunting-only player gets, and what kills them |
| Progression, revive | the same 1,000 runs, but defeats are logged and the bot carries on (boss retries capped at 12) | Whether later content is beatable at all, and how many attempts it takes |
| Arena duels | 3 builds × 6 levels × 28 enemies × 15 seeds ≈ 7,500 fights | Each enemy against a player of a given level with fair gear for that level |
| Static gear tables | every weapon, armor piece and spell | Damage per swing, damage per mana, mitigation and price efficiency |

The four builds: **warrior** (Strength/Vitality), **ranger** (Dexterity/Agility), **mage** (Intelligence/Wisdom)
and **spellblade** (Strength/Intelligence).

The bots:

- **In combat**, a bot plays like a careful human. It drinks potions or casts heals when low, cures heavy
  damage-over-time, and spends mana potions as a caster. Each turn it compares a weapon swing against every
  castable spell by expected value; it only casts damage-over-time if that effect isn't already ticking, and it
  wards up against hard hitters. Boss quick-time events are modelled from the player's Reflexes.
- **Between fights**, a bot rests below 60% HP, then shops: it sells junk, repairs gear, buys the best weapon
  and armor it can afford that it meets the requirements for, buys spells (healing spells for everyone),
  keeps a level-appropriate potion stock, and spends stat points by its build.

## Headline findings (most severe first)

1. **Levelling is far too fast, and XP ignores what you fought.** A fight pays 25–150 XP × (1 + enemy STR/20),
   so a goblin pays the same as a minotaur, while a level costs only 100 + 15/level. Bots reach level 10 in
   **about 11 fights** (1.1–1.7 fights per level). Milestone bosses are gated by level, so players reach
   the Titan with starter-tier gear and about 200 gold.
2. **The bosses are walls, not climaxes.**

   | Outcome | Titan (lv 10) | Elder Dragon (lv 15) | Earth Eater Worm (lv 20) | Rat King (lv 25) |
   |---|---|---|---|---|
   | Permadeath runs that ever beat it | 0 of 1,000 | 0 | 0 | 0 |
   | Revive runs that never beat it in 12 tries | about 60% | most | most | almost all |
   | Arena win rate at its level, best shop gear | 93% | 47% | 16% | 2% |

   The only way past them today is the quest route you found (quest XP, items and stats).
3. **Normal enemies stop mattering by level 5.** They grow +5% HP and +3% damage per level while the player's
   weapon and attributes grow much faster. From level 5 to 25 a goblin dies in 2 turns and costs about 3% HP. Orcs,
   wolves and bandits cost about 10–15%, so there's nothing to learn in between bosses.
4. **Enemy stats are random, not designed.** Every enemy rolls Strength and Agility from 5–15 and defense from
   0–5 regardless of type, so a goblin can hit as hard as a minotaur. Enemy armor is flat subtraction
   (0–5), which means almost nothing. The player's armor is a percentage.
5. **The economy is flat.** Gold per fight (10–50 × a strength factor) doesn't grow with level. Median gold sits
   around 110–230 from level 1 to 27, and almost all of it goes on potions and repairs.
6. **Magic is shallow and its tiers are inverted.**
   - **Intelligence barely matters:** +1% spell damage per point, so 30 INT adds only 30%.
   - **Collegium spells lose to the general store.** Thunder Chorus (30 MP) does what Lightning Bolt does
     for 25 MP, and Meteor Lance is weaker than Lightning Bolt.
   - **Rejuvenate**, the college's premium heal, heals less than the basic shop *Heal* (68 vs 88).
   - **Aegis Ward** is *Ward* at a higher price.
   - **Boss trophy spells are the least mana-efficient spells in the game.** Dragon's Breath does 1.8 damage per
     mana against Fireball's 3.8.
   - **Damage-over-time is flat** (8–18 per turn), so against a 1,500 HP boss it's a rounding error.
   - **Bots almost only cast single-target damage.** Fire Bolt was cast 160,000 times; debuffs are almost
     never worth a turn.
7. **Item prices aren't tied to power.**
   - **Halberd** (26 damage) and **Spear** (24) cost 50g, less than half the price of weaker weapons.
     Halberd is the most-bought item in the whole sweep.
   - **Bows cost more and hit less** than melee weapons at the same tier.
   - **Mage Robes** are *Enchanted Robes* for 40g more.
   - **Cracked Iron Armor** requires Agility.
8. **The ranged build is the weakest in every race.** It reaches the Titan 20–76% of the time, against 72–92%
   for mages. The causes are the bow pricing, early fragility, and the regenerating Troll, which out-heals
   low-damage builds.
9. **Fights don't need your toolkit.** The best play is "hit, potion when low". Status effects are minor,
   enemies have no resistances or immunities, and there's nothing to cleanse, buff or debuff that changes a fight.
10. **Curios aren't a bug, but they're confusing.** Their bonuses apply automatically while carried and there's
    no limit, so carrying every charm stacks them all. You expected to equip a few; that's the better design.

## Race and build snapshot (permadeath: % of runs that reached the Titan alive)

| Race | Warrior | Ranger | Mage | Spellblade |
|---|---|---|---|---|
| Human | 68 | 48 | 72 | 80 |
| Elf | 68 | 60 | 88 | 76 |
| Orc | 72 | 68 | 76 | 80 |
| Dwarf | 80 | 76 | 92 | 72 |
| Druid | 72 | **20** | 88 | 76 |
| Halfling | 68 | 36 | 80 | 52 |
| Gnome | 76 | 76 | 84 | 76 |
| Dragonkin | 84 | 76 | 88 | 80 |
| Beastkin | 88 | 68 | 84 | 76 |
| Revenant | 68 | 36 | 76 | 68 |

Races are reasonably close to each other. The real gaps come from the build (ranged is weak, caster is strong).
Halfling and Revenant rangers suffer most, because their bonuses are in Stealth, Charisma and status resistance,
which hunting doesn't use.

## What I recommend: design targets

The goal you described is for late fights to make you use everything. That needs three numbers to line up:

| Target | Normal fights | Boss fights |
|---|---|---|
| Length | 3–6 player turns | 14–22 turns |
| HP lost | 15–35% per fight | more than your whole HP pool if you only attack |
| Pacing | you rest every 2–4 fights | you need roughly 2–4 heals or potions, a ward or two, and sustained debuffs and damage-over-time |

Weapon attacks should be the reliable baseline. Spells should be stronger per turn but cost mana. Debuffs and
damage-over-time should be what makes a boss *winnable*, not just faster.

## What I'm changing (in order)

1. **Progression.**
   - **XP and gold come from the enemy's threat** (its health × damage at its level), scaled down when you
     fight far below your level.
   - **Steeper XP curve:** about 3 fights per level early, 6–9 by the 20s. The hunting route reaches each boss
     with appropriate gear.
2. **Enemies.**
   - **Designed stats:** each enemy gets a level, Strength/Agility/defense ranges and per-level growth tuned to
     keep pace with the player.
   - **Matching armor:** enemy armor becomes a percentage, like the player's.
   - **Finer hunt pools:** level bands every five levels, with stronger affixes that can double up on elites.
   - **Matchups:** resistances (physical or magic) and status immunities, so fights reward switching tools.
3. **Bosses.** Each is retuned to a 14–22-turn fight at its level, with mechanics that call for specific tools:
   the Worm's armor wants magic, the Rat King's swarm wants cures and wards, and each Titan is immune to its
   own element's effect.
4. **Magic.**
   - **Intelligence scaling:** spell damage +4% per point above 10.
   - **Damage-over-time:** scales with the caster, and different types stack.
   - **New effects:** Haste (act twice), Weaken (enemy deals less), Expose (enemy takes more) and Silence
     (no enemy spells).
   - **Healing line:** Mend → Heal → Greater Heal, plus Renewal over time, Sanctuary, Drain Life and Purify.
     The Collegium gets the best versions, and boss trophies become top-tier.
5. **Items.**
   - **Prices from power:** every weapon, armor piece and spell is priced by formula, so new items price
     themselves.
   - **Ranged fixed:** bows and crossbows retuned to parity with melee.
6. **Equipment.**
   - **Amulet and ring slots** with a passive system: regeneration, mana regeneration, immunities,
     resistances, attribute/HP/mana bonuses, crit, lifesteal, thorns, spell power, gold/XP find, and more.
     Bonuses apply while worn and leave when removed.
   - **Curios** become equippable in 3 trinket slots instead of always-on.
7. **Content.** 25 weapons, 25 armors, 25 spells and 30 rings/amulets, with requirements, on-hit effects and
   passives.
8. **Re-measure.** Re-run the same sweeps, tune until the targets above hold, and run the test suite.

## Future-proofing

- **The simulator** is in `tools/balance_sim.py`. When you add a boss, run
  `python tools/balance_sim.py progression --runs 40` and check its win rate stays in the 40–70% band for
  bots on the first try. Real players with quests and minigames will do better than bots.
- **Prices and enemy growth are formulas**, so new items and enemies fit the curve unless you deliberately
  override them.
- **Equipment passives are a registry.** A new effect is one entry plus the hook that reads it.

---

# After the rebalance

The same simulator, re-run with every change in place: 10 races × 4 builds × 10 seeds in revive mode, plus
10 permadeath runs per pair. That's 800 playthroughs, and the tuning took six intermediate sweeps.

## Headline comparison

| | Before | After |
|---|---|---|
| Fights to reach level 10 | ~11 | ~35 |
| Fights per level (early / mid / late) | 1.1 / 1.7 / 3 | 3–5 / 6–7 / 7–9 |
| Permadeath runs that beat the Rat King | 0% | 34–73% depending on build |
| Bosses beaten on the first try (bots) | Titan ~0%; nothing after it | Titan 80–88%, Dragon 73–88%, Worm 75–97%, Rat King 46–78% |
| Normal fights: turns / HP lost / defeat rate (levels 16–25) | 8 / 72% / 58% (wrecked by under-gearing) | 6–8 / 24–28% / under 1% (boss fights excluded) |
| Median gold at level 10 / 20 | 220 / 122 | 322 / 3,000 |
| Most-bought item | Halberd (mispriced 50g) | King's Signet, then Mend and utility spells |
| Spells bots cast besides damage | almost none | Lacerate, Drain Life, Ward, Enfeeble, Renewal, Expose Weakness, Quicken, Purify |

## Boss fights now

| Boss | Bot first-try win | Median player turns | What it asks of you |
|---|---|---|---|
| Titan (lv 10) | 80–88% | 19 | Survive two telegraphed slams; each Titan is immune to its own element |
| Elder Dragon (lv 15) | 73–88% | 24 | Immune to burn, weakens you, breathes fire: cure, ward, don't rely on fire |
| Earth Eater Worm (lv 20) | 75–97% | 25 | Armored and partly physical-resistant, burrows behind a ward: magic or debuffs help |
| Rat King (lv 25) | 46–78% | 31 | Poison, haste bursts and blinding filth: cleanse, heal, burn its regeneration away |

Bots are worse players than you on the toolkit side. They never visit the Collegium, choose jewelry by a crude
heuristic and never flee, so expect real first-try rates to be somewhat higher.

## Remaining imbalance (deliberate or for later)

- **Mages are still the strongest bot build** (73% permadeath survival against about 35% for the others).
  They stack damage, heals and wards, which is the "use everything" style you want for the late game, and
  martial builds can buy into it (Mend, Ward, Renewal and Purify only need Wisdom 9–11). I'd revisit after
  companions and stamina-style martial abilities exist, rather than nerf magic further now.
- **Late gold piles up** (about 7,700 at level 25) because the best gear tops out at level 20–22. New
  late-game items, Collegium gear, enchanting or crafting will give it somewhere to go.
- **The 25+ hunt pool is shallow** (7 enemies). Your story enemies and bosses will fill it.

## What changed

**Progression and economy**
- XP and gold now come from an enemy's *threat* (√(effective HP × damage)), with a penalty for farming far
  weaker foes. A level costs 100 × level^1.15 XP, and every fifth level grants a bonus stat point.
- Shops stock gear for your level, and every item is priced by formula (`fair_value` in `catalog.py`).
- Worn gear keeps at least 70% of its power until it breaks; it used to fall to 10%.

**Combat math**
- Weapons gain +3.5% damage per point of their main attribute above 10, plus a small flat bonus.
- Spells gain +3% per point of Intelligence above 10, and healing +4% per point of Wisdom above 10.
- Damage-over-time from spells scales with the caster.
- Magic ignores 30% of enemy armor, and enemy armor is now a percentage, like the player's.
- Armor penetration scales with enemy level.
- New effects: Haste, Weaken, Expose and Silence. Fire stops regeneration.

**Enemies**
- Each enemy has a design level, its own stat ranges and per-level growth.
- 10 new hunt enemies and 7 new affixes; elites can roll two.
- Resistances, immunities, lifesteal and thorns; each Titan has an element.
- All bosses retuned.

**Equipment**
- Amulet and ring slots, plus 3 trinket slots (curios now must be equipped; three at most).
- 27 passive types (regeneration, lifesteal, thorns, immunities, resistances, spell power and more), all in
  `rpg/core/passives.py`.

**Content**
- 25 new weapons, 25 armors, 25 spells (a full healing line, Haste, debuffs, drains) and 30 rings and amulets.
- Every weapon, armor piece and spell has requirements.

## How to keep it balanced

```bash
python tools/balance_sim.py progression --runs 40                    # each race's native build
python tools/balance_sim.py progression --runs 20 --builds warrior,ranger,mage,spellblade
python tools/balance_sim.py arena --levels 10,15,20,25                 # duels against every enemy
python tools/balance_sim.py gear --attrs 18                            # weapon, armor and spell tables
```

Rules of thumb I used:

- **Normal fights:** 3–8 turns, 15–35% HP lost, under 2% bot defeats.
- **Bosses:** 45–85% first-try bot wins, and 15–30 turns.
- **New gear:** omit `value=` so the item is priced by formula, and keep its damage, defense and
  requirements inside the tier table at the top of `catalog.py`.
