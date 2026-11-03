"""Inventory with stacking consumables, unique gear and equipment slots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rpg.config import INVENTORY_SIZE
from rpg.core.items import (
    Accessory,
    AccessorySlot,
    Armor,
    Consumable,
    Curio,
    Item,
    ItemKind,
    Spell,
    Weapon,
    item_from_dict,
)


class InventoryFullError(Exception):
    pass


class SlotError(ValueError):
    """The item can't go in (all trinket slots are full, or it isn't wearable)."""


class Slot(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SPELL = "spell"
    AMULET = "amulet"
    RING = "ring"
    TRINKET1 = "trinket1"
    TRINKET2 = "trinket2"
    TRINKET3 = "trinket3"

    @property
    def label(self) -> str:
        return "Trinket" if self.value.startswith("trinket") else self.value.capitalize()


SLOT_TYPES: dict[Slot, type[Item]] = {Slot.WEAPON: Weapon, Slot.ARMOR: Armor, Slot.SPELL: Spell}
TRINKET_SLOTS = (Slot.TRINKET1, Slot.TRINKET2, Slot.TRINKET3)
GEAR_SLOTS = (Slot.WEAPON, Slot.ARMOR, Slot.AMULET, Slot.RING, *TRINKET_SLOTS)  # slots whose bonuses apply


@dataclass
class Stack:
    item: Item
    quantity: int = 1


class Inventory:
    """Ordered list of stacks. Stackable items merge by ``stack_key``; gear is one stack per item."""

    def __init__(self, capacity: int = INVENTORY_SIZE) -> None:
        self.capacity = capacity
        self.stacks: list[Stack] = []
        self.equipped: dict[Slot, Item | None] = {slot: None for slot in Slot}

    # ------------------------------------------------------------ queries
    def __iter__(self):
        return iter(self.stacks)

    def __len__(self) -> int:
        return len(self.stacks)

    @property
    def is_full(self) -> bool:
        return len(self.stacks) >= self.capacity

    def find(self, uid: str) -> Stack | None:
        return next((s for s in self.stacks if s.item.uid == uid), None)

    def find_by_name(self, name: str) -> Stack | None:
        lowered = name.lower()
        return next((s for s in self.stacks if s.item.name.lower() == lowered), None)

    def quantity_of(self, uid: str) -> int:
        stack = self.find(uid)
        return stack.quantity if stack else 0

    def items_of_kind(self, kind: ItemKind) -> list[Item]:
        return [s.item for s in self.stacks if s.item.kind == kind]

    def stacks_of_kind(self, kind: ItemKind) -> list[Stack]:
        return [s for s in self.stacks if s.item.kind == kind]

    @property
    def weapon(self) -> Weapon | None:
        return self.equipped[Slot.WEAPON]  # type: ignore[return-value]

    @property
    def armor(self) -> Armor | None:
        return self.equipped[Slot.ARMOR]  # type: ignore[return-value]

    @property
    def spell(self) -> Spell | None:
        return self.equipped[Slot.SPELL]  # type: ignore[return-value]

    def is_equipped(self, item: Item) -> bool:
        return any(eq is item for eq in self.equipped.values())

    def consumables(self) -> list[Stack]:
        return [s for s in self.stacks if isinstance(s.item, Consumable)]

    def spells(self) -> list[Spell]:
        return [s.item for s in self.stacks if isinstance(s.item, Spell)]  # type: ignore[misc]

    # ------------------------------------------------------------ mutation
    def add(self, item: Item, quantity: int = 1) -> Stack:
        """Add an item. Raises InventoryFullError if a new slot is needed and none is free."""
        if quantity < 1:
            raise ValueError("quantity must be positive")
        key = item.stack_key()
        if key is not None:
            for stack in self.stacks:
                if stack.item.stack_key() == key:
                    stack.quantity += quantity
                    return stack
            if self.is_full:
                raise InventoryFullError(item.name)
            stack = Stack(item, quantity)
            self.stacks.append(stack)
            return stack
        # Unique gear: one stack per instance
        if len(self.stacks) + quantity > self.capacity:
            raise InventoryFullError(item.name)
        stack = Stack(item, 1)
        self.stacks.append(stack)
        for _ in range(quantity - 1):
            self.stacks.append(Stack(item.clone(), 1))
        return stack

    def remove(self, uid: str, quantity: int = 1) -> Item:
        """Remove ``quantity`` of the stack with ``uid``; unequips the item if its stack empties."""
        stack = self.find(uid)
        if stack is None:
            raise KeyError(uid)
        if stack.quantity < quantity:
            raise ValueError(f"Only {stack.quantity} {stack.item.name} in inventory")
        stack.quantity -= quantity
        if stack.quantity == 0:
            self.stacks.remove(stack)
            for slot, equipped in self.equipped.items():
                if equipped is stack.item:
                    self.equipped[slot] = None
        return stack.item

    def slot_for(self, item: Item) -> Slot:
        if isinstance(item, Accessory):
            return Slot.AMULET if item.slot == AccessorySlot.AMULET else Slot.RING
        if isinstance(item, Curio):
            if not item.equippable:
                raise SlotError(f"{item.name} can't be worn.")
            free = next((slot for slot in TRINKET_SLOTS if self.equipped[slot] is None), None)
            if free is None:
                raise SlotError("All three trinket slots are full. Remove a trinket first.")
            return free
        for slot, cls in SLOT_TYPES.items():
            if isinstance(item, cls):
                return slot
        raise TypeError(f"{item.name} cannot be equipped")

    def equip(self, item: Item) -> Slot:
        if self.find(item.uid) is None:
            raise KeyError(item.uid)
        if self.is_equipped(item):
            return next(slot for slot, eq in self.equipped.items() if eq is item)
        slot = self.slot_for(item)
        self.equipped[slot] = item
        return slot

    def unequip(self, slot: Slot) -> None:
        self.equipped[slot] = None

    def unequip_item(self, item: Item) -> None:
        for slot, equipped in self.equipped.items():
            if equipped is item:
                self.equipped[slot] = None

    def worn(self) -> list[Item]:
        """Equipped gear whose bonuses apply (weapon, armor, jewelry, trinkets; not the readied spell)."""
        return [self.equipped[slot] for slot in GEAR_SLOTS if self.equipped[slot] is not None]

    def accessories(self) -> list[Item]:
        return [s.item for s in self.stacks if isinstance(s.item, Accessory)]

    # ------------------------------------------------------------ serialization
    def to_dict(self) -> dict:
        return {
            "capacity": self.capacity,
            "stacks": [{"item": s.item.to_dict(), "quantity": s.quantity} for s in self.stacks],
            "equipped": {slot.value: (item.uid if item else None) for slot, item in self.equipped.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        inv = cls(int(data.get("capacity", INVENTORY_SIZE)))
        from rpg.core.catalog import ITEMS

        for entry in data.get("stacks", []):
            item = item_from_dict(entry["item"])
            ITEMS.refresh_requirements(item)  # catalog balance changes apply to saved items
            inv.stacks.append(Stack(item, int(entry.get("quantity", 1))))
        for slot_name, uid in (data.get("equipped") or {}).items():
            if uid:
                stack = inv.find(uid)
                if stack and slot_name in Slot._value2member_map_:
                    inv.equipped[Slot(slot_name)] = stack.item
        return inv
