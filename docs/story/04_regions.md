# Regions, hunting and bosses

Hunting is its own activity, but where you hunt and what you can find are shaped by the story.

## How hunting works

- **You hunt where you are.** Each region has its own creatures, so hunting in the Ashwood means spriggans,
  hagravens and werewolves, not goblins. The story (or your own travels) opens new regions.
- **Regions have a starting level, not a ceiling.** Each region has a minimum level its creatures are never
  weaker than: a low-level player who wanders into the Frostreach meets level-25 trolls and should run.
- **Returning is normal.** The story will send you back to regions you've already explored (a quest in the
  Hearthlands at level 40, a guild errand in the Ashwood), and you may hunt there while you're back. So enemies
  keep growing with you. A region you've explored stays a little gentler than new ground (its creatures run a
  few levels below you), but never trivial. Old regions become *understood*, not conquered.
- **Regions change over time.** As the story moves on, a region you return to may be different: Titan-spawn
  after its Titan stirs, soldiers once the war reaches it, refugees, new bounties. Coming back should show you
  what changed.
- **Grinding is allowed.** You can hunt known regions as long as you like for gold, gear and levels. Story enemies
  grow to match an over-levelled player but never shrink, so grinding helps without breaking the story.
- **Town bounty boards.** Each town posts contracts: clear a nest, kill a named beast, thin the wolves before
  the caravans leave. They pay gold and local standing, refresh over time, and react to the story (a town under
  siege posts war bounties; a town you abandoned posts none).

## Three kinds of boss

| Type | How you meet it | Repeatable? |
|---|---|---|
| **Regional bosses** | Each region has one or two champions with no story ties: a rare encounter after you've hunted there a while, or through a bounty | Once per run (NG+ brings them back) |
| **Legendary hunts** | Lore-gated. When a quest teaches you what a beast is and where it lies, a **Track** option appears in that region's hunt menu. Tracking takes a few steps (signs, tracks, a scene), then the fight, when you choose. | Once per run |
| **Story bosses** | Only inside quests, as story beats | No |

So nobody meets a Titan by grinding. You meet one after you've learned what Titans are and gone looking.

## The map and travel (built)

The map lives in [story/regions.yaml](../../story/regions.yaml): each region's starting level, its creatures
and its roads. Roads go both ways.

```
                             Titanfell
                                 |
    Shrieking Cliffs ------- Frostreach ------- Mt. Aegis ------- Emberpeaks
         |         \          /                    |                  |
         |          Glassmere -------------- Brennhold                |
         |         /                               |                  |
    Drowned Marches -- Ashwood ------------ The Hearthlands           |
         |                                         |                  |
         +------------------------------------ Barrowfields ------- Valoria
```

- **On foot** you can only go one road, to a region next door. It takes 6 hours, and about a quarter of the
  time the road brings trouble (bandits or a local creature, a cutpurse, a lost potion); sometimes luck
  (a dropped purse, a potion, an old soldier's tip).
- **By carriage** you can go anywhere, 4 hours a road. Highwaymen stop a carriage 4% of the time.
- **The fare** is 15 gold, plus 10 per road, plus hazard pay of half a gold per level of the destination's
  starting level, rounded to 5. From Emberwick: Brennhold or the Ashwood 30, the Barrowfields 35, Glassmere
  40, Mt. Aegis 45, the Drowned Marches 50, Valoria 55, the Frostreach or the Cliffs 60, the Emberpeaks 70,
  Titanfell 90. Riding home to the Hearthlands is the cheapest (25).
- **Why that price.** Hunts pay about 13 gold a fight at levels 1-3, 21 at 5, 34 at 10 and 50 at 15. A
  short ride is about two hunts early on and under one by level 10; the far, deadly places cost 5-7 early
  hunts, so nobody reaches them on pocket change.

Hunting meets the region's own creatures at your level, but never below its starting level. Familiar
creatures in a region you've outgrown are weaker for your level and pay less (rewards follow how dangerous
an enemy is), which nudges you onward. The milestone bosses (the Titan at level 10 and so on) still turn up
on any hunt until they become lore-gated legendary hunts.

## The regions

Levels are a draft. The first number is roughly where a region becomes safe to enter; the second is where the
story mostly leaves it (you'll still come back). The map should feel like a cold kingdom: lowlands in the
middle, mountains and ice to the north, ruins to the south, fire to the east.

| Region | From level | Feel | Common enemies | Regional bosses | Legendary hunt (lore-gated) | Story role |
|---|---|---|---|---|---|---|
| **The Hearthlands** | 1–10 | Farms, frozen fields, the Harrow Road, Emberwick (first hub) | Wolves, goblins, bandits, skeletons | "Old Greymaw" the giant wolf; the Bandit Queen of Harrow Road | | Origins converge; the war arrives |
| **Brennhold and the Undercity** | 5–30 | The capital above; sewers and tunnels below | Thugs, cutthroats, rat swarms, sewer ghouls | The Gutter Hydra (a rumour that turns out true) | | Politics, the Iron Company's headquarters (built over the Undercity's heart, on purpose), the Undercity, the Rat King (story boss) |
| **The Ashwood** | 8–22 | Ancient dark forest, freezing from the roots | Spriggans, hagravens, cave bears, werewolves | The Hag Mother (hagraven coven queen) | **Forgin, Titan of Earth** | The Grove; the first Titan and your first word (Act I climax) |
| **Glassmere** | 10–25 | A frozen lake, the Collegium's great tower, a scholars' town | Harpies, wraiths, escaped arcane experiments | The Unbound Familiar | | The Collegium questline |
| **Mt. Aegis and the Holds** | 15–35 | The dwarven mountain: gates, halls, deep mines | Trolls, ogres, giants, stone golems, deep goblins | Stonejaw the Troll King | **The Earth Eater Worm** | The dwarves; the Worm; (much later) the secret of the mountain |
| **The Barrowfields** | 15–30 | Burial mounds and the old graveyard, never quiet | Skeletons, barrow wights, wraiths, the Ghost Horror | The Barrow-King | | The restless dead, the Hearth Order, Revenants |
| **The Frostreach** | 25–45 | The north: glaciers, beastkin tribes, endless white | Frost trolls, ice wolves, beastkin raiders, wraiths | The Frost Giant chieftain | **Herix, Titan of Ice** | The north and the Free Holds' heartland |
| **The Shrieking Cliffs** | 30–45 | Wind-carved sea cliffs | Harpies, wyverns, storm spirits | The Harpy Matriarch | **Vexer, Titan of Wind** | Smugglers' coast; the Undercity's routes |
| **The Drowned Marches** | 30–50 | Frozen swamp and sunken villages | Basilisks, wyverns, bog creatures, deserters | The Bog Witch | **Titan of Shadow** | Refugees, deserters, the war's ugliest corner |
| **The Ruins of Valoria** | 40–60 | The fallen empire in the south, preserved in ice and light | Wights, wraith lords, golems, Valorian constructs | The Clockwork Colossus | **The Valorian Warden** | The Lich Regent (story boss) and the Titan of Light (story) |
| **The Emberpeaks** | 45–65 | Volcanic peaks in the east, the only warm place left | Fire elementals, young dragons, wyverns, dragon-cultists | The Molten Tyrant (a fire giant) | **The Elder Dragon**; **Olgath, Titan of Fire** | The dragons and the Dragon's Pact |
| **Titanfell** | 65–80 | The shattered far north where the land itself has moved | The strongest wild elites | Rotating apex beasts | **Zodd, Titan of Darkness**; **Implex, Titan of Chaos** | Endgame; NG+ |

## The bosses we already have, re-placed

| Boss | Was | Becomes |
|---|---|---|
| Titan (random element) | Forced at level 10 on any hunt | Eight Titans, each a lore-gated legendary hunt in its own region (one is an Act I story climax) |
| Elder Dragon | Forced at level 15 | A legendary hunt and story figure in the Emberpeaks (Act III), and the key to the Dragon's Pact |
| Earth Eater Worm | Forced at level 20 | A legendary hunt under Mt. Aegis, unlocked by the dwarves' questline (Act II) |
| Rat King | Forced at level 25 | A story boss in the Undercity questline (Act II), or your fate in the Rat King ending |
| Valorian Warden | Story only | A legendary hunt guarding Valoria's gate (Act III) |
| Lich Regent | Story only | The story boss beneath Valoria, and the Lich ending |
| Clockwork Colossus | Story only | Valoria's regional boss |
| Stone Sentinel | Test quest | An early regional or story boss in Hearthlands ruins |
| Ghost Horror | Idle haunting | Stays as camp folklore, and becomes a Barrowfields regular |

## The creatures (built)

Every region now has ten creatures of its own on top of a few from the original roster: 120 new in all, half
new species (the Hollow Scarecrow, the Gutter Knight, the Mad Dwarf, the Echo of Stone) and half variants of
existing ones (the Bandit Cutthroat, the Feral Frost Bear, the Wight Huskarl). They're defined in
`rpg/core/creatures.py`, hunted per `story/regions.yaml`, and described in the Bestiary with lore from
`story/bestiary.yaml`. Regional bosses and legendary hunts are still to come.

## New enemies we'll need (the original list)

The current roster covers beasts and monsters well, but a war story needs people to fight, and each region
needs its own flavour:

- **People:** soldiers and officers of each political side, deserters, cutthroats, cultists, inquisitors,
  rogue mages, beastkin raiders.
- **The Undercity:** rats in every size, rat swarms, sewer ghouls, the Rat King's knights.
- **Ice and north:** ice wolves, frost wraiths, glacier crawlers.
- **Titan-spawn:** small stone creatures shaken loose by a waking Titan, one family per element. They become
  common in a region once its Titan stirs, so the world visibly changes.
