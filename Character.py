import random
from config import RACE_STATS, DEFAULT_STATS, BASE_XP_REQUIREMENT, XP_INCREASE_PER_LEVEL, HEALTH_GAIN_PER_LEVEL, MIN_XP_REWARD, MAX_XP_REWARD, DAMAGE_VARIANCE, STARTING_GOLD
from Inventory import Inventory
from Weapon import Weapon
from Item import Consumable, Armor

class Character:
    """Enhanced Character class with improved stats, inventory, and combat"""
    
    def __init__(self, name, race):
        self.name = name
        self.race = race
        self.level = 1
        self.xp = 0
        self.alive = True
        self.gold = STARTING_GOLD
        
        # Get race stats or use defaults
        race_data = RACE_STATS.get(race, DEFAULT_STATS)
        self.stats = race_data.copy()
        
        # Remove health from stats and set it separately
        self.max_health = self.stats.pop('health')
        self.health = self.max_health
        
        # Initialize inventory system
        self.inventory = Inventory()
        
        # Give starting equipment based on race
        self._give_starting_equipment()
    
    def _give_starting_equipment(self):
        """Give race-appropriate starting equipment"""
        if self.race == 'Elf':
            bow = Weapon("Elven Bow", 12, 80, "A graceful elven bow", 50, "ranged")
            self.inventory.add_item(bow)
            self.inventory.equip_weapon("Elven Bow")
        elif self.race == 'Orc':
            axe = Weapon("Orcish Axe", 18, 120, "A brutal orcish war axe", 75, "melee")
            self.inventory.add_item(axe)
            self.inventory.equip_weapon("Orcish Axe")
        elif self.race == 'Human':
            sword = Weapon("Iron Sword", 15, 100, "A reliable iron sword", 60, "melee")
            self.inventory.add_item(sword)
            self.inventory.equip_weapon("Iron Sword")
        elif self.race == 'Dwarf':
            hammer = Weapon("Dwarven Hammer", 16, 150, "A sturdy dwarven war hammer", 80, "melee")
            self.inventory.add_item(hammer)
            self.inventory.equip_weapon("Dwarven Hammer")
        
        # Give starting consumables
        health_potion = Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25)
        self.inventory.add_item(health_potion, 3)
    
    def __str__(self):
        return f"{self.name} (Level {self.level} {self.race})"
    
    def get_status(self):
        """Get detailed character status"""
        status = f"\n=== {self.name} ===\n"
        status += f"Race: {self.race}\n"
        status += f"Level: {self.level}\n"
        status += f"XP: {self.xp}/{self.xp_required()}\n"
        status += f"Health: {self.health}/{self.max_health}\n"
        status += f"Gold: {self.gold} 💰\n"
        status += f"Stats: STR:{self.stats['strength']} AGI:{self.stats['agility']} INT:{self.stats['intelligence']}\n"
        
        weapon = self.inventory.equipped_weapon
        armor = self.inventory.equipped_armor
        status += f"Weapon: {weapon.name if weapon else 'None'}\n"
        status += f"Armor: {armor.name if armor else 'None'}\n"
        
        return status
    
    def xp_required(self):
        """Calculate XP required for next level"""
        return BASE_XP_REQUIREMENT + ((self.level - 1) * XP_INCREASE_PER_LEVEL)
    
    def gain_xp(self, amount):
        """Gain experience points and handle leveling"""
        self.xp += amount
        levels_gained = 0
        
        while self.xp >= self.xp_required():
            self.xp -= self.xp_required()
            self.level += 1
            self.max_health += HEALTH_GAIN_PER_LEVEL
            self.health += HEALTH_GAIN_PER_LEVEL  # Heal on level up
            levels_gained += 1
            
            # Increase stats on level up
            self.stats['strength'] += 1
            self.stats['agility'] += 1
            self.stats['intelligence'] += 1
        
        if levels_gained > 0:
            print(f"\n🎉 {self.name} leveled up {levels_gained} time(s)! Now level {self.level}")
            print(f"Health increased to {self.max_health}! All stats increased!")
    
    def heal(self, amount):
        """Heal the character"""
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        healed = self.health - old_health
        return healed
    
    def take_damage(self, damage):
        """Take damage, considering armor"""
        armor = self.inventory.equipped_armor
        defense = armor.defense if armor else 0
        
        # Calculate damage reduction
        reduced_damage = max(1, damage - defense)  # Minimum 1 damage
        
        self.health -= reduced_damage
        if self.health <= 0:
            self.health = 0
            self.alive = False
        
        return reduced_damage
    
    def attack(self, target):
        """Attack a target with equipped weapon"""
        if not self.alive:
            return f"{self.name} is dead and cannot attack!"
        
        weapon = self.inventory.equipped_weapon
        if not weapon:
            return f"{self.name} has no weapon equipped!"
        
        if weapon.is_broken():
            return f"{self.name}'s {weapon.name} is broken!"
        
        # Calculate damage
        base_damage = weapon.get_effective_damage()
        strength_bonus = self.stats['strength'] * 0.5
        agility_bonus = self.stats['agility'] * 0.3
        
        # Add some randomness
        damage_variance = random.uniform(-DAMAGE_VARIANCE, DAMAGE_VARIANCE)
        final_damage = int((base_damage + strength_bonus + agility_bonus) * (1 + damage_variance))
        final_damage = max(1, final_damage)  # Minimum 1 damage
        
        # Use weapon (reduces durability)
        weapon.use()
        
        # Apply damage to target
        actual_damage = target.take_damage(final_damage)
        
        result = f"{self.name} attacks {target.name} with {weapon.name} for {actual_damage} damage!"
        
        if not target.alive:
            xp_gained = random.randint(MIN_XP_REWARD, MAX_XP_REWARD)
            self.gain_xp(xp_gained)
            result += f"\n💀 {target.name} has been defeated! Gained {xp_gained} XP!"
        
        return result
    
    def use_item(self, item_name):
        """Use an item from inventory"""
        success, message = self.inventory.use_item(item_name, self)
        return message
    
    def equip_weapon(self, weapon_name):
        """Equip a weapon from inventory"""
        success, message = self.inventory.equip_weapon(weapon_name)
        return message
    
    def equip_armor(self, armor_name):
        """Equip armor from inventory"""
        success, message = self.inventory.equip_armor(armor_name)
        return message
    
    def show_inventory(self):
        """Display inventory contents"""
        return self.inventory.list_items()
    
    def get_available_actions(self):
        """Get list of available combat actions"""
        actions = ["attack"]
        
        # Add consumable items
        consumables = self.inventory.get_consumables()
        for consumable in consumables:
            actions.append(f"use {consumable.name}")
        
        return actions
    
    def add_gold(self, amount):
        """Add gold to the character"""
        self.gold += amount
        return f"Gained {amount} gold! Total: {self.gold} 💰"
    
    def spend_gold(self, amount):
        """Spend gold if the character has enough"""
        if self.gold >= amount:
            self.gold -= amount
            return True, f"Spent {amount} gold. Remaining: {self.gold} 💰"
        else:
            return False, f"Not enough gold! You have {self.gold} but need {amount}." 