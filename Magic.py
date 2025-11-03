from Item import Item

class Magic(Item):
    def __init__(self, name, description, damage, mana, value=0, spell_type=None):
        super().__init__(name, "magic", value, description)
        self.damage = damage
        self.mana = mana
        # Infer spell type if not provided
        if spell_type is None:
            n = (name or "").lower()
            if "heal" in n:
                self.spell_type = "heal"
            elif "ward" in n or "shield" in n:
                self.spell_type = "shield"
            elif "blind" in n:
                self.spell_type = "blind"
            elif "poison" in n or "venom" in n:
                self.spell_type = "poison"
            else:
                self.spell_type = "damage"
        else:
            self.spell_type = spell_type

    def __str__(self):
        return f"{self.name} - {self.description} (Damage: {self.damage}, Mana: {self.mana})"

    def __repr__(self):
        return f"Magic('{self.name}', '{self.description}', {self.damage}, {self.mana}, {self.value}, '{self.spell_type}')"
    
    def cast(self, caster, target):
        """Cast the magic spell. For support spells, target may be ignored."""
        from Enemy import Enemy
        if not caster.alive:
            return f"{caster.name} is dead and cannot cast magic!"
        if self.spell_type == 'heal':
            # Use damage as potency if provided, else a sensible default
            amount = self.damage if self.damage > 0 else 60
            if hasattr(caster, 'stats'):
                amount += int(caster.stats.get('intelligence', 0) * 2)
            healed = caster.heal(amount)
            return f"{caster.name} casts {self.name} and restores {healed} HP!", 0
        elif self.spell_type == 'shield':
            # Apply a shield reduction for a few turns
            reduction = 0.35
            turns = 3
            if hasattr(caster, 'add_status'):
                caster.add_status('shield', { 'reduction_pct': reduction, 'turns': turns })
            return f"{caster.name} casts {self.name}. A ward shimmers around you ({int(reduction*100)}% for {turns} turns).", 0
        elif self.spell_type == 'blind':
            if not isinstance(target, Enemy) or not target.alive:
                return f"There is no valid target to blind!", 0
            penalty = 0.25
            turns = 3
            if hasattr(target, 'add_status'):
                target.add_status('blind', { 'accuracy_penalty': penalty, 'turns': turns })
            return f"{caster.name} casts {self.name}. {target.name} staggers, vision clouded!", 0
        elif self.spell_type == 'freeze':
            if not isinstance(target, Enemy) or not target.alive:
                return f"There is no valid target to freeze!", 0
            turns = 1
            if hasattr(target, 'add_status'):
                target.add_status('frozen', { 'turns': turns })
            return f"{caster.name} casts {self.name}. {target.name} is frozen in place!", 0
        elif self.spell_type == 'burn':
            if not isinstance(target, Enemy) or not target.alive:
                return f"There is no valid target to burn!", 0
            dot = max(5, int(self.damage or 10))
            turns = 3
            if hasattr(target, 'add_status'):
                target.add_status('burn', { 'damage': dot, 'turns': turns })
            return f"{caster.name} casts {self.name}. Flames cling to {target.name} ({dot}/turn)!", 0
        elif self.spell_type == 'poison':
            if not isinstance(target, Enemy) or not target.alive:
                return f"There is no valid target to poison!", 0
            dot = max(6, int(self.damage or 12))
            turns = 3
            if hasattr(target, 'add_status'):
                target.add_status('poison', { 'damage': dot, 'turns': turns })
            return f"{caster.name} casts {self.name}. {target.name} is poisoned ({dot}/turn)!", 0
        else:
            if not target.alive:
                return f"Cannot cast magic on {target.name} - target is already dead!", 0
            # Damage spell
            actual_damage = target.take_damage(self.damage, attacker=caster, damage_type='magic')
            result = f"{caster.name} casts {self.name} on {target.name} for {actual_damage} damage!"
            if not target.alive:
                result += f"\n💀 {self.name} has killed {target.name}!"
            return result, actual_damage 

    def get_requirement(self):
        """Return a tuple (stat_name, min_value) representing the intelligence requirement to equip this spell.
        Stronger spells require higher intelligence.
        """
        if self.damage <= 20:
            return ("intelligence", 10)
        elif self.damage <= 35:
            return ("intelligence", 12)
        else:
            return ("intelligence", 14)