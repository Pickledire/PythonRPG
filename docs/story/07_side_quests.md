# Side questlines

One per region beyond the Hearthlands (which has Brannoc's jobs). None are part of the main story, but each
sets flags and reputation the main story can pick up later. Scenes live in `dialogues/<region>/`, quest stages
in `story/quests/regions.yaml`, board entries in `story/board.yaml`.

| Region | Questline | Cast (personality) | How it plays | Flags and reputation it leaves |
|---|---|---|---|---|
| Brennhold | **The Clockwork Finch** | Pell, gnome tinker (scatterbrained, kind); Ma Vetch, moneylender (deadpan); Sergeant Holm (dull, loves forms) | Night-only market, the shell game (memory), the Watch House by day (bribe, argue, or a perfect form) or night (stealth or lockpick) | `brennhold_crowned_coin` (a coin with a crown of tails), `brennhold_watch_ledger` (the watch takes Undercity money), `finch_nim_forgiven`; rep.undercity, rep.iron_company, rep.pell |
| The Ashwood | **Ash and Antler** | Ilvaren, elf ranger (cold, proud); Hob, poacher (gentle, desperate); Rook, Grove zealot (calm, frightening) | Tracking with Wisdom, scent or nightfall; a moral choice over Hob; settle the zealot by words, kinship, a fight or betrayal; choose a reward | `ashwood_hob` (freed / helped / taught / arrested / given / betrayed), `ashwood_rook` (calmed / beaten / obeyed); rep.grove, rep.elves, rep.free_holds |
| Glassmere | **Six Years Overdue** | Fennick, librarian (anxious, pedantic); Mother Ressa, landlady (grumpy, worse on Kindlemorn); Corwin, student (grieving) | A rent-day mood, a locked door (lockpick), the singing ice (balance), a drowned sister, four ways to end it | `glassmere_book` (returned / kept), `glassmere_lissa` (rested / waiting), `glassmere_names` (someone underlined every passage about true names); rep.collegium |
| Mt. Aegis | **The Feast of the Gate** | Hilde, brewmaster (loud, jolly); Thrain (dour, grieving); Brokk, apprentice (nervous) | Goblins in the hop caves (fight, bribe, daylight, the miners' signal), a sabotage mystery, tapping the cask (timing), the drinking contest (quick-time) | `aegis_brokk` (quiet / exposed / secret), `aegis_brew_quality`, `aegis_feast` (peace / hilde / thrain); rep.holds |
| The Barrowfields | **The Gravedigger's Count** | Old Sedge (slow, morbid, dead and doesn't know it); Sister Corva, inquisitor (furious, brave) | Night-only visits, three barrows in any order, the Order's torches, a quiet ending | `barrow_burned`, `barrow_corva` (left / dawn / burned / fought), `barrow_sedge_rested`; rep.hearth_order |
| The Frostreach | **The Long Hunt** | Kesh, young hunter (eager, scared); Elder Thorvi (stern, values truth); Yrsa, shaman (odd, kind) | Earn a place at the fire (gift, endurance, words, kinship, the shaman), the stalk (stealth), the alpha, whose kill was it | `frost_kesh` (finished / honest / given / claimed), `frost_welcomed`; rep.tribes |
| The Shrieking Cliffs | **False Lights** | Keeper Morwen (paranoid, talks to her lamp); Dilly, halfling smuggler (cheerful crook) | A drowned sailor (talk if you're dead, fight if not), the cliff (agility, small hands or hours), the strongbox (lockpick), the false light (fight, bluff or a drop) | `cliffs_dilly` (ally / turned_in), `cliffs_merchant_note` (a Brennhold merchant house pays the wreckers), `cliffs_sailor_rested`; rep.undercity, rep.coast |
| The Drowned Marches | **A Wedding in the Marsh** | Captain Renn (sardonic, kind); Mira and Tamsin; Father Gully, priest (drunk); Varga, bounty hunter (cold, polite) | All talk: three errands in any order, a bounty hunter (talk, pay, fight or sell him out), a wedding (toast, gift, object) | `marches_renn` (safe / fought / sold), `marches_ring`, `marches_feast`, `marches_toast`; rep.regency, rep.free_holds |
| The Ruins of Valoria | **The Last Lesson** | Magistra Ithriel (brilliant, impatient); the Instructor, an automaton (polite, implacable); a bound soul | A rune-lock (memory), an examination scored as you answer (the answers are on the chalkboard), a soul to free, bind or leave | `valoria_exam` (passed / expelled), `valoria_soul` (freed / bound / left), `valoria_gave_crystal`; rep.collegium |
| The Emberpeaks | **Pilgrim's Road** | Sereth, dragonkin pilgrim (serene, doubting); the Scaleguard (bored); Mother Kallax (warm, certain) | An eruption (quick-time), the checkpoint (kinship, lie, tithe, the back way or a fight), the hounds, a question at the altar | `ember_sereth` (stays / leaves / wanders), `ember_answer`; rep.dragon_cult |
| Titanfell | **Cartographer's Folly** | Wendel, cartographer (cheerful, a little mad) | Three landmarks in any order (a fight or a cleverer way at each), the surveyor's glass (timing), stay or go home | `titanfell_drift` (the land is moving north), `titanfell_wendel` (stays / home) |

**Light lore.** Small things a curious player might notice, never explained: the crowned coin and the ledger
in Brennhold, the stags lying with their heads toward the deep wood, the warm halls of Aegis, the margin note
about true names, Valoria's schoolhouse, the furnace door under the Emberpeaks, the ice talking in its sleep,
and Titanfell turning over like a sleeper.

**Placeholders.** Choices that show greyed out until their content exists (`future:` conditions):
`undercity_guild`, `iron_company_guild`, `grove_initiate`, `collegium_member`, `holds_clan_friend`,
`hearth_order_member`, `free_holds_member`, `dragon_cult_sworn`. `tools/story_check.py` lists them.

**Proof they work.** `tools/story_bot.py` plays every questline dozens of times with random choices: every one
can be finished, by a strong hero or a weak, poor one.
