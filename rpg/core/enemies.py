"""Enemies, bosses, affixes and the level-scaled enemy factory.

Content is data: add an ``EnemyTemplate`` to ``ENEMIES`` and it becomes available to hunts (via
``LEVEL_POOLS``), dialogue ``start_combat`` effects (by id or name) and tests.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Callable

from rpg import config
from rpg.core.attributes import Attributes
from rpg.core.effects import EffectKind, EffectSpec, StatusEffect
from rpg.core.entities import Combatant, DamageType
from rpg.core.items import Spell, SpellType

IntRange = int | tuple[int, int]


def _roll(value: IntRange, rng: random.Random) -> int:
    return rng.randint(*value) if isinstance(value, tuple) else int(value)


def _enemy_spell(name: str, spell_type: SpellType, power: int = 0, description: str = "") -> Spell:
    return Spell(template_id=f"enemy:{name.lower().replace(' ', '_')}", name=name, spell_type=spell_type,
                 power=power, mana_cost=0, description=description)


# ------------------------------------------------------------------ boss quick-time events
@dataclass(frozen=True)
class QTETrigger:
    """A telegraphed boss move the player answers with a quick-time event instead of a dice roll.

    It fires (once) on the boss's first turn at or below ``hp_below`` of its health and replaces the boss's
    action that turn. Hit every prompt (score >= ``success_score``) to avoid it, optionally staggering the boss
    or punishing it for ``counter_damage`` of its max HP; hit some (>= ``partial_score``) to take half damage;
    otherwise take ``fail_damage`` of your max HP plus ``fail_effect``. ``{name}`` is the boss's name.
    """

    hp_below: float
    title: str
    telegraph: str
    success_text: str = "You evade {name}'s attack!"
    partial_text: str = "You only half avoid the blow."
    fail_text: str = "{name}'s attack lands squarely."
    prompts: int = 4
    window: float = 1.5  # seconds per prompt before skill and traits adjust it
    dc: int = 12  # Reflexes difficulty
    keys: str = ""  # prompt key pool; empty uses the default letters
    fail_damage: float = config.QTE_FAIL_DAMAGE
    fail_effect: EffectSpec | None = None
    stagger: bool = True
    counter_damage: float = 0.0
    success_score: float = 1.0
    partial_score: float = 0.5


# ------------------------------------------------------------------ templates
@dataclass(frozen=True)
class EnemyTemplate:
    template_id: str
    name: str
    hp: IntRange
    damage: IntRange
    enemy_type: str = "monster"
    description: str = ""
    is_boss: bool = False
    spellbook: tuple[Callable[[], Spell], ...] = ()
    spell_chance: float = config.ENEMY_SPELL_CHANCE
    on_hit: tuple[EffectSpec, ...] = ()
    regen_pct: float = 0.0  # fraction of max HP regenerated at the start of each turn
    title_variants: tuple[tuple[str, str], ...] = ()  # (name, description) picked at random (Titans)
    intro_title: str = ""
    intro_lines: tuple[str, ...] = ()
    reward_choices: tuple[str, ...] = ()  # boss trophies: player picks one
    guaranteed_drops: tuple[tuple[str, int], ...] = ()
    aliases: tuple[str, ...] = ()
    qte_triggers: tuple[QTETrigger, ...] = ()  # telegraphed moves answered with quick-time events


class Enemy(Combatant):
    def __init__(self, template: EnemyTemplate, rng: random.Random) -> None:
        name, description = template.name, template.description
        if template.title_variants:
            variant_name, variant_title = rng.choice(template.title_variants)
            name, description = f"{template.name}: {variant_name}", variant_title
        strength, agility = rng.randint(5, 15), rng.randint(5, 15)
        # Enemies use Strength (damage, crits) and Agility (accuracy); casters heal for the flat base amount.
        attributes = Attributes(strength=strength, dexterity=agility, agility=agility, vitality=0, intelligence=0,
                                wisdom=0, charisma=0)
        super().__init__(name, _roll(template.hp, rng), attributes)
        self.template = template
        self.template_id = template.template_id
        self.base_damage = _roll(template.damage, rng)
        self.defense = rng.randint(0, 5)
        self.enemy_type = template.enemy_type
        self.description = description
        self.is_boss = template.is_boss
        self.level = rng.randint(3, 7) if template.is_boss else 1
        self.spellbook = [factory() for factory in template.spellbook]
        self.spell_chance = template.spell_chance
        self.on_hit: list[EffectSpec] = list(template.on_hit)
        self.regen_pct = template.regen_pct
        self.affixes: list[str] = []
        if self.is_boss:
            self.attributes.strength = int(self.attributes.strength * 1.1)
            self.attributes.agility = int(self.attributes.agility * 1.1)
            self.defense = int(self.defense * 1.1)

    def mitigate(self, raw: int, damage_type: DamageType, penetration: float = 0.0) -> int:
        defense = self.defense // 2 if damage_type == DamageType.MAGIC else self.defense
        return max(1, int(raw - defense))

    def effective_defense(self, damage_type: DamageType, penetration: float = 0.0) -> float:
        return self.defense / 2 if damage_type == DamageType.MAGIC else float(self.defense)

    def scale(self, hp_factor: float, damage_factor: float, stat_factor: float = 1.0) -> None:
        self.max_hp = max(1, int(self.max_hp * hp_factor))
        self.hp = self.max_hp
        self.base_damage = max(1, int(self.base_damage * damage_factor))
        if stat_factor != 1.0:
            self.attributes.strength = int(self.attributes.strength * stat_factor)
            self.attributes.agility = int(self.attributes.agility * stat_factor)
            self.defense = int(self.defense * stat_factor)

    def choose_spell(self, target: Combatant, rng: random.Random) -> Spell | None:
        """Simple contextual AI: heal when hurt, ward when unwarded, don't re-apply active debuffs."""
        if not self.spellbook or rng.random() >= self.spell_chance:
            return None
        options: list[Spell] = []
        for spell in self.spellbook:
            if spell.spell_type == SpellType.HEAL:
                if self.hp_ratio < 0.5:
                    options.append(spell)
            elif spell.spell_type == SpellType.SHIELD:
                if not self.has_effect(EffectKind.SHIELD):
                    options.append(spell)
            elif spell.spell_type == SpellType.DAMAGE:
                options.append(spell)
            else:
                effect = spell.primary_effect()
                if effect and not target.has_effect(effect.kind):
                    options.append(spell)
        return rng.choice(options) if options else None

    def info_lines(self) -> list[str]:
        lines = [
            f"Type: {self.enemy_type}" + (f" · Boss level {self.level}" if self.is_boss else ""),
            f"Health {self.max_hp} · Damage {self.base_damage} · Defense {self.defense}",
            f"STR {self.attributes.strength} · AGI {self.attributes.agility}",
        ]
        if self.affixes:
            lines.append("Modifiers: " + ", ".join(self.affixes))
        if self.spellbook:
            lines.append("Casts: " + ", ".join(s.name for s in self.spellbook))
        if self.on_hit:
            lines.append("On hit: " + "; ".join(e.describe() for e in self.on_hit))
        if self.regen_pct:
            lines.append(f"Regenerates {int(self.regen_pct * 100)}% HP each turn")
        if self.description:
            lines.append(self.description)
        return lines


# ------------------------------------------------------------------ affixes
@dataclass(frozen=True)
class Affix:
    name: str
    description: str
    apply: Callable[[Enemy], None]


def _enraged(e: Enemy) -> None:
    e.base_damage = int(e.base_damage * 1.25)
    e.attributes.strength += 5


def _armored(e: Enemy) -> None:
    e.defense += 5
    e.max_hp = int(e.max_hp * 1.15)
    e.hp = e.max_hp


def _shielded(e: Enemy) -> None:
    e.add_effect(StatusEffect(EffectKind.SHIELD, 3, 0.25, "Shielded"))


def _swift(e: Enemy) -> None:
    e.attributes.agility += 8


def _venomous(e: Enemy) -> None:
    e.on_hit.append(EffectSpec(EffectKind.POISON, 6, 3, 0.30))


def _searing(e: Enemy) -> None:
    e.on_hit.append(EffectSpec(EffectKind.BURN, 5, 3, 0.30))


AFFIXES: list[Affix] = [
    Affix("Enraged", "+25% damage, +5 strength", _enraged),
    Affix("Armored", "+5 defense, +15% health", _armored),
    Affix("Shielded", "Starts behind a 25% ward", _shielded),
    Affix("Swift", "+8 agility", _swift),
    Affix("Venomous", "Attacks may poison", _venomous),
    Affix("Searing", "Attacks may burn", _searing),
]


def apply_affix(enemy: Enemy, affix: Affix) -> None:
    affix.apply(enemy)
    enemy.affixes.append(affix.name)
    enemy.name = f"{affix.name} {enemy.name}"


# ------------------------------------------------------------------ roster
TITANS = (
    ("Olgath", "The Titan of Fire"), ("Herix", "The Titan of Ice"), ("Forgin", "The Titan of Earth"),
    ("Vexer", "The Titan of Wind"), ("Morrg", "The Titan of Shadow"), ("Gorren", "The Titan of Light"),
    ("Zodd", "The Titan of Darkness"), ("Implex", "The Titan of Chaos"),
)

_bleed = lambda p, t, c: EffectSpec(EffectKind.BLEED, p, t, c)  # noqa: E731
_poison = lambda p, t, c: EffectSpec(EffectKind.POISON, p, t, c)  # noqa: E731

_burn = lambda p, t, c: EffectSpec(EffectKind.BURN, p, t, c)  # noqa: E731

TITAN_QTES = (
    QTETrigger(0.6, "CRUSHING FISTS", "{name} raises both fists high above your head!",
               success_text="You roll aside as the fists crater the stone where you stood!",
               fail_text="The fists come down on you like a falling mountain.", prompts=4, window=1.5, dc=12),
    QTETrigger(0.25, "AVALANCHE", "{name} tears a slab from the cave wall and hurls it!",
               success_text="You weave through the falling rock and slash at its exposed ankle!",
               fail_text="Stone buries you to the waist.", prompts=5, window=1.3, dc=13, counter_damage=0.06),
)
DRAGON_QTES = (
    QTETrigger(0.65, "INFERNO", "{name} rears back, its throat glowing white-hot!",
               success_text="You dive behind a pillar as the flames roar past!",
               fail_text="Dragonfire washes over you.", prompts=5, window=1.3, dc=14,
               fail_effect=_burn(14, 3, 1.0)),
    QTETrigger(0.3, "TAIL SWEEP", "{name}'s tail whips around in a scything arc!",
               success_text="You vault the tail and drive your blade between two scales!",
               fail_text="The tail sweeps you off your feet.", prompts=5, window=1.2, dc=14, keys="←→↑↓",
               counter_damage=0.05),
)
WORM_QTES = (
    QTETrigger(0.6, "ERUPTION", "The ground bulges beneath your feet — {name} is coming up!",
               success_text="You leap clear as the maw bursts out of the earth!",
               fail_text="You are thrown into the air by the eruption.", prompts=5, window=1.2, dc=15, keys="←→↑↓"),
    QTETrigger(0.3, "ENGULF", "{name} opens its maw wide and lunges to swallow you whole!",
               success_text="You brace your weapon in its jaws and wrench free, tearing its gums!",
               fail_text="Teeth like millstones close around you before you tear loose.", prompts=6, window=1.15,
               dc=16, counter_damage=0.05),
)
RAT_KING_QTES = (
    QTETrigger(0.55, "THE SWARM", "{name} shrieks and the floor turns into a carpet of rats!",
               success_text="You stamp a path through the swarm before it can climb you!",
               fail_text="Rats pour over you, biting.", prompts=6, window=1.1, dc=16, fail_effect=_poison(10, 3, 1.0)),
    QTETrigger(0.25, "CROWN OF TAILS", "{name}'s knotted tails lash out to bind you!",
               success_text="You cut through the knot of tails and the whole crown screams!",
               fail_text="The tails squeeze the air from your lungs.", prompts=6, window=1.05, dc=17,
               counter_damage=0.05),
)
SENTINEL_QTES = (
    QTETrigger(0.7, "STONE FIST", "{name} lifts its fist; the runes on its knuckles flare!",
               success_text="You sidestep and the fist cracks the flagstones!",
               fail_text="The stone fist slams into your chest.", prompts=3, window=1.8, dc=10),
    QTETrigger(0.35, "CORE BREACH", "{name}'s chest plate grinds open, its core blazing — strike it!",
               success_text="You drive your weapon into the blazing core!",
               partial_text="You graze the core as the plates slam shut.",
               fail_text="The plates slam shut and a pulse of force hurls you back.", prompts=4, window=1.6, dc=11,
               stagger=False, counter_damage=0.15),
)

GENERIC_BOSS_INTRO = (
    "{name} stands before you — {title}.",
    "",
    "The air thickens. Every instinct tells you to run.",
    "You hold your ground.",
    "",
    "This is no ordinary foe.",
)
TITAN_REWARDS = ("titan_hammer", "titan_claw_dagger", "titans_curse")

_TEMPLATES: list[EnemyTemplate] = [
    # common
    EnemyTemplate("goblin", "Goblin", 40, 8, "humanoid", "A small, green-skinned creature with sharp teeth."),
    EnemyTemplate("orc", "Orc Warrior", 80, 15, "humanoid", "A large, brutish warrior with crude armor.",
                  aliases=("orc warrior",)),
    EnemyTemplate("skeleton", "Skeleton", 35, 10, "undead", "Animated bones held together by dark magic."),
    EnemyTemplate("troll", "Cave Troll", 120, 20, "giant", "A massive creature with regenerative abilities.",
                  regen_pct=0.03, aliases=("cave troll",)),
    EnemyTemplate("spriggan", "Spriggan", 100, 20, "fae", "A small, agile creature with a knack for stealth."),
    EnemyTemplate("dragon", "Young Dragon", 200, 35, "dragon", "A fearsome winged beast with fiery breath.",
                  spellbook=(lambda: _enemy_spell("Dragonfire", SpellType.BURN, 12, "Dragonfire that sticks"),),
                  aliases=("young dragon",)),
    EnemyTemplate("wolf", "Wolf", 50, 10, "beast", "A wild wolf, with sharp teeth and claws.",
                  on_hit=(_bleed(4, 3, 0.20),)),
    EnemyTemplate("giant", "Giant", 100, 20, "giant", "A massive creature with a huge club made of wood."),
    EnemyTemplate("bandit", "Bandit", 60, 12, "humanoid", "An opportunistic highwayman looking for an easy score."),
    EnemyTemplate("dire_wolf", "Dire Wolf", 80, 16, "beast", "A larger, more vicious wolf with keen instincts.",
                  on_hit=(_bleed(5, 3, 0.25),)),
    EnemyTemplate("wraith", "Wraith", 110, 22, "undead", "A vengeful spirit that drains warmth and hope.",
                  spellbook=(lambda: _enemy_spell("Blind", SpellType.BLIND, 0, "Chill the eyes"),)),
    EnemyTemplate("ogre", "Ogre", 160, 24, "giant", "A brutish hulk with crushing blows and thick hide."),
    EnemyTemplate("minotaur", "Minotaur", 180, 28, "beast", "A horned labyrinth-stalker with feral strength.",
                  on_hit=(_bleed(7, 3, 0.25),)),
    EnemyTemplate("hagraven", "Hagraven", 95, 22, "witch", "A corrupted hag who weaves dark magic and preys on wanderers.",
                  spellbook=(lambda: _enemy_spell("Venom Hex", SpellType.POISON, 12, "Rot that walks"),)),
    EnemyTemplate("horrid_monster", "Horrid Monster", 160, 26, "aberration",
                  "A grotesque being stitched from nightmare and shadow."),
    EnemyTemplate("ghost_horror", "Ghost Horror", 140, 24, "undead", "A formless terror of whispers and frostbitten dread.",
                  spellbook=(lambda: _enemy_spell("Freeze", SpellType.FREEZE, 0, "Terror that stills"),),
                  intro_title="A HAUNTING PRESENCE ARRIVES",
                  intro_lines=("You wait... and something waits with you...",
                               "Frost creeps along the floor, swallowing your footprints...",
                               "The torches gutter. Breath fogs the air. All goes silent...",
                               "From the stillness, {name} takes shape — sorrow given form...",
                               "",
                               "It has come to punish hesitation.")),
    # story / dialogue encounters
    EnemyTemplate("archmage", "Archmage", 400, 40, "humanoid", "A master of the arcane arts, relentless and precise.",
                  spellbook=(lambda: _enemy_spell("Blind", SpellType.BLIND),
                             lambda: _enemy_spell("Freeze", SpellType.FREEZE),
                             lambda: _enemy_spell("Burn", SpellType.BURN, 10, "A searing brand that lingers"),
                             lambda: _enemy_spell("Ward", SpellType.SHIELD),
                             lambda: _enemy_spell("Heal", SpellType.HEAL)),
                  guaranteed_drops=(("superior_health_potion", 3), ("mage_robes", 1), ("runed_staff", 1))),
    EnemyTemplate("yjurgen", "Yjurgen", 150, 50, "humanoid",
                  "A large brute of a man, with a thick beard and a strong sense of honor and justice."),
    EnemyTemplate("ziggy", "Ziggy", 340, 8, "humanoid", "A fat man, covered head to toe in armor but slow and weak."),
    EnemyTemplate("jarvask", "Jarvask", 200, 12, "humanoid", "Well rounded fighter, not too strong, not too weak."),
    EnemyTemplate("gorren", "Gorren", 60, 80, "humanoid", "Berserk madman with no armor, yet wielding a massive axe."),
    EnemyTemplate("morrg", "Morrg", 90, 20, "humanoid", "A dark and twisted figure, with a twisted sense of humor."),
    # bosses
    EnemyTemplate("titan", "Titan", (400, 600), (25, 45), "Boss", is_boss=True, title_variants=TITANS,
                  intro_title="A TITAN AWAKENS",
                  intro_lines=("As you search for enemies to slay, you find yourself entering a dark cave.",
                               "The air grows cold and heavy as you venture deeper into its depths...",
                               "",
                               "Walking further in, you see {name}, {title}.",
                               "",
                               "The ground shakes as it rises to stand at your arrival.",
                               "You have never seen anything this massive before.",
                               "",
                               "Its eyes burn with ancient power as it turns to face you.",
                               "The very walls of the cave tremble with each movement it makes.",
                               "",
                               "This is not just an enemy... This is a Titan."),
                  reward_choices=TITAN_REWARDS, qte_triggers=TITAN_QTES),
    EnemyTemplate("valorian_warden", "Valorian Warden", 650, 50, "Boss",
                  "A sentinel bound to the gates by oath and old steel.", is_boss=True,
                  intro_title="THE GATE REMEMBERS", intro_lines=GENERIC_BOSS_INTRO, reward_choices=TITAN_REWARDS),
    EnemyTemplate("lich_regent", "Lich Regent", 700, 55, "Boss", "A sovereign of silence wearing a crown of names.",
                  is_boss=True,
                  spellbook=(lambda: _enemy_spell("Grave Rot", SpellType.POISON, 14),
                             lambda: _enemy_spell("Deathly Ward", SpellType.SHIELD)),
                  intro_title="THE SILENT THRONE", intro_lines=GENERIC_BOSS_INTRO, reward_choices=TITAN_REWARDS),
    EnemyTemplate("clockwork_colossus", "Clockwork Colossus", 800, 60, "Boss",
                  "A titan of gears and grief, wound to outlast the sun.", is_boss=True,
                  intro_title="GEARS OF GRIEF", intro_lines=GENERIC_BOSS_INTRO, reward_choices=TITAN_REWARDS),
    EnemyTemplate("elder_dragon", "Elder Dragon", (800, 1000), (45, 60), "Boss",
                  "An ancient wyrm wreathed in ruinous flame.", is_boss=True,
                  spellbook=(lambda: _enemy_spell("Ruinous Flame", SpellType.BURN, 14),),
                  intro_title="ANCIENT FIRE STIRS",
                  intro_lines=("The mountain groans as a cavern yawns wide...",
                               "Ash swirls. Embers drift like fallen stars...",
                               "A shadow uncoils, vast and patient — {name}, {title}.",
                               "",
                               "Its breath sears the air. Scales blaze like forged mail.",
                               "Claws score the stone with idle, ruinous grace...",
                               "This is no mere beast. This is an ending with wings."),
                  reward_choices=("dragon_tooth_greatsword", "elder_scale_bow", "dragons_breath"),
                  qte_triggers=DRAGON_QTES),
    EnemyTemplate("earth_eater_worm", "Earth Eater Worm", (1100, 1300), (60, 70), "Boss",
                  "A burrowing leviathan whose maw devours stone and light.", is_boss=True,
                  intro_title="THE EARTH SPLITS OPEN",
                  intro_lines=("Pebbles skitter. Cracks race like lightning underfoot...",
                               "The ground heaves as if the world is changing its mind.",
                               "Soil domes, shatters — and the maw of {name}, {title}, blooms like a pit.",
                               "Ribs of stone snap between its rings. The air tastes of iron and old dark.",
                               "It listens with its whole body. It answers with hunger."),
                  reward_choices=("earthsplitter_maul", "stonebore_crossbow", "seismic_rift"),
                  qte_triggers=WORM_QTES),
    EnemyTemplate("rat_king", "Rat King", (1400, 1600), (70, 85), "Boss",
                  "A crown of tails, sovereign of skitter and rot.", is_boss=True,
                  on_hit=(_poison(8, 3, 0.30),),
                  intro_title="A SCRATCHING CROWN APPROACHES",
                  intro_lines=("Threads of chittering stitch the dark...",
                               "Stone sweats; the air smells of cellar and spoil.",
                               "Rats pour like water, braiding themselves about a throne — {name}, {title}.",
                               "Eyes glitter in a hundred small faces. One voice speaks from all of them.",
                               "It promises a kingdom of tunnels, and taxes paid in gnawed bone."),
                  reward_choices=("gnawblade", "sewer_longbow", "pestilent_swarm"), qte_triggers=RAT_KING_QTES),
    # Minigame showcase quest (dialogues/test_vault). A beatable level-1 boss with two quick-time events.
    EnemyTemplate("stone_sentinel", "Stone Sentinel", 230, 15, "construct",
                  "A vault guardian of carved granite, its core ticking like a slow heart.", is_boss=True,
                  intro_title="THE VAULT WAKES",
                  intro_lines=("Dust sifts from the ceiling as the alcove at the end of the hall splits open.",
                               "",
                               "{name} steps down from its plinth, granite grinding on granite.",
                               "Runes crawl across its knuckles. Somewhere in its chest, a core ticks.",
                               "",
                               "It turns its blank face toward you."),
                  reward_choices=("sentinel_plate", "sentinel_core", "hourglass_pendant"),
                  qte_triggers=SENTINEL_QTES),
]

# Weighted hunt pools by player level band: (max_level_exclusive, [(template_id, weight), ...])
LEVEL_POOLS: list[tuple[int, list[tuple[str, int]]]] = [
    (5, [("skeleton", 30), ("goblin", 30), ("wolf", 30), ("orc", 3), ("troll", 2), ("spriggan", 3), ("bandit", 2)]),
    (10, [("orc", 25), ("troll", 20), ("bandit", 20), ("dire_wolf", 15), ("giant", 6), ("wraith", 6), ("hagraven", 8)]),
    (10**9, [("giant", 18), ("wraith", 18), ("ogre", 18), ("minotaur", 18), ("dragon", 10), ("hagraven", 8),
             ("skeleton", 3), ("goblin", 3), ("wolf", 2), ("bandit", 2)]),
]


def normalize_enemy_id(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


class UnknownEnemyError(KeyError):
    pass


@dataclass
class EnemyFactory:
    templates: dict[str, EnemyTemplate] = field(default_factory=dict)
    _aliases: dict[str, str] = field(default_factory=dict)

    def register(self, template: EnemyTemplate) -> None:
        if template.template_id in self.templates:
            raise ValueError(f"Duplicate enemy id: {template.template_id}")
        self.templates[template.template_id] = template
        for alias in (template.name, *template.aliases):
            self._aliases[normalize_enemy_id(alias)] = template.template_id

    def resolve(self, enemy_id: str) -> str:
        key = normalize_enemy_id(enemy_id)
        if key in self.templates:
            return key
        if key in self._aliases:
            return self._aliases[key]
        raise UnknownEnemyError(enemy_id)

    def create(self, enemy_id: str, rng: random.Random | None = None) -> Enemy:
        rng = rng or random.Random()
        return Enemy(self.templates[self.resolve(enemy_id)], rng)

    def random_for_level(self, level: int, rng: random.Random) -> Enemy:
        pool = next(entries for limit, entries in LEVEL_POOLS if level < limit)
        ids, weights = zip(*pool)
        enemy = self.create(rng.choices(ids, weights=weights, k=1)[0], rng)
        bonus = max(0, level - 1)
        enemy.scale(1 + config.LEVEL_HP_SCALING * bonus, 1 + config.LEVEL_DAMAGE_SCALING * bonus)
        return enemy

    @staticmethod
    def roll_affix(enemy: Enemy, rng: random.Random, chance: float = config.AFFIX_CHANCE) -> Affix | None:
        if enemy.is_boss or rng.random() >= chance:
            return None
        affix = rng.choice(AFFIXES)
        apply_affix(enemy, affix)
        return affix


ENEMIES = EnemyFactory()
for _template in _TEMPLATES:
    ENEMIES.register(_template)
