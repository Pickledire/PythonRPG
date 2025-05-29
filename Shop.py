from Weapon import Weapon
from Item import Consumable, Armor

class Shop:
    """Shop class for buying and selling items"""
    
    def __init__(self):
        self.inventory = self._create_shop_inventory()
    
    def _create_shop_inventory(self):
        """Create the shop's inventory with various items"""
        shop_items = []
        
        # Weapons
        weapons = [
            Weapon("Bronze Sword", 12, 80, "A basic bronze sword", 80, "melee"),
            Weapon("Steel Sword", 20, 120, "A sharp steel blade", 150, "melee"),
            Weapon("Silver Sword", 28, 100, "A gleaming silver sword", 250, "melee"),
            Weapon("Enchanted Blade", 35, 150, "A magically enhanced sword", 400, "melee"),
            
            Weapon("Short Bow", 15, 90, "A simple wooden bow", 100, "ranged"),
            Weapon("Long Bow", 22, 110, "A powerful longbow", 180, "ranged"),
            Weapon("Crossbow", 30, 80, "A mechanical crossbow", 300, "ranged"),
            
            Weapon("Oak Staff", 14, 70, "A wooden magic staff", 120, "magic"),
            Weapon("Crystal Staff", 25, 90, "A staff with a crystal orb", 220, "magic"),
            Weapon("Arcane Staff", 32, 110, "A staff humming with power", 350, "magic"),
            
            Weapon("War Hammer", 25, 150, "A heavy two-handed hammer", 200, "melee"),
            Weapon("Battle Axe", 30, 130, "A fearsome two-handed axe", 280, "melee"),
        ]
        
        # Armor
        armors = [
            Armor("Cloth Robes", 2, 60, "Basic cloth protection", 30),
            Armor("Leather Armor", 5, 100, "Flexible leather protection", 80),
            Armor("Studded Leather", 8, 120, "Reinforced leather armor", 150),
            Armor("Chain Mail", 12, 150, "Interlocked metal rings", 220),
            Armor("Scale Mail", 15, 140, "Overlapping metal scales", 300),
            Armor("Plate Armor", 20, 200, "Heavy metal plates", 450),
            Armor("Enchanted Robes", 10, 80, "Magically protected robes", 280),
            Armor("Dragon Scale", 25, 180, "Armor made from dragon scales", 600),
        ]
        
        # Consumables
        consumables = [
            Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25),
            Consumable("Greater Health Potion", "heal", 100, "Restores 100 HP", 50),
            Consumable("Superior Health Potion", "heal", 200, "Restores 200 HP", 100),
            Consumable("Mega Health Potion", "heal", 500, "Restores 500 HP", 200),
        ]
        
        # Add all items to shop inventory
        for item in weapons + armors + consumables:
            shop_items.append({
                'item': item,
                'stock': 99 if item.item_type == 'consumable' else 1,
                'price': item.value
            })
        
        return shop_items
    
    def display_items(self, item_type=None):
        """Display shop items, optionally filtered by type"""
        if item_type:
            items = [item for item in self.inventory if item['item'].item_type == item_type and item['stock'] > 0]
            print(f"\n=== {item_type.upper()} ===")
        else:
            items = [item for item in self.inventory if item['stock'] > 0]
            print("\n=== SHOP INVENTORY ===")
        
        if not items:
            print("No items available in this category.")
            return []
        
        for i, shop_item in enumerate(items, 1):
            item = shop_item['item']
            price = shop_item['price']
            stock = shop_item['stock']
            
            if item.item_type == 'weapon':
                print(f"{i}. {item.name} - {price}💰 (Damage: {item.damage}, Durability: {item.max_durability})")
            elif item.item_type == 'armor':
                print(f"{i}. {item.name} - {price}💰 (Defense: {item.defense}, Durability: {item.max_durability})")
            elif item.item_type == 'consumable':
                print(f"{i}. {item.name} - {price}💰 (Effect: {item.effect_value}, Stock: {stock})")
            else:
                print(f"{i}. {item.name} - {price}💰")
            
            if item.description:
                print(f"    {item.description}")
        
        return items
    
    def buy_item(self, item_index, available_items, player):
        """Handle buying an item"""
        if 1 <= item_index <= len(available_items):
            shop_item = available_items[item_index - 1]
            item = shop_item['item']
            price = shop_item['price']
            
            # Check if player has enough gold
            if player.gold >= price:
                # Check if player has inventory space
                success, message = player.inventory.add_item(item)
                if success:
                    # Deduct gold and reduce stock
                    player.spend_gold(price)
                    shop_item['stock'] -= 1
                    return True, f"Purchased {item.name} for {price}💰!"
                else:
                    return False, "Your inventory is full!"
            else:
                return False, f"Not enough gold! You need {price}💰 but only have {player.gold}💰"
        else:
            return False, "Invalid item selection!"
    
    def sell_item(self, player, item_name):
        """Handle selling an item from player inventory"""
        item = player.inventory.get_item(item_name)
        if not item:
            return False, f"You don't have {item_name} in your inventory!"
        
        # Calculate sell price (50% of original value)
        sell_price = max(1, item.value // 2)
        
        # Remove item from inventory and add gold
        success, message = player.inventory.remove_item(item_name, 1)
        if success:
            player.add_gold(sell_price)
            return True, f"Sold {item_name} for {sell_price}💰!"
        else:
            return False, message
    
    def get_sellable_items(self, player):
        """Get list of items player can sell"""
        sellable = []
        for inv_item in player.inventory.items:
            item = inv_item['item']
            quantity = inv_item['quantity']
            sell_price = max(1, item.value // 2)
            sellable.append({
                'item': item,
                'quantity': quantity,
                'sell_price': sell_price
            })
        return sellable 