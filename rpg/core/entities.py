"""Combatants: the shared base class and the player character."""

from __future__ import annotations

from enum import Enum

from rpg import config
from rpg.core.attributes import Attribute, Attributes
from rpg.core.catalog import ITEMS
from rpg.core.effects import CLEANSABLE, EffectKind, StatusEffect
from rpg.core.formulas import armor_mitigation
from rpg.core.inventory import Inventory
from rpg.core.items import Armor, Item, Spell, Weapon


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


class Player(Combatant):
    def __init__(self, name: str, race: str, attributes: Attributes, max_hp: int) -> None:
        super().__init__(name, max_hp, attributes)
        self.race = race
        self.level = 1
        self.xp = 0
        self.gold = config.STARTING_GOLD
        self.max_mana = config.STARTING_MANA
        self.mana = self.max_mana
        self.inventory = Inventory()
        self.kills = 0
        self.stat_points = 0

    @classmethod
    def create(cls, name: str, race: str) -> "Player":
        if race not in config.RACES:
            raise ValueError(f"Unknown race: {race}")
        data = config.RACES[race]
        player = cls(name.strip() or "Adventurer", race, Attributes.from_dict(data), int(data["health"]))
        for template_id in data["starting_items"]:
            item = ITEMS.create(template_id)
            player.inventory.add(item)
            if template_id in data["equip"]:
                player.inventory.equip(item)
        for template_id, qty in config.STARTING_CONSUMABLES.items():
            player.inventory.add(ITEMS.create(template_id), qty)
        return player

    # ------------------------------------------------------------ progression
    @property
    def xp_required(self) -> int:
        return config.BASE_XP_REQUIREMENT + (self.level - 1) * config.XP_INCREASE_PER_LEVEL

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
        return gained

    def spend_stat_point(self, attribute: Attribute) -> int:
        if self.stat_points <= 0:
            raise ValueError("No stat points to spend")
        self.stat_points -= 1
        return self.attributes.add(attribute, 1)

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
        req = item.requirement
        if req is None or req.met_by(self.attributes):
            return True, ""
        current = self.attributes.get(req.attribute)
        return False, f"Requires {req.describe()} (you have {current})."

    def equip(self, item: Item) -> str:
        ok, reason = self.meets_requirement(item)
        if not ok:
            raise ValueError(reason)
        self.inventory.equip(item)
        return f"Equipped {item.name}."

    # ------------------------------------------------------------ defense
    def effective_defense(self, damage_type: DamageType, penetration: float = 0.0) -> float:
        armor = self.armor
        defense = armor.effective_defense if armor else 0.0
        defense *= 1.0 - penetration
        if damage_type == DamageType.MAGIC:
            defense *= 0.5  # magic slips past half of your armor
        return defense

    def mitigate(self, raw: int, damage_type: DamageType, penetration: float = 0.0) -> int:
        multiplier = armor_mitigation(self.effective_defense(damage_type, penetration))
        return int(max(1, round(raw * multiplier)))

    # ------------------------------------------------------------ serialization
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "race": self.race,
            "level": self.level,
            "xp": self.xp,
            "gold": self.gold,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mana": self.mana,
            "max_mana": self.max_mana,
            "attributes": self.attributes.to_dict(),
            "stat_points": self.stat_points,
            "kills": self.kills,
            "effects": [e.to_dict() for e in self.effects.values()],
            "inventory": self.inventory.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        player = cls(data["name"], data.get("race", "Human"), Attributes.from_dict(data.get("attributes", {})),
                     int(data.get("max_hp", 100)))
        player.level = int(data.get("level", 1))
        player.xp = int(data.get("xp", 0))
        player.gold = int(data.get("gold", 0))
        player.hp = int(data.get("hp", player.max_hp))
        player.max_mana = int(data.get("max_mana", config.STARTING_MANA))
        player.mana = int(data.get("mana", player.max_mana))
        player.stat_points = int(data.get("stat_points", 0))
        player.kills = int(data.get("kills", 0))
        for raw in data.get("effects", []):
            effect = StatusEffect.from_dict(raw)
            player.effects[effect.kind] = effect
        player.inventory = Inventory.from_dict(data.get("inventory", {}))
        return player
