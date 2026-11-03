"""Combatants: the shared base class and the player character."""

from __future__ import annotations

from enum import Enum

from rpg import config
from rpg.core.attributes import Attribute, Attributes, unmet
from rpg.core.catalog import ITEMS
from rpg.core.effects import CLEANSABLE, EffectKind, StatusEffect
from rpg.core.formulas import (
    armor_mitigation,
    xp_to_next,
    dodge_chance,
    dot_resistance,
    max_hp_for,
    max_mana_for,
    status_resist_chance,
)
from rpg.core.inventory import Inventory, SlotError
from rpg.core.items import Armor, Consumable, ConsumableEffect, Item, Spell, Weapon
from rpg.core.passives import clamp_total, immunity_key


class DamageType(str, Enum):
    PHYSICAL = "physical"
    MAGIC = "magic"


class Combatant:
    """Anything that can fight: has HP, attributes and status effects."""

    def __init__(self, name: str, max_hp: int, attributes: Attributes) -> None:
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.attributes = attributes
        self.effects: dict[EffectKind, StatusEffect] = {}

    # ------------------------------------------------------------ vitals
    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.hp / self.max_hp if self.max_hp else 0.0

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + max(0, int(amount)))
        return self.hp - before

    def lose_hp(self, amount: int) -> int:
        """True damage that bypasses armor and wards (damage over time)."""
        before = self.hp
        self.hp = max(0, self.hp - max(0, int(amount)))
        return before - self.hp

    # ------------------------------------------------------------ defense
    def effective_defense(self, damage_type: DamageType, penetration: float = 0.0) -> float:
        return 0.0

    def mitigate(self, raw: int, damage_type: DamageType, penetration: float = 0.0) -> int:
        """How much of ``raw`` damage gets through armor and wards (minimum 1)."""
        raise NotImplementedError

    def take_hit(self, raw: int, damage_type: DamageType = DamageType.PHYSICAL, penetration: float = 0.0) -> int:
        dealt = self.mitigate(raw, damage_type, penetration)
        shield = self.effects.get(EffectKind.SHIELD)
        if shield:
            dealt = max(1, int(dealt * (1.0 - shield.potency)))
        return self.lose_hp(dealt)

    # ------------------------------------------------------------ effects
    def effect(self, kind: EffectKind) -> StatusEffect | None:
        return self.effects.get(kind)

    def has_effect(self, kind: EffectKind) -> bool:
        return kind in self.effects

    def add_effect(self, effect: StatusEffect) -> StatusEffect:
        """Apply or refresh an effect (longer duration and stronger potency win)."""
        current = self.effects.get(effect.kind)
        if current:
            current.turns = max(current.turns, effect.turns)
            current.potency = max(current.potency, effect.potency)
            return current
        self.effects[effect.kind] = effect
        return effect

    def remove_effect(self, kind: EffectKind) -> None:
        self.effects.pop(kind, None)

    def cleanse(self) -> list[EffectKind]:
        removed = [k for k in list(self.effects) if k in CLEANSABLE]
        for kind in removed:
            del self.effects[kind]
        return removed

    def blind_penalty(self) -> float:
        blind = self.effects.get(EffectKind.BLIND)
        return blind.potency if blind else 0.0

    # Defensive traits (enemies have none of these by default; the player gets them from attributes and gear)
    def passive(self, key: str) -> float:
        """Summed equipment passive (see rpg.core.passives); enemies have none."""
        return 0.0

    def immune(self, kind: EffectKind) -> bool:
        return False

    def resist(self, damage_type: "DamageType") -> float:
        """Share of incoming damage of this type that is ignored."""
        return 0.0

    def dot_multiplier(self) -> float:
        """Multiplier on poison/burn/bleed damage taken."""
        return 1.0

    def status_resist(self) -> float:
        """Chance to resist a harmful status effect entirely."""
        return 0.0

    def dodge(self) -> float:
        """Chance to avoid a weapon attack."""
        return 0.0


class Player(Combatant):
    def __init__(self, name: str, race: str, attributes: Attributes, max_hp: int, max_mana: int) -> None:
        super().__init__(name, max_hp, attributes)
        self.race = race
        self.level = 1
        self.xp = 0
        self.gold = config.STARTING_GOLD
        self.max_mana = max_mana
        self.mana = self.max_mana
        self.inventory = Inventory()
        self.kills = 0
        self.stat_points = 0
        self.skill_primes: dict[str, int] = {}  # skill -> bonus for the next minigame that uses it
        # What worn gear currently adds on top of the base character (kept so removal is exact).
        self._gear_attrs: dict[str, int] = {}
        self._gear_hp = 0
        self._gear_mana = 0
        self._passives: dict[str, float] = {}

    @classmethod
    def create(cls, name: str, race: str) -> "Player":
        if race not in config.RACES:
            raise ValueError(f"Unknown race: {race}")
        data = config.RACES[race]
        attributes = Attributes.from_dict(data)
        player = cls(name.strip() or "Adventurer", race, attributes,
                     max_hp_for(int(data["base_hp"]), attributes.vitality), max_mana_for(attributes.wisdom))
        for template_id in data["starting_items"]:
            item = ITEMS.create(template_id)
            player.inventory.add(item)
            if template_id in data["equip"]:
                player.inventory.equip(item)
        for template_id, qty in config.STARTING_CONSUMABLES.items():
            player.inventory.add(ITEMS.create(template_id), qty)
        player.refresh_gear()
        return player

    # ------------------------------------------------------------ progression
    @property
    def xp_required(self) -> int:
        return xp_to_next(self.level)

    def gain_xp(self, amount: int) -> int:
        """Add XP and level up as many times as earned. Returns levels gained (points go to stat_points)."""
        self.xp += max(0, int(amount))
        gained = 0
        while self.xp >= self.xp_required:
            self.xp -= self.xp_required
            self.level += 1
            gained += 1
            self.max_hp += config.HEALTH_GAIN_PER_LEVEL
            self.hp += config.HEALTH_GAIN_PER_LEVEL
            self.max_mana += config.MANA_GAIN_PER_LEVEL
            self.mana += config.MANA_GAIN_PER_LEVEL
            self.stat_points += config.STAT_POINTS_PER_LEVEL
            if config.BONUS_STAT_POINT_EVERY and self.level % config.BONUS_STAT_POINT_EVERY == 0:
                self.stat_points += 1
        return gained

    def spend_stat_point(self, attribute: Attribute) -> int:
        if self.stat_points <= 0:
            raise ValueError("No stat points to spend")
        self.stat_points -= 1
        return self.change_attribute(attribute, 1)

    def change_attribute(self, attribute: Attribute | str, delta: int) -> int:
        """Change an attribute and keep derived pools in step (Vitality -> HP, Wisdom -> mana)."""
        attribute = Attribute(attribute)
        before = self.attributes.get(attribute)
        after = self.attributes.add(attribute, delta)
        diff = after - before
        if attribute == Attribute.VITALITY and diff:
            self.max_hp = max(1, self.max_hp + diff * config.HP_PER_VITALITY)
            self.hp = max(1, min(self.max_hp, self.hp + diff * config.HP_PER_VITALITY))
        elif attribute == Attribute.WISDOM and diff:
            self.max_mana = max(0, self.max_mana + diff * config.MANA_PER_WISDOM)
            self.mana = max(0, min(self.max_mana, self.mana + diff * config.MANA_PER_WISDOM))
        return after

    def set_attribute(self, attribute: Attribute | str, value: int) -> int:
        return self.change_attribute(attribute, int(value) - self.attributes.get(attribute))

    # ------------------------------------------------------------ worn gear
    def refresh_gear(self, keep_current: bool = False) -> None:
        """Re-sum attribute bonuses, pool bonuses and passives from everything worn and apply the difference.

        Call after equipping or removing gear. ``keep_current`` leaves HP/mana alone (used when loading a save).
        """
        attrs: dict[str, int] = {}
        passives: dict[str, float] = {}
        for item in self.inventory.worn():
            for key, value in item.attribute_bonuses.items():
                attrs[key] = attrs.get(key, 0) + value
            for key, value in item.passives.items():
                passives[key] = passives.get(key, 0.0) + value
        hp, mana = self.hp, self.mana
        for attribute in Attribute:
            delta = attrs.get(attribute.value, 0) - self._gear_attrs.get(attribute.value, 0)
            if delta:
                self.change_attribute(attribute, delta)
        hp_delta = int(passives.get("max_hp", 0)) - self._gear_hp
        mana_delta = int(passives.get("max_mana", 0)) - self._gear_mana
        self.max_hp = max(1, self.max_hp + hp_delta)
        self.max_mana = max(0, self.max_mana + mana_delta)
        if keep_current:
            self.hp, self.mana = hp, mana
        else:
            self.hp += max(0, hp_delta)
            self.mana += max(0, mana_delta)
        self.hp = max(1, min(self.hp, self.max_hp))
        self.mana = max(0, min(self.mana, self.max_mana))
        self._gear_attrs = attrs
        self._gear_hp, self._gear_mana = int(passives.get("max_hp", 0)), int(passives.get("max_mana", 0))
        self._passives = {key: clamp_total(key, value) for key, value in passives.items()}

    def passive(self, key: str) -> float:
        return self._passives.get(key, 0.0)

    @property
    def passives(self) -> dict[str, float]:
        return dict(self._passives)

    def immune(self, kind: EffectKind) -> bool:
        return self.passive(immunity_key(kind)) > 0

    def resist(self, damage_type: "DamageType") -> float:
        return self.passive(f"resist_{damage_type.value}")

    def base_attributes(self) -> Attributes:
        """Attributes without worn bonuses (what level-ups and saves work with)."""
        base = Attributes.from_dict(self.attributes.to_dict())
        for key, value in self._gear_attrs.items():
            base.add(key, -value)
        return base

    # ------------------------------------------------------------ attribute-driven defenses
    def dot_multiplier(self) -> float:
        return max(0.2, 1.0 - dot_resistance(self.attributes.vitality) - self.passive("dot_resist"))

    def status_resist(self) -> float:
        return min(0.75, status_resist_chance(self.attributes.wisdom) + self.passive("status_resist"))

    def dodge(self) -> float:
        return min(0.4, dodge_chance(self.attributes.agility) + self.passive("dodge"))

    # ------------------------------------------------------------ resources
    def restore_mana(self, amount: int) -> int:
        before = self.mana
        self.mana = min(self.max_mana, self.mana + max(0, int(amount)))
        return self.mana - before

    def spend_mana(self, amount: int) -> bool:
        if self.mana < amount:
            return False
        self.mana -= amount
        return True

    def add_gold(self, amount: int) -> int:
        self.gold = max(0, self.gold + int(amount))
        return self.gold

    def spend_gold(self, amount: int) -> bool:
        if self.gold < amount:
            return False
        self.gold -= amount
        return True

    def full_restore(self) -> None:
        self.hp = self.max_hp
        self.mana = self.max_mana

    # ------------------------------------------------------------ equipment
    @property
    def weapon(self) -> Weapon | None:
        return self.inventory.weapon

    @property
    def armor(self) -> Armor | None:
        return self.inventory.armor

    @property
    def spell(self) -> Spell | None:
        return self.inventory.spell

    def meets_requirement(self, item: Item) -> tuple[bool, str]:
        """Check every attribute requirement; the reason lists each one that isn't met."""
        missing = unmet(item.requirements or (), self.attributes)
        if not missing:
            return True, ""
        parts = [f"{r.attribute.label} {r.minimum} (you have {self.attributes.get(r.attribute)})" for r in missing]
        return False, "Requires " + ", ".join(parts) + "."

    def equip(self, item: Item) -> str:
        ok, reason = self.meets_requirement(item)
        if not ok:
            raise ValueError(reason)
        try:
            self.inventory.equip(item)
        except SlotError as exc:
            raise ValueError(str(exc)) from None
        self.refresh_gear()
        return f"Equipped {item.name}."

    def unequip(self, item: Item) -> str:
        self.inventory.unequip_item(item)
        self.refresh_gear()
        return f"Removed {item.name}."

    # ------------------------------------------------------------ skills (minigames)
    def skill_items(self) -> list[Item]:
        """Items whose minigame modifiers apply: everything equipped, including jewelry and trinkets.

        New equipment slots (cloaks, boots...) only need to appear in ``inventory.equipped``.
        """
        return [item for item in self.inventory.equipped.values() if item is not None]

    def prime_skill(self, skill: str, amount: int) -> int:
        """Prime a skill for the next trial that uses it. Primes don't stack; the strongest one wins."""
        self.skill_primes[skill] = max(self.skill_primes.get(skill, 0), int(amount))
        return self.skill_primes[skill]

    def consume_prime(self, skill: str) -> int:
        return self.skill_primes.pop(skill, 0)

    def lockpicks(self) -> list[Consumable]:
        """Lockpicks carried, one entry per pick, best quality first."""
        picks: list[Consumable] = []
        for stack in self.inventory.consumables():
            item = stack.item
            if isinstance(item, Consumable) and item.effect == ConsumableEffect.LOCKPICK:
                picks += [item] * stack.quantity
        return sorted(picks, key=lambda pick: -pick.potency)

    # ------------------------------------------------------------ defense
    def effective_defense(self, damage_type: DamageType, penetration: float = 0.0) -> float:
        armor = self.armor
        defense = (armor.effective_defense if armor else 0.0) + self.passive("armor")
        defense *= 1.0 - penetration
        if damage_type == DamageType.MAGIC:
            defense *= 0.5  # magic slips past half of your armor
        return defense

    def mitigate(self, raw: int, damage_type: DamageType, penetration: float = 0.0) -> int:
        multiplier = armor_mitigation(self.effective_defense(damage_type, penetration)) * (1 - self.resist(damage_type))
        return int(max(1, round(raw * multiplier)))

    # ------------------------------------------------------------ serialization
    def to_dict(self) -> dict:
        # Saves hold the *base* character; worn bonuses are re-applied from the equipped gear on load.
        gear_vit = self._gear_attrs.get("vitality", 0)
        gear_wis = self._gear_attrs.get("wisdom", 0)
        return {
            "name": self.name,
            "race": self.race,
            "level": self.level,
            "xp": self.xp,
            "gold": self.gold,
            "hp": self.hp,
            "max_hp": self.max_hp - self._gear_hp - gear_vit * config.HP_PER_VITALITY,
            "mana": self.mana,
            "max_mana": self.max_mana - self._gear_mana - gear_wis * config.MANA_PER_WISDOM,
            "attributes": self.base_attributes().to_dict(),
            "stat_points": self.stat_points,
            "kills": self.kills,
            "skill_primes": dict(self.skill_primes),
            "effects": [e.to_dict() for e in self.effects.values()],
            "inventory": self.inventory.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        race = data.get("race", "Human")
        # Saves from before the seven-attribute system only have STR/AGI/INT: fill the rest from the race.
        attributes = Attributes.from_dict(data.get("attributes", {}), defaults=config.RACES.get(race, {}))
        player = cls(data["name"], race, attributes, int(data.get("max_hp", 100)),
                     int(data.get("max_mana", max_mana_for(attributes.wisdom))))
        player.level = int(data.get("level", 1))
        player.xp = int(data.get("xp", 0))
        player.gold = int(data.get("gold", 0))
        player.hp = int(data.get("hp", player.max_hp))
        player.mana = int(data.get("mana", player.max_mana))
        player.stat_points = int(data.get("stat_points", 0))
        player.kills = int(data.get("kills", 0))
        player.skill_primes = {str(k): int(v) for k, v in (data.get("skill_primes") or {}).items()}
        for raw in data.get("effects", []):
            effect = StatusEffect.from_dict(raw)
            player.effects[effect.kind] = effect
        player.inventory = Inventory.from_dict(data.get("inventory", {}))
        player.refresh_gear(keep_current=True)
        return player
