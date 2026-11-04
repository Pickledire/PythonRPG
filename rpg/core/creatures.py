"""The creatures of each region (ten per region), registered with ``ENEMIES`` alongside the originals.

Two ways to make one:

- ``creature(...)``: a new species. Its numbers come from a curve fitted to the original roster at its design
  level, shaped by a role (a brute hits hard and soaks damage, a skirmisher is quick and fragile, ...), so new
  creatures sit in line with the old ones.
- ``variant(base, ...)``: a twist on an existing creature (a Bandit Cutthroat from a Bandit), with its numbers
  nudged and traits added.

Like every template, the numbers describe the creature *at its design level*; hunts scale it to the player's
level and to the region's starting level (see ``story/regions.yaml``). Their lore lives in
``story/bestiary.yaml``. Names avoid the elite-modifier words (Enraged, Armored, Swift, Venomous, ...) because
those are added as prefixes.
"""

from __future__ import annotations

import dataclasses
import math

from rpg import config
from rpg.core.effects import EffectKind, EffectSpec
from rpg.core.enemies import UNDEAD, EnemyTemplate, _spell
from rpg.core.items import SpellType

P, M = "physical", "magic"

# Health and damage of an ordinary creature at its design level (fitted to the original roster).
STD_HP = ((1, 40), (3, 58), (6, 95), (10, 135), (14, 190), (18, 215), (24, 250))
STD_DAMAGE = ((1, 7.5), (3, 11), (6, 14.5), (10, 19), (14, 21.5), (18, 22.5), (24, 25))

# role: (health x, damage x, strength +/-, agility +/-, defense band, spell chance)
ROLES = {
    "brute": (1.3, 1.1, 4, -3, "high", None),
    "hunter": (1.0, 1.0, 1, 3, "low", None),
    "skirmisher": (0.8, 0.95, -2, 6, "low", None),
    "soldier": (1.05, 1.0, 2, 0, "mid", None),
    "tank": (1.25, 0.95, 4, -6, "very high", None),
    "caster": (0.8, 0.85, -4, 0, "low", 0.45),
    "spirit": (0.85, 0.95, -2, 3, "low", 0.35),
    "swarm": (0.7, 0.8, -3, 7, "none", None),
}


def _curve(points: tuple[tuple[int, float], ...], level: int) -> float:
    if level <= points[0][0]:
        return points[0][1]
    for (l0, v0), (l1, v1) in zip(points, points[1:]):
        if level <= l1:
            return v0 + (v1 - v0) * (level - l0) / (l1 - l0)
    (l0, v0), (l1, v1) = points[-2], points[-1]
    return v1 + (v1 - v0) / (l1 - l0) * (level - l1)


def _defense(band: str, level: int) -> tuple[int, int]:
    low = {"none": 0, "low": level * 0.25, "mid": level * 0.5 + 2, "high": level * 0.7 + 4,
           "very high": level + 8}[band]
    return int(low), int(low) + (1 if band == "none" else 3)


def creature(template_id: str, name: str, kind: str, role: str, level: int, description: str,
             **traits) -> EnemyTemplate:
    hp_x, dmg_x, str_d, agi_d, band, spell_chance = ROLES[role]
    hp = _curve(STD_HP, level) * hp_x * traits.pop("hp", 1.0)
    damage = _curve(STD_DAMAGE, level) * dmg_x * traits.pop("dmg", 1.0)
    stat = 6 + 0.55 * level
    strength, agility = max(2, round(stat + str_d)), max(2, round(stat + agi_d))
    if spell_chance is not None:
        traits.setdefault("spell_chance", spell_chance)
    return EnemyTemplate(
        template_id, name, (round(hp * 0.95), round(hp * 1.05)), (math.floor(damage * 0.93), math.ceil(damage * 1.07)),
        kind, description, level=level, strength=(strength - 1, strength + 1), agility=(agility - 1, agility + 1),
        defense=_defense(band, level), **traits)


def _scaled(value, factor: float):
    if isinstance(value, tuple):
        return tuple(max(1, round(v * factor)) for v in value)
    return max(1, round(value * factor))


def variant(base: EnemyTemplate, template_id: str, name: str, description: str, *, hp: float = 1.0,
            dmg: float = 1.0, level: int | None = None, strength: int = 0, agility: int = 0, defense: int = 0,
            **changes) -> EnemyTemplate:
    """A twist on ``base``: health and damage multiplied, stats nudged, any other field replaced."""
    if level is not None and level != base.level:  # keep it as strong *for its level* as the original
        hp *= _curve(STD_HP, level) / _curve(STD_HP, base.level)
        dmg *= _curve(STD_DAMAGE, level) / _curve(STD_DAMAGE, base.level)
        shift = round(0.55 * (level - base.level))
        strength, agility = strength + shift, agility + shift
    nudge = lambda r, d: (max(1, r[0] + d), max(1, r[1] + d)) if isinstance(r, tuple) else max(1, r + d)  # noqa: E731
    return dataclasses.replace(
        base, template_id=template_id, name=name, description=description, hp=_scaled(base.hp, hp),
        damage=_scaled(base.damage, dmg), level=level or base.level, strength=nudge(base.strength, strength),
        agility=nudge(base.agility, agility), defense=nudge(base.defense, defense), aliases=(), title_variants=(),
        intro_title="", intro_lines=(), reward_choices=(), guaranteed_drops=(), qte_triggers=(), is_boss=False,
        **changes)


bleed = lambda p, t, c: EffectSpec(EffectKind.BLEED, p, t, c)  # noqa: E731
poison = lambda p, t, c: EffectSpec(EffectKind.POISON, p, t, c)  # noqa: E731
burn = lambda p, t, c: EffectSpec(EffectKind.BURN, p, t, c)  # noqa: E731
freeze = lambda c: EffectSpec(EffectKind.FROZEN, 0, 1, c)  # noqa: E731
blind = lambda c: EffectSpec(EffectKind.BLIND, 0.25, 2, c)  # noqa: E731
weaken = lambda c: EffectSpec(EffectKind.WEAKEN, 0.2, 2, c)  # noqa: E731
CONSTRUCT = (EffectKind.POISON, EffectKind.BLEED, EffectKind.BLIND)
ward = EffectSpec(EffectKind.SHIELD, 0.25, 3)
haste = EffectSpec(EffectKind.HASTE, 1, 2)


def build(original: dict[str, EnemyTemplate]) -> list[EnemyTemplate]:
    """Every region creature. ``original`` is the roster so far, for variants."""
    made: dict[str, EnemyTemplate] = {}

    def base(template_id: str) -> EnemyTemplate:
        return made.get(template_id) or original[template_id]

    def add(*templates: EnemyTemplate) -> None:
        for t in templates:
            made[t.template_id] = t

    # ============================================================ the Hearthlands (from level 1)
    add(
        variant(base("bandit"), "bandit_cutthroat", "Bandit Cutthroat",
                "A thin, quick bandit with a curved knife and no interest in talking.", hp=0.8, dmg=1.05,
                agility=4, defense=-2, on_hit=(bleed(4, 3, 0.3),)),
        variant(base("bandit"), "bandit_archer", "Bandit Archer",
                "Shoots from behind the hedgerows and runs when you get close.", hp=0.75, level=2, agility=5,
                defense=-3, on_hit=(blind(0.12),)),
        variant(base("goblin"), "goblin_firestarter", "Goblin Firestarter",
                "A goblin with a lit torch and a terrible idea.", hp=0.9, spell_chance=0.35,
                spellbook=(_spell("Flung Torch", SpellType.BURN, 5, "Burning pitch, thrown badly"),)),
        variant(base("skeleton"), "frostbitten_skeleton", "Frostbitten Skeleton",
                "Bones that lay in a frozen field all winter. The cold came up with them.", level=2,
                immune=(*UNDEAD, EffectKind.FROZEN), on_hit=(freeze(0.08),), resist=((P, -0.15),)),
        creature("regency_enforcer", "Regency Enforcer", "humanoid", "soldier", 3,
                 "A tax collector's muscle in the Regent's colours. Here for the harvest, and anything else.",
                 hp=1.1),
        creature("deserter", "Deserter", "humanoid", "hunter", 2,
                 "A soldier who walked away from someone's war. Hungry, scared, and still armed.",
                 on_hit=(bleed(3, 2, 0.2),)),
        creature("hollow_scarecrow", "Hollow Scarecrow", "construct", "brute", 3,
                 "Straw, sackcloth and a pumpkin grin, walking on its own. Something told it to.",
                 immune=(EffectKind.POISON, EffectKind.BLEED), resist=((P, 0.2), (M, -0.3))),
        creature("tusked_boar", "Tusked Boar", "beast", "brute", 2,
                 "A wild boar gone lean and mean in the long winter. It charges first and never thinks.",
                 on_hit=(bleed(4, 2, 0.2),)),
        creature("crow_swarm", "Crow Swarm", "beast", "swarm", 1,
                 "A black cloud of crows grown bold on the frozen dead.", on_hit=(blind(0.2),)),
        creature("hedge_witch", "Hedge Witch", "witch", "caster", 4,
                 "A village wise-woman who went too far into the old ways, and liked it there.",
                 spellbook=(_spell("Rotting Curse", SpellType.POISON, 6, "Your blood turns sour"),
                            _spell("Hedge Hex", SpellType.WEAKEN, 0, "Your arm forgets its strength"))),
    )

    # ============================================================ Brennhold and the Undercity (from level 5)
    add(
        creature("undercity_thug", "Undercity Thug", "humanoid", "brute", 5,
                 "Broad, bored and paid by the bone. The Undercity's first and least subtle answer."),
        creature("rat_swarm", "Rat Swarm", "beast", "swarm", 5,
                 "A tide of rats pouring out of a drain, all teeth and no fear.", on_hit=(poison(3, 3, 0.25),)),
        creature("sewer_ghoul", "Sewer Ghoul", "undead", "hunter", 6,
                 "Something that was a person once, and now lives on what floats past in the dark.",
                 immune=UNDEAD, on_hit=(poison(4, 3, 0.3),)),
        creature("gutter_knight", "Gutter Knight", "humanoid", "tank", 7,
                 "A man in rusted plate who never takes the helm off. Rats nest in the gaps of his armour.",
                 on_hit=(poison(4, 3, 0.2),)),
        variant(base("cellar_rat"), "plague_rat", "Plague Rat",
                "A bloated rat with weeping eyes. Whatever it has, it wants to share.", level=5,
                on_hit=(poison(4, 3, 0.35),)),
        variant(base("bandit"), "undercity_smuggler", "Undercity Smuggler",
                "Knows every tunnel under the capital and doesn't want you knowing any of them.", level=5,
                agility=3, on_hit=(blind(0.15),)),
        variant(base("regency_enforcer"), "corrupt_watchman",
                "Corrupt Watchman", "City watch by day. By night, the same club, a different employer.",
                level=6, hp=1.05),
        creature("cutpurse", "Cutpurse", "humanoid", "skirmisher", 4,
                 "Small, fast, and gone before you notice your purse is lighter.", hp=0.9),
        creature("gutter_mage", "Gutter Mage", "humanoid", "caster", 6,
                 "Thrown out of the Collegium, or never let in. Sells spells by the hour in the back alleys.",
                 spellbook=(_spell("Cinder Spit", SpellType.BURN, 7, "A mouthful of sparks"),
                            _spell("Hush", SpellType.SILENCE, 0, "Your words stick in your throat"))),
        creature("sewer_leech", "Sewer Leech", "beast", "hunter", 6,
                 "A leech as long as your arm, clinging to the walls of the deep drains.", lifesteal=0.25,
                 resist=((M, -0.2),)),
    )

    # ============================================================ the Ashwood (from level 8)
    add(
        variant(base("spriggan"), "spriggan_matron", "Spriggan Matron",
                "An old spriggan, bark gone grey, who mends her children as fast as you cut them.", level=9,
                spell_chance=0.4,
                spellbook=(_spell("Sap Mending", SpellType.HEAL, 40, "The bark knits shut"),
                           _spell("Briar Snare", SpellType.BLEED, 7, "Thorns that bite and hold"))),
        creature("pine_stalker", "Pine Stalker", "beast", "skirmisher", 8,
                 "A grey lynx the size of a pony that hunts from the branches.", on_hit=(bleed(5, 3, 0.3),)),
        variant(base("cave_bear"), "ashwood_grizzly", "Ashwood Grizzly",
                "Too hungry to sleep through the winter, and angry about it.", hp=1.05, dmg=1.05),
        variant(base("hagraven"), "hagraven_sister", "Hagraven Sister",
                "A younger hagraven, feathers still coming in. She learned the blinding hexes first.",
                hp=0.85, level=8,
                spellbook=(_spell("Feather Storm", SpellType.BLIND, 0, "Black feathers fill your eyes"),
                           _spell("Venom Hex", SpellType.POISON, 8, "Rot that walks"))),
        creature("wisp", "Wisp", "spirit", "spirit", 8,
                 "A cold blue light between the trees that drifts away when you follow it. Then it doesn't.",
                 immune=(*UNDEAD, EffectKind.BURN), resist=((P, 0.35), (M, -0.25)),
                 spellbook=(_spell("Witchlight", SpellType.BLIND, 0, "Light that blinds and lingers"),
                            _spell("Cold Fire", SpellType.DAMAGE, 12, "It burns like ice"))),
        creature("rimebark_treant", "Rimebark Treant", "fae", "tank", 10,
                 "A young tree that pulled up its roots when the frost reached them, and walked.",
                 immune=(EffectKind.BLEED, EffectKind.POISON), resist=((P, 0.15), (M, -0.2)), regen_pct=0.03),
        creature("ashwood_weaver", "Ashwood Weaver", "beast", "hunter", 9,
                 "A spider as big as a dog, spinning webs across the old paths.", on_hit=(poison(6, 3, 0.35),),
                 spell_chance=0.25, spellbook=(_spell("Web", SpellType.FREEZE, 0, "Sticky silk binds your legs"),)),
        variant(base("werewolf"), "young_werewolf", "Young Werewolf",
                "Bitten last autumn. Still learning what it is, and how much it likes it.", level=10, hp=0.9),
        creature("grove_zealot", "Grove Zealot", "humanoid", "caster", 10,
                 "A druid of the hard old ways, who believes the forest should eat the towns back.",
                 spellbook=(_spell("Thorn Burst", SpellType.BLEED, 7, "The ground grows spikes"),
                            _spell("Bark Skin", SpellType.SHIELD, 0, "Wood creeps over skin"),
                            _spell("Wild Growth", SpellType.REGEN, 0, "The forest feeds its own"))),
        variant(base("wolf"), "shadow_wolf", "Shadow Wolf",
                "A black wolf that runs with the dark between the pines. You see the eyes first.", level=8,
                on_hit=(bleed(5, 3, 0.25), blind(0.12))),
    )

    # ============================================================ Glassmere (from level 10)
    add(
        creature("rogue_apprentice", "Rogue Apprentice", "humanoid", "caster", 10,
                 "A Collegium student who stole a book above their year and can't stop reading it.",
                 spellbook=(_spell("Frost Bolt", SpellType.FREEZE, 0, "A shard of the lake"),
                            _spell("Arcane Dart", SpellType.DAMAGE, 14, "Fast, sharp, badly aimed"))),
        variant(base("wraith"), "mere_shade", "Shade of the Mere",
                "Someone who went through the ice. They still walk the lake, looking for the hole.",
                on_hit=(freeze(0.1),), immune=(*UNDEAD, EffectKind.FROZEN)),
        creature("runebound_sentry", "Runebound Sentry", "construct", "tank", 12,
                 "A Collegium guardian of carved stone and glowing runes, left on watch long after its masters "
                 "forgot it.", immune=CONSTRUCT, resist=((M, 0.35), (P, -0.15))),
        creature("mana_wyrm", "Mana Wyrm", "aberration", "skirmisher", 11,
                 "A serpent of pure, raw magic that leaked out of the Collegium's tower and won't go back.",
                 resist=((M, 0.4), (P, -0.25)), spell_chance=0.3,
                 spellbook=(_spell("Spell Bite", SpellType.SILENCE, 0, "It eats the words out of your mouth"),)),
        creature("ice_lurker", "Ice Lurker", "beast", "brute", 11,
                 "It waits under the ice for the sound of footsteps. Then the ice isn't there.",
                 immune=(EffectKind.FROZEN,), on_hit=(bleed(6, 3, 0.25),),
                 starts_with=(EffectSpec(EffectKind.HASTE, 1, 1),)),
        variant(base("harpy"), "harpy_screecher", "Harpy Screecher",
                "Her scream carries across the whole lake. Up close it does worse.", level=10, spell_chance=0.45),
        creature("stitched_familiar", "Stitched Familiar", "aberration", "hunter", 12,
                 "Three animals and a spell, sewn together by a student who wanted a better cat.",
                 on_hit=(bleed(5, 3, 0.2), poison(5, 3, 0.2))),
        variant(base("ashwood_weaver"), "glass_spider",
                "Glass Spider", "A spider you can see straight through, with webs like frost on a window.",
                level=10, defense=-1, on_hit=(poison(7, 3, 0.35),), immune=(EffectKind.FROZEN,)),
        creature("frost_sprite", "Frost Sprite", "fae", "swarm", 10,
                 "A tiny, giggling thing of snow and spite. They come in threes.", immune=(EffectKind.FROZEN,),
                 spell_chance=0.35, spellbook=(_spell("Rime Kiss", SpellType.FREEZE, 0, "Frost on your lips"),)),
        creature("wandering_grimoire", "Wandering Grimoire", "construct", "caster", 13,
                 "A spellbook that walked out of the Collegium library on its own pages. It reads itself aloud.",
                 immune=CONSTRUCT, resist=((M, 0.2),),
                 spellbook=(_spell("Recite: Burn", SpellType.BURN, 9, "The words catch fire"),
                            _spell("Recite: Hush", SpellType.SILENCE, 0, "A page turns, and you can't speak"),
                            _spell("Recite: Ward", SpellType.SHIELD, 0, "Binding glyphs"))),
    )

    # ============================================================ Mt. Aegis and the Holds (from level 15)
    add(
        creature("mad_dwarf", "Mad Dwarf", "humanoid", "brute", 14,
                 "A miner who went too deep and heard something in the rock. He's been digging toward it since.",
                 starts_with=(haste,), on_hit=(bleed(6, 3, 0.25),)),
        variant(base("goblin"), "deep_goblin", "Deep Goblin",
                "Pale and big-eyed from generations in the dark. It doesn't need a torch to find you.",
                level=13, hp=1.1, immune=(EffectKind.BLIND,)),
        variant(base("goblin"), "deep_goblin_shaman", "Deep Goblin Shaman",
                "Wears a necklace of dwarven teeth and talks to the dark. Sometimes it answers.", level=14,
                hp=0.85, immune=(EffectKind.BLIND,), spell_chance=0.45,
                spellbook=(_spell("Cave Curse", SpellType.WEAKEN, 0, "The weight of the mountain"),
                           _spell("Fungal Rot", SpellType.POISON, 9, "Spores in your lungs"))),
        creature("holdguard_automaton", "Holdguard Automaton", "construct", "tank", 16,
                 "A dwarf-forged guardian of brass and stone, still walking the patrol it was given a thousand "
                 "years ago.", immune=CONSTRUCT, resist=((P, 0.25), (M, -0.2))),
        variant(base("troll"), "stonehide_troll", "Stonehide Troll",
                "A troll that rolled in quarry dust until its skin set like mortar.", level=14, defense=6,
                resist=((P, 0.15),)),
        variant(base("ogre"), "ogre_mauler", "Ogre Mauler",
                "An ogre with a mine cart's axle for a club. It has swung it at a lot of dwarves.", dmg=1.1,
                level=15),
        creature("tunnel_crawler", "Tunnel Crawler", "beast", "tank", 15,
                 "A plated centipede as long as a mine shaft. The miners hear it in the walls.",
                 on_hit=(poison(7, 3, 0.25),)),
        variant(base("giant"), "hill_giant", "Hill Giant",
                "Lives on the mountain's lower slopes and throws boulders at anything that moves.", level=15),
        creature("oathbroken_dwarf", "Oathbroken Dwarf", "humanoid", "soldier", 16,
                 "Cast out of the Holds for a broken oath. Still wears the clan's armour, with the crest "
                 "scratched off.",
                 spellbook=(_spell("Shield Bash", SpellType.WEAKEN, 0, "A rim of iron to the jaw"),),
                 spell_chance=0.25),
        variant(base("wraith"), "miners_shade", "Miner's Shade",
                "A ghost with a lamp that never goes out, still looking for the way back up.", level=14,
                on_hit=(blind(0.15),)),
    )

    # ============================================================ the Barrowfields (from level 15)
    add(
        variant(base("skeleton"), "skeleton_archer", "Skeleton Archer",
                "It loosed arrows at the barrow's enemies five hundred years ago. It hasn't run out.", level=13,
                hp=0.85, agility=4, on_hit=(bleed(5, 2, 0.2),)),
        variant(base("skeleton"), "skeletal_champion", "Skeletal Champion",
                "A chieftain's sworn shield, buried at his feet and still standing guard.", level=14, hp=1.2,
                defense=5, resist=((M, -0.15),)),
        creature("headless_knight", "Bloodied Headless Knight", "undead", "brute", 15,
                 "A knight in red-rusted mail with nothing above the collar. It finds you anyway.",
                 immune=UNDEAD, on_hit=(bleed(7, 3, 0.3),)),
        variant(base("sewer_ghoul"), "grave_ghoul", "Grave Ghoul",
                "It digs. It eats. It digs again.", level=13, hp=1.1),
        creature("bone_crawler", "Bone Crawler", "undead", "tank", 14,
                 "Dozens of skeletons that fell apart and put themselves back together as one thing.",
                 immune=UNDEAD, resist=((P, 0.1),)),
        creature("gravehound", "Gravehound", "undead", "hunter", 13,
                 "A dog buried with its master, still loyal, still hungry.", immune=UNDEAD,
                 on_hit=(bleed(6, 3, 0.25),)),
        creature("wailing_widow", "Wailing Widow", "spirit", "spirit", 15,
                 "A grieving shade in a burial veil. Her wail stops hearts, or at least the spells in them.",
                 immune=(*UNDEAD, EffectKind.FROZEN), resist=((P, 0.3),),
                 spellbook=(_spell("Wail", SpellType.SILENCE, 0, "A scream with no end"),
                            _spell("Grief", SpellType.WEAKEN, 0, "Your arms grow heavy with it"))),
        variant(base("wisp"), "corpse_candle", "Corpse Candle",
                "A pale flame over a fresh grave. Folk say it marks where the next one will be dug.", level=13),
        variant(base("bandit"), "grave_robber", "Grave Robber",
                "Digs up barrow-gold to sell in Brennhold. Doesn't like witnesses.", level=12, agility=3,
                on_hit=(blind(0.15),)),
        variant(base("barrow_wight"), "wight_huskarl", "Wight Huskarl",
                "A dead king's guard in rotted mail, with a dead king's axe.", level=14, hp=1.1, dmg=1.1),
    )

    # ============================================================ the Frostreach (from level 25)
    add(
        variant(base("wolf"), "ice_wolf", "Ice Wolf",
                "A white wolf of the high ice. Its breath freezes on its own fur.", level=18,
                immune=(EffectKind.FROZEN,), on_hit=(freeze(0.08), bleed(6, 3, 0.2))),
        variant(base("dire_wolf"), "snowmane_alpha", "Snowmane Alpha",
                "Leads the white packs. It's been watching you longer than you've been watching it.", level=20,
                hp=1.1, immune=(EffectKind.FROZEN,)),
        creature("beastkin_raider", "Beastkin Raider", "humanoid", "skirmisher", 19,
                 "A northern raider in bone and fur. The tribes don't welcome southerners, and say so with "
                 "spears.", on_hit=(bleed(7, 3, 0.25),)),
        variant(base("cave_bear"), "feral_frost_bear", "Feral Frost Bear",
                "A white bear gone half-mad with hunger. It doesn't stop to eat what it kills.", level=19,
                hp=1.1, immune=(EffectKind.FROZEN,), on_hit=(bleed(8, 3, 0.25), freeze(0.06))),
        variant(base("giant"), "frost_giant", "Frost Giant",
                "A giant with blue skin and a beard of icicles. The cold comes off it like heat off a forge.",
                level=21, immune=(EffectKind.FROZEN,), on_hit=(freeze(0.1),)),
        creature("glacier_crawler", "Glacier Crawler", "beast", "tank", 20,
                 "An armoured thing that lives inside the glacier and comes out to feed.",
                 immune=(EffectKind.FROZEN,), resist=((P, 0.15),)),
        variant(base("wraith"), "frost_wraith", "Frost Wraith",
                "Someone who lay down in the snow to rest. The cold never let them get up.", level=19,
                immune=(*UNDEAD, EffectKind.FROZEN), on_hit=(freeze(0.12),)),
        creature("snow_stalker", "Snow Stalker", "beast", "hunter", 20,
                 "A long-armed white ape that hunts in blizzards. The tribes won't say its name.",
                 immune=(EffectKind.FROZEN,), on_hit=(bleed(8, 3, 0.25),)),
        creature("mammoth", "Mammoth", "beast", "brute", 21,
                 "A shaggy giant of the northern plains, peaceful until it isn't.", hp=1.15,
                 resist=((P, 0.1),)),
    )
    add(  # built on a creature from the block above
        variant(base("beastkin_raider"), "beastkin_shaman",
                "Beastkin Shaman", "Speaks for the spirits of the ice. They seem to listen.", hp=0.85,
                spell_chance=0.45,
                spellbook=(_spell("Glacier's Grip", SpellType.FREEZE, 0, "Ice climbs your legs"),
                           _spell("Hunt Song", SpellType.HASTE, 0, "Drums only she can hear"))),
    )

    # ============================================================ the Shrieking Cliffs (from level 30)
    add(
        variant(base("harpy"), "stormwing_harpy", "Stormwing Harpy",
                "Rides the gales off the sea and drops on you out of the wind.", level=19,
                starts_with=(haste,)),
        creature("storm_spirit", "Storm Spirit", "elemental", "spirit", 20,
                 "A knot of wind and lightning that howls through the cliffs.",
                 immune=(EffectKind.POISON, EffectKind.BLEED), resist=((P, 0.35),),
                 spellbook=(_spell("Lightning", SpellType.DAMAGE, 22, "The sky falls on you"),
                            _spell("Gale", SpellType.BLIND, 0, "Wind full of grit"))),
        variant(base("wyvern"), "cliff_wyvern", "Cliff Wyvern",
                "Nests on ledges no climber can reach and hunts anything that tries.", level=19, agility=3),
        variant(base("wraith"), "howling_shade", "Howling Shade",
                "The wind through the rocks sounds like screaming. Some of it is.", level=18,
                spellbook=(_spell("Howl", SpellType.SILENCE, 0, "The wind takes your voice"),)),
        variant(base("undercity_smuggler"),
                "cliffside_smuggler", "Cliffside Smuggler",
                "Hauls the Undercity's goods up the cliff paths at night.", level=18, hp=1.1),
        creature("wrecker", "Wrecker", "humanoid", "soldier", 19,
                 "Lights false lanterns on the rocks to wreck the ships, and comes down with an axe for the "
                 "survivors.", on_hit=(bleed(7, 3, 0.2),)),
        creature("cliff_crab", "Cliff Crab", "beast", "tank", 18,
                 "A crab the size of a cart, with a shell no blade has scratched.", resist=((P, 0.25), (M, -0.2))),
        variant(base("crow_swarm"), "razorbeak_flock", "Razorbeak Flock",
                "Sea birds with beaks like knives, that strip a carcass in a minute.", level=18,
                on_hit=(bleed(6, 3, 0.3),)),
        variant(base("hagraven"), "brine_hag", "Brine Hag",
                "A sea-witch who calls the fog in and drowns whatever walks out of it.", level=19,
                spellbook=(_spell("Drowning", SpellType.DAMAGE, 20, "Your lungs fill with salt water"),
                           _spell("Sea Fog", SpellType.BLIND, 0, "Grey, wet, endless"))),
        creature("drowned_sailor", "Drowned Sailor", "undead", "soldier", 19,
                 "Washed up on the rocks and walked up the cliff. It still has its cutlass.", immune=UNDEAD,
                 on_hit=(bleed(6, 3, 0.2),)),
    )

    # ============================================================ the Drowned Marches (from level 30)
    add(
        creature("bog_lurker", "Bog Lurker", "beast", "brute", 19,
                 "Lies under the frozen mud with only its eyes showing.", on_hit=(poison(8, 3, 0.25),)),
        variant(base("troll"), "marsh_troll", "Marsh Troll",
                "A troll covered in weed and leeches. It smells worse than it fights, which is saying "
                "something.", level=19, on_hit=(poison(8, 3, 0.25),)),
        variant(base("deserter"), "deserter_captain", "Deserter Captain",
                "Led his men out of the war and into the marsh. They do what he says now.", level=19, hp=1.15,
                spellbook=(_spell("Rally", SpellType.HASTE, 0, "Hold the line, lads"),), spell_chance=0.25),
        creature("bog_corpse", "Bog Corpse", "undead", "tank", 19,
                 "The marsh kept this one perfectly. Leather skin, peat-black, and walking.", immune=UNDEAD),
        variant(base("sewer_leech"), "marsh_leech", "Marsh Leech",
                "Grows fat on the deserters who come out here. Then on whoever comes looking for them.",
                level=18, hp=1.1),
        variant(base("basilisk"), "mire_basilisk", "Mire Basilisk",
                "A smaller, muddier basilisk. Its gaze works just as well.", level=18, hp=0.9),
        variant(base("wisp"), "marsh_light", "Marsh Light",
                "A flickering light over the water that leads travellers to the deep parts.", level=18,
                spellbook=(_spell("Lure", SpellType.WEAKEN, 0, "Follow, follow"),
                           _spell("Cold Fire", SpellType.DAMAGE, 18, "It burns like ice"))),
        variant(base("stone_golem"), "bog_golem", "Bog Golem",
                "Mud and roots and a drowned man's bones, shaped into something that walks.", level=19,
                defense=-8, resist=((P, 0.15),), on_hit=(poison(8, 3, 0.25),)),
        creature("plague_toad", "Plague Toad", "beast", "hunter", 18,
                 "A toad the size of an ox, sweating poison. Don't lick it.", immune=(EffectKind.POISON,),
                 on_hit=(poison(9, 3, 0.4),)),
        creature("sunken_knight", "Sunken Knight", "undead", "brute", 20,
                 "Rode out to defend a village that's now under the swamp. Still riding, on foot.",
                 immune=UNDEAD, resist=((M, -0.15),)),
    )

    # ============================================================ the Ruins of Valoria (from level 40)
    add(
        creature("valorian_legionnaire", "Valorian Legionnaire", "undead", "soldier", 21,
                 "A soldier of the fallen empire, still in formation, still guarding a city that died a "
                 "thousand years ago.", immune=UNDEAD, resist=((P, 0.1),)),
        creature("valorian_automaton", "Valorian Automaton", "construct", "tank", 22,
                 "Brass and sun-crystal, built to serve an empire. It never noticed the empire was gone.",
                 immune=CONSTRUCT, resist=((M, 0.25),)),
        creature("bound_soul", "Bound Soul", "spirit", "spirit", 22,
                 "A soul still chained to the old binding. It pulls at you, as though you could free it.",
                 immune=(*UNDEAD, EffectKind.FROZEN), resist=((P, 0.35),),
                 spellbook=(_spell("Soul Pull", SpellType.DAMAGE, 22, "Something in you goes with it",
                                   drain=0.5),)),
        creature("deathless_acolyte", "Deathless Acolyte", "undead", "caster", 22,
                 "A priest who served the Lich Regent in life and never saw a reason to stop.", immune=UNDEAD,
                 spellbook=(_spell("Grave Bolt", SpellType.DAMAGE, 24, "Cold that comes from below"),
                            _spell("Wither", SpellType.WEAKEN, 0, "Your strength drains away"),
                            _spell("Dark Mending", SpellType.HEAL, 60, "Dead flesh, knitting"))),
        variant(base("wraith"), "radiant_shade", "Radiant Shade",
                "A ghost that shines with the stolen light of Valoria. Looking at it hurts.", level=21,
                spellbook=(_spell("Blinding Light", SpellType.BLIND, 0, "The light of a dead sun"),
                           _spell("Soul Drain", SpellType.DAMAGE, 20, "Warmth, stolen", drain=0.5))),
        variant(base("stone_golem"), "glass_golem", "Glass Golem",
                "A golem of clear crystal. Strike it wrong and the edges cut you back.", level=21, thorns=0.15),
        creature("frozen_courtier", "Frozen Courtier", "undead", "caster", 21,
                 "A Valorian noble preserved in the ice, still dressed for a feast. Very offended you came "
                 "without an invitation.", immune=(*UNDEAD, EffectKind.FROZEN),
                 spellbook=(_spell("Disdain", SpellType.WEAKEN, 0, "You feel very small"),
                            _spell("Hush", SpellType.SILENCE, 0, "Silence in the court"),
                            _spell("Frost Kiss", SpellType.FREEZE, 0, "Cold lips, cold hands"))),
        variant(base("wraith_lord"), "wraith_captain", "Wraith Captain",
                "Leads the lesser dead on the ruined walls, the way it did when they were alive.", hp=0.85,
                level=22),
    )
    add(  # built on a creature from the block above
        variant(base("valorian_automaton"),
                "clockwork_hound", "Clockwork Hound", "A hunting dog of gears and glass, still ticking.",
                hp=0.75, dmg=1.05, agility=8, defense=-8),
    )
    add(  # built on a creature from the block above
        variant(base("valorian_legionnaire"),
                "legion_bowman", "Legion Bowman", "Loosed its last volley the night Valoria fell, and has "
                "been loosing ever since.", hp=0.8, agility=5, defense=-4, on_hit=(bleed(7, 3, 0.25),)),
    )

    # ============================================================ the Emberpeaks (from level 45)
    add(
        creature("dragon_cultist", "Dragon Cultist", "humanoid", "caster", 21,
                 "Prays to the old dragons and has the burn scars to prove it.",
                 spellbook=(_spell("Scald", SpellType.BURN, 10, "Fire from an open hand"),
                            _spell("Fervour", SpellType.HASTE, 0, "Faith, burning"))),
        variant(base("fire_elemental"), "cinder_elemental", "Cinder Elemental",
                "Ash and embers that hold together just long enough to hurt you.", level=21, hp=0.9,
                on_hit=(burn(10, 3, 0.35),)),
        variant(base("wraith"), "ash_wraith", "Ash Wraith",
                "Someone who burned on the mountain. They still smoulder.", level=21,
                immune=(*UNDEAD, EffectKind.BURN), on_hit=(burn(9, 3, 0.3),)),
        variant(base("dragon"), "ember_drake", "Ember Drake",
                "A dragon's lesser cousin, all speed and bad temper.", level=20, hp=0.85, agility=4),
        creature("salamander", "Fire Salamander", "beast", "hunter", 21,
                 "Swims in the lava pools and comes out glowing.", immune=(EffectKind.BURN,),
                 on_hit=(burn(10, 3, 0.35),), resist=((M, 0.15),)),
        variant(base("stone_golem"), "obsidian_golem", "Obsidian Golem",
                "Black volcanic glass shaped into a guardian. It's still warm inside.", level=22,
                on_hit=(burn(10, 3, 0.25),), thorns=0.1),
        creature("cinder_hound", "Cinder Hound", "beast", "hunter", 21,
                 "A dog with a coal for a heart, bred by the cult to hunt pilgrims.", immune=(EffectKind.BURN,),
                 on_hit=(burn(9, 3, 0.3), bleed(7, 3, 0.2))),
        variant(base("giant"), "fire_giant", "Fire Giant",
                "A giant whose hair is smoke and whose club is a smouldering tree.", level=22,
                immune=(EffectKind.BURN,), on_hit=(burn(12, 3, 0.3),)),
    )
    add(  # built on a creature from the block above
        variant(base("dragon_cultist"), "scaleguard",
                "Scaleguard", "A cult warrior in armour of shed dragon scales.", hp=1.5, dmg=1.15, defense=12,
                strength=6, spellbook=(), spell_chance=config.ENEMY_SPELL_CHANCE, immune=(EffectKind.BURN,)),
    )
    add(  # built on a creature from the block above
        variant(base("dragon_cultist"), "cult_flamecaller",
                "Cult Flamecaller", "A cultist who has started speaking to the fire, and listening.", hp=0.9,
                spellbook=(_spell("Firestorm", SpellType.DAMAGE, 26, "The sky rains fire"),
                           _spell("Scald", SpellType.BURN, 12, "Fire from an open hand"))),
    )

    # ============================================================ Titanfell (from level 65)
    add(
        variant(base("horrid_monster"), "riftborn_horror", "Riftborn Horror",
                "Crawled out of a crack in the earth that wasn't there last year.", level=22,
                resist=((P, 0.15), (M, 0.15))),
        creature("shardling", "Shardling", "construct", "tank", 22,
                 "A small creature of living stone, broken off something enormous. It moves like it's "
                 "trying to remember how.", immune=CONSTRUCT, resist=((P, 0.3),)),
        creature("obsidian_stalker", "Obsidian Stalker", "beast", "skirmisher", 23,
                 "Black, glassy and sharp all over. It casts no shadow.", on_hit=(bleed(10, 3, 0.35),),
                 immune=(EffectKind.BLEED,)),
        creature("the_unshaped", "The Unshaped", "aberration", "brute", 23,
                 "A thing that won't hold one form. Every time you look away, it's something else.",
                 resist=((P, 0.2), (M, 0.2)),
                 spellbook=(_spell("Shift", SpellType.VULNERABLE, 0, "You feel yourself come apart"),),
                 spell_chance=0.3),
        variant(base("frost_troll"), "ancient_frost_troll", "Ancient Frost Troll",
                "Older than the kingdom. Moss grows on the ice on its back.", level=24, hp=1.15),
        variant(base("wyvern"), "elder_wyvern", "Elder Wyvern",
                "Scarred from a hundred years of fighting its own kind for the high air.", level=23, hp=1.15),
        variant(base("mammoth"), "colossal_mammoth", "Colossal Mammoth",
                "Too big. Everything up here is the wrong size.", level=24, hp=1.1),
        variant(base("dragon"), "starved_dragon", "Starved Dragon",
                "Thin as a rake, ribs like a ship's hull. It hasn't eaten in years and it's very glad to see "
                "you.", level=23, hp=0.9, dmg=1.15, lifesteal=0.15),
        variant(base("giant"), "hollow_giant", "Hollow Giant",
                "A giant that died up here and kept walking. The wind howls through its ribs.", level=23,
                immune=UNDEAD, resist=((M, -0.15),)),
        creature("stone_echo", "Echo of Stone", "spirit", "spirit", 24,
                 "A voice in the rock, half-seen. It speaks in a language you almost understand.",
                 immune=(*UNDEAD, EffectKind.FROZEN), resist=((P, 0.35), (M, 0.1)),
                 spellbook=(_spell("Rumble", SpellType.DAMAGE, 26, "The ground shrugs"),
                            _spell("Weight of Ages", SpellType.WEAKEN, 0, "You feel very, very old"))),
    )
    # ============================================================ story only (side quests; not hunted anywhere)
    add(
        creature("hearth_inquisitor", "Hearth Order Inquisitor", "humanoid", "soldier", 15,
                 "A sworn hunter of the unnatural in a scorched grey habit, carrying a torch and a mace.",
                 spell_chance=0.3, on_hit=(burn(7, 3, 0.25),),
                 spellbook=(_spell("Purging Flame", SpellType.BURN, 10, "The fire that cleanses"),
                            _spell("Hearth Ward", SpellType.SHIELD, 0, "Faith, made solid"))),
        creature("bounty_hunter", "Regency Bounty Hunter", "humanoid", "hunter", 19,
                 "Paid by the head, and very good at counting.", on_hit=(bleed(7, 3, 0.25),),
                 starts_with=(haste,)),
    )
    return list(made.values())
