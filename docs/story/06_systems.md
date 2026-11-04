# What the engine needs

The story bible above asks for systems the game doesn't have yet. This is the list for the coding side, in the
order I'd build them. None of it replaces what exists; the dialogue nodes, combat, minigames, items and
balance tools all carry over.

## 1. The story's memory (needed by everything else)

| System | Why the story needs it |
|---|---|
| **The Ledger** | Numbers as well as flags: reputation per faction, values, guild rank, arc stage, war state. Effects like `add rep.collegium 5`; conditions like `rep.collegium >= 20`. |
| **Visit tracking and "once"** | Node effects fire once unless marked repeatable (this closes most of today's exploits), and scenes can check "have you been here" for first-visit and return lines. |
| **Conditional text** | One node, many lines: race-specific lines, echoes of earlier choices, `{player}` and `{race}` in text, without duplicating nodes. |
| **Locked choices shown greyed** | `[Requires Collegium rank 3]` or `[The Wardens no longer trust you]` visible but disabled; truly secret choices stay hidden. |
| **Quests and arcs as data** | A quest file with availability, stages, journal text, which quests exclude each other, and act gates, instead of the Python list in `session.py`. A journal screen to read them. |
| **Writer-friendly files** | YAML with many nodes per file and comments, instead of one JSON file per node. JSON keeps loading. |

## 2. The world map

| System | Why |
|---|---|
| **Regions and travel** | Where you are decides your hunts, shops, bounties and quests. Travel between known regions; the story opens new ones. |
| **Towns as hubs** | Emberwick replaces "the camp". Each town has its own inn (rest), shop stock, bounty board and quest-givers. |
| **Region hunts** | Each region's enemy pool and level range (enemies match your level within it). |
| **Bounty boards** | Per-town contracts that refresh and react to the story. |
| **Regional bosses** | Rare encounters or bounties, once per run. |
| **Track legendary hunts** | A Track option that appears in a region's hunt menu once a lore flag is set; a few tracking scenes, then the fight. Replaces the forced level-10/15/20/25 bosses. |

## 3. Factions

| System | Why |
|---|---|
| **Reputation** | Standing per faction; prices, stock, who talks to you, which quests appear. |
| **Guild membership** | Ranks, the rivalry rule (joining one closes its rival), the one-master rule, betrayal scenes. |
| **Members-only shops** | Each guild hall sells its own stock by rank (the Collegium shop becomes one of these). |
| **Allegiance** | Your side in the war (or Unsworn), locked at the end of Act II. |
| **Race reactivity** | Price modifiers, guard lines and race-only choices, all driven by data. |

## 4. Structure and endings

| System | Why |
|---|---|
| **Origins** | A race-specific starting scene chosen at character creation, converging on Emberwick. |
| **Acts and the point of no return** | Act gates, the commitment scene, and path locking with the deep-requirement exceptions. |
| **Endings** | Assembled from mythic, realm and personal fate, with conditional epilogue entries and a final screen. Any scene can also end the run on the spot (the house in Emberwick): autosave, roll the ending, record it. |
| **Titan words** | A learned list, shown as glyphs in the journal; conditions like `knows_word forgin`; later a rare combat ability. The stone-cost is the count of words: it drives description, NPC reactions and choices, never stats. |
| **Story tools** | A flag and variable registry (catches typos), an expanded linter (unreachable nodes, dead ends, repeatable rewards), a diagram export to see the story graph, and a **story bot** that explores the choices to prove every ending is reachable and every lock holds. |

## 5. Rebalance for level 80

The current numbers are tuned for level 25. Once the structure is set: a new XP curve, about three more gear
tiers, enemy growth to 80, story XP and rewards included, and new enemy families (soldiers, rats, ice, Titan-
spawn). The balance simulator re-runs it like last time, now walking region to region.

## 6. Later

The meta profile across runs (which endings you've seen, starting with the house), NG+, meeting your old self,
the Mountain Wakes ending, companions (the Druid's
animal companions first).

## Suggested order

1. The Ledger, visit tracking and "once", conditional text, greyed choices, quests as data, YAML.
2. The story tools (registry, linter, story bot, diagram export).
3. Regions, towns, travel, region hunts, bounties, regional bosses and Track.
4. Reputation, guilds and allegiance.
5. Origins and endings.
6. Clear out the old test dialogue, build the spine (placeholder scenes from origin to every ending), and prove
   it with the story bot.
7. Write Act I for real, starting with two or three origins.
8. Rebalance for level 80.
