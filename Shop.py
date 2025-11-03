import shutil
from Weapon import Weapon
from Item import Consumable, Armor
from Magic import Magic

class Shop:
    """Shop class for buying and selling items with rotation support"""
    
    def __init__(self, mode: str = 'general'):
        self.mode = mode  # 'general' or 'magic'
        self.inventory = []
        self._pools = self._build_pools()
        self.refresh_inventory()
    
    def _build_pools(self):
        """Build item pools for rotation"""
        pools = { 'weapon': [], 'armor': [], 'consumable': [], 'magic': [] }
        
        # Weapons
        weapons = [
            Weapon("Bronze Sword", 10, 90, "A basic bronze sword", 40, "melee"),
            Weapon("Steel Sword", 18, 120, "A sharp steel blade", 80, "melee"),
            Weapon("Silver Sword", 26, 110, "A gleaming silver sword", 125, "melee"),
            Weapon("Enchanted Blade", 33, 150, "A magically enhanced sword", 200, "melee"),
            Weapon("Greatsword", 38, 180, "A massive two-handed sword", 300, "melee"),
            Weapon("Broadsword", 28, 150, "A wide blade sword", 175, "melee"),

            Weapon("Short Bow", 12, 90, "A simple wooden bow", 50, "ranged"),
            Weapon("Long Bow", 20, 110, "A powerful longbow", 180, "ranged"),
            Weapon("Crossbow", 28, 100, "A mechanical crossbow", 150, "ranged"),
            
            Weapon("Oak Staff", 12, 80, "A wooden magic staff", 60, "magic"),
            Weapon("Crystal Staff", 22, 100, "A staff with a crystal orb", 110, "magic"),
            Weapon("Arcane Staff", 30, 110, "A staff humming with power", 175, "magic"),
            
            Weapon("War Hammer", 24, 150, "A heavy two-handed hammer", 100, "melee"),
            Weapon("Battle Axe", 28, 130, "A fearsome two-handed axe", 140, "melee"),
            Weapon("Axe", 20, 110, "A basic axe", 50, "melee"),
            Weapon("Halberd", 26, 110, "A basic halberd", 50, "melee"),
            Weapon("Spear", 24, 110, "A basic spear", 50, "melee"),        
        ]
        
        # Armor
        armors = [
            Armor("Cloth Robes", 6, 60, "Basic cloth protection", 30),
            Armor("Leather Armor", 10, 110, "Flexible leather protection", 40),
            Armor("Studded Leather", 14, 130, "Reinforced leather armor", 75),
            Armor("Chain Mail", 18, 150, "Interlocked metal rings", 110),
            Armor("Scale Mail", 22, 160, "Overlapping metal scales", 150),
            Armor("Plate Armor", 24, 200, "Heavy metal plates", 225),
            Armor("Enchanted Robes", 18, 100, "Magically protected robes", 140),
            Armor("Dragon Scale", 28, 180, "Armor made from dragon scales", 200),
            Armor("Mithril Armor", 32, 220, "A mithril armor", 300),
        ]
        
        # Consumables
        consumables = [
            Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25),
            Consumable("Greater Health Potion", "heal", 100, "Restores 100 HP", 50),
            Consumable("Superior Health Potion", "heal", 200, "Restores 200 HP", 100),
            Consumable("Mega Health Potion", "heal", 500, "Restores 500 HP", 200),
            Consumable("Mana Potion", "mana", 30, "Restores 30 mana", 20),
            Consumable("Greater Mana Potion", "mana", 60, "Restores 60 mana", 40),
            Consumable("Superior Mana Potion", "mana", 100, "Restores 100 mana", 75),
        ]
        
        # Magic
        magic = [
            Magic("Fireball", "A fiery ball of energy", 67, 20, 200),
            Magic("Ice Shard", "A sharp ice shard", 45, 15, 150),
            Magic("Lightning Bolt", "A powerful lightning bolt", 80, 25, 300),
            Magic("Fire Bolt", "A fiery bolt of energy", 30, 10, 100),
            Magic("Ice Bolt", "A sharp ice bolt", 25, 10, 100),
            Magic("Lightning Bolt", "A powerful lightning bolt", 23, 10, 150),
            Magic("Heal", "Mend flesh and resolve", 0, 14, 180, spell_type='heal'),
            Magic("Ward", "Shape a barrier of will", 0, 12, 160, spell_type='shield'),
            Magic("Blind", "Steal the enemy's surety", 0, 16, 200, spell_type='blind'),
            Magic("Venom Spray", "Coat the foe in biting poison", 12, 14, 170, spell_type='poison'),
        ]
        for w in weapons:
            pools['weapon'].append(w)
        for a in armors:
            pools['armor'].append(a)
        for c in consumables:
            pools['consumable'].append(c)
        for m in magic:
            pools['magic'].append(m)
        return pools

    def refresh_inventory(self, seed=None):
        """Rotate inventory selection. Use optional seed for deterministic rotation."""
        import random
        rnd = random.Random()
        if seed is not None:
            rnd.seed(int(seed))
        else:
            rnd.seed()
        self.inventory = []
        if self.mode == 'general':
            # Sample a subset
            for item in rnd.sample(self._pools['weapon'], k=min(5, len(self._pools['weapon']))):
                self.inventory.append({'item': item, 'stock': 1, 'price': item.value})
            for item in rnd.sample(self._pools['armor'], k=min(4, len(self._pools['armor']))):
                self.inventory.append({'item': item, 'stock': 1, 'price': item.value})
            for item in rnd.sample(self._pools['consumable'], k=min(5, len(self._pools['consumable']))):
                self.inventory.append({'item': item, 'stock': 99, 'price': item.value})
            for item in rnd.sample(self._pools['magic'], k=min(3, len(self._pools['magic']))):
                self.inventory.append({'item': item, 'stock': 1, 'price': item.value})
        elif self.mode == 'magic':
            # Curate stronger spells only
            better_spells = [
                Magic("Meteor Lance", "A spear of falling starfire", 72, 26, 320),
                Magic("Frozen Crown", "A ring of razors made of winter", 68, 24, 300),
                Magic("Thunder Chorus", "A chorus of bolts that rarely agree", 80, 30, 360),
                Magic("Aegis Ward", "A disciplined barrier spell", 0, 14, 180),
                Magic("Sun Flare", "A bright unmaking for stubborn shadows", 76, 28, 340),
                Magic("Freeze", "Still the foe's limbs", 0, 18, 240, spell_type='freeze'),
                Magic("Burn", "Searing flame that lingers", 14, 16, 240, spell_type='burn'),
            ]
            pool = self._pools['magic'] + better_spells
            for item in rnd.sample(pool, k=min(6, len(pool))):
                self.inventory.append({'item': item, 'stock': 1, 'price': item.value})
            # Mana/health potions
            for item in rnd.sample(self._pools['consumable'], k=min(3, len(self._pools['consumable']))):
                self.inventory.append({'item': item, 'stock': 99, 'price': item.value})
    
    def display_items(self, item_type=None):
        """Display shop items, optionally filtered by type"""
        def center(line: str):
            try:
                term_width = shutil.get_terminal_size(fallback=(120, 40)).columns
            except Exception:
                term_width = 120
            ui_width = max(60, min(140, term_width - 0))
            padding = max(0, (ui_width - len(line)) // 2)
            print(" " * padding + line)
        if item_type:
            items = [item for item in self.inventory if item['item'].item_type == item_type and item['stock'] > 0]
            center(f"\n=== {item_type.upper()} ===")
        else:
            items = [item for item in self.inventory if item['stock'] > 0]
            center("\n=== SHOP INVENTORY ===")
        
        if not items:
            print("No items available in this category.")
            return []
        
        for i, shop_item in enumerate(items, 1):
            item = shop_item['item']
            price = shop_item['price']
            stock = shop_item['stock']
            
            if item.item_type == 'weapon':
                # Show stat requirement if available
                req_txt = ""
                if hasattr(item, 'get_requirement'):
                    stat, val = item.get_requirement()
                    req_txt = f", Req: {stat.capitalize()} {val}+"
                center(f"{i}. {item.name} - {price}💰 (Damage: {item.damage}, Durability: {item.max_durability}{req_txt})")
            elif item.item_type == 'armor':
                req_txt = ""
                if hasattr(item, 'get_requirement'):
                    stat, val = item.get_requirement()
                    req_txt = f", Req: {stat.capitalize()} {val}+"
                center(f"{i}. {item.name} - {price}💰 (Defense: {item.defense}, Durability: {item.max_durability}{req_txt})")
            elif item.item_type == 'consumable':
                center(f"{i}. {item.name} - {price}💰 (Effect: {item.effect_value}, Stock: {stock})")
            elif item.item_type == 'magic':
                req_txt = ""
                if hasattr(item, 'get_requirement'):
                    stat, val = item.get_requirement()
                    req_txt = f", Req: {stat.capitalize()} {val}+"
                if hasattr(item, 'spell_type') and item.spell_type != 'damage':
                    center(f"{i}. {item.name} - {price}💰 (Spell: {item.spell_type}, Mana: {item.mana}{req_txt})")
                else:
                    center(f"{i}. {item.name} - {price}💰 (Damage: {item.damage}, Mana: {item.mana}{req_txt})")
            else:
                center(f"{i}. {item.name} - {price}💰")
            
            if item.description:
                center(f"{item.description}")
        
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