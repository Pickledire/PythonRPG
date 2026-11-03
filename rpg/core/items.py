"""Item model: weapons, armor, consumables, spells and curios.

Every item instance has a unique ``uid`` so two items that share a name (a worn sword and a
fresh one) are never confused. ``template_id`` points back at the catalog entry it came from.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from rpg.core.attributes import Attribute, Requirement, Requirements, describe_requirements
from rpg.core.effects import EffectKind, EffectSpec


def new_uid() -> str:
    return uuid.uuid4().hex[:12]


class ItemKind(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    SPELL = "spell"
    ACCESSORY = "accessory"
    MISC = "misc"

    @property
    def label(self) -> str:
        return {"weapon": "Weapon", "armor": "Armor", "consumable": "Consumable", "spell": "Spell",
                "accessory": "Jewelry", "misc": "Curio"}[self.value]


class WeaponClass(str, Enum):
    MELEE = "melee"
    RANGED = "ranged"
    MAGIC = "magic"


class ConsumableEffect(str, Enum):
    HEAL = "heal"
    MANA = "mana"
    RESTORE = "restore"  # heals HP and mana by the same amount
    CURE = "cure"  # removes harmful status effects
    SKILL_BOOST = "skill_boost"  # primes ``skill`` by ``potency`` for the next minigame that uses it
    LOCKPICK = "lockpick"  # spent by the lockpicking minigame; ``potency`` is the pick's quality (1-3)


class SpellType(str, Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    SHIELD = "shield"
    BLIND = "blind"
    POISON = "poison"
    BURN = "burn"
    BLEED = "bleed"
    FREEZE = "freeze"
    REGEN = "regen"  # healing over time on yourself
    HASTE = "haste"  # act twice per turn
    WEAKEN = "weaken"  # enemy deals less damage
    VULNERABLE = "vulnerable"  # enemy takes more damage ("Expose")
    SILENCE = "silence"  # enemy can't cast
    CLEANSE = "cleanse"  # remove your harmful effects


SELF_TARGETED = {SpellType.HEAL, SpellType.SHIELD, SpellType.REGEN, SpellType.HASTE, SpellType.CLEANSE}
WISDOM_SPELLS = {SpellType.HEAL, SpellType.SHIELD, SpellType.REGEN, SpellType.CLEANSE}


# ---------------------------------------------------------------- default requirement rules
# Catalog entries may override these with explicit (often multi-attribute) requirements.
FINESSE_KEYWORDS = ("dagger", "claw", "rapier")


def is_finesse(name: str, weapon_class: "WeaponClass") -> bool:
    return weapon_class == WeaponClass.MELEE and any(k in name.lower() for k in FINESSE_KEYWORDS)


def _tier(value: int, tiers: tuple[tuple[int, int], ...], top: int) -> int:
    for limit, requirement in tiers:
        if value <= limit:
            return requirement
    return top


def default_weapon_requirements(name: str, damage: int, weapon_class: "WeaponClass", finesse: bool) -> Requirements:
    if weapon_class == WeaponClass.RANGED or finesse:
        return (Requirement(Attribute.DEXTERITY, _tier(damage, ((18, 10), (25, 12)), 14)),)
    if weapon_class == WeaponClass.MAGIC:
        return (Requirement(Attribute.INTELLIGENCE, _tier(damage, ((20, 10), (35, 12)), 14)),)
    return (Requirement(Attribute.STRENGTH, _tier(damage, ((15, 8), (25, 12)), 15)),)


def default_armor_requirements(name: str, defense: int) -> Requirements:
    lowered = name.lower()
    if any(k in lowered for k in ("plate", "dragon", "mithril", "chain", "scale", "mail")):
        attribute = Attribute.STRENGTH
    elif any(k in lowered for k in ("leather", "studded", "hide")):
        attribute = Attribute.AGILITY
    elif any(k in lowered for k in ("cloth", "robe", "enchanted", "vestment")):
        attribute = Attribute.INTELLIGENCE
    else:
        attribute = Attribute.STRENGTH if defense >= 20 else Attribute.AGILITY
    return (Requirement(attribute, _tier(defense, ((12, 8), (20, 10), (35, 12)), 14)),)


def default_spell_requirements(power: int, spell_type: "SpellType") -> Requirements:
    attribute = Attribute.WISDOM if spell_type in WISDOM_SPELLS else Attribute.INTELLIGENCE
    return (Requirement(attribute, _tier(power, ((20, 10), (35, 12)), 14)),)


# ---------------------------------------------------------------- items
@dataclass(kw_only=True)
class Item:
    template_id: str
    name: str
    value: int = 0
    description: str = ""
    requirements: Requirements | None = None  # None -> derived from the item's default rules
    # Minigame modifiers (see rpg.core.skills). Equipped gear and carried curios apply them.
    skill_bonuses: dict[str, int] = field(default_factory=dict)
    traits: tuple[str, ...] = ()
    # Worn bonuses (see rpg.core.passives): attributes like {"strength": 2} and passives like {"regen_pct": 0.03}.
    attribute_bonuses: dict[str, int] = field(default_factory=dict)
    passives: dict[str, float] = field(default_factory=dict)
    uid: str = field(default_factory=new_uid)

    kind: ClassVar[ItemKind] = ItemKind.MISC

    def __post_init__(self) -> None:
        if self.requirements is None:
            self.requirements = self.default_requirements()
        else:
            self.requirements = tuple(self.requirements)
        self.skill_bonuses = {str(k): int(v) for k, v in (self.skill_bonuses or {}).items() if int(v)}
        self.traits = tuple(self.traits or ())
        self.attribute_bonuses = {str(k): int(v) for k, v in (self.attribute_bonuses or {}).items() if int(v)}
        self.passives = {str(k): float(v) for k, v in (self.passives or {}).items() if float(v)}

    @property
    def equippable(self) -> bool:
        return False

    def worn_text(self) -> str:
        """``STR +2 · Regenerate HP/turn +3%`` for attribute bonuses and passives."""
        from rpg.core.passives import passive_text

        parts = [f"{Attribute(k).short} {v:+d}" for k, v in self.attribute_bonuses.items()]
        parts += [passive_text(k, v) for k, v in self.passives.items()]
        return " · ".join(parts)

    def bonus_text(self) -> str:
        """``Stealth +3 · Balance -1 · Keen senses`` (empty when the item has no minigame modifiers)."""
        from rpg.core.skills import SKILL_INFO, TRAITS, Skill

        parts = [self.worn_text()] if self.worn_text() else []
        for key, amount in self.skill_bonuses.items():
            try:
                label = SKILL_INFO[Skill(key)].label
            except ValueError:
                label = key.capitalize()
            parts.append(f"{label} {amount:+d}")
        parts += [TRAITS[t].label if t in TRAITS else t for t in self.traits]
        return " · ".join(parts)

    def default_requirements(self) -> Requirements:
        return ()

    @property
    def stackable(self) -> bool:
        return False

    def stack_key(self) -> tuple | None:
        """Items with equal stack keys share an inventory slot. ``None`` means never stack."""
        return None

    @property
    def sell_price(self) -> int:
        from rpg.config import SELL_RATIO

        return max(1, int(self.value * SELL_RATIO))

    def summary(self) -> str:
        """One-line stat summary for tables."""
        return self.description

    def details(self) -> list[str]:
        """Multi-line description for detail panes."""
        lines = [f"{self.kind.label}", self.description] if self.description else [self.kind.label]
        if self.bonus_text():
            lines.append(("Trinket: " if self.kind == ItemKind.MISC else "") + self.bonus_text())
        if self.requirements:
            lines.append(f"Requires {describe_requirements(self.requirements)}")
        lines.append(f"Value {self.value}g · sells for {self.sell_price}g")
        return lines

    def clone(self) -> "Item":
        """Fresh copy with a new uid (shop stock and loot tables hand out clones)."""
        return item_from_dict({**self.to_dict(), "uid": new_uid()})

    # ------------------------------------------------------------ serialization
    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "template_id": self.template_id,
            "uid": self.uid,
            "name": self.name,
            "value": self.value,
            "description": self.description,
            "requirements": [r.to_dict() for r in self.requirements or ()],
            **({"skill_bonuses": dict(self.skill_bonuses)} if self.skill_bonuses else {}),
            **({"traits": list(self.traits)} if self.traits else {}),
            **({"attribute_bonuses": dict(self.attribute_bonuses)} if self.attribute_bonuses else {}),
            **({"passives": dict(self.passives)} if self.passives else {}),
        }

    @classmethod
    def _base_kwargs(cls, data: dict) -> dict:
        return {
            "template_id": data.get("template_id", "custom"),
            "uid": data.get("uid") or new_uid(),
            "name": data["name"],
            "value": int(data.get("value", 0)),
            "description": data.get("description", ""),
            # Older saves stored a single "requirement"; those are re-derived from the current rules
            # (catalog items are refreshed from the catalog on load anyway).
            "requirements": (tuple(Requirement.from_dict(r) for r in data["requirements"])
                             if "requirements" in data else None),
            "skill_bonuses": dict(data.get("skill_bonuses") or {}),
            "traits": tuple(data.get("traits") or ()),
            "attribute_bonuses": dict(data.get("attribute_bonuses") or {}),
            "passives": dict(data.get("passives") or {}),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(**cls._base_kwargs(data))


@dataclass(kw_only=True)
class Weapon(Item):
    damage: int
    weapon_class: WeaponClass = WeaponClass.MELEE
    max_durability: int = 100
    durability: int = -1  # -1 means "start at max"
    on_hit: EffectSpec | None = None
    finesse: bool | None = None  # light blade that scales with Dexterity; None -> guessed from the name

    kind: ClassVar[ItemKind] = ItemKind.WEAPON

    @property
    def equippable(self) -> bool:
        return True

    def __post_init__(self) -> None:
        if self.durability < 0:
            self.durability = self.max_durability
        if self.finesse is None:
            self.finesse = is_finesse(self.name, self.weapon_class)
        super().__post_init__()

    def default_requirements(self) -> Requirements:
        return default_weapon_requirements(self.name, self.damage, self.weapon_class, bool(self.finesse))

    @property
    def is_broken(self) -> bool:
        return self.durability <= 0

    @property
    def effective_damage(self) -> int:
        """A worn weapon loses up to 30% of its damage; a broken one does nothing until repaired."""
        if self.is_broken:
            return 0
        ratio = self.durability / self.max_durability if self.max_durability else 1
        return int(self.damage * (0.7 + 0.3 * ratio))

    def wear(self, amount: int = 1) -> bool:
        """Spend durability; returns True if this use broke the weapon."""
        was_intact = not self.is_broken
        self.durability = max(0, self.durability - amount)
        return was_intact and self.is_broken

    def repair(self) -> None:
        self.durability = self.max_durability

    @property
    def missing_durability(self) -> int:
        return self.max_durability - self.durability

    def summary(self) -> str:
        style = "finesse" if self.finesse else self.weapon_class.value
        text = f"DMG {self.damage} · {style} · {self.durability}/{self.max_durability}"
        if self.on_hit:
            text += f" · {self.on_hit.describe()}"
        if self.bonus_text():
            text += f" · {self.bonus_text()}"
        return text

    def details(self) -> list[str]:
        lines = [
            ("Finesse" if self.finesse else self.weapon_class.value.capitalize()) + " weapon",
            self.description,
            f"Damage {self.damage} (effective {self.effective_damage})",
            f"Durability {self.durability}/{self.max_durability}" + ("  BROKEN" if self.is_broken else ""),
        ]
        if self.on_hit:
            lines.append(f"On hit: {self.on_hit.describe()}")
        if self.bonus_text():
            lines.append(f"When equipped: {self.bonus_text()}")
        if self.requirements:
            lines.append(f"Requires {describe_requirements(self.requirements)}")
        lines.append(f"Value {self.value}g · sells for {self.sell_price}g")
        return [line for line in lines if line]

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "damage": self.damage,
            "weapon_class": self.weapon_class.value,
            "max_durability": self.max_durability,
            "durability": self.durability,
            "on_hit": self.on_hit.to_dict() if self.on_hit else None,
            "finesse": self.finesse,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Weapon":
        return cls(
            **cls._base_kwargs(data),
            damage=int(data.get("damage", 1)),
            weapon_class=WeaponClass(data.get("weapon_class", "melee")),
            max_durability=int(data.get("max_durability", 100)),
            durability=int(data.get("durability", -1)),
            on_hit=EffectSpec.from_dict(data.get("on_hit")),
            finesse=data.get("finesse"),
        )


@dataclass(kw_only=True)
class Armor(Item):
    defense: int
    max_durability: int = 100
    durability: int = -1

    kind: ClassVar[ItemKind] = ItemKind.ARMOR

    @property
    def equippable(self) -> bool:
        return True

    def __post_init__(self) -> None:
        if self.durability < 0:
            self.durability = self.max_durability
        super().__post_init__()

    def default_requirements(self) -> Requirements:
        return default_armor_requirements(self.name, self.defense)

    @property
    def is_broken(self) -> bool:
        return self.durability <= 0

    @property
    def effective_defense(self) -> float:
        """Battered armor loses up to 30% of its rating; broken armor does nothing until repaired."""
        if self.is_broken:
            return 0.0
        ratio = self.durability / self.max_durability if self.max_durability else 1
        return self.defense * (0.7 + 0.3 * ratio)

    def wear(self, amount: int = 1) -> bool:
        was_intact = not self.is_broken
        self.durability = max(0, self.durability - amount)
        return was_intact and self.is_broken

    def repair(self) -> None:
        self.durability = self.max_durability

    @property
    def missing_durability(self) -> int:
        return self.max_durability - self.durability

    def summary(self) -> str:
        text = f"DEF {self.defense} · {self.durability}/{self.max_durability}"
        return f"{text} · {self.bonus_text()}" if self.bonus_text() else text

    def details(self) -> list[str]:
        lines = [
            "Armor",
            self.description,
            f"Defense {self.defense} (effective {self.effective_defense:.0f})",
            f"Durability {self.durability}/{self.max_durability}" + ("  BROKEN" if self.is_broken else ""),
        ]
        if self.bonus_text():
            lines.append(f"When worn: {self.bonus_text()}")
        if self.requirements:
            lines.append(f"Requires {describe_requirements(self.requirements)}")
        lines.append(f"Value {self.value}g · sells for {self.sell_price}g")
        return [line for line in lines if line]

    def to_dict(self) -> dict:
        return {**super().to_dict(), "defense": self.defense, "max_durability": self.max_durability, "durability": self.durability}

    @classmethod
    def from_dict(cls, data: dict) -> "Armor":
        return cls(
            **cls._base_kwargs(data),
            defense=int(data.get("defense", 0)),
            max_durability=int(data.get("max_durability", 100)),
            durability=int(data.get("durability", -1)),
        )


@dataclass(kw_only=True)
class Consumable(Item):
    effect: ConsumableEffect
    potency: int = 0
    skill: str | None = None  # the skill a SKILL_BOOST primes

    kind: ClassVar[ItemKind] = ItemKind.CONSUMABLE

    @property
    def stackable(self) -> bool:
        return True

    def stack_key(self) -> tuple:
        return (self.kind.value, self.name, self.effect.value, self.potency, self.skill)

    @property
    def usable_in_combat(self) -> bool:
        return self.effect != ConsumableEffect.LOCKPICK

    def summary(self) -> str:
        if self.effect == ConsumableEffect.SKILL_BOOST:
            from rpg.core.skills import Skill

            label = Skill(self.skill).label if self.skill else "Skill"
            return f"+{self.potency} {label} for your next {label.lower()} trial"
        if self.effect == ConsumableEffect.LOCKPICK:
            return {1: "Snaps under strain", 2: "Takes more strain before it snaps"}.get(
                self.potency, "Almost never snaps")
        return {
            ConsumableEffect.HEAL: f"Restores {self.potency} HP",
            ConsumableEffect.MANA: f"Restores {self.potency} mana",
            ConsumableEffect.RESTORE: f"Restores {self.potency} HP and mana",
            ConsumableEffect.CURE: "Cures poison, burn, bleed, blind and frost",
        }[self.effect]

    def details(self) -> list[str]:
        return [line for line in ["Consumable", self.description, self.summary(), f"Value {self.value}g · sells for {self.sell_price}g"] if line]

    def to_dict(self) -> dict:
        data = {**super().to_dict(), "effect": self.effect.value, "potency": self.potency}
        if self.skill:
            data["skill"] = self.skill
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Consumable":
        return cls(**cls._base_kwargs(data), effect=ConsumableEffect(data.get("effect", "heal")),
                   potency=int(data.get("potency", 0)), skill=data.get("skill"))


@dataclass(kw_only=True)
class Spell(Item):
    spell_type: SpellType
    power: int = 0  # damage for damage spells, potency for support/status spells
    mana_cost: int = 10
    inflicts: EffectSpec | None = None  # optional secondary effect on the target
    effect: EffectSpec | None = None  # overrides the spell type's default status effect
    self_effect: EffectSpec | None = None  # a buff on the caster as well (Sanctuary: heal + ward)
    drain: float = 0.0  # damage spells: heal the caster for this share of damage dealt

    kind: ClassVar[ItemKind] = ItemKind.SPELL

    @property
    def equippable(self) -> bool:
        return True

    def default_requirements(self) -> Requirements:
        return default_spell_requirements(self.power, self.spell_type)

    @property
    def targets_self(self) -> bool:
        return self.spell_type in SELF_TARGETED

    def primary_effect(self) -> EffectSpec | None:
        """The status a status-type spell applies (damage/heal spells have none unless ``effect`` is set)."""
        if self.effect:
            return self.effect
        return {
            SpellType.SHIELD: EffectSpec(EffectKind.SHIELD, 0.3, 3),
            SpellType.BLIND: EffectSpec(EffectKind.BLIND, 0.25, 3),
            SpellType.FREEZE: EffectSpec(EffectKind.FROZEN, 0, 1),
            SpellType.BURN: EffectSpec(EffectKind.BURN, max(5, self.power or 10), 4),
            SpellType.POISON: EffectSpec(EffectKind.POISON, max(6, self.power or 12), 4),
            SpellType.BLEED: EffectSpec(EffectKind.BLEED, max(5, self.power or 10), 4),
            SpellType.REGEN: EffectSpec(EffectKind.REGEN, max(6, self.power or 10), 4),
            SpellType.HASTE: EffectSpec(EffectKind.HASTE, 1, 2),
            SpellType.WEAKEN: EffectSpec(EffectKind.WEAKEN, 0.3, 3),
            SpellType.VULNERABLE: EffectSpec(EffectKind.VULNERABLE, 0.25, 3),
            SpellType.SILENCE: EffectSpec(EffectKind.SILENCE, 0, 2),
        }.get(self.spell_type)

    def summary(self) -> str:
        if self.spell_type == SpellType.DAMAGE:
            text = f"DMG {self.power} · {self.mana_cost} MP"
            if self.drain:
                text += f" · heals {int(self.drain * 100)}% of damage"
        elif self.spell_type == SpellType.HEAL:
            text = f"Heal {self.power or 'base'} · {self.mana_cost} MP"
        elif self.spell_type == SpellType.CLEANSE:
            text = f"Purge harmful effects · {self.mana_cost} MP"
        else:
            effect = self.primary_effect()
            text = f"{effect.describe() if effect else self.spell_type.value} · {self.mana_cost} MP"
        if self.inflicts:
            text += f" · {self.inflicts.describe()}"
        if self.self_effect:
            text += f" · you gain {self.self_effect.describe()}"
        return text

    def details(self) -> list[str]:
        lines = [f"{self.spell_type.value.capitalize()} spell", self.description, self.summary()]
        if self.requirements:
            lines.append(f"Requires {describe_requirements(self.requirements)}")
        lines.append(f"Value {self.value}g · sells for {self.sell_price}g")
        return [line for line in lines if line]

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "spell_type": self.spell_type.value,
            "power": self.power,
            "mana_cost": self.mana_cost,
            "inflicts": self.inflicts.to_dict() if self.inflicts else None,
            "effect": self.effect.to_dict() if self.effect else None,
            "self_effect": self.self_effect.to_dict() if self.self_effect else None,
            "drain": self.drain,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Spell":
        return cls(
            **cls._base_kwargs(data),
            spell_type=SpellType(data.get("spell_type", "damage")),
            power=int(data.get("power", 0)),
            mana_cost=int(data.get("mana_cost", 10)),
            inflicts=EffectSpec.from_dict(data.get("inflicts")),
            effect=EffectSpec.from_dict(data.get("effect")),
            self_effect=EffectSpec.from_dict(data.get("self_effect")),
            drain=float(data.get("drain", 0.0)),
        )


class AccessorySlot(str, Enum):
    AMULET = "amulet"
    RING = "ring"


@dataclass(kw_only=True)
class Accessory(Item):
    """Amulets and rings: worn for their attribute bonuses and passives (see rpg.core.passives)."""

    slot: AccessorySlot = AccessorySlot.RING

    kind: ClassVar[ItemKind] = ItemKind.ACCESSORY

    def __post_init__(self) -> None:
        self.slot = AccessorySlot(self.slot)
        super().__post_init__()

    @property
    def equippable(self) -> bool:
        return True

    def summary(self) -> str:
        return f"{self.slot.value.capitalize()} · {self.worn_text() or self.description}"

    def details(self) -> list[str]:
        lines = [self.slot.value.capitalize(), self.description]
        if self.worn_text():
            lines.append(f"When worn: {self.worn_text()}")
        if self.requirements:
            lines.append(f"Requires {describe_requirements(self.requirements)}")
        lines.append(f"Value {self.value}g · sells for {self.sell_price}g")
        return [line for line in lines if line]

    def to_dict(self) -> dict:
        return {**super().to_dict(), "slot": self.slot.value}

    @classmethod
    def from_dict(cls, data: dict) -> "Accessory":
        return cls(**cls._base_kwargs(data), slot=AccessorySlot(data.get("slot", "ring")))


@dataclass(kw_only=True)
class Curio(Item):
    """Quest trinkets, tools and charms. They stack, can be sold, and do nothing in combat.

    Curios with bonuses (tools and charms) are *trinkets*: equip up to three for their ``skill_bonuses``,
    ``traits`` and passives. Plain story curios can't be equipped.
    """

    kind: ClassVar[ItemKind] = ItemKind.MISC

    @property
    def equippable(self) -> bool:
        return bool(self.skill_bonuses or self.traits or self.passives or self.attribute_bonuses)

    @property
    def stackable(self) -> bool:
        return True

    def stack_key(self) -> tuple:
        return (self.kind.value, self.name)

    def summary(self) -> str:
        return f"Trinket: {self.bonus_text()}" if self.bonus_text() else self.description


ITEM_CLASSES: dict[str, type[Item]] = {
    ItemKind.WEAPON.value: Weapon,
    ItemKind.ARMOR.value: Armor,
    ItemKind.CONSUMABLE.value: Consumable,
    ItemKind.SPELL.value: Spell,
    ItemKind.ACCESSORY.value: Accessory,
    ItemKind.MISC.value: Curio,
}


def item_from_dict(data: dict) -> Item:
    cls = ITEM_CLASSES.get(data.get("kind", "misc"), Curio)
    return cls.from_dict(data)
