"""Enemies, bosses, affixes and the level-scaled enemy factory.

Content is data: add an ``EnemyTemplate`` to ``_TEMPLATES`` and it becomes available to hunts (via
``LEVEL_POOLS``), dialogue ``start_combat`` effects (by id or name) and tests.

Scaling: a template describes the enemy *at its design level* (``level``). ``EnemyFactory.create(id, rng, level)``
grows or shrinks it from there (``scale_to_level``): +8% HP, +5.5% damage, +0.5 defense and +0.4 Strength/
Agility per level. Hunts create enemies at about the player's level; bosses never shrink below their design
level and grow at half rate above it. Defense is a percentage (``armor_mitigation``), as it is for the player.
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
from rpg.core.formulas import armor_mitigation
from rpg.core.items import Spell, SpellType

IntRange = int | tuple[int, int]

HP_GROWTH = 0.08
DAMAGE_GROWTH = 0.055
DEFENSE_GROWTH = 0.5
STAT_GROWTH = 0.4
MIN_SCALE = 0.55
BOSS_GROWTH_SHARE = 0.5  # bosses fought above their level grow at half rate
MAGIC_ARMOR_SHARE = 0.7  # magic ignores 30% of an enemy's defense


def _roll(value: IntRange, rng: random.Random) -> int:
    return rng.randint(*value) if isinstance(value, tuple) else int(value)


def _enemy_spell(name: str, spell_type: SpellType, power: int = 0, description: str = "", *,
                 effect: EffectSpec | None = None, inflicts: EffectSpec | None = None, drain: float = 0.0) -> Spell:
    return Spell(template_id=f"enemy:{name.lower().replace(' ', '_')}", name=name, spell_type=spell_type,
                 power=power, mana_cost=0, description=description, effect=effect, inflicts=inflicts, drain=drain)


def _spell(*args, **kwargs) -> Callable[[], Spell]:
    return lambda: _enemy_spell(*args, **kwargs)


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
    level: int = 1  # the level these numbers describe
    strength: IntRange = (6, 10)
    agility: IntRange = (6, 10)
    defense: IntRange = (2, 5)
    resist: tuple[tuple[str, float], ...] = ()  # (("physical", 0.3),): share of that damage type ignored
    immune: tuple[EffectKind, ...] = ()
    lifesteal: float = 0.0
    thorns: float = 0.0  # share of physical weapon damage reflected at the attacker
    spellbook: tuple[Callable[[], Spell], ...] = ()
    spell_chance: float = config.ENEMY_SPELL_CHANCE
    on_hit: tuple[EffectSpec, ...] = ()
    regen_pct: float = 0.0  # fraction of max HP regenerated each turn (stopped while burning)
    starts_with: tuple[EffectSpec, ...] = ()  # effects the enemy enters the fight with (a ward, haste...)
    title_variants: tuple[tuple[str, str], ...] = ()  # (name, description) picked at random (Titans)
    intro_title: str = ""
    intro_lines: tuple[str, ...] = ()
    reward_choices: tuple[str, ...] = ()  # boss trophies: player picks one
    guaranteed_drops: tuple[tuple[str, int], ...] = ()
    aliases: tuple[str, ...] = ()
    qte_triggers: tuple[QTETrigger, ...] = ()  # telegraphed moves answered with quick-time events


# Each Titan embodies an element: immune to its own effect, and it strikes with it.
TITAN_ELEMENTS: dict[str, dict] = {
    "fire": {"immune": (EffectKind.BURN,), "on_hit": (EffectSpec(EffectKind.BURN, 10, 3, 0.3),)},
    "ice": {"immune": (EffectKind.FROZEN,), "on_hit": (EffectSpec(EffectKind.FROZEN, 0, 1, 0.12),)},
    "earth": {"immune": (EffectKind.BLEED,), "resist": {"physical": 0.2}},
    "wind": {"immune": (EffectKind.BLIND,), "starts_with": (EffectSpec(EffectKind.HASTE, 1, 2),)},
    "shadow": {"immune": (EffectKind.BLIND,), "on_hit": (EffectSpec(EffectKind.BLIND, 0.25, 2, 0.25),)},
    "light": {"immune": (EffectKind.SILENCE, EffectKind.BLIND), "resist": {"magic": 0.2}},
    "darkness": {"immune": (EffectKind.POISON,), "lifesteal": 0.2},
    "chaos": {"immune": (EffectKind.FROZEN,), "on_hit": (EffectSpec(EffectKind.VULNERABLE, 0.2, 2, 0.25),)},
}


class Enemy(Combatant):
    def __init__(self, template: EnemyTemplate, rng: random.Random) -> None:
        name, description = template.name, template.description
        if template.title_variants:
            variant_name, variant_title = rng.choice(template.title_variants)
            name, description = f"{template.name}: {variant_name}", variant_title
        strength, agility = _roll(template.strength, rng), _roll(template.agility, rng)
        # Enemies use Strength (damage, crits) and Agility (accuracy); their spells grow with their level.
        attributes = Attributes(strength=strength, dexterity=agility, agility=agility, vitality=0, intelligence=0,
                                wisdom=0, charisma=0)
        super().__init__(name, _roll(template.hp, rng), attributes)
        self.template = template
        self.template_id = template.template_id
        self.base_damage = _roll(template.damage, rng)
        self.defense = _roll(template.defense, rng)
        self.enemy_type = template.enemy_type
        self.description = description
        self.is_boss = template.is_boss
        self.level = template.level
        self.spellbook = [factory() for factory in template.spellbook]
        self.spell_chance = template.spell_chance
        self.on_hit: list[EffectSpec] = list(template.on_hit)
        self.regen_pct = template.regen_pct
        self.resistances: dict[str, float] = dict(template.resist)
        self.immunities: set[EffectKind] = set(template.immune)
        self.lifesteal = template.lifesteal
        self.thorns = template.thorns
        self.affixes: list[str] = []
        for spec in template.starts_with:
            self.add_effect(spec.create("Innate"))
        if template.title_variants:
            self._apply_element(description)

    def _apply_element(self, description: str) -> None:
        element = TITAN_ELEMENTS.get(description.rstrip(".").split()[-1].lower())
        if not element:
            return
        self.immunities.update(element.get("immune", ()))
        self.on_hit += list(element.get("on_hit", ()))
        for kind, share in element.get("resist", {}).items():
            self.resistances[kind] = self.resistances.get(kind, 0.0) + share
        self.lifesteal += element.get("lifesteal", 0.0)
        for spec in element.get("starts_with", ()):
            self.add_effect(spec.create("Element"))

    # ------------------------------------------------------------ defenses
    def immune(self, kind: EffectKind) -> bool:
        return kind in self.immunities

    def resist(self, damage_type: DamageType) -> float:
        return self.resistances.get(damage_type.value, 0.0)

    def effective_defense(self, damage_type: DamageType, penetration: float = 0.0) -> float:
        defense = self.defense * (1 - penetration)
        return defense * MAGIC_ARMOR_SHARE if damage_type == DamageType.MAGIC else float(defense)

    def mitigate(self, raw: int, damage_type: DamageType, penetration: float = 0.0) -> int:
        multiplier = armor_mitigation(self.effective_defense(damage_type, penetration)) * (1 - self.resist(damage_type))
        return max(1, int(round(raw * multiplier)))

    # ------------------------------------------------------------ scaling
    def scale(self, hp_factor: float, damage_factor: float, stat_factor: float = 1.0) -> None:
        self.max_hp = max(1, int(self.max_hp * hp_factor))
        self.hp = self.max_hp
        self.base_damage = max(1, int(self.base_damage * damage_factor))
        if stat_factor != 1.0:
            self.attributes.strength = int(self.attributes.strength * stat_factor)
            self.attributes.agility = int(self.attributes.agility * stat_factor)
            self.defense = int(self.defense * stat_factor)

    def scale_to_level(self, level: int) -> None:
        """Grow (or shrink) this enemy from its design level to ``level``."""
        delta = level - self.template.level
        if self.is_boss:
            delta = max(0, delta) * BOSS_GROWTH_SHARE
        hp = max(MIN_SCALE, 1 + HP_GROWTH * delta)
        damage = max(MIN_SCALE, 1 + DAMAGE_GROWTH * delta)
        self.scale(hp, damage)
        self.defense = max(0, int(round(self.defense + DEFENSE_GROWTH * delta)))
        bump = int(round(STAT_GROWTH * delta))
        self.attributes.strength = max(1, self.attributes.strength + bump)
        self.attributes.agility = max(1, self.attributes.agility + bump)
        self.attributes.dexterity = self.attributes.agility
        self.level = max(1, level if not self.is_boss else max(level, self.template.level))

    # ------------------------------------------------------------ behaviour
    def choose_spell(self, target: Combatant, rng: random.Random) -> Spell | None:
        """Contextual AI: heal and cleanse when hurt, buff when unbuffed, don't re-apply active debuffs."""
        if not self.spellbook or rng.random() >= self.spell_chance:
            return None
        harmful_on_me = any(k in self.effects for k in (EffectKind.POISON, EffectKind.BURN, EffectKind.BLEED,
                                                        EffectKind.WEAKEN, EffectKind.VULNERABLE))
        options: list[Spell] = []
        for spell in self.spellbook:
            t = spell.spell_type
            if t in (SpellType.HEAL, SpellType.REGEN):
                if self.hp_ratio < 0.5 and not self.has_effect(EffectKind.REGEN):
                    options.append(spell)
            elif t == SpellType.CLEANSE:
                if harmful_on_me:
                    options.append(spell)
            elif t in (SpellType.SHIELD, SpellType.HASTE):
                effect = spell.primary_effect()
                if effect and not self.has_effect(effect.kind):
                    options.append(spell)
            elif t == SpellType.DAMAGE:
                options.append(spell)
            else:
                effect = spell.primary_effect()
                if effect and not target.has_effect(effect.kind) and not target.immune(effect.kind):
                    options.append(spell)
        return rng.choice(options) if options else None

    def info_lines(self) -> list[str]:
        lines = [
            f"Level {self.level} {self.enemy_type}" + (" · Boss" if self.is_boss and self.enemy_type != "Boss" else ""),
            f"Health {self.max_hp} · Damage {self.base_damage} · Defense {self.defense}",
            f"STR {self.attributes.strength} · AGI {self.attributes.agility}",
        ]
        if self.affixes:
            lines.append("Modifiers: " + ", ".join(self.affixes))
        if self.resistances:
            lines.append("Resists: " + ", ".join(f"{k} {int(v * 100)}%" for k, v in self.resistances.items()))
        if self.immunities:
            lines.append("Immune: " + ", ".join(sorted(k.value for k in self.immunities)))
        if self.spellbook:
            lines.append("Casts: " + ", ".join(s.name for s in self.spellbook))
        if self.on_hit:
            lines.append("On hit: " + "; ".join(e.describe() for e in self.on_hit))
        if self.regen_pct:
            lines.append(f"Regenerates {int(self.regen_pct * 100)}% HP each turn (fire stops it)")
        if self.lifesteal:
            lines.append(f"Drains {int(self.lifesteal * 100)}% of the damage it deals")
        if self.thorns:
            lines.append(f"Reflects {int(self.thorns * 100)}% of weapon damage")
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
    e.attributes.strength += 4


def _armored(e: Enemy) -> None:
    e.defense += 8
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


def _vampiric(e: Enemy) -> None:
    e.lifesteal += 0.25


def _thorned(e: Enemy) -> None:
    e.thorns += 0.15


def _frenzied(e: Enemy) -> None:
    e.add_effect(StatusEffect(EffectKind.HASTE, 2, 1, "Frenzied"))


def _regenerating(e: Enemy) -> None:
    e.regen_pct += 0.03


def _hulking(e: Enemy) -> None:
    e.max_hp = int(e.max_hp * 1.4)
    e.hp = e.max_hp
    e.base_damage = int(e.base_damage * 1.1)
    e.attributes.agility = max(1, e.attributes.agility - 4)


def _ethereal(e: Enemy) -> None:
    e.resistances["physical"] = e.resistances.get("physical", 0.0) + 0.3


def _hexing(e: Enemy) -> None:
    e.spellbook.append(_enemy_spell("Hex of Frailty", SpellType.VULNERABLE))


AFFIXES: list[Affix] = [
    Affix("Enraged", "+25% damage, +4 strength", _enraged),
    Affix("Armored", "+8 defense, +15% health", _armored),
    Affix("Shielded", "Starts behind a 25% ward", _shielded),
    Affix("Swift", "+8 agility", _swift),
    Affix("Venomous", "Attacks may poison", _venomous),
    Affix("Searing", "Attacks may burn", _searing),
    Affix("Vampiric", "Heals for 25% of the damage it deals", _vampiric),
    Affix("Thorned", "Reflects 15% of weapon damage", _thorned),
    Affix("Frenzied", "Starts hasted for two turns", _frenzied),
    Affix("Regenerating", "Regenerates 3% HP each turn", _regenerating),
    Affix("Hulking", "+40% health, +10% damage, slower", _hulking),
    Affix("Ethereal", "Resists 30% of physical damage", _ethereal),
    Affix("Hexing", "Casts Hex of Frailty (you take more damage)", _hexing),
]
AFFIX_BY_NAME = {a.name: a for a in AFFIXES}


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
_freeze = lambda c: EffectSpec(EffectKind.FROZEN, 0, 1, c)  # noqa: E731
_blind = lambda c: EffectSpec(EffectKind.BLIND, 0.25, 2, c)  # noqa: E731
UNDEAD = (EffectKind.POISON, EffectKind.BLEED)
P = "physical"
M = "magic"

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
    # ---------------------------------------------------------------- levels 1-6
    EnemyTemplate("goblin", "Goblin", (34, 40), (6, 8), "humanoid", "A small, green-skinned creature with sharp teeth.",
                  level=1, strength=(5, 8), agility=(8, 12), defense=(0, 2)),
    EnemyTemplate("skeleton", "Skeleton", (32, 38), (7, 9), "undead", "Animated bones held together by dark magic.",
                  level=1, strength=(6, 9), agility=(5, 8), defense=(4, 6), immune=UNDEAD),
    # Story only (Brannoc's cellar, Emberwick); not in the hunt pools.
    EnemyTemplate("cellar_rat", "Cellar Rat", (28, 34), (5, 7), "beast",
                  "A rat the size of a small dog. It has clearly been eating well.",
                  level=1, strength=(4, 6), agility=(11, 14), defense=(0, 2), aliases=("giant rat",)),
    EnemyTemplate("wolf", "Wolf", (40, 46), (7, 9), "beast", "A wild wolf, with sharp teeth and claws.",
                  level=1, strength=(6, 8), agility=(10, 13), defense=(1, 3), on_hit=(_bleed(4, 3, 0.20),)),
    EnemyTemplate("bandit", "Bandit", (56, 64), (10, 12), "humanoid",
                  "An opportunistic highwayman looking for an easy score.",
                  level=3, strength=(8, 11), agility=(8, 11), defense=(4, 8)),
    EnemyTemplate("orc", "Orc Warrior", (74, 82), (12, 14), "humanoid", "A large, brutish warrior with crude armor.",
                  level=4, strength=(11, 14), agility=(6, 9), defense=(6, 10), aliases=("orc warrior",)),
    EnemyTemplate("spriggan", "Spriggan", (64, 72), (11, 13), "fae", "A small, agile creature with a knack for stealth.",
                  level=5, strength=(6, 8), agility=(12, 15), defense=(3, 5),
                  spellbook=(_spell("Briar Snare", SpellType.BLEED, 6, "Thorns that bite and hold"),)),
    EnemyTemplate("troll", "Cave Troll", (112, 124), (14, 16), "giant", "A massive creature with regenerative abilities.",
                  level=6, strength=(13, 16), agility=(5, 7), defense=(5, 8), regen_pct=0.05, aliases=("cave troll",)),
    EnemyTemplate("dire_wolf", "Dire Wolf", (78, 86), (13, 15), "beast",
                  "A larger, more vicious wolf with keen instincts.",
                  level=6, strength=(10, 12), agility=(12, 15), defense=(3, 6), on_hit=(_bleed(5, 3, 0.25),)),
    # ---------------------------------------------------------------- levels 8-12
    EnemyTemplate("hagraven", "Hagraven", (84, 94), (15, 17), "witch",
                  "A corrupted hag who weaves dark magic and preys on wanderers.",
                  level=8, strength=(7, 10), agility=(9, 12), defense=(4, 6), spell_chance=0.45,
                  spellbook=(_spell("Venom Hex", SpellType.POISON, 9, "Rot that walks"),
                             _spell("Hex of Frailty", SpellType.VULNERABLE, 0, "Your skin turns to paper"))),
    EnemyTemplate("cave_bear", "Cave Bear", (136, 148), (16, 18), "beast",
                  "A shaggy mountain of muscle that has never once been told no.",
                  level=8, strength=(14, 17), agility=(6, 8), defense=(8, 10), on_hit=(_bleed(6, 3, 0.25),)),
    EnemyTemplate("harpy", "Harpy", (76, 84), (14, 16), "beast", "A shrieking, filth-winged hunter of high crags.",
                  level=9, strength=(7, 9), agility=(15, 18), defense=(3, 5), spell_chance=0.3,
                  spellbook=(_spell("Shriek", SpellType.BLIND, 0, "A scream that blurs the world"),)),
    EnemyTemplate("ghost_horror", "Ghost Horror", (130, 145), (16, 18), "undead",
                  "A formless terror of whispers and frostbitten dread.",
                  level=8, strength=(8, 10), agility=(10, 12), defense=(2, 4), resist=((P, 0.35),),
                  immune=(*UNDEAD, EffectKind.FROZEN),
                  spellbook=(_spell("Freeze", SpellType.FREEZE, 0, "Terror that stills"),),
                  intro_title="A HAUNTING PRESENCE ARRIVES",
                  intro_lines=("You wait... and something waits with you...",
                               "Frost creeps along the floor, swallowing your footprints...",
                               "The torches gutter. Breath fogs the air. All goes silent...",
                               "From the stillness, {name} takes shape — sorrow given form...",
                               "",
                               "It has come to punish hesitation.")),
    EnemyTemplate("giant", "Giant", (160, 176), (19, 21), "giant", "A massive creature with a huge club made of wood.",
                  level=10, strength=(16, 19), agility=(4, 6), defense=(10, 14)),
    EnemyTemplate("wraith", "Wraith", (98, 110), (17, 19), "undead", "A vengeful spirit that drains warmth and hope.",
                  level=10, strength=(8, 10), agility=(12, 14), defense=(2, 4), resist=((P, 0.3),), immune=UNDEAD,
                  spellbook=(_spell("Chill", SpellType.BLIND, 0, "Chill the eyes"),
                             _spell("Soul Drain", SpellType.DAMAGE, 14, "Warmth, stolen", drain=0.5))),
    EnemyTemplate("barrow_wight", "Barrow Wight", (132, 146), (18, 20), "undead",
                  "A dead chieftain in rotted mail, still guarding a hoard no one remembers.",
                  level=12, strength=(12, 14), agility=(8, 10), defense=(10, 13), resist=((P, 0.25),), immune=UNDEAD,
                  spellbook=(_spell("Grave Chill", SpellType.WEAKEN, 0, "Cold that saps the arm"),
                             _spell("Barrow Touch", SpellType.DAMAGE, 16, "A touch like a buried winter",
                                    drain=0.4))),
    EnemyTemplate("ogre", "Ogre", (196, 214), (21, 24), "giant", "A brutish hulk with crushing blows and thick hide.",
                  level=12, strength=(17, 20), agility=(5, 7), defense=(12, 16)),
    # ---------------------------------------------------------------- levels 13-18
    EnemyTemplate("werewolf", "Werewolf", (162, 178), (19, 22), "beast", "A cursed hunter, half man, all hunger.",
                  level=13, strength=(14, 16), agility=(15, 18), defense=(6, 9), regen_pct=0.03,
                  on_hit=(_bleed(8, 3, 0.3),), spell_chance=0.25,
                  spellbook=(_spell("Frenzy", SpellType.HASTE, 0, "Moonlit fury"),)),
    EnemyTemplate("minotaur", "Minotaur", (204, 222), (21, 24), "beast", "A horned labyrinth-stalker with feral strength.",
                  level=14, strength=(18, 21), agility=(8, 10), defense=(12, 15), on_hit=(_bleed(7, 3, 0.25),)),
    EnemyTemplate("basilisk", "Basilisk", (190, 210), (20, 23), "beast",
                  "A crowned serpent whose gaze turns blood to stone.",
                  level=15, strength=(13, 15), agility=(10, 12), defense=(16, 20), immune=(EffectKind.POISON,),
                  on_hit=(_poison(9, 3, 0.35),), spell_chance=0.3,
                  spellbook=(_spell("Petrifying Gaze", SpellType.FREEZE, 0, "Do not meet its eyes"),)),
    EnemyTemplate("stone_golem", "Stone Golem", (256, 278), (20, 23), "construct",
                  "A walking fortress of quarried stone. Blades skate off it.",
                  level=17, strength=(19, 22), agility=(3, 5), defense=(22, 26), resist=((P, 0.3),),
                  immune=(EffectKind.POISON, EffectKind.BLEED, EffectKind.BLIND)),
    EnemyTemplate("dragon", "Young Dragon", (218, 240), (22, 25), "dragon", "A fearsome winged beast with fiery breath.",
                  level=17, strength=(16, 19), agility=(11, 13), defense=(16, 20), immune=(EffectKind.BURN,),
                  spellbook=(_spell("Dragonfire", SpellType.BURN, 12, "Dragonfire that sticks"),),
                  aliases=("young dragon",)),
    EnemyTemplate("wyvern", "Wyvern", (200, 218), (21, 24), "dragon", "A two-legged drake with a dripping tail spike.",
                  level=18, strength=(15, 17), agility=(15, 18), defense=(12, 15), on_hit=(_poison(10, 3, 0.35),)),
    # ---------------------------------------------------------------- levels 20+
    EnemyTemplate("fire_elemental", "Fire Elemental", (190, 208), (21, 24), "elemental",
                  "A pillar of living flame. Steel softens near it.",
                  level=20, strength=(13, 15), agility=(13, 15), defense=(8, 10), resist=((P, 0.15),),
                  immune=(EffectKind.BURN, EffectKind.POISON, EffectKind.BLEED), on_hit=(_burn(9, 3, 0.3),),
                  spellbook=(_spell("Flame Lash", SpellType.DAMAGE, 22, "A whip of fire"),)),
    EnemyTemplate("frost_troll", "Frost Troll", (290, 312), (24, 26), "giant",
                  "A troll of the high ice, its blood colder than the glacier it sleeps in.",
                  level=22, strength=(20, 23), agility=(6, 8), defense=(16, 20), regen_pct=0.03,
                  immune=(EffectKind.FROZEN,), on_hit=(_freeze(0.08),)),
    EnemyTemplate("wraith_lord", "Wraith Lord", (236, 256), (24, 26), "undead",
                  "A crowned shade that commands lesser dead with a whisper.",
                  level=24, strength=(14, 16), agility=(15, 17), defense=(8, 12), resist=((P, 0.25),),
                  immune=(*UNDEAD, EffectKind.FROZEN), spell_chance=0.45,
                  spellbook=(_spell("Hush", SpellType.SILENCE, 0, "All words die"),
                             _spell("Soul Rend", SpellType.DAMAGE, 26, "It pulls something out of you", drain=0.5),
                             _spell("Dread", SpellType.WEAKEN, 0, "Your arms grow heavy"))),
    EnemyTemplate("horrid_monster", "Horrid Monster", (200, 220), (22, 25), "aberration",
                  "A grotesque being stitched from nightmare and shadow.", level=14, strength=(15, 18),
                  agility=(9, 11), defense=(10, 13)),
    # ---------------------------------------------------------------- story / dialogue encounters
    EnemyTemplate("archmage", "Archmage", 420, 24, "humanoid", "A master of the arcane arts, relentless and precise.",
                  level=14, strength=(8, 10), agility=(12, 14), defense=(10, 12), resist=((M, 0.3),),
                  spell_chance=0.55,
                  spellbook=(_spell("Blind", SpellType.BLIND), _spell("Freeze", SpellType.FREEZE),
                             _spell("Burn", SpellType.BURN, 10, "A searing brand that lingers"),
                             _spell("Ward", SpellType.SHIELD), _spell("Heal", SpellType.HEAL, 60),
                             _spell("Arcane Bolt", SpellType.DAMAGE, 26)),
                  guaranteed_drops=(("superior_health_potion", 3), ("mage_robes", 1), ("runed_staff", 1))),
    EnemyTemplate("yjurgen", "Yjurgen", 160, 24, "humanoid",
                  "A large brute of a man, with a thick beard and a strong sense of honor and justice.",
                  level=9, strength=(16, 18), agility=(8, 10), defense=(8, 10)),
    EnemyTemplate("ziggy", "Ziggy", 260, 8, "humanoid", "A fat man, covered head to toe in armor but slow and weak.",
                  level=6, strength=(8, 10), agility=(3, 5), defense=(24, 28)),
    EnemyTemplate("jarvask", "Jarvask", 150, 13, "humanoid", "Well rounded fighter, not too strong, not too weak.",
                  level=6, strength=(11, 13), agility=(11, 13), defense=(8, 10)),
    EnemyTemplate("gorren", "Gorren", 70, 34, "humanoid", "Berserk madman with no armor, yet wielding a massive axe.",
                  level=8, strength=(18, 20), agility=(10, 12), defense=(0, 0)),
    EnemyTemplate("morrg", "Morrg", 90, 15, "humanoid", "A dark and twisted figure, with a twisted sense of humor.",
                  level=5, strength=(9, 11), agility=(10, 12), defense=(5, 7),
                  spellbook=(_spell("Cruel Jest", SpellType.WEAKEN),)),
    # ---------------------------------------------------------------- bosses
    EnemyTemplate("stone_sentinel", "Stone Sentinel", 230, 12, "construct",
                  "A vault guardian of carved granite, its core ticking like a slow heart.", is_boss=True,
                  level=3, strength=(9, 11), agility=(5, 7), defense=(10, 12), immune=(EffectKind.POISON, EffectKind.BLEED),
                  intro_title="THE VAULT WAKES",
                  intro_lines=("Dust sifts from the ceiling as the alcove at the end of the hall splits open.",
                               "",
                               "{name} steps down from its plinth, granite grinding on granite.",
                               "Runes crawl across its knuckles. Somewhere in its chest, a core ticks.",
                               "",
                               "It turns its blank face toward you."),
                  reward_choices=("sentinel_plate", "sentinel_core", "hourglass_pendant"),
                  qte_triggers=SENTINEL_QTES),
    EnemyTemplate("titan", "Titan", (500, 550), (44, 48), "Boss", is_boss=True, title_variants=TITANS,
                  level=10, strength=(15, 17), agility=(7, 9), defense=(16, 18),
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
    EnemyTemplate("elder_dragon", "Elder Dragon", (820, 880), (48, 52), "Boss",
                  "An ancient wyrm wreathed in ruinous flame.", is_boss=True,
                  level=15, strength=(18, 20), agility=(11, 13), defense=(22, 26), immune=(EffectKind.BURN,),
                  spell_chance=0.35,
                  spellbook=(_spell("Ruinous Flame", SpellType.BURN, 14), _spell("Wing Buffet", SpellType.WEAKEN),
                             _spell("Searing Gout", SpellType.DAMAGE, 34)),
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
    EnemyTemplate("valorian_warden", "Valorian Warden", 1250, 44, "Boss",
                  "A sentinel bound to the gates by oath and old steel.", is_boss=True,
                  level=18, strength=(19, 21), agility=(10, 12), defense=(34, 38), thorns=0.12,
                  spellbook=(_spell("Shield Wall", SpellType.SHIELD), _spell("Oathbreaker", SpellType.VULNERABLE)),
                  intro_title="THE GATE REMEMBERS", intro_lines=GENERIC_BOSS_INTRO, reward_choices=TITAN_REWARDS),
    EnemyTemplate("earth_eater_worm", "Earth Eater Worm", (1050, 1120), (54, 58), "Boss",
                  "A burrowing leviathan whose maw devours stone and light.", is_boss=True,
                  level=20, strength=(20, 22), agility=(8, 10), defense=(20, 24), resist=((P, 0.15),),
                  immune=(EffectKind.BLIND, EffectKind.FROZEN), on_hit=(_bleed(12, 3, 0.3),), spell_chance=0.25,
                  spellbook=(_spell("Burrow", SpellType.SHIELD, 0, "It sinks into the earth",
                                    effect=EffectSpec(EffectKind.SHIELD, 0.4, 2)),),
                  intro_title="THE EARTH SPLITS OPEN",
                  intro_lines=("Pebbles skitter. Cracks race like lightning underfoot...",
                               "The ground heaves as if the world is changing its mind.",
                               "Soil domes, shatters — and the maw of {name}, {title}, blooms like a pit.",
                               "Ribs of stone snap between its rings. The air tastes of iron and old dark.",
                               "It listens with its whole body. It answers with hunger."),
                  reward_choices=("earthsplitter_maul", "stonebore_crossbow", "seismic_rift"),
                  qte_triggers=WORM_QTES),
    EnemyTemplate("lich_regent", "Lich Regent", 1500, 46, "Boss", "A sovereign of silence wearing a crown of names.",
                  is_boss=True, level=22, strength=(14, 16), agility=(14, 16), defense=(18, 22), resist=((M, 0.3),),
                  immune=(*UNDEAD, EffectKind.FROZEN, EffectKind.SILENCE), spell_chance=0.5,
                  spellbook=(_spell("Grave Rot", SpellType.POISON, 14), _spell("Deathly Ward", SpellType.SHIELD),
                             _spell("Crown of Silence", SpellType.SILENCE),
                             _spell("Name Theft", SpellType.DAMAGE, 34, drain=0.5)),
                  intro_title="THE SILENT THRONE", intro_lines=GENERIC_BOSS_INTRO, reward_choices=TITAN_REWARDS),
    EnemyTemplate("clockwork_colossus", "Clockwork Colossus", 1750, 50, "Boss",
                  "A titan of gears and grief, wound to outlast the sun.", is_boss=True,
                  level=24, strength=(22, 24), agility=(6, 8), defense=(40, 44), resist=((P, 0.25),),
                  immune=(EffectKind.POISON, EffectKind.BLEED, EffectKind.BLIND),
                  spellbook=(_spell("Overclock", SpellType.HASTE),),
                  intro_title="GEARS OF GRIEF", intro_lines=GENERIC_BOSS_INTRO, reward_choices=TITAN_REWARDS),
    EnemyTemplate("rat_king", "Rat King", (1250, 1330), (46, 49), "Boss",
                  "A crown of tails, sovereign of skitter and rot.", is_boss=True,
                  level=25, strength=(20, 22), agility=(15, 17), defense=(18, 22), immune=(EffectKind.POISON,),
                  regen_pct=0.01, on_hit=(_poison(9, 3, 0.3),), spell_chance=0.3,
                  spellbook=(_spell("Plague Bite", SpellType.POISON, 16), _spell("Gnawing Frenzy", SpellType.HASTE),
                             _spell("Filth Cloud", SpellType.BLIND)),
                  intro_title="A SCRATCHING CROWN APPROACHES",
                  intro_lines=("Threads of chittering stitch the dark...",
                               "Stone sweats; the air smells of cellar and spoil.",
                               "Rats pour like water, braiding themselves about a throne — {name}, {title}.",
                               "Eyes glitter in a hundred small faces. One voice speaks from all of them.",
                               "It promises a kingdom of tunnels, and taxes paid in gnawed bone."),
                  reward_choices=("gnawblade", "sewer_longbow", "pestilent_swarm"), qte_triggers=RAT_KING_QTES),
]

# Weighted hunt pools by player level band: (max_level_exclusive, [(template_id, weight), ...])
LEVEL_POOLS: list[tuple[int, list[tuple[str, int]]]] = [
    (4, [("goblin", 30), ("skeleton", 25), ("wolf", 30), ("bandit", 15)]),
    (7, [("orc", 22), ("bandit", 15), ("wolf", 10), ("dire_wolf", 14), ("spriggan", 14), ("troll", 10),
         ("skeleton", 8), ("goblin", 7)]),
    (10, [("troll", 15), ("dire_wolf", 12), ("hagraven", 14), ("orc", 12), ("cave_bear", 15), ("harpy", 14),
          ("spriggan", 8), ("bandit", 10)]),
    (13, [("giant", 14), ("wraith", 14), ("cave_bear", 10), ("harpy", 10), ("hagraven", 12), ("barrow_wight", 14),
          ("ogre", 10), ("troll", 8), ("werewolf", 8)]),
    (16, [("ogre", 14), ("werewolf", 14), ("minotaur", 12), ("barrow_wight", 12), ("basilisk", 12), ("giant", 10),
          ("wraith", 10), ("hagraven", 6)]),
    (20, [("minotaur", 14), ("basilisk", 12), ("stone_golem", 12), ("dragon", 10), ("wyvern", 12), ("werewolf", 10),
          ("ogre", 8), ("barrow_wight", 8)]),
    (24, [("wyvern", 14), ("stone_golem", 12), ("fire_elemental", 14), ("dragon", 12), ("frost_troll", 12),
          ("minotaur", 8), ("basilisk", 8)]),
    (10**9, [("frost_troll", 14), ("wraith_lord", 14), ("fire_elemental", 12), ("dragon", 12), ("wyvern", 10),
             ("stone_golem", 10), ("minotaur", 6)]),
]


def normalize_enemy_id(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


class UnknownEnemyError(KeyError):
    pass


def affix_chance(level: int) -> float:
    return min(0.5, config.AFFIX_CHANCE + 0.01 * level)


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

    def create(self, enemy_id: str, rng: random.Random | None = None, level: int | None = None) -> Enemy:
        """A fresh enemy; with ``level`` it is scaled from its design level (bosses never shrink)."""
        rng = rng or random.Random()
        enemy = Enemy(self.templates[self.resolve(enemy_id)], rng)
        if level is not None:
            enemy.scale_to_level(level)
        return enemy

    def random_for_level(self, level: int, rng: random.Random) -> Enemy:
        pool = next(entries for limit, entries in LEVEL_POOLS if level < limit)
        ids, weights = zip(*pool)
        enemy_level = max(1, level + rng.choice((-1, 0, 0, 0, 1)))
        return self.create(rng.choices(ids, weights=weights, k=1)[0], rng, enemy_level)

    @staticmethod
    def roll_affix(enemy: Enemy, rng: random.Random, chance: float | None = None) -> Affix | None:
        """Maybe give a hunt enemy a modifier; from level 15 elites can roll a second one."""
        if enemy.is_boss or rng.random() >= (affix_chance(enemy.level) if chance is None else chance):
            return None
        affix = rng.choice(AFFIXES)
        apply_affix(enemy, affix)
        if enemy.level >= 15 and rng.random() < config.DOUBLE_AFFIX_CHANCE:
            second = rng.choice([a for a in AFFIXES if a is not affix])
            apply_affix(enemy, second)
        return affix


ENEMIES = EnemyFactory()
for _template in _TEMPLATES:
    ENEMIES.register(_template)
