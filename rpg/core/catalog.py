"""Item catalog and factory.

All item content is declared here as data. To add an item, call ``ITEMS.register(...)`` (or add a
line below) and reference its id from shops, loot tables, enemy rewards or dialogue JSON.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rpg.core.effects import EffectKind, EffectSpec
from rpg.core.items import (
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


class ItemFactory:
    """Registry of item templates; every ``create`` call returns a brand new instance."""

    def __init__(self) -> None:
        self._templates: dict[str, ItemTemplate] = {}

    def register(self, template_id: str, cls: type[Item], **params: Any) -> None:
        if template_id in self._templates:
            raise ValueError(f"Duplicate item id: {template_id}")
        self._templates[template_id] = ItemTemplate(template_id, cls, params)

    def weapon(self, template_id: str, name: str, damage: int, durability: int, value: int, description: str,
               weapon_class: WeaponClass = WeaponClass.MELEE, on_hit: EffectSpec | None = None) -> None:
        self.register(template_id, Weapon, name=name, damage=damage, max_durability=durability, value=value,
                      description=description, weapon_class=weapon_class, on_hit=on_hit)

    def armor(self, template_id: str, name: str, defense: int, durability: int, value: int, description: str) -> None:
        self.register(template_id, Armor, name=name, defense=defense, max_durability=durability, value=value,
                      description=description)

    def consumable(self, template_id: str, name: str, effect: ConsumableEffect, potency: int, value: int,
                   description: str) -> None:
        self.register(template_id, Consumable, name=name, effect=effect, potency=potency, value=value,
                      description=description)

    def spell(self, template_id: str, name: str, spell_type: SpellType, power: int, mana_cost: int, value: int,
              description: str, inflicts: EffectSpec | None = None) -> None:
        self.register(template_id, Spell, name=name, spell_type=spell_type, power=power, mana_cost=mana_cost,
                      value=value, description=description, inflicts=inflicts)

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
          (weapon/armor/magic/spell/consumable, or melee/ranged as weapon shorthands).
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
        if kind == "weapon":
            return Weapon(template_id=template_id, name=name, damage=int(spec.get("damage", 10)),
                          max_durability=int(spec.get("durability", 100)), value=value, description=description,
                          weapon_class=WeaponClass(weapon_class or "melee"))
        if kind == "armor":
            return Armor(template_id=template_id, name=name, defense=int(spec.get("defense", 5)),
                         max_durability=int(spec.get("durability", 100)), value=value, description=description)
        if kind in ("magic", "spell"):
            return Spell(template_id=template_id, name=name, description=description, value=value,
                         spell_type=SpellType(spec.get("spell_type", "damage")), power=int(spec.get("damage", 15)),
                         mana_cost=int(spec.get("mana", 8)))
        if kind == "consumable" and int(spec.get("heal", spec.get("potency", 0)) or 0) > 0:
            return Consumable(template_id=template_id, name=name, description=description, value=value,
                              effect=ConsumableEffect(spec.get("effect", "heal")),
                              potency=int(spec.get("heal", spec.get("potency", 0))))
        return Curio(template_id=template_id, name=name, description=description, value=value)


ITEMS = ItemFactory()

M, R, MG = WeaponClass.MELEE, WeaponClass.RANGED, WeaponClass.MAGIC
_bleed = lambda potency, turns, chance: EffectSpec(EffectKind.BLEED, potency, turns, chance)  # noqa: E731
_burn = lambda potency, turns, chance: EffectSpec(EffectKind.BURN, potency, turns, chance)  # noqa: E731
_poison = lambda potency, turns, chance: EffectSpec(EffectKind.POISON, potency, turns, chance)  # noqa: E731
_freeze = lambda chance: EffectSpec(EffectKind.FROZEN, 0, 1, chance)  # noqa: E731
_blind = lambda chance: EffectSpec(EffectKind.BLIND, 0.25, 2, chance)  # noqa: E731

# ------------------------------------------------------------------- starting gear
ITEMS.weapon("iron_sword", "Iron Sword", 15, 100, 60, "A reliable iron sword.")
ITEMS.weapon("elven_bow", "Elven Bow", 12, 80, 50, "A graceful elven bow.", R)
ITEMS.weapon("orcish_axe", "Orcish Axe", 18, 120, 75, "A brutal orcish war axe.", on_hit=_bleed(3, 2, 0.10))
ITEMS.weapon("dwarven_hammer", "Dwarven Hammer", 16, 150, 80, "A sturdy dwarven war hammer.")
ITEMS.spell("elven_blast", "Elven Blast", SpellType.DAMAGE, 22, 10, 100, "A magical blast of energy.")
ITEMS.spell("dwarven_scream", "Dwarven Scream", SpellType.DAMAGE, 14, 10, 80, "A powerful dwarven scream.",
            inflicts=_blind(0.20))

# ------------------------------------------------------------------- general store weapons
ITEMS.weapon("bronze_sword", "Bronze Sword", 10, 90, 40, "A basic bronze sword.")
ITEMS.weapon("steel_sword", "Steel Sword", 18, 120, 80, "A sharp steel blade.")
ITEMS.weapon("silver_sword", "Silver Sword", 26, 110, 125, "A gleaming silver sword.")
ITEMS.weapon("enchanted_blade", "Enchanted Blade", 33, 150, 200, "A magically enhanced sword.")
ITEMS.weapon("greatsword", "Greatsword", 38, 180, 300, "A massive two-handed sword.")
ITEMS.weapon("broadsword", "Broadsword", 28, 150, 175, "A wide-bladed sword.")
ITEMS.weapon("short_bow", "Short Bow", 12, 90, 50, "A simple wooden bow.", R)
ITEMS.weapon("long_bow", "Long Bow", 20, 110, 180, "A powerful longbow.", R)
ITEMS.weapon("crossbow", "Crossbow", 28, 100, 150, "A mechanical crossbow.", R)
ITEMS.weapon("oak_staff", "Oak Staff", 12, 80, 60, "A wooden magic staff.", MG)
ITEMS.weapon("crystal_staff", "Crystal Staff", 22, 100, 110, "A staff with a crystal orb.", MG)
ITEMS.weapon("arcane_staff", "Arcane Staff", 30, 110, 175, "A staff humming with power.", MG)
ITEMS.weapon("war_hammer", "War Hammer", 24, 150, 100, "A heavy two-handed hammer.")
ITEMS.weapon("battle_axe", "Battle Axe", 28, 130, 140, "A fearsome two-handed axe.", on_hit=_bleed(5, 3, 0.15))
ITEMS.weapon("axe", "Axe", 20, 110, 50, "A basic axe.")
ITEMS.weapon("halberd", "Halberd", 26, 110, 50, "A basic halberd.")
ITEMS.weapon("spear", "Spear", 24, 110, 50, "A basic spear.", on_hit=_bleed(4, 2, 0.15))

# ------------------------------------------------------------------- loot-only weapons
ITEMS.weapon("magic_staff", "Magic Staff", 18, 80, 150, "A staff crackling with energy.", MG)
ITEMS.weapon("runed_staff", "Runed Staff", 30, 150, 200, "A balanced staff etched with runes.", MG)

# ------------------------------------------------------------------- armor
ITEMS.armor("cloth_robes", "Cloth Robes", 6, 60, 30, "Basic cloth protection.")
ITEMS.armor("leather_armor", "Leather Armor", 10, 110, 40, "Flexible leather protection.")
ITEMS.armor("studded_leather", "Studded Leather", 14, 130, 75, "Reinforced leather armor.")
ITEMS.armor("chain_mail", "Chain Mail", 18, 150, 110, "Interlocked metal rings.")
ITEMS.armor("scale_mail", "Scale Mail", 22, 160, 150, "Overlapping metal scales.")
ITEMS.armor("plate_armor", "Plate Armor", 24, 200, 225, "Heavy metal plates.")
ITEMS.armor("enchanted_robes", "Enchanted Robes", 18, 100, 140, "Magically protected robes.")
ITEMS.armor("dragon_scale", "Dragon Scale", 28, 180, 200, "Armor made from dragon scales.")
ITEMS.armor("mithril_armor", "Mithril Armor", 32, 220, 300, "Light as silk, hard as legend.")
ITEMS.armor("cracked_iron_armor", "Cracked Iron Armor", 3, 30, 25, "Half-broken plate. Better than nothing.")
ITEMS.armor("mage_robes", "Mage Robes", 18, 100, 180, "Robes woven with protective sigils.")

# ------------------------------------------------------------------- consumables
H, MA = ConsumableEffect.HEAL, ConsumableEffect.MANA
ITEMS.consumable("health_potion", "Health Potion", H, 50, 25, "A small red vial.")
ITEMS.consumable("greater_health_potion", "Greater Health Potion", H, 100, 50, "A generous dose of healing.")
ITEMS.consumable("superior_health_potion", "Superior Health Potion", H, 200, 100, "Thick, glowing and potent.")
ITEMS.consumable("mega_health_potion", "Mega Health Potion", H, 500, 200, "Could revive a statue.")
ITEMS.consumable("mana_potion", "Mana Potion", MA, 30, 20, "Tastes faintly of ozone.")
ITEMS.consumable("greater_mana_potion", "Greater Mana Potion", MA, 60, 40, "A swirling blue draught.")
ITEMS.consumable("superior_mana_potion", "Superior Mana Potion", MA, 100, 75, "Bottled starlight.")
ITEMS.consumable("antidote", "Antidote", ConsumableEffect.CURE, 0, 30, "Bitter herbs that purge afflictions.")
ITEMS.consumable("elixir", "Elixir", ConsumableEffect.RESTORE, 75, 90, "Restores body and mind alike.")

# ------------------------------------------------------------------- spells (general store)
D = SpellType.DAMAGE
ITEMS.spell("fireball", "Fireball", D, 67, 20, 200, "A fiery ball of energy.", inflicts=_burn(8, 3, 0.25))
ITEMS.spell("ice_shard", "Ice Shard", D, 45, 15, 150, "A sharp ice shard.", inflicts=_freeze(0.15))
ITEMS.spell("lightning_bolt", "Lightning Bolt", D, 80, 25, 300, "A powerful lightning bolt.")
ITEMS.spell("fire_bolt", "Fire Bolt", D, 30, 10, 100, "A fiery bolt of energy.", inflicts=_burn(5, 2, 0.20))
ITEMS.spell("ice_bolt", "Ice Bolt", D, 25, 10, 100, "A sharp ice bolt.", inflicts=_freeze(0.10))
ITEMS.spell("lesser_lightning_bolt", "Lesser Lightning Bolt", D, 23, 10, 150, "A crackling minor bolt.")
ITEMS.spell("heal", "Heal", SpellType.HEAL, 0, 14, 180, "Mend flesh and resolve.")
ITEMS.spell("ward", "Ward", SpellType.SHIELD, 0, 12, 160, "Shape a barrier of will.")
ITEMS.spell("blind", "Blind", SpellType.BLIND, 0, 16, 200, "Steal the enemy's surety.")
ITEMS.spell("venom_spray", "Venom Spray", SpellType.POISON, 12, 14, 170, "Coat the foe in biting poison.")
ITEMS.spell("spark", "Spark", D, 12, 5, 50, "A tiny burst of lightning.")

# ------------------------------------------------------------------- spells (Collegium Arcana)
ITEMS.spell("meteor_lance", "Meteor Lance", D, 72, 26, 320, "A spear of falling starfire.", inflicts=_burn(10, 3, 0.30))
ITEMS.spell("frozen_crown", "Frozen Crown", D, 68, 24, 300, "A ring of razors made of winter.", inflicts=_freeze(0.20))
ITEMS.spell("thunder_chorus", "Thunder Chorus", D, 80, 30, 360, "A chorus of bolts that rarely agree.")
ITEMS.spell("aegis_ward", "Aegis Ward", SpellType.SHIELD, 0, 14, 180, "A disciplined barrier spell.")
ITEMS.spell("sun_flare", "Sun Flare", D, 76, 28, 340, "A bright unmaking for stubborn shadows.", inflicts=_blind(0.25))
ITEMS.spell("freeze", "Freeze", SpellType.FREEZE, 0, 18, 240, "Still the foe's limbs.")
ITEMS.spell("burn", "Burn", SpellType.BURN, 14, 16, 240, "Searing flame that lingers.")
ITEMS.spell("hemorrhage", "Hemorrhage", SpellType.BLEED, 12, 16, 230, "Open old wounds with a whisper.")

# ------------------------------------------------------------------- boss trophies
ITEMS.weapon("titan_hammer", "Titan Hammer", 40, 200, 0, "A colossal hammer forged with Titan power.")
ITEMS.weapon("titan_claw_dagger", "Titan Claw Dagger", 28, 160, 0, "A razor-fast dagger carved from Titan claws.",
             on_hit=_bleed(6, 3, 0.25))
ITEMS.spell("titans_curse", "Titan's Curse", D, 45, 35, 0, "An ancient curse that devastates foes.",
            inflicts=_poison(10, 3, 0.40))
ITEMS.weapon("dragon_tooth_greatsword", "Dragon Tooth Greatsword", 60, 180, 0, "A colossal blade hewn from an elder fang.",
             on_hit=_burn(8, 2, 0.20))
ITEMS.weapon("elder_scale_bow", "Elder Scale Bow", 44, 140, 0, "Strung with sinew, scales hard as steel.", R)
ITEMS.spell("dragons_breath", "Dragon's Breath", D, 70, 45, 0, "Exhale searing ancient flame.", inflicts=_burn(12, 3, 0.50))
ITEMS.weapon("earthsplitter_maul", "Earthsplitter Maul", 58, 200, 0, "A maul that remembers fault-lines.")
ITEMS.weapon("stonebore_crossbow", "Stonebore Crossbow", 46, 160, 0, "Bolts punch through armor like shale.", R)
ITEMS.spell("seismic_rift", "Seismic Rift", D, 62, 38, 0, "Tear the ground beneath your foe.", inflicts=_freeze(0.20))
ITEMS.weapon("gnawblade", "Gnawblade", 48, 170, 0, "Edges serrated like hungry teeth.", on_hit=_bleed(8, 3, 0.30))
ITEMS.weapon("sewer_longbow", "Sewer Longbow", 42, 150, 0, "A bow that never misses in the dark.", R)
ITEMS.spell("pestilent_swarm", "Pestilent Swarm", SpellType.POISON, 18, 22, 0, "Unleash a tide of biting filth.")

# ------------------------------------------------------------------- pools
GENERAL_SHOP_POOLS: dict[str, list[str]] = {
    "weapon": ["bronze_sword", "steel_sword", "silver_sword", "enchanted_blade", "greatsword", "broadsword",
               "short_bow", "long_bow", "crossbow", "oak_staff", "crystal_staff", "arcane_staff", "war_hammer",
               "battle_axe", "axe", "halberd", "spear"],
    "armor": ["cloth_robes", "leather_armor", "studded_leather", "chain_mail", "scale_mail", "plate_armor",
              "enchanted_robes", "dragon_scale", "mithril_armor"],
    "consumable": ["health_potion", "greater_health_potion", "superior_health_potion", "mega_health_potion",
                   "mana_potion", "greater_mana_potion", "superior_mana_potion", "antidote", "elixir"],
    "spell": ["fireball", "ice_shard", "lightning_bolt", "fire_bolt", "ice_bolt", "lesser_lightning_bolt", "heal",
              "ward", "blind", "venom_spray"],
}
GENERAL_SHOP_COUNTS = {"weapon": 5, "armor": 4, "consumable": 5, "spell": 3}

MAGIC_SHOP_SPELLS = GENERAL_SHOP_POOLS["spell"] + [
    "meteor_lance", "frozen_crown", "thunder_chorus", "aegis_ward", "sun_flare", "freeze", "burn", "hemorrhage",
]
MAGIC_SHOP_COUNTS = {"spell": 6, "consumable": 3}

# Random combat loot (weighted equally within a category).
LOOT_TABLE: dict[str, list[str]] = {
    "weapon": ["steel_sword", "magic_staff", "war_hammer"],
    "consumable": ["health_potion", "greater_health_potion", "mana_potion", "antidote"],
    "armor": ["leather_armor", "chain_mail", "plate_armor", "cracked_iron_armor"],
}
