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
        elif self.effect_type == "mana":
            old_mana = target.mana
            target.mana = min(target.max_mana, target.mana + self.effect_value)
            restored = target.mana - old_mana
            return f"{target.name} restored {restored} mana!"
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

    def get_requirement(self):
        """Return a tuple (stat_name, min_value) representing the stat requirement to equip this armor.
        Rules:
        - Heavy plate/dragon/mithril → strength
        - Chain/scale/mail → strength (moderate)
        - Leather/studded → agility
        - Cloth/robes/enchanted → intelligence
        Requirement scales softly with defense value.
        """
        name_lower = self.name.lower()
        # Determine category by name
        if any(k in name_lower for k in ["plate", "dragon", "mithril"]):
            base_stat = ("strength",)
        elif any(k in name_lower for k in ["chain", "scale", "mail"]):
            base_stat = ("strength",)
        elif any(k in name_lower for k in ["leather", "studded"]):
            base_stat = ("agility",)
        elif any(k in name_lower for k in ["cloth", "robe", "enchanted"]):
            base_stat = ("intelligence",)
        else:
            # Fallback: use defense to choose
            base_stat = ("strength",) if self.defense >= 20 else ("agility",)

        stat_name = base_stat[0]
        # Scale requirement by defense tiers
        if self.defense <= 12:
            req = 8
        elif self.defense <= 20:
            req = 10
        elif self.defense <= 35:
            req = 12
        else:
            req = 14
        return (stat_name, req)