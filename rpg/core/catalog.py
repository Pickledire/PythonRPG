"""Item catalog and factory.

All item content is declared here as data. To add an item, call one of the ``ITEMS.weapon/armor/...``
helpers below and reference its id from shops, loot tables, enemy rewards, races or dialogue JSON.

Prices: leave ``value`` out and the item is priced from its power by ``fair_value`` (damage, defense, spell
power, effects and passives), so new items slot into the economy automatically. Pass ``value=`` to override.

Requirements: leave ``requirements`` out to use the default rule for the item type (see
``rpg.core.items``), or pass ``req(strength=14, dexterity=13)`` for explicit, multi-attribute gates.

Tiers (what a piece is meant for):

    tier  levels   weapon dmg   armor def   main requirement
    1     1-4      9-16         4-12        8-11
    2     5-9      17-24        13-20       11-13
    3     10-14    25-33        21-28       13-15
    4     15-19    34-42        29-36       15-17
    5     20-25    43-52        37-45       17-19
    trophies       36-58        30-40       boss loot, one tier above the boss's level

Minigame modifiers: ``skills={"stealth": 3}`` and ``traits=("keen_senses",)``. Worn bonuses:
``attributes={"strength": 2}`` and ``passives={"regen_pct": 0.03}`` (see ``rpg.core.passives``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rpg.core.attributes import Requirements, req
from rpg.core.effects import EffectKind, EffectSpec
from rpg.core.items import (
    Accessory,
    AccessorySlot,
    Armor,
    Consumable,
    ConsumableEffect,
    Curio,
    Item,
    Spell,
    SpellType,
    Weapon,
    WeaponClass,
)


class UnknownItemError(KeyError):
    pass


@dataclass(frozen=True)
class ItemTemplate:
    template_id: str
    cls: type[Item]
    params: dict[str, Any]

    def create(self) -> Item:
        return self.cls(template_id=self.template_id, **self.params)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "item"


# ------------------------------------------------------------------ pricing
PASSIVE_VALUE = {  # gold per unit of each passive
    "max_hp": 2.5, "max_mana": 2.0, "regen_pct": 4000, "mana_regen": 18, "crit": 1500, "crit_damage": 400,
    "accuracy": 800, "dodge": 1800, "armor": 12, "weapon_damage": 900, "spell_power": 900, "healing": 600,
    "lifesteal": 1800, "thorns": 700, "execute": 400, "dot_power": 500, "dot_resist": 400, "status_resist": 600,
    "resist_physical": 1500, "resist_magic": 1000, "mana_cost": 1200, "start_ward": 400, "start_haste": 150,
    "flee": 300, "gold_find": 400, "xp_gain": 600,
}
ATTRIBUTE_POINT_VALUE = 45
IMMUNITY_VALUE = 90
EFFECT_VALUE = {  # utility spell value per (potency x turns), or flat
    EffectKind.SHIELD: 300, EffectKind.BLIND: 500, EffectKind.WEAKEN: 500, EffectKind.VULNERABLE: 600,
}


def bonus_value(item: Item) -> float:
    value = sum(ATTRIBUTE_POINT_VALUE * v for v in item.attribute_bonuses.values())
    for key, amount in item.passives.items():
        value += IMMUNITY_VALUE if key.startswith("immune_") else PASSIVE_VALUE.get(key, 0) * amount
    value += 20 * sum(item.skill_bonuses.values()) + 60 * len(item.traits)
    return value


def effect_value(spec: EffectSpec | None) -> float:
    if spec is None:
        return 0.0
    if spec.kind in (EffectKind.POISON, EffectKind.BURN, EffectKind.BLEED, EffectKind.REGEN):
        base = spec.potency * spec.turns * 4
    elif spec.kind in EFFECT_VALUE:
        base = spec.potency * spec.turns * EFFECT_VALUE[spec.kind]
    elif spec.kind == EffectKind.HASTE:
        base = 250 * spec.turns
    elif spec.kind == EffectKind.SILENCE:
        base = 200 * spec.turns
    else:  # frozen
        base = 350
    return base * spec.chance


def fair_value(item: Item) -> int:
    """Price from power. Keeps the economy consistent as content grows."""
    if isinstance(item, Weapon):
        value = 1.3 * item.damage ** 1.6 + effect_value(item.on_hit) * 0.6
    elif isinstance(item, Armor):
        value = 1.5 * item.defense ** 1.6
    elif isinstance(item, Spell):
        t = item.spell_type
        if t == SpellType.DAMAGE:
            value = 0.9 * item.power ** 1.5 * (1 + item.drain * 0.8)
        elif t == SpellType.HEAL:
            value = 3 * (item.power or 60)
        elif t == SpellType.CLEANSE:
            value = 150
        else:
            value = effect_value(item.primary_effect())
        value += effect_value(item.inflicts) * 0.5 + effect_value(item.self_effect) * 0.7
    elif isinstance(item, Accessory):
        value = 30
    else:
        value = 20
    value += bonus_value(item)
    return max(5, int(round(value / 5)) * 5)


class ItemFactory:
    """Registry of item templates; every ``create`` call returns a brand new instance."""

    def __init__(self) -> None:
        self._templates: dict[str, ItemTemplate] = {}

    def register(self, template_id: str, cls: type[Item], **params: Any) -> None:
        if template_id in self._templates:
            raise ValueError(f"Duplicate item id: {template_id}")
        if params.get("value") is None:
            params["value"] = 0
            params["value"] = fair_value(cls(template_id=template_id, **params))
        self._templates[template_id] = ItemTemplate(template_id, cls, params)

    def weapon(self, template_id: str, name: str, damage: int, description: str,
               weapon_class: WeaponClass = WeaponClass.MELEE, *, on_hit: EffectSpec | None = None,
               requirements: Requirements | None = None, finesse: bool | None = None, durability: int | None = None,
               value: int | None = None, skills: dict[str, int] | None = None, traits: tuple[str, ...] = (),
               attributes: dict[str, int] | None = None, passives: dict[str, float] | None = None) -> None:
        self.register(template_id, Weapon, name=name, damage=damage, max_durability=durability or 80 + damage * 3,
                      value=value, description=description, weapon_class=weapon_class, on_hit=on_hit,
                      requirements=requirements, finesse=finesse, skill_bonuses=skills or {}, traits=traits,
                      attribute_bonuses=attributes or {}, passives=passives or {})

    def armor(self, template_id: str, name: str, defense: int, description: str, *,
              requirements: Requirements | None = None, durability: int | None = None, value: int | None = None,
              skills: dict[str, int] | None = None, traits: tuple[str, ...] = (),
              attributes: dict[str, int] | None = None, passives: dict[str, float] | None = None) -> None:
        self.register(template_id, Armor, name=name, defense=defense, max_durability=durability or 90 + defense * 4,
                      value=value, description=description, requirements=requirements, skill_bonuses=skills or {},
                      traits=traits, attribute_bonuses=attributes or {}, passives=passives or {})

    def consumable(self, template_id: str, name: str, effect: ConsumableEffect, potency: int, value: int,
                   description: str, skill: str | None = None) -> None:
        self.register(template_id, Consumable, name=name, effect=effect, potency=potency, value=value,
                      description=description, skill=skill)

    def curio(self, template_id: str, name: str, value: int, description: str,
              skills: dict[str, int] | None = None, traits: tuple[str, ...] = (),
              passives: dict[str, float] | None = None) -> None:
        self.register(template_id, Curio, name=name, value=value, description=description,
                      skill_bonuses=skills or {}, traits=traits, passives=passives or {})

    def spell(self, template_id: str, name: str, spell_type: SpellType, power: int, mana_cost: int, description: str,
              *, inflicts: EffectSpec | None = None, effect: EffectSpec | None = None,
              self_effect: EffectSpec | None = None, drain: float = 0.0, requirements: Requirements | None = None,
              value: int | None = None) -> None:
        self.register(template_id, Spell, name=name, spell_type=spell_type, power=power, mana_cost=mana_cost,
                      value=value, description=description, inflicts=inflicts, effect=effect, self_effect=self_effect,
                      drain=drain, requirements=requirements)

    def jewelry(self, template_id: str, name: str, slot: AccessorySlot, description: str, *,
                attributes: dict[str, int] | None = None, passives: dict[str, float] | None = None,
                requirements: Requirements | None = None, value: int | None = None,
                skills: dict[str, int] | None = None, traits: tuple[str, ...] = ()) -> None:
        self.register(template_id, Accessory, name=name, slot=slot, description=description,
                      attribute_bonuses=attributes or {}, passives=passives or {}, requirements=requirements or (),
                      value=value, skill_bonuses=skills or {}, traits=traits)

    # ------------------------------------------------------------ lookup
    def __contains__(self, template_id: str) -> bool:
        return template_id in self._templates

    def ids(self) -> list[str]:
        return list(self._templates)

    def create(self, template_id: str) -> Item:
        try:
            return self._templates[template_id].create()
        except KeyError:
            raise UnknownItemError(template_id) from None

    def refresh_requirements(self, item: Item) -> None:
        """Re-apply current catalog data to an item loaded from a save, so balance changes reach old saves:
        requirements, modifiers, and the core numbers (damage, defense, spell power and cost, value)."""
        if item.template_id not in self._templates:
            return
        fresh = self._templates[item.template_id].create()
        item.requirements = fresh.requirements
        item.skill_bonuses = dict(fresh.skill_bonuses)
        item.traits = fresh.traits
        item.attribute_bonuses = dict(fresh.attribute_bonuses)
        item.passives = dict(fresh.passives)
        item.value = fresh.value
        item.description = fresh.description
        if isinstance(item, Weapon) and isinstance(fresh, Weapon):
            ratio = item.durability / item.max_durability if item.max_durability else 1
            item.damage, item.on_hit, item.finesse = fresh.damage, fresh.on_hit, fresh.finesse
            item.max_durability = fresh.max_durability
            item.durability = int(round(ratio * fresh.max_durability))
        elif isinstance(item, Armor) and isinstance(fresh, Armor):
            ratio = item.durability / item.max_durability if item.max_durability else 1
            item.defense, item.max_durability = fresh.defense, fresh.max_durability
            item.durability = int(round(ratio * fresh.max_durability))
        elif isinstance(item, Spell) and isinstance(fresh, Spell):
            item.power, item.mana_cost, item.inflicts = fresh.power, fresh.mana_cost, fresh.inflicts
            item.effect, item.self_effect, item.drain = fresh.effect, fresh.self_effect, fresh.drain

    def find_id_by_name(self, name: str) -> str | None:
        lowered = name.strip().lower()
        for template in self._templates.values():
            if str(template.params.get("name", "")).lower() == lowered:
                return template.template_id
        return None

    def from_spec(self, spec: str | dict) -> Item:
        """Build an item from a dialogue ``give_item`` payload.

        * A string is looked up as a catalog id, then as a display name; unknown names become curios.
        * A dict may name a catalog ``id``; otherwise it describes a custom item by ``type``
          (weapon/armor/magic/spell/consumable/ring/amulet, or melee/ranged as weapon shorthands).
        """
        if isinstance(spec, str):
            if spec in self._templates:
                return self.create(spec)
            found = self.find_id_by_name(spec)
            if found:
                return self.create(found)
            return Curio(template_id=f"custom:{slugify(spec)}", name=spec, description=f"A mysterious item named {spec}.")

        if "id" in spec and spec["id"] in self._templates:
            return self.create(spec["id"])
        name = str(spec.get("name", "Unknown Item"))
        found = self.find_id_by_name(name)
        if found and len(spec) <= 2:  # just {"name": ..., "type": ...}: use the catalog version
            return self.create(found)

        kind = str(spec.get("type", "consumable")).lower()
        weapon_class = spec.get("weapon_type")
        if kind in ("melee", "ranged"):
            weapon_class, kind = kind, "weapon"
        template_id = f"custom:{slugify(name)}"
        description = str(spec.get("description", ""))
        value = int(spec.get("value", 0))
        requirements = req(**spec["requires"]) if isinstance(spec.get("requires"), dict) else None
        extras = {"skill_bonuses": {str(k): int(v) for k, v in (spec.get("skills") or {}).items()},
                  "traits": tuple(spec.get("traits") or ()),
                  "attribute_bonuses": {str(k): int(v) for k, v in (spec.get("attributes") or {}).items()},
                  "passives": {str(k): float(v) for k, v in (spec.get("passives") or {}).items()}}
        if kind == "weapon":
            return Weapon(template_id=template_id, name=name, damage=int(spec.get("damage", 10)),
                          max_durability=int(spec.get("durability", 100)), value=value, description=description,
                          weapon_class=WeaponClass(weapon_class or "melee"), requirements=requirements, **extras)
        if kind == "armor":
            return Armor(template_id=template_id, name=name, defense=int(spec.get("defense", 5)),
                         max_durability=int(spec.get("durability", 100)), value=value, description=description,
                         requirements=requirements, **extras)
        if kind in ("magic", "spell"):
            return Spell(template_id=template_id, name=name, description=description, value=value,
                         spell_type=SpellType(spec.get("spell_type", "damage")), power=int(spec.get("damage", 15)),
                         mana_cost=int(spec.get("mana", 8)), requirements=requirements)
        if kind in ("ring", "amulet"):
            return Accessory(template_id=template_id, name=name, description=description, value=value,
                             slot=AccessorySlot(kind), requirements=requirements or (), **extras)
        if kind in ("curio", "charm", "tool", "misc"):
            return Curio(template_id=template_id, name=name, description=description, value=value, **extras)
        if kind == "consumable" and int(spec.get("heal", spec.get("potency", 0)) or 0) > 0:
            return Consumable(template_id=template_id, name=name, description=description, value=value,
                              effect=ConsumableEffect(spec.get("effect", "heal")),
                              potency=int(spec.get("heal", spec.get("potency", 0))))
        return Curio(template_id=template_id, name=name, description=description, value=value)


ITEMS = ItemFactory()

M, R, MG = WeaponClass.MELEE, WeaponClass.RANGED, WeaponClass.MAGIC
D = SpellType.DAMAGE
AMULET, RING = AccessorySlot.AMULET, AccessorySlot.RING
_bleed = lambda potency, turns, chance: EffectSpec(EffectKind.BLEED, potency, turns, chance)  # noqa: E731
_burn = lambda potency, turns, chance: EffectSpec(EffectKind.BURN, potency, turns, chance)  # noqa: E731
_poison = lambda potency, turns, chance: EffectSpec(EffectKind.POISON, potency, turns, chance)  # noqa: E731
_freeze = lambda chance: EffectSpec(EffectKind.FROZEN, 0, 1, chance)  # noqa: E731
_blind = lambda chance: EffectSpec(EffectKind.BLIND, 0.25, 2, chance)  # noqa: E731
_weaken = lambda potency, turns, chance: EffectSpec(EffectKind.WEAKEN, potency, turns, chance)  # noqa: E731
_expose = lambda potency, turns, chance: EffectSpec(EffectKind.VULNERABLE, potency, turns, chance)  # noqa: E731
_ward = lambda potency, turns: EffectSpec(EffectKind.SHIELD, potency, turns)  # noqa: E731

# =================================================================== WEAPONS
# ------------------------------------------------------------------- racial starting gear (tier 1)
ITEMS.weapon("iron_sword", "Iron Sword", 13, "A reliable iron sword.", requirements=req(strength=9))
ITEMS.weapon("elven_bow", "Elven Bow", 12, "A graceful elven bow.", R, skills={"precision": 1})
ITEMS.weapon("orcish_axe", "Orcish Axe", 14, "A brutal orcish war axe.", on_hit=_bleed(3, 3, 0.15),
             requirements=req(strength=11))
ITEMS.weapon("dwarven_hammer", "Dwarven Hammer", 14, "A sturdy dwarven war hammer.", requirements=req(strength=10))
ITEMS.weapon("thornwood_staff", "Thornwood Staff", 11, "A living branch that still puts out buds.", MG,
             passives={"healing": 0.05})
ITEMS.weapon("halfling_dagger", "Halfling Dagger", 11, "Small, sharp and always where you left it.",
             skills={"lockpicking": 1}, passives={"crit": 0.03})
ITEMS.weapon("clockwork_crossbow", "Clockwork Crossbow", 13, "Self-winding, mostly.", R, skills={"precision": 1})
ITEMS.weapon("dragonkin_glaive", "Dragonkin Glaive", 14, "A curved blade on a long haft, scaled grip.",
             requirements=req(strength=11))
ITEMS.weapon("bone_claws", "Bone Claws", 11, "Hooked claws lashed to the knuckles.", on_hit=_bleed(4, 3, 0.2))
ITEMS.weapon("grave_blade", "Grave Blade", 13, "Pitted iron pulled from the coffin you woke in.",
             requirements=req(strength=9), passives={"lifesteal": 0.03})
ITEMS.spell("elven_blast", "Elven Blast", D, 20, 8, "A magical blast of energy.")
ITEMS.spell("dwarven_scream", "Dwarven Scream", D, 14, 8, "A powerful dwarven scream.", inflicts=_blind(0.3))
ITEMS.spell("arc_spark", "Arc Spark", D, 16, 6, "A crackling arc from a gnomish coil.")
ITEMS.spell("thorn_lash", "Thorn Lash", SpellType.BLEED, 7, 9, "Whip a vine of thorns across the foe.",
            requirements=req(wisdom=10))
ITEMS.spell("ember_breath", "Ember Breath", SpellType.BURN, 7, 9, "Exhale the fire in your blood.",
            requirements=req(vitality=11))
ITEMS.spell("wither", "Wither", SpellType.POISON, 7, 9, "The grave's touch, borrowed.", requirements=req(wisdom=11))

# ------------------------------------------------------------------- melee (strength)
ITEMS.weapon("twisted_iron_blade", "Twisted Iron Blade", 12, "Bent in a forge accident and sold anyway.",
             requirements=req(strength=8))
ITEMS.weapon("bronze_sword", "Bronze Sword", 10, "A basic bronze sword.", requirements=req(strength=8))
ITEMS.weapon("axe", "Axe", 16, "A woodsman's axe with a fighting edge.", requirements=req(strength=10))
ITEMS.weapon("bronze_mace", "Bronze Mace", 16, "A flanged head on an ash haft. Simple and honest.",
             on_hit=_weaken(0.15, 2, 0.15), requirements=req(strength=10))
ITEMS.weapon("steel_sword", "Steel Sword", 18, "A sharp steel blade.", requirements=req(strength=11))
ITEMS.weapon("chipped_oak_greatsword", "Chipped Oakhardened Greatsword", 20,
             "Fire-hardened oak edged with salvaged steel. Ugly, heavy, effective.",
             requirements=req(strength=12, vitality=10))
ITEMS.weapon("spear", "Spear", 20, "A long ash spear with a leaf-shaped head.", on_hit=_bleed(4, 3, 0.15),
             requirements=req(strength=11, agility=10))
ITEMS.weapon("war_hammer", "War Hammer", 23, "A heavy two-handed hammer.", on_hit=_weaken(0.2, 2, 0.15),
             requirements=req(strength=12))
ITEMS.weapon("forged_iron_mace", "Forged Iron Mace", 22, "Black iron with a spiked crown. Rattles helmets.",
             on_hit=_weaken(0.2, 2, 0.2), requirements=req(strength=12))
ITEMS.weapon("halberd", "Halberd", 25, "Axe, spike and hook on one long pole.", on_hit=_bleed(5, 3, 0.15),
             requirements=req(strength=13, dexterity=11))
ITEMS.weapon("silver_sword", "Silver Sword", 25, "A gleaming silver sword.", on_hit=_expose(0.15, 2, 0.2),
             requirements=req(strength=12, dexterity=11))
ITEMS.weapon("steel_longsword", "Steel Longsword", 26, "A knight's weapon, well balanced and well kept.",
             requirements=req(strength=13, dexterity=10))
ITEMS.weapon("broadsword", "Broadsword", 27, "A wide-bladed sword.", requirements=req(strength=13))
ITEMS.weapon("orcish_cleaver", "Orcish Cleaver", 28, "Half sword, half butcher's tool. All orc.",
             on_hit=_bleed(7, 3, 0.25), requirements=req(strength=14))
ITEMS.weapon("battle_axe", "Battle Axe", 29, "A fearsome two-handed axe.", on_hit=_bleed(6, 3, 0.2),
             requirements=req(strength=14, vitality=11))
ITEMS.weapon("enchanted_blade", "Enchanted Blade", 30, "A sword etched with a smouldering rune.",
             on_hit=_burn(6, 3, 0.25), requirements=req(strength=13, intelligence=12))
ITEMS.weapon("dwarf_forged_waraxe", "Dwarf-Forged War Axe", 32, "Folded steel, rune-stamped at the cheek.",
             on_hit=_bleed(7, 3, 0.25), requirements=req(strength=14, vitality=12))
ITEMS.weapon("silvered_longsword", "Silvered Longsword", 34, "Silver-chased steel that bites deeper into the wounded.",
             on_hit=_expose(0.2, 2, 0.2), requirements=req(strength=14, dexterity=12), passives={"execute": 0.15})
ITEMS.weapon("greatsword", "Greatsword", 38, "A massive two-handed sword.", requirements=req(strength=15, vitality=12))
ITEMS.weapon("tempered_steel_greatsword", "Tempered Steel Greatsword", 43,
             "Quenched in oil seven times; it rings like a bell.", requirements=req(strength=16, vitality=13))
ITEMS.weapon("obsidian_glaive", "Obsidian Glaive", 44, "A volcanic-glass blade on a blackwood haft. Wickedly sharp.",
             on_hit=_bleed(10, 3, 0.3), requirements=req(strength=16, agility=12))
ITEMS.weapon("mithril_longsword", "Mithril Longsword", 45, "Light as a reed and never needs sharpening.",
             requirements=req(strength=15, dexterity=15), passives={"crit": 0.05})
ITEMS.weapon("dwarven_runehammer", "Dwarven Runehammer", 47, "Each blow stamps a frost-rune into the foe.",
             on_hit=_freeze(0.12), requirements=req(strength=17, vitality=14))
ITEMS.weapon("ancestral_greatsword", "Ancestral Greatsword", 51, "A blade of the old kings, passed hand to hand "
             "for nine generations.", requirements=req(strength=18, vitality=15), passives={"lifesteal": 0.05})

# ------------------------------------------------------------------- finesse (dexterity)
ITEMS.weapon("rusted_shiv", "Rusted Shiv", 10, "A prison-made blade. The rust does half the work.",
             on_hit=_poison(3, 3, 0.2), finesse=True, requirements=req(dexterity=8))
ITEMS.weapon("elven_dirk", "Elven Dirk", 20, "A leaf-bladed dirk, quick in the hand.", finesse=True,
             requirements=req(dexterity=12, agility=10), passives={"crit": 0.05})
ITEMS.weapon("rapier", "Rapier", 24, "A needle-thin duelling blade.", requirements=req(dexterity=13, agility=11),
             passives={"crit": 0.04})
ITEMS.weapon("assassins_stiletto", "Assassin's Stiletto", 31, "A thin spike made for the gaps in armor.",
             on_hit=_poison(7, 3, 0.3), finesse=True, requirements=req(dexterity=14, agility=12),
             passives={"crit_damage": 0.25})
ITEMS.weapon("moonsilver_sabre", "Moonsilver Sabre", 41, "Curved moonsilver that leaves a pale trail.",
             on_hit=_bleed(9, 3, 0.3), finesse=True, requirements=req(dexterity=16, agility=13))

# ------------------------------------------------------------------- ranged (dexterity)
ITEMS.weapon("short_bow", "Short Bow", 12, "A simple wooden bow.", R, requirements=req(dexterity=9))
ITEMS.weapon("hunting_bow", "Ash Hunting Bow", 16, "Springy ash, waxed string, good for deer and worse.", R,
             requirements=req(dexterity=10))
ITEMS.weapon("long_bow", "Long Bow", 22, "A powerful longbow.", R, requirements=req(dexterity=12, strength=10),
             skills={"precision": 1})
ITEMS.weapon("yew_longbow", "Yew Longbow", 27, "Heartwood and sapwood laminated into a war bow.", R,
             requirements=req(dexterity=13, strength=10), skills={"precision": 1})
ITEMS.weapon("crossbow", "Crossbow", 30, "A mechanical crossbow.", R, requirements=req(dexterity=13, strength=12))
ITEMS.weapon("heavy_crossbow", "Heavy Steel Crossbow", 38, "A windlass crossbow whose bolts punch through plate.", R,
             on_hit=_expose(0.2, 2, 0.25), requirements=req(dexterity=14, strength=13))
ITEMS.weapon("elven_greatbow", "Elven Greatbow", 44, "Taller than its archer and twice as patient.", R,
             requirements=req(dexterity=16, agility=12), passives={"crit": 0.05}, skills={"precision": 2})

# ------------------------------------------------------------------- staves (intelligence; magic damage)
ITEMS.weapon("oak_staff", "Oak Staff", 11, "A wooden magic staff.", MG, requirements=req(intelligence=9))
ITEMS.weapon("ashwood_staff", "Ashwood Staff", 15, "A pale staff that hums faintly in the hand.", MG,
             requirements=req(intelligence=10), passives={"mana_regen": 2})
ITEMS.weapon("magic_staff", "Magic Staff", 17, "A staff crackling with energy.", MG, requirements=req(intelligence=10))
ITEMS.weapon("crystal_staff", "Crystal Staff", 21, "A staff with a crystal orb.", MG, requirements=req(intelligence=12))
ITEMS.weapon("ironbark_staff", "Ironbark Staff", 24, "Druid-grown ironbark. Healing comes easier with it.", MG,
             requirements=req(intelligence=12, wisdom=11), passives={"healing": 0.1})
ITEMS.weapon("arcane_staff", "Arcane Staff", 29, "A staff humming with power.", MG,
             requirements=req(intelligence=13, wisdom=11), passives={"spell_power": 0.04})
ITEMS.weapon("runed_staff", "Runed Staff", 32, "A balanced staff etched with runes.", MG,
             requirements=req(intelligence=15, wisdom=12), passives={"spell_power": 0.05})
ITEMS.weapon("stormglass_staff", "Stormglass Staff", 37, "Lightning trapped in a glass rod.", MG,
             requirements=req(intelligence=15, wisdom=12), passives={"spell_power": 0.06})
ITEMS.weapon("archmagi_staff", "Staff of the Archmagi", 45, "Granted to masters of the Collegium. Spells flow "
             "through it like water.", MG, requirements=req(intelligence=17, wisdom=14),
             passives={"spell_power": 0.08, "mana_cost": 0.05})

# ------------------------------------------------------------------- boss trophies
ITEMS.weapon("titan_hammer", "Titan Hammer", 40, "A colossal hammer forged with Titan power.",
             on_hit=_freeze(0.12), requirements=req(strength=15, vitality=12))
ITEMS.weapon("titan_claw_dagger", "Titan Claw Dagger", 35, "A razor-fast dagger carved from Titan claws.",
             on_hit=_bleed(9, 3, 0.3), finesse=True, requirements=req(dexterity=14, agility=13))
ITEMS.weapon("dragon_tooth_greatsword", "Dragon Tooth Greatsword", 50, "A colossal blade hewn from an elder fang.",
             on_hit=_burn(12, 3, 0.3), requirements=req(strength=17, vitality=13))
ITEMS.weapon("elder_scale_bow", "Elder Scale Bow", 47, "Strung with sinew, scales hard as steel.", R,
             on_hit=_burn(10, 3, 0.25), requirements=req(dexterity=16, agility=12))
ITEMS.weapon("earthsplitter_maul", "Earthsplitter Maul", 55, "A maul that remembers fault-lines.",
             on_hit=_freeze(0.15), requirements=req(strength=18, vitality=14))
ITEMS.weapon("stonebore_crossbow", "Stonebore Crossbow", 53, "Bolts punch through armor like shale.", R,
             on_hit=_expose(0.25, 2, 0.3), requirements=req(dexterity=17, strength=13))
ITEMS.weapon("gnawblade", "Gnawblade", 56, "Edges serrated like hungry teeth.", on_hit=_bleed(14, 3, 0.35),
             requirements=req(dexterity=18, agility=15), finesse=True)
ITEMS.weapon("sewer_longbow", "Sewer Longbow", 55, "A bow that never misses in the dark.", R,
             on_hit=_poison(14, 3, 0.35), requirements=req(dexterity=18, agility=14), passives={"accuracy": 0.05})

# =================================================================== ARMOR
# ------------------------------------------------------------------- light (agility / dexterity)
ITEMS.armor("cracked_iron_armor", "Cracked Iron Armor", 4, "Half-broken plate. Better than nothing.",
            requirements=req(strength=8))
ITEMS.armor("padded_gambeson", "Padded Gambeson", 8, "Quilted linen, warm and surprisingly sturdy.",
            requirements=req(agility=8))
ITEMS.armor("leather_armor", "Leather Armor", 10, "Flexible leather protection.", requirements=req(agility=9),
            skills={"stealth": 1})
ITEMS.armor("boiled_leather_cuirass", "Boiled Leather Cuirass", 13, "Hardened in wax until it turns a blade.",
            requirements=req(agility=10))
ITEMS.armor("studded_leather", "Studded Leather", 15, "Reinforced leather armor.",
            requirements=req(agility=11, dexterity=10), skills={"stealth": 1})
ITEMS.armor("whisperweave_garb", "Whisperweave Garb", 15, "Spider-silk layers that swallow every rustle.",
            requirements=req(agility=12, dexterity=11), skills={"stealth": 4, "balance": 1})
ITEMS.armor("acrobats_harness", "Acrobat's Harness", 15, "Strapped leather built for ledges and rooftops.",
            requirements=req(agility=13, vitality=10), skills={"balance": 3, "reflexes": 1}, passives={"dodge": 0.03})
ITEMS.armor("wolfhide_jerkin", "Wolfhide Jerkin", 17, "Thick winter pelt over boiled leather.",
            requirements=req(agility=11, vitality=10), passives={"dot_resist": 0.1})
ITEMS.armor("rangers_leathers", "Ranger's Leathers", 21, "Mottled green leathers worn by border wardens.",
            requirements=req(agility=12, dexterity=12), passives={"accuracy": 0.04}, skills={"stealth": 1})
ITEMS.armor("shadow_leathers", "Shadow Leathers", 26, "Blackened hide that drinks the light.",
            requirements=req(agility=14, dexterity=13), skills={"stealth": 3}, passives={"dodge": 0.04})
ITEMS.armor("nightstalker_garb", "Nightstalker Garb", 29, "Soft boots, dark wraps and a hood that hides the eyes.",
            requirements=req(agility=15, dexterity=13), skills={"stealth": 2}, passives={"crit": 0.04})
ITEMS.armor("elven_leafmail", "Elven Leafmail", 34, "Overlapping leaves of enchanted bronze, light as linen.",
            requirements=req(agility=15, dexterity=14), passives={"dodge": 0.05})
ITEMS.armor("drakehide_armor", "Drakehide Armor", 39, "Tanned wyvern hide. Fire slides off it.",
            requirements=req(agility=16, vitality=13), passives={"immune_burn": 1, "dot_resist": 0.1})

# ------------------------------------------------------------------- heavy (strength / vitality)
ITEMS.armor("ringmail_hauberk", "Ringmail Hauberk", 14, "Rings sewn onto a leather coat.",
            requirements=req(strength=10), skills={"stealth": -1})
ITEMS.armor("chain_mail", "Chain Mail", 19, "Interlocked metal rings.", requirements=req(strength=11),
            skills={"stealth": -2})
ITEMS.armor("iron_brigandine", "Iron Brigandine", 22, "Iron plates riveted inside a canvas coat.",
            requirements=req(strength=12, vitality=10), skills={"stealth": -1})
ITEMS.armor("scale_mail", "Scale Mail", 24, "Overlapping metal scales.", requirements=req(strength=13, vitality=11),
            skills={"stealth": -2})
ITEMS.armor("orcish_bonemail", "Orcish Bonemail", 25, "Iron and sharpened bone. Hugging it is a mistake.",
            requirements=req(strength=13), passives={"thorns": 0.1}, skills={"stealth": -2})
ITEMS.armor("dwarven_lamellar", "Dwarven Lamellar", 27, "Laced steel plates, every one stamped with a clan mark.",
            requirements=req(strength=13, vitality=12), passives={"dot_resist": 0.1}, skills={"stealth": -2})
ITEMS.armor("steel_breastplate", "Steel Breastplate", 29, "A polished cuirass over mail.",
            requirements=req(strength=14, vitality=12), skills={"stealth": -2})
ITEMS.armor("trollhide_armor", "Trollhide Armor", 31, "The hide never quite stopped healing.",
            requirements=req(strength=14, vitality=14), passives={"regen_pct": 0.015}, skills={"stealth": -2})
ITEMS.armor("plate_armor", "Plate Armor", 32, "Heavy metal plates.", requirements=req(strength=15, vitality=13),
            skills={"stealth": -4, "balance": -1})
ITEMS.armor("knights_plate", "Knight's Plate", 35, "Full harness with a tabard and a name engraved inside.",
            requirements=req(strength=15, vitality=14), passives={"status_resist": 0.05}, skills={"stealth": -4})
ITEMS.armor("dragon_scale", "Dragon Scale", 38, "Armor made from dragon scales.",
            requirements=req(strength=16, vitality=14), passives={"immune_burn": 1}, skills={"stealth": -2})
ITEMS.armor("mithril_armor", "Mithril Armor", 40, "Light as silk, hard as legend.",
            requirements=req(strength=15, dexterity=15))
ITEMS.armor("blackiron_plate", "Blackiron Plate", 41, "Forged in a starless smithy from iron that fell from the sky.",
            requirements=req(strength=17, vitality=15), passives={"resist_physical": 0.05}, skills={"stealth": -4})
ITEMS.armor("dwarven_runeplate", "Dwarven Runeplate", 44, "Rune-scribed plate that drinks hostile magic.",
            requirements=req(strength=18, vitality=16), passives={"resist_magic": 0.1}, skills={"stealth": -4})
ITEMS.armor("sentinel_plate", "Sentinel Plate", 30, "Stone-grey plate cut from a vault guardian's shell.",
            requirements=req(strength=13, vitality=12), skills={"stealth": -3, "balance": 1, "reflexes": 1},
            passives={"immune_bleed": 1})

# ------------------------------------------------------------------- robes (intelligence / wisdom)
ITEMS.armor("novice_robes", "Novice's Robes", 7, "Grey wool with a Collegium patch.", requirements=req(intelligence=9),
            passives={"max_mana": 15})
ITEMS.armor("cloth_robes", "Cloth Robes", 6, "Basic cloth protection.", requirements=req(intelligence=8),
            passives={"max_mana": 10})
ITEMS.armor("silk_robes", "Woven Silk Robes", 12, "Silk spun with silver thread that tingles near magic.",
            requirements=req(intelligence=10, wisdom=10), passives={"mana_regen": 2})
ITEMS.armor("scholars_vestments", "Scholar's Vestments", 16, "Deep pockets for notes, deeper sleeves for wands.",
            requirements=req(intelligence=12, wisdom=11), passives={"spell_power": 0.04})
ITEMS.armor("enchanted_robes", "Enchanted Robes", 18, "Magically protected robes.",
            requirements=req(intelligence=12, wisdom=11), passives={"spell_power": 0.03, "max_mana": 15},
            skills={"focus": 1})
ITEMS.armor("thornweave_robes", "Thornweave Robes", 20, "Living briars woven into cloth. They bite back.",
            requirements=req(wisdom=13, intelligence=11), passives={"thorns": 0.08, "regen_pct": 0.01})
ITEMS.armor("archivists_mantle", "Archivist's Mantle", 21, "Every thread is a warding glyph copied by hand.",
            requirements=req(intelligence=14, wisdom=13), passives={"mana_cost": 0.08})
ITEMS.armor("druidic_hide", "Druidic Hide", 22, "Bark-stitched hide blessed by the grove.",
            requirements=req(wisdom=13, vitality=11), skills={"stealth": 2, "balance": 1}, passives={"regen_pct": 0.01})
ITEMS.armor("mage_robes", "Mage Robes", 22, "Robes woven with protective sigils.",
            requirements=req(intelligence=13, wisdom=12), passives={"spell_power": 0.05, "max_mana": 20},
            skills={"focus": 2})
ITEMS.armor("battlemage_coat", "Battlemage Coat", 26, "A riveted coat with a mage-proofed lining.",
            requirements=req(intelligence=13, strength=12), passives={"resist_magic": 0.1})
ITEMS.armor("vestments_of_dawn", "Vestments of Dawn", 27, "White and gold, warm as morning sun.",
            requirements=req(wisdom=16, intelligence=12), passives={"healing": 0.15, "status_resist": 0.08})
ITEMS.armor("robes_of_the_magus", "Robes of the Magus", 30, "Collegium master's robes, heavy with old enchantment.",
            requirements=req(intelligence=16, wisdom=14), passives={"spell_power": 0.07, "max_mana": 30})
ITEMS.armor("starwoven_raiment", "Starwoven Raiment", 34, "Night sky caught in cloth. Spells slide off it.",
            requirements=req(intelligence=17, wisdom=15), passives={"spell_power": 0.08, "resist_magic": 0.15})

# =================================================================== CONSUMABLES
H, MA = ConsumableEffect.HEAL, ConsumableEffect.MANA
ITEMS.consumable("health_potion", "Health Potion", H, 50, 25, "A small red vial.")
ITEMS.consumable("greater_health_potion", "Greater Health Potion", H, 110, 55, "A generous dose of healing.")
ITEMS.consumable("superior_health_potion", "Superior Health Potion", H, 220, 110, "Thick, glowing and potent.")
ITEMS.consumable("mega_health_potion", "Mega Health Potion", H, 450, 220, "Could revive a statue.")
ITEMS.consumable("mana_potion", "Mana Potion", MA, 35, 20, "Tastes faintly of ozone.")
ITEMS.consumable("greater_mana_potion", "Greater Mana Potion", MA, 75, 45, "A swirling blue draught.")
ITEMS.consumable("superior_mana_potion", "Superior Mana Potion", MA, 140, 85, "Bottled starlight.")
ITEMS.consumable("antidote", "Antidote", ConsumableEffect.CURE, 0, 30, "Bitter herbs that purge afflictions.")
ITEMS.consumable("elixir", "Elixir", ConsumableEffect.RESTORE, 100, 110, "Restores body and mind alike.")

# ------------------------------------------------------------------- minigame tools and tonics
# Lockpicks are spent by the lockpicking minigame (potency = quality). Tonics prime a skill for the next
# trial that uses it; drink one from the inventory, in combat, or from a trial's briefing.
LP, SB = ConsumableEffect.LOCKPICK, ConsumableEffect.SKILL_BOOST
ITEMS.consumable("lockpick", "Lockpick", LP, 1, 12, "A bent iron pick. Snaps if you force it.")
ITEMS.consumable("masterwork_lockpick", "Masterwork Lockpick", LP, 2, 45, "Tempered steel, springy and forgiving.")
ITEMS.consumable("mithril_lockpick", "Mithril Lockpick", LP, 3, 120, "So fine it hums when it touches a pin.")
ITEMS.consumable("muffling_salve", "Muffling Salve", SB, 3, 35, "Wax and wool-fat for boots and buckles.", "stealth")
ITEMS.consumable("steadyhand_tonic", "Steadyhand Tonic", SB, 3, 35, "Calms the tremor in your fingers.", "lockpicking")
ITEMS.consumable("quicksilver_draught", "Quicksilver Draught", SB, 3, 40, "Your heartbeat outruns your fear.", "reflexes")
ITEMS.consumable("sage_tea", "Sage Tea", SB, 3, 30, "Bitter, clarifying, faintly minty.", "focus")
ITEMS.consumable("catfoot_draught", "Catfoot Draught", SB, 3, 35, "Your feet find the floor before you do.", "balance")
ITEMS.consumable("hawkeye_drops", "Hawkeye Drops", SB, 3, 35, "Stings, then the world sharpens.", "precision")

# ------------------------------------------------------------------- trinkets (curios you equip, up to three)
ITEMS.curio("thieves_tools", "Thieves' Tools", 90, "Tension wrenches, rakes and a hook in an oilcloth roll.",
            skills={"lockpicking": 2})
ITEMS.curio("tinkers_loupe", "Tinker's Loupe", 140, "A jeweller's lens that shows how mechanisms want to move.",
            skills={"lockpicking": 1, "precision": 1}, traits=("tinker",))
ITEMS.curio("owl_feather_charm", "Owl Feather Charm", 110, "Owls hear everything and are never heard.",
            skills={"stealth": 1}, traits=("keen_senses",))
ITEMS.curio("hourglass_pendant", "Hourglass Pendant", 160, "The sand inside falls a little too slowly.",
            skills={"reflexes": 1}, traits=("quickened",), passives={"start_haste": 1})
ITEMS.curio("memory_stone", "Memory Stone", 120, "A smooth river stone that holds on to what it sees.",
            skills={"focus": 2}, traits=("eidetic",))
ITEMS.curio("climbers_chalk", "Climber's Chalk", 40, "A pouch of chalk. Dry hands, sure feet.", skills={"balance": 1})
ITEMS.curio("sentinel_core", "Sentinel Core", 150, "A warm stone heart that still ticks against your ribs.",
            skills={"reflexes": 2}, traits=("steady_hands",), passives={"armor": 4})

# =================================================================== SPELLS
# ------------------------------------------------------------------- general store
ITEMS.spell("spark", "Spark", D, 12, 4, "A tiny burst of lightning.")
ITEMS.spell("fire_bolt", "Fire Bolt", D, 26, 9, "A fiery bolt of energy.", inflicts=_burn(5, 3, 0.25))
ITEMS.spell("ice_bolt", "Ice Bolt", D, 22, 8, "A sharp ice bolt.", inflicts=_freeze(0.12))
ITEMS.spell("lesser_lightning_bolt", "Lesser Lightning Bolt", D, 24, 8, "A crackling minor bolt.")
ITEMS.spell("acid_splash", "Acid Splash", D, 24, 9, "Burning acid that eats into armor.", inflicts=_expose(0.2, 2, 0.5))
ITEMS.spell("arcane_missiles", "Arcane Missiles", D, 33, 11, "Three darts of force that never miss.",
            requirements=req(intelligence=12))
ITEMS.spell("ice_shard", "Ice Shard", D, 38, 14, "A sharp ice shard.", inflicts=_freeze(0.15))
ITEMS.spell("stone_spear", "Stone Spear", D, 44, 16, "Rock torn from the ground and hurled like a lance.",
            inflicts=_bleed(8, 3, 0.35), requirements=req(intelligence=13))
ITEMS.spell("fireball", "Fireball", D, 52, 18, "A fiery ball of energy.", inflicts=_burn(9, 3, 0.35),
            requirements=req(intelligence=14, wisdom=10))
ITEMS.spell("lightning_bolt", "Lightning Bolt", D, 60, 22, "A powerful lightning bolt.",
            requirements=req(intelligence=15, wisdom=11))
ITEMS.spell("drain_life", "Drain Life", D, 30, 13, "Pull the life out of your foe and into yourself.", drain=0.6,
            requirements=req(intelligence=12, wisdom=10))
ITEMS.spell("venom_spray", "Venom Spray", SpellType.POISON, 11, 12, "Coat the foe in biting poison.")
ITEMS.spell("lacerate", "Lacerate", SpellType.BLEED, 12, 12, "Invisible blades open old wounds.",
            requirements=req(intelligence=11))
ITEMS.spell("blind", "Blind", SpellType.BLIND, 0, 12, "Steal the enemy's surety.",
            requirements=req(intelligence=10, charisma=10))
ITEMS.spell("blinding_flash", "Blinding Flash", SpellType.BLIND, 0, 12, "A burst of white light.",
            effect=EffectSpec(EffectKind.BLIND, 0.35, 3), requirements=req(intelligence=10, wisdom=10))
ITEMS.spell("enfeeble", "Enfeeble", SpellType.WEAKEN, 0, 12, "Sap the strength from the enemy's arms.",
            requirements=req(intelligence=11))
ITEMS.spell("expose_weakness", "Expose Weakness", SpellType.VULNERABLE, 0, 13,
            "Mark the gaps in the foe's guard for everything that follows.", requirements=req(intelligence=12))
ITEMS.spell("quicken", "Quicken", SpellType.HASTE, 0, 14, "For one breath, the world slows around you.",
            effect=EffectSpec(EffectKind.HASTE, 1, 1), requirements=req(intelligence=11, agility=10))
ITEMS.spell("mend", "Mend", SpellType.HEAL, 30, 7, "Knit small wounds closed.", requirements=req(wisdom=9))
ITEMS.spell("heal", "Heal", SpellType.HEAL, 55, 12, "Mend flesh and resolve.", requirements=req(wisdom=11))
ITEMS.spell("renewal", "Renewal", SpellType.REGEN, 12, 12, "A slow green warmth that keeps healing.",
            requirements=req(wisdom=11))
ITEMS.spell("purify", "Purify", SpellType.CLEANSE, 0, 10, "Burn away poison, curses and frost.",
            requirements=req(wisdom=11))
ITEMS.spell("ward", "Ward", SpellType.SHIELD, 0, 12, "Shape a barrier of will.", requirements=req(wisdom=10))

# ------------------------------------------------------------------- Collegium Arcana (stronger, pricier)
ITEMS.spell("freeze", "Freeze", SpellType.FREEZE, 0, 16, "Still the foe's limbs.")
ITEMS.spell("burn", "Burn", SpellType.BURN, 16, 15, "Searing flame that lingers.", requirements=req(intelligence=12))
ITEMS.spell("hemorrhage", "Hemorrhage", SpellType.BLEED, 15, 15, "Open old wounds with a whisper.",
            requirements=req(intelligence=12, wisdom=11))
ITEMS.spell("plague_touch", "Plague Touch", SpellType.POISON, 18, 16, "A rot that spreads for five long turns.",
            effect=EffectSpec(EffectKind.POISON, 18, 5), requirements=req(intelligence=13, wisdom=11))
ITEMS.spell("frost_nova", "Frost Nova", D, 50, 19, "A ring of ice that bursts outward.", inflicts=_freeze(0.3),
            requirements=req(intelligence=14, wisdom=11))
ITEMS.spell("meteor_lance", "Meteor Lance", D, 76, 24, "A spear of falling starfire.", inflicts=_burn(12, 3, 0.4),
            requirements=req(intelligence=15, wisdom=12))
ITEMS.spell("frozen_crown", "Frozen Crown", D, 70, 22, "A ring of razors made of winter.", inflicts=_freeze(0.25),
            requirements=req(intelligence=15, wisdom=12))
ITEMS.spell("sun_flare", "Sun Flare", D, 74, 24, "A bright unmaking for stubborn shadows.",
            inflicts=EffectSpec(EffectKind.BLIND, 0.3, 2, 0.4), requirements=req(intelligence=15, wisdom=12))
ITEMS.spell("thunder_chorus", "Thunder Chorus", D, 88, 28, "A chorus of bolts that rarely agree.",
            requirements=req(intelligence=16, wisdom=12))
ITEMS.spell("soul_siphon", "Soul Siphon", D, 62, 26, "Tear out a piece of the enemy and wear it as your own.",
            drain=0.5, requirements=req(intelligence=15, wisdom=13))
ITEMS.spell("inferno", "Inferno", D, 72, 30, "The air itself catches fire.", inflicts=_burn(20, 4, 1.0),
            requirements=req(intelligence=16, wisdom=12))
ITEMS.spell("chain_lightning", "Chain Lightning", D, 108, 34, "Lightning that leaps and keeps leaping.",
            requirements=req(intelligence=17, wisdom=13))
ITEMS.spell("curse_of_frailty", "Curse of Frailty", SpellType.VULNERABLE, 0, 20, "Everything that hits it hits harder.",
            effect=EffectSpec(EffectKind.VULNERABLE, 0.4, 3), requirements=req(intelligence=15, wisdom=12))
ITEMS.spell("hex_of_ruin", "Hex of Ruin", SpellType.WEAKEN, 0, 26, "Weaken and expose in one ugly word.",
            effect=EffectSpec(EffectKind.WEAKEN, 0.35, 3), inflicts=_expose(0.3, 3, 1.0),
            requirements=req(intelligence=16, wisdom=13))
ITEMS.spell("silence", "Silence", SpellType.SILENCE, 0, 15, "Steal the words from a caster's mouth.",
            requirements=req(intelligence=13, wisdom=11))
ITEMS.spell("haste", "Haste", SpellType.HASTE, 0, 22, "Two turns of borrowed speed: act twice each turn.",
            requirements=req(intelligence=14, agility=11))
ITEMS.spell("aegis_ward", "Aegis Ward", SpellType.SHIELD, 0, 16, "A disciplined barrier that holds longer.",
            effect=_ward(0.45, 4), requirements=req(wisdom=13, intelligence=10))
ITEMS.spell("arcane_barrier", "Arcane Barrier", SpellType.SHIELD, 0, 22, "A dome of force that eats most of a blow.",
            effect=_ward(0.6, 3), requirements=req(wisdom=15, intelligence=12))
ITEMS.spell("greater_heal", "Greater Heal", SpellType.HEAL, 100, 20, "A surge of restoring light.",
            requirements=req(wisdom=14))
ITEMS.spell("rejuvenate", "Rejuvenate", SpellType.REGEN, 22, 18, "A druid's renewal, green and patient.",
            effect=EffectSpec(EffectKind.REGEN, 22, 5), requirements=req(wisdom=14))
ITEMS.spell("sanctuary", "Sanctuary", SpellType.HEAL, 70, 26, "Heal, then shelter behind holy light.",
            self_effect=_ward(0.35, 2), requirements=req(wisdom=15, intelligence=12))
ITEMS.spell("divine_light", "Divine Light", SpellType.HEAL, 170, 32, "A column of light that knits bone.",
            requirements=req(wisdom=17))

# ------------------------------------------------------------------- boss trophy spells
ITEMS.spell("titans_curse", "Titan's Curse", D, 54, 24, "An ancient curse that devastates foes.",
            inflicts=_poison(16, 4, 1.0), requirements=req(intelligence=14, wisdom=12))
ITEMS.spell("dragons_breath", "Dragon's Breath", D, 104, 30, "Exhale searing ancient flame.",
            inflicts=_burn(22, 4, 1.0), requirements=req(intelligence=16, wisdom=12))
ITEMS.spell("seismic_rift", "Seismic Rift", D, 108, 32, "Tear the ground beneath your foe.", inflicts=_freeze(0.35),
            self_effect=_ward(0.3, 2), requirements=req(intelligence=17, wisdom=13))
ITEMS.spell("pestilent_swarm", "Pestilent Swarm", SpellType.POISON, 30, 22, "Unleash a tide of biting filth.",
            effect=EffectSpec(EffectKind.POISON, 30, 5), inflicts=_weaken(0.3, 3, 1.0),
            requirements=req(intelligence=17, wisdom=14))

# =================================================================== JEWELRY (one amulet, one ring)
# ------------------------------------------------------------------- amulets
ITEMS.jewelry("amulet_of_vigor", "Amulet of Vigor", AMULET, "A bloodstone on a leather cord.", passives={"max_hp": 25})
ITEMS.jewelry("scholars_pendant", "Scholar's Pendant", AMULET, "A tiny brass astrolabe that never stops turning.",
              attributes={"intelligence": 1}, passives={"xp_gain": 0.1})
ITEMS.jewelry("merchants_medallion", "Merchant's Medallion", AMULET, "Guild silver, polished by greedy thumbs.",
              attributes={"charisma": 2}, passives={"gold_find": 0.2})
ITEMS.jewelry("amulet_of_warding", "Amulet of Warding", AMULET, "Wards flare up the moment steel is drawn.",
              passives={"start_ward": 0.3})
ITEMS.jewelry("talisman_of_purity", "Talisman of Purity", AMULET, "A silver leaf that tarnishes near poison.",
              passives={"immune_poison": 1, "dot_resist": 0.1})
ITEMS.jewelry("heartwood_locket", "Heartwood Locket", AMULET, "Holds a sliver of a very old tree.",
              attributes={"vitality": 2}, passives={"healing": 0.15})
ITEMS.jewelry("amulet_of_swiftness", "Amulet of Swiftness", AMULET, "A hawk's feather in glass.",
              attributes={"agility": 1}, passives={"start_haste": 1})
ITEMS.jewelry("warlords_torc", "Warlord's Torc", AMULET, "A twisted gold torc taken from a fallen chieftain.",
              attributes={"strength": 2}, passives={"weapon_damage": 0.08}, requirements=req(strength=12))
ITEMS.jewelry("pendant_of_clarity", "Pendant of Clarity", AMULET, "A clear crystal that keeps the mind still.",
              passives={"immune_silence": 1, "immune_blind": 1, "mana_regen": 2})
ITEMS.jewelry("icewarden_amulet", "Icewarden Amulet", AMULET, "Rime never melts from its face.",
              passives={"immune_frozen": 1, "resist_magic": 0.08})
ITEMS.jewelry("phoenix_feather", "Phoenix Feather Amulet", AMULET, "Warm to the touch, even in snow.",
              passives={"immune_burn": 1, "healing": 0.1, "max_hp": 15})
ITEMS.jewelry("vampire_fang_necklace", "Vampire Fang Necklace", AMULET, "Three long fangs on a black chain.",
              passives={"lifesteal": 0.08}, requirements=req(strength=11))
ITEMS.jewelry("troll_blood_amulet", "Troll-Blood Amulet", AMULET, "A vial of troll blood that never clots.",
              passives={"regen_pct": 0.03}, requirements=req(vitality=13))
ITEMS.jewelry("archmage_amulet", "Archmage's Amulet", AMULET, "The sigil of the Collegium's inner circle.",
              passives={"spell_power": 0.08, "max_mana": 30}, requirements=req(intelligence=15))
ITEMS.jewelry("amulet_of_the_unbroken", "Amulet of the Unbroken", AMULET, "Worn by those who refused to fall.",
              passives={"status_resist": 0.15, "max_hp": 40, "dot_resist": 0.1}, requirements=req(vitality=15))

# ------------------------------------------------------------------- rings
ITEMS.jewelry("copper_ring_of_might", "Copper Ring of Might", RING, "Green with age and still strong.",
              attributes={"strength": 1})
ITEMS.jewelry("silver_ring_of_wit", "Silver Ring of Wit", RING, "Engraved with a riddle you almost understand.",
              attributes={"intelligence": 2})
ITEMS.jewelry("ring_of_fortitude", "Ring of Fortitude", RING, "A plain iron band that never bends.",
              attributes={"vitality": 2})
ITEMS.jewelry("ring_of_the_fox", "Ring of the Fox", RING, "A fox carved chasing its own tail.",
              attributes={"agility": 2}, passives={"flee": 0.1})
ITEMS.jewelry("marksmans_band", "Marksman's Band", RING, "Worn on the draw hand by archers who never miss.",
              attributes={"dexterity": 2}, passives={"accuracy": 0.04})
ITEMS.jewelry("ring_of_the_wellspring", "Ring of the Wellspring", RING, "A drop of water that never evaporates.",
              passives={"max_mana": 25, "mana_regen": 2})
ITEMS.jewelry("ring_of_thorns", "Ring of Thorns", RING, "A briar-wrapped band that pricks whoever grabs you.",
              passives={"thorns": 0.15})
ITEMS.jewelry("ring_of_ironskin", "Ring of Ironskin", RING, "Your skin feels like leather while it's on.",
              passives={"armor": 6, "resist_physical": 0.05})
ITEMS.jewelry("bloodstone_ring", "Bloodstone Ring", RING, "Red flecks that pulse when blood is spilled.",
              passives={"lifesteal": 0.05, "crit": 0.03})
ITEMS.jewelry("serpent_ring", "Serpent Ring", RING, "A coiled adder with ruby eyes.",
              passives={"dot_power": 0.25, "immune_poison": 1})
ITEMS.jewelry("sorcerers_band", "Sorcerer's Band", RING, "Three metals, braided by a mage who hated waste.",
              passives={"mana_cost": 0.12, "spell_power": 0.04}, requirements=req(intelligence=12))
ITEMS.jewelry("assassins_signet", "Assassin's Signet", RING, "A blank signet. Assassins don't sign their work.",
              passives={"crit": 0.06, "crit_damage": 0.25}, requirements=req(dexterity=13))
ITEMS.jewelry("executioners_ring", "Executioner's Ring", RING, "A heavy black band. It wants things finished.",
              passives={"execute": 0.3}, requirements=req(strength=13))
ITEMS.jewelry("ring_of_regeneration", "Ring of Regeneration", RING, "A green stone that warms when you bleed.",
              passives={"regen_pct": 0.02}, requirements=req(vitality=12))
ITEMS.jewelry("kings_signet", "King's Signet", RING, "The seal of a forgotten crown. Everyone listens.",
              attributes={"strength": 1, "dexterity": 1, "agility": 1, "vitality": 1, "intelligence": 1, "wisdom": 1,
                          "charisma": 2})

# =================================================================== POOLS
WEAPON_POOL = ["twisted_iron_blade", "bronze_sword", "axe", "bronze_mace", "steel_sword", "chipped_oak_greatsword",
               "spear", "war_hammer", "forged_iron_mace", "halberd", "silver_sword", "steel_longsword", "broadsword",
               "orcish_cleaver", "battle_axe", "enchanted_blade", "dwarf_forged_waraxe", "silvered_longsword",
               "greatsword", "tempered_steel_greatsword", "obsidian_glaive", "mithril_longsword",
               "dwarven_runehammer", "ancestral_greatsword", "rusted_shiv", "elven_dirk", "rapier",
               "assassins_stiletto", "moonsilver_sabre", "short_bow", "hunting_bow", "long_bow", "yew_longbow",
               "crossbow", "heavy_crossbow", "elven_greatbow", "oak_staff", "ashwood_staff", "magic_staff",
               "crystal_staff", "ironbark_staff", "arcane_staff", "runed_staff", "stormglass_staff"]
ARMOR_POOL = ["cracked_iron_armor", "padded_gambeson", "leather_armor", "boiled_leather_cuirass", "studded_leather",
              "whisperweave_garb", "acrobats_harness", "wolfhide_jerkin", "rangers_leathers", "shadow_leathers",
              "nightstalker_garb", "elven_leafmail", "drakehide_armor", "ringmail_hauberk", "chain_mail",
              "iron_brigandine", "scale_mail", "orcish_bonemail", "dwarven_lamellar", "steel_breastplate",
              "trollhide_armor", "plate_armor", "knights_plate", "dragon_scale", "mithril_armor", "blackiron_plate",
              "dwarven_runeplate", "novice_robes", "cloth_robes", "silk_robes", "scholars_vestments",
              "enchanted_robes", "thornweave_robes", "archivists_mantle", "druidic_hide", "mage_robes",
              "battlemage_coat"]
GENERAL_SPELLS = ["spark", "fire_bolt", "ice_bolt", "lesser_lightning_bolt", "acid_splash", "arcane_missiles",
                  "ice_shard", "stone_spear", "fireball", "lightning_bolt", "drain_life", "venom_spray", "lacerate",
                  "blind", "blinding_flash", "enfeeble", "expose_weakness", "quicken", "mend", "heal", "renewal",
                  "purify", "ward"]
COLLEGIUM_SPELLS = ["freeze", "burn", "hemorrhage", "plague_touch", "frost_nova", "meteor_lance", "frozen_crown",
                    "sun_flare", "thunder_chorus", "soul_siphon", "inferno", "chain_lightning", "curse_of_frailty",
                    "hex_of_ruin", "silence", "haste", "aegis_ward", "arcane_barrier", "greater_heal", "rejuvenate",
                    "sanctuary", "divine_light"]
JEWELRY_POOL = ["amulet_of_vigor", "scholars_pendant", "merchants_medallion", "amulet_of_warding",
                "talisman_of_purity", "heartwood_locket", "amulet_of_swiftness", "warlords_torc", "pendant_of_clarity",
                "icewarden_amulet", "phoenix_feather", "vampire_fang_necklace", "troll_blood_amulet",
                "amulet_of_the_unbroken", "copper_ring_of_might", "silver_ring_of_wit", "ring_of_fortitude",
                "ring_of_the_fox", "marksmans_band", "ring_of_the_wellspring", "ring_of_thorns", "ring_of_ironskin",
                "bloodstone_ring", "serpent_ring", "sorcerers_band", "assassins_signet", "executioners_ring",
                "ring_of_regeneration", "kings_signet"]
MAGIC_JEWELRY = ["archmage_amulet", "pendant_of_clarity", "sorcerers_band", "ring_of_the_wellspring",
                 "silver_ring_of_wit", "scholars_pendant", "icewarden_amulet"]
COLLEGIUM_GEAR = ["archmagi_staff", "robes_of_the_magus", "starwoven_raiment", "vestments_of_dawn"]

GENERAL_SHOP_POOLS: dict[str, list[str]] = {
    "weapon": WEAPON_POOL,
    "armor": ARMOR_POOL,
    "consumable": ["health_potion", "greater_health_potion", "superior_health_potion", "mega_health_potion",
                   "mana_potion", "greater_mana_potion", "superior_mana_potion", "antidote", "elixir",
                   "masterwork_lockpick", "muffling_salve", "steadyhand_tonic", "quicksilver_draught", "sage_tea",
                   "catfoot_draught", "hawkeye_drops"],
    "spell": GENERAL_SPELLS,
    "accessory": JEWELRY_POOL,
    "curio": ["thieves_tools", "tinkers_loupe", "owl_feather_charm", "hourglass_pendant", "memory_stone",
              "climbers_chalk"],
}
GENERAL_SHOP_COUNTS = {"weapon": 6, "armor": 5, "consumable": 6, "spell": 4, "accessory": 3, "curio": 2}
# Always on the shelf, in unlimited supply.
GENERAL_SHOP_STAPLES = ["lockpick", "health_potion", "antidote"]

MAGIC_SHOP_SPELLS = COLLEGIUM_SPELLS + ["heal", "renewal", "purify", "fireball", "lightning_bolt", "drain_life"]
MAGIC_SHOP_COUNTS = {"spell": 7, "consumable": 3, "accessory": 2, "gear": 2}
MAGIC_SHOP_EXTRAS = {"accessory": MAGIC_JEWELRY, "gear": COLLEGIUM_GEAR}

# Random combat loot. A category is picked by weight, then an item near the enemy's tier (see progression).
LOOT_TABLE: dict[str, list[str]] = {
    "weapon": WEAPON_POOL,
    "armor": ARMOR_POOL,
    "consumable": ["health_potion", "greater_health_potion", "superior_health_potion", "mana_potion",
                   "greater_mana_potion", "antidote", "elixir", "lockpick"],
    "accessory": JEWELRY_POOL,
}
LOOT_WEIGHTS = {"weapon": 3, "armor": 3, "consumable": 5, "accessory": 1}
