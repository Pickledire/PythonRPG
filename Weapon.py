from Item import Item

class Weapon(Item):
    """Weapon class that inherits from Item"""
    
    def __init__(self, name, damage, durability=100, description="", value=0, weapon_type="melee"):
        super().__init__(name, "weapon", value, description)
        self.damage = damage
        self.durability = durability
        self.max_durability = durability
        self.weapon_type = weapon_type  # 'melee', 'ranged', 'magic'
    
    def __str__(self):
        return f"{self.name} (Damage: {self.damage}, Durability: {self.durability}/{self.max_durability})"
    
    def use(self):
        """Use the weapon (reduces durability)"""
        if self.durability > 0:
            self.durability -= 1
            return True
        return False
    
    def repair(self, amount=None):
        """Repair the weapon"""
        if amount is None:
            amount = self.max_durability
        self.durability = min(self.max_durability, self.durability + amount)
    
    def is_broken(self):
        """Check if weapon is broken"""
        return self.durability <= 0
    
    def get_effective_damage(self):
        """Get damage considering durability"""
        if self.is_broken():
            return 0
        # Reduce damage as durability decreases
        durability_ratio = self.durability / self.max_durability
        return int(self.damage * max(0.1, durability_ratio))  # Minimum 10% damage

    def get_requirement(self):
        """Return a tuple (stat_name, min_value) representing the stat requirement to equip this weapon.
        Rules:
        - melee → strength (heavy weapons need more)
        - ranged → agility (bows/crossbows)
        - magic → intelligence (handled primarily by Magic, but some weapons may be magic type)
        - agile melee (daggers/claws/rapiers) → agility
        """
        name_lower = self.name.lower()
        # Detect agile melee by name
        is_agile_melee = self.weapon_type == "melee" and any(k in name_lower for k in ["dagger", "claw", "rapier"])

        if self.weapon_type == "ranged" or is_agile_melee:
            # Agility requirement based on damage tiers
            if self.damage <= 18:
                return ("agility", 10)
            elif self.damage <= 25:
                return ("agility", 12)
            else:
                return ("agility", 14)
        elif self.weapon_type == "magic":
            # Intelligence requirement based on damage tiers
            if self.damage <= 20:
                return ("intelligence", 10)
            elif self.damage <= 35:
                return ("intelligence", 12)
            else:
                return ("intelligence", 14)
        else:
            # Melee defaults to strength; heavy weapons need more
            if self.damage <= 15:
                return ("strength", 8)
            elif self.damage <= 25:
                return ("strength", 12)
            else:
                return ("strength", 15)
