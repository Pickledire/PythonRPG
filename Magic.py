from Item import Item

class Magic(Item):
    def __init__(self, name, description, damage, mana, value=0):
        super().__init__(name, "magic", value, description)
        self.damage = damage
        self.mana = mana

    def __str__(self):
        return f"{self.name} - {self.description} (Damage: {self.damage}, Mana: {self.mana})"

    def __repr__(self):
        return f"Magic('{self.name}', '{self.description}', {self.damage}, {self.mana}, {self.value})"
    
    def cast(self, caster, target):
        """Cast the magic spell from caster to target"""
        if not caster.alive:
            return f"{caster.name} is dead and cannot cast magic!"
            
        if not target.alive:
            return f"Cannot cast magic on {target.name} - target is already dead!"
            
        # Apply damage to target
        actual_damage = target.take_damage(self.damage)
        
        result = f"{caster.name} casts {self.name} on {target.name} for {actual_damage} damage!"
        
        if not target.alive:
            result += f"\n💀 {self.name} has killed {target.name}!"
        
        return result, actual_damage 