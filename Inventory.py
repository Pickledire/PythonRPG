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
    
    def add_item(self, item, quantity=1):
        """Add an item to inventory"""
        if len(self.items) >= self.max_size:
            return False, "Inventory is full!"
        
        # Check if item already exists (for stackable items)
        for inv_item in self.items:
            if inv_item['item'].name == item.name and inv_item['item'].item_type == item.item_type:
                inv_item['quantity'] += quantity
                return True, f"Added {quantity} {item.name}(s) to inventory"
        
        # Add new item
        self.items.append({'item': item, 'quantity': quantity})
        return True, f"Added {quantity} {item.name}(s) to inventory"
    
    def remove_item(self, item_name, quantity=1):
        """Remove an item from inventory"""
        for i, inv_item in enumerate(self.items):
            if inv_item['item'].name == item_name:
                if inv_item['quantity'] > quantity:
                    inv_item['quantity'] -= quantity
                    return True, f"Removed {quantity} {item_name}(s)"
                elif inv_item['quantity'] == quantity:
                    removed_item = self.items.pop(i)
                    return True, f"Removed {quantity} {item_name}(s)"
                else:
                    return False, f"Not enough {item_name} in inventory"
        return False, f"{item_name} not found in inventory"
    
    def get_item(self, item_name):
        """Get an item from inventory by name"""
        for inv_item in self.items:
            if inv_item['item'].name == item_name:
                return inv_item['item']
        return None
    
    def equip_weapon(self, weapon_name):
        """Equip a weapon"""
        weapon = self.get_item(weapon_name)
        if weapon and isinstance(weapon, Weapon):
            self.equipped_weapon = weapon
            return True, f"Equipped {weapon_name}"
        return False, f"Cannot equip {weapon_name}"
    
    def equip_armor(self, armor_name):
        """Equip armor"""
        armor = self.get_item(armor_name)
        if armor and isinstance(armor, Armor):
            self.equipped_armor = armor
            return True, f"Equipped {armor_name}"
        return False, f"Cannot equip {armor_name}"
    
    def equip_magic(self, magic_name):
        """Equip a magic spell"""
        magic = self.get_item(magic_name)
        if magic and isinstance(magic, Magic):
            self.equipped_magic = magic
            return True, f"Equipped {magic_name}"
        return False, f"Cannot equip {magic_name}"
    
    def use_item(self, item_name, target=None):
        """Use a consumable item"""
        item = self.get_item(item_name)
        if item and isinstance(item, Consumable):
            result = item.use(target)
            self.remove_item(item_name, 1)
            return True, result
        return False, f"Cannot use {item_name}"
    
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