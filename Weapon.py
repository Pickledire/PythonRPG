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
