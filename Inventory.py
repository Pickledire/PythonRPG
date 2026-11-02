import copy
from Item import Item, Consumable, Armor
from Weapon import Weapon
from Magic import Magic

class Inventory:
    """Manages character inventory and equipment"""
    
    def __init__(self, max_size=50):
        self.items = []
        self.max_size = max_size
        self.equipped_weapon = None
        self.equipped_armor = None
        self.equipped_magic = None
        self.owner = None  # Character that owns this inventory
    
    def _find_index(self, item_or_name):
        """Locate an inventory entry by the item object itself (preferred) or by name."""
        if isinstance(item_or_name, Item):
            for i, inv_item in enumerate(self.items):
                if inv_item['item'] is item_or_name:
                    return i
            return None
        for i, inv_item in enumerate(self.items):
            if inv_item['item'].name == item_or_name:
                return i
        return None

    @staticmethod
    def _can_stack(a, b):
        """Only identical consumables stack. Gear keeps its own entry (own durability),
        and same-named items with different stats are never merged."""
        return (
            isinstance(a, Consumable) and isinstance(b, Consumable)
            and a.name == b.name
            and a.effect_type == b.effect_type
            and a.effect_value == b.effect_value
        )

    def add_item(self, item, quantity=1):
        """Add an item to inventory"""
        # Stack onto an existing identical consumable first (doesn't need a free slot)
        for inv_item in self.items:
            if self._can_stack(inv_item['item'], item):
                inv_item['quantity'] += quantity
                return True, f"Added {quantity} {item.name}(s) to inventory"

        if isinstance(item, Consumable):
            if len(self.items) >= self.max_size:
                return False, "Inventory is full!"
            self.items.append({'item': item, 'quantity': quantity})
            return True, f"Added {quantity} {item.name}(s) to inventory"

        # Non-stackable gear: one entry per copy, each its own object
        if len(self.items) + quantity > self.max_size:
            return False, "Inventory is full!"
        for n in range(quantity):
            copy_needed = n > 0 or any(inv_item['item'] is item for inv_item in self.items)
            self.items.append({'item': copy.deepcopy(item) if copy_needed else item, 'quantity': 1})
        return True, f"Added {quantity} {item.name}(s) to inventory"

    def remove_item(self, item_or_name, quantity=1):
        """Remove an item from inventory (by object or name). Unequips it if it was equipped."""
        i = self._find_index(item_or_name)
        if i is None:
            return False, f"{getattr(item_or_name, 'name', item_or_name)} not found in inventory"
        inv_item = self.items[i]
        name = inv_item['item'].name
        if inv_item['quantity'] > quantity:
            inv_item['quantity'] -= quantity
            return True, f"Removed {quantity} {name}(s)"
        if inv_item['quantity'] < quantity:
            return False, f"Not enough {name} in inventory"
        removed = self.items.pop(i)['item']
        if self.equipped_weapon is removed:
            self.equipped_weapon = None
        if self.equipped_armor is removed:
            self.equipped_armor = None
        if self.equipped_magic is removed:
            self.equipped_magic = None
        return True, f"Removed {quantity} {name}(s)"

    def get_item(self, item_or_name):
        """Get an item from inventory by object or name"""
        i = self._find_index(item_or_name)
        return self.items[i]['item'] if i is not None else None

    def equip_weapon(self, weapon_name):
        """Equip a weapon"""
        weapon = self.get_item(weapon_name)
        if weapon and isinstance(weapon, Weapon):
            self.equipped_weapon = weapon
            return True, f"Equipped {weapon.name}"
        return False, f"Cannot equip {getattr(weapon_name, 'name', weapon_name)}"

    def equip_armor(self, armor_name):
        """Equip armor"""
        armor = self.get_item(armor_name)
        if armor and isinstance(armor, Armor):
            self.equipped_armor = armor
            return True, f"Equipped {armor.name}"
        return False, f"Cannot equip {getattr(armor_name, 'name', armor_name)}"

    def equip_magic(self, magic_name):
        """Equip a magic spell"""
        magic = self.get_item(magic_name)
        if magic and isinstance(magic, Magic):
            # Enforce intelligence requirement if owner is available
            if self.owner is not None and hasattr(magic, 'get_requirement'):
                req_stat, req_value = magic.get_requirement()
                if getattr(self.owner, 'stats', {}).get(req_stat, 0) < req_value:
                    return False, f"You need {req_stat.capitalize()} {req_value} to equip {magic.name}. (Current: {self.owner.stats.get(req_stat,0)})"
            self.equipped_magic = magic
            return True, f"Equipped {magic.name}"
        return False, f"Cannot equip {getattr(magic_name, 'name', magic_name)}"

    def use_item(self, item_name, target=None):
        """Use a consumable item"""
        item = self.get_item(item_name)
        if item and isinstance(item, Consumable):
            result = item.use(target)
            self.remove_item(item, 1)
            return True, result
        return False, f"Cannot use {getattr(item_name, 'name', item_name)}"

    def list_items(self):
        """List all items in inventory"""
        if not self.items:
            return "Inventory is empty"
        
        result = "=== INVENTORY ===\n"
        for inv_item in self.items:
            item = inv_item['item']
            quantity = inv_item['quantity']
            result += f"{item.name} x{quantity} - {item.item_type}\n"
        
        result += "\n=== EQUIPPED ===\n"
        result += f"Weapon: {self.equipped_weapon.name if self.equipped_weapon else 'None'}\n"
        result += f"Armor: {self.equipped_armor.name if self.equipped_armor else 'None'}\n"
        result += f"Magic: {self.equipped_magic.name if self.equipped_magic else 'None'}\n"
        return result
    
    def get_weapons(self):
        """Get all weapons in inventory"""
        weapons = []
        for inv_item in self.items:
            if isinstance(inv_item['item'], Weapon):
                weapons.append(inv_item['item'])
        return weapons
    
    def get_magic(self):
        """Get all magic in inventory"""
        magic = []
        for inv_item in self.items:
            if isinstance(inv_item['item'], Magic):
                magic.append(inv_item['item'])
        return magic

    def get_consumables(self):
        """Get all consumable items"""
        consumables = []
        for inv_item in self.items:
            if isinstance(inv_item['item'], Consumable):
                consumables.append(inv_item['item'])
        return consumables 