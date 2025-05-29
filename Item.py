class Item:
    """Base class for all items in the game"""
    
    def __init__(self, name, item_type, value=0, description=""):
        self.name = name
        self.item_type = item_type
        self.value = value
        self.description = description
    
    def __str__(self):
        return f"{self.name}"
    
    def __repr__(self):
        return f"{self.name} ({self.item_type})"
    
    def get_info(self):
        """Return detailed information about the item"""
        return f"{self.name} - {self.description} (Value: {self.value})"


class Consumable(Item):
    """Consumable items like potions"""
    
    def __init__(self, name, effect_type, effect_value, description="", value=0):
        super().__init__(name, "consumable", value, description)
        self.effect_type = effect_type  # 'heal', 'mana', 'buff', etc.
        self.effect_value = effect_value
    
    def use(self, target):
        """Use the consumable on a target"""
        if self.effect_type == "heal":
            old_health = target.health
            target.health = min(target.max_health, target.health + self.effect_value)
            healed = target.health - old_health
            return f"{target.name} was healed for {healed} HP!"
        # Add more effect types as needed
        return f"{self.name} was used on {target.name}"


class Armor(Item):
    """Armor items that provide defense"""
    
    def __init__(self, name, defense, durability=100, description="", value=0):
        super().__init__(name, "armor", value, description)
        self.defense = defense
        self.durability = durability
        self.max_durability = durability
    
    def __str__(self):
        return f"{self.name} (Defense: {self.defense}, Durability: {self.durability}/{self.max_durability})" 