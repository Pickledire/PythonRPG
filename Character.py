import random
from colorama import Fore, Style
from config import RACE_STATS, DEFAULT_STATS, BASE_XP_REQUIREMENT, XP_INCREASE_PER_LEVEL, HEALTH_GAIN_PER_LEVEL, MIN_XP_REWARD, MAX_XP_REWARD, DAMAGE_VARIANCE, STARTING_GOLD
from Inventory import Inventory
from Weapon import Weapon
from Item import Consumable, Armor
from Magic import Magic

class Character:
    
    def __init__(self, name, race):
        self.name = name
        self.race = race
        self.level = 1
        self.xp = 0
        self.alive = True
        self.gold = STARTING_GOLD
        self.mana = 100
        self.max_mana = 100
        self.level_10_boss = False
        self.kills = 0
        # Color scheme for character display
        self.colors = {
            'name': Fore.CYAN + Style.BRIGHT,
            'race': Fore.YELLOW + Style.BRIGHT,
            'level': Fore.GREEN + Style.BRIGHT,
            'health': Fore.RED + Style.BRIGHT,
            'gold': Fore.YELLOW + Style.BRIGHT,
            'stats': Fore.BLUE + Style.BRIGHT,
            'success': Fore.GREEN + Style.BRIGHT,
            'error': Fore.RED + Style.BRIGHT,
            'warning': Fore.YELLOW,
            'weapon': Fore.CYAN,
            'armor': Fore.MAGENTA,
            'xp': Fore.GREEN,
            'border': Fore.CYAN + Style.BRIGHT,
            'magic': Fore.BLUE + Style.BRIGHT,
            'menu': Fore.WHITE + Style.BRIGHT,
            'enemy': Fore.RED + Style.BRIGHT,
            'reset': Style.RESET_ALL
        }
        
        # Get race stats or use defaults
        race_data = RACE_STATS.get(race, DEFAULT_STATS)
        self.stats = race_data.copy()
        
        # Remove health from stats and set it separately
        self.max_health = self.stats.pop('health')
        self.health = self.max_health
        
        # Initialize inventory system
        self.inventory = Inventory()
        self.inventory.owner = self
        self.status_effects = {}
        
        # Give starting equipment based on race
        self._give_starting_equipment()
    
    def _give_starting_equipment(self):
        if self.race == 'Elf':
            bow = Weapon("Elven Bow", 12, 80, "A graceful elven bow", 50, "ranged")
            elven_magic = Magic("Elven Blast", "A magical blast of energy", 22, 10, 100)
            self.inventory.add_item(bow)
            self.inventory.add_item(elven_magic)
            self.inventory.equip_weapon("Elven Bow")
            self.inventory.equip_magic("Elven Blast")
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
            dwarven_magic = Magic("Dwarven Scream", "A powerful dwarven scream", 14, 10, 80)
            self.inventory.add_item(hammer)
            self.inventory.add_item(dwarven_magic)
            self.inventory.equip_weapon("Dwarven Hammer")
            self.inventory.equip_magic("Dwarven Scream")
        
        # Give starting consumables
        health_potion = Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25)
        self.inventory.add_item(health_potion, 3)
    
    def __str__(self):
        return f"{self.name} (Level {self.level} {self.race})"
    
    def get_status(self):
        # Create visual health and XP bars
        def create_bar(current, maximum, width=20, filled_char="█", empty_char="░"):
            if maximum == 0:
                percentage = 0
            else:
                percentage = current / maximum
            filled = int(width * percentage)
            empty = width - filled
            return filled_char * filled + empty_char * empty
        
        # Health bar with color coding
        health_percentage = self.health / self.max_health if self.max_health > 0 else 0
        if health_percentage > 0.6:
            health_color = Fore.GREEN + Style.BRIGHT
        elif health_percentage > 0.3:
            health_color = Fore.YELLOW + Style.BRIGHT
        else:
            health_color = Fore.RED + Style.BRIGHT
        
        health_bar = create_bar(self.health, self.max_health)
        
        # XP bar
        xp_required = self.xp_required()
        xp_bar = create_bar(self.xp, xp_required)
        
        # Build status string with colors
        status = f"\n{self.colors['border']}{'═' * 50}{self.colors['reset']}\n"
        status += f"{self.colors['name']}🛡️  {self.name}{self.colors['reset']} - {self.colors['race']}{self.race}{self.colors['reset']} {self.colors['level']}(Level {self.level}){self.colors['reset']}\n"
        status += f"{self.colors['border']}{'═' * 50}{self.colors['reset']}\n"
        
        # Health display
        status += f"{health_color}❤️  Health: [{health_bar}] {self.health}/{self.max_health}{self.colors['reset']}\n"
        
        # Mana display
        mana_bar = create_bar(self.mana, self.max_mana)
        status += f"{self.colors['magic']}🔮 Mana: [{mana_bar}] {self.mana}/{self.max_mana}{self.colors['reset']}\n"
        
        # XP display
        status += f"{self.colors['xp']}⭐ XP: [{xp_bar}] {self.xp}/{xp_required}{self.colors['reset']}\n"
        
        # Gold
        status += f"{self.colors['gold']}💰 Gold: {self.gold}{self.colors['reset']}\n"
        
        # Stats
        status += f"{self.colors['stats']}📊 Stats: STR:{self.stats['strength']} AGI:{self.stats['agility']} INT:{self.stats['intelligence']}{self.colors['reset']}\n"
        
        # Equipment
        magic_items = self.inventory.get_magic()
        weapon = self.inventory.equipped_weapon
        armor = self.inventory.equipped_armor
        status += f"{self.colors['weapon']}⚔️  Weapon: {weapon.name if weapon else 'None'}{self.colors['reset']}\n"
        status += f"{self.colors['armor']}🛡️  Armor: {armor.name if armor else 'None'}{self.colors['reset']}\n"
        status += f"{self.colors['magic']}🔮  Spells Known: {len(magic_items)}{self.colors['reset']}\n"
        
        status += f"{self.colors['border']}{'═' * 50}{self.colors['reset']}"
        
        return status
    
    def xp_required(self):
        return BASE_XP_REQUIREMENT + ((self.level - 1) * XP_INCREASE_PER_LEVEL)
    
    def gain_xp(self, amount):
        self.xp += amount
        levels_gained = 0
        
        while self.xp >= self.xp_required():
            self.xp -= self.xp_required()
            self.level += 1
            self.max_health += HEALTH_GAIN_PER_LEVEL
            self.health += HEALTH_GAIN_PER_LEVEL  # Heal on level up
            levels_gained += 1
            
            # Let the player choose a stat to increase
            self._choose_stat_increase()
            
            # Increase mana on level up
            self.max_mana += 10
            self.mana += 10
        
        if levels_gained > 0:
            print(f"\n{self.colors['level']}🎉 {self.name} leveled up {levels_gained} time(s)! Now level {self.level}{self.colors['reset']}")
            print(f"{self.colors['health']}Health increased to {self.max_health}! Choose a stat each level.{self.colors['reset']}")

    def _choose_stat_increase(self):
        """Prompt the player to choose a stat to increase on level up."""
        while True:
            print(f"\n{self.colors['border']}{'─'*40}{self.colors['reset']}")
            print(f"{self.colors['xp']}Choose a stat to increase:{self.colors['reset']}\n")
            print(f"{self.colors['stats']}1. Strength{self.colors['reset']} (current: {self.stats['strength']})")
            print(f"{self.colors['stats']}2. Agility{self.colors['reset']} (current: {self.stats['agility']})")
            print(f"{self.colors['stats']}3. Intelligence{self.colors['reset']} (current: {self.stats['intelligence']})")
            choice = input(f"{self.colors['menu']}Enter 1, 2, or 3: {self.colors['reset']}").strip()
            if choice == '1':
                self.stats['strength'] += 1
                print(f"{self.colors['success']}Strength increased to {self.stats['strength']}{self.colors['reset']}")
                break
            elif choice == '2':
                self.stats['agility'] += 1
                print(f"{self.colors['success']}Agility increased to {self.stats['agility']}{self.colors['reset']}")
                break
            elif choice == '3':
                self.stats['intelligence'] += 1
                print(f"{self.colors['success']}Intelligence increased to {self.stats['intelligence']}{self.colors['reset']}")
                break
            else:
                print(f"{self.colors['error']}Invalid choice. Please enter 1, 2, or 3.{self.colors['reset']}")
    
    def heal(self, amount):
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        healed = self.health - old_health
        return healed
    
    def restore_mana(self, amount):
        old_mana = self.mana
        self.mana = min(self.max_mana, self.mana + amount)
        restored = self.mana - old_mana
        return restored
    
    def rest(self):
        """Rest to restore health and mana"""
        health_restored = self.heal(self.max_health // 4)  # Restore 25% health
        mana_restored = self.restore_mana(self.max_mana // 2)  # Restore 50% mana
        return f"You rest and recover {health_restored} HP and {mana_restored} mana."
    
    def take_damage(self, damage, attacker=None, damage_type='physical'):
        armor = self.inventory.equipped_armor
        defense = armor.defense if armor else 0

        # Armor penetration for strong attackers / bosses
        penetration = 0.0
        if attacker is not None:
            try:
                # Base on attacker base damage and strength
                if hasattr(attacker, 'base_damage') and attacker.base_damage >= 40:
                    penetration += 0.25
                if hasattr(attacker, 'stats'):
                    penetration += min(0.15, attacker.stats.get('strength', 0) * 0.01)
                # Bosses get a bit more penetration
                from Enemy import Boss
                if isinstance(attacker, Boss):
                    penetration += 0.10
            except Exception:
                pass
        penetration = min(0.5, max(0.0, penetration))

        effective_defense = defense * (1.0 - penetration)
        # Magic damage bypasses some armor
        if damage_type == 'magic':
            effective_defense *= 0.5

        # Diminishing returns formula for mitigation
        mitigation_multiplier = 100.0 / (100.0 + (effective_defense * 1.5))
        reduced_damage = int(max(1, round(damage * mitigation_multiplier)))
        # Shield reduces final damage
        shield = self.status_effects.get('shield')
        if shield and shield.get('turns', 0) > 0:
            pct = float(shield.get('reduction_pct', 0))
            reduced_damage = max(1, int(reduced_damage * (1.0 - pct)))

        self.health -= reduced_damage
        if self.health <= 0:
            self.health = 0
            self.alive = False
        
        return reduced_damage
    
    def attack(self, target):
        if not self.alive:
            return f"{self.colors['name']}{self.name}{self.colors['reset']} is dead and cannot attack!"
        
        weapon = self.inventory.equipped_weapon
        if not weapon:
            return f"{self.colors['name']}{self.name}{self.colors['reset']} has no weapon equipped!"
        
        if weapon.is_broken():
            return f"{self.colors['name']}{self.name}{self.colors['reset']}'s {self.colors['weapon']}{weapon.name}{self.colors['reset']} is broken!"
        
        # Accuracy and crits
        base_accuracy = 0.85 + (self.stats['agility'] * 0.003)
        # Target blind increases hit chance a bit (if enemy is blind, easier to hit)
        if hasattr(target, 'status_effects') and target.status_effects.get('blind', {}).get('turns', 0) > 0:
            base_accuracy += 0.10
        if random.random() > min(0.98, base_accuracy):
            weapon.use() if weapon else None
            return f"{self.colors['name']}{self.name}{self.colors['reset']} attacks {self.colors['enemy']}{target.name}{self.colors['reset']} but misses!"

        # Calculate damage
        base_damage = weapon.get_effective_damage()
        strength_bonus = self.stats['strength'] * 0.5
        agility_bonus = self.stats['agility'] * 0.3
        

        # Add some randomness
        damage_variance = random.uniform(-DAMAGE_VARIANCE, DAMAGE_VARIANCE)
        final_damage = int((base_damage + strength_bonus + agility_bonus) * (1 + damage_variance))
        # Crits
        crit_chance = 0.10 + (self.stats['strength'] * 0.002)
        crit = random.random() < min(0.5, crit_chance)
        if crit:
            final_damage = int(final_damage * 1.5)
        final_damage = max(1, final_damage)  # Minimum 1 damage
        
        # Use weapon (reduces durability)
        weapon.use()
        
        # Apply damage to target
        actual_damage = target.take_damage(final_damage)
        
        crit_txt = " (CRIT!)" if crit else ""
        result = f"{self.colors['name']}{self.name}{self.colors['reset']} attacks {Fore.RED}{target.name}{self.colors['reset']} with {self.colors['weapon']}{weapon.name}{self.colors['reset']} for {Fore.RED + Style.BRIGHT}{actual_damage}{self.colors['reset']} damage{crit_txt}!"
        
        if not target.alive:
            xp_gained = random.randint(MIN_XP_REWARD, MAX_XP_REWARD)
            self.gain_xp(xp_gained)
            result += f"\n{Fore.RED + Style.BRIGHT}💀 {target.name} has been defeated!{self.colors['reset']} {self.colors['xp']}Gained {xp_gained} XP!{self.colors['reset']}"
        
        return result

    def add_status(self, name: str, data: dict):
        if not isinstance(data, dict):
            return
        self.status_effects[name] = data

    def on_turn_start(self):
        messages = []
        # Poison
        p = self.status_effects.get('poison')
        if p and p.get('turns', 0) > 0:
            dmg = int(p.get('damage', 5))
            self.health = max(0, self.health - dmg)
            p['turns'] -= 1
            messages.append(f"{self.colors['error']}{self.name} suffers {dmg} poison damage!{self.colors['reset']}")
            if p['turns'] <= 0:
                self.status_effects.pop('poison', None)
        # Burn
        bdot = self.status_effects.get('burn')
        if bdot and bdot.get('turns', 0) > 0:
            dmg = int(bdot.get('damage', 6))
            self.health = max(0, self.health - dmg)
            bdot['turns'] -= 1
            messages.append(f"{self.colors['error']}{self.name} takes {dmg} burn damage!{self.colors['reset']}")
            if bdot['turns'] <= 0:
                self.status_effects.pop('burn', None)
        # Shield decay
        s = self.status_effects.get('shield')
        if s and s.get('turns', 0) > 0:
            s['turns'] -= 1
            if s['turns'] <= 0:
                self.status_effects.pop('shield', None)
                messages.append(f"{self.colors['warning']}{self.name}'s ward fades.{self.colors['reset']}")
        # Blind decay
        b = self.status_effects.get('blind')
        if b and b.get('turns', 0) > 0:
            b['turns'] -= 1
            if b['turns'] <= 0:
                self.status_effects.pop('blind', None)
        # Frozen decay (skip handled in player_turn/enemy_turn)
        f = self.status_effects.get('frozen')
        if f and f.get('turns', 0) > 0:
            f['turns'] -= 1
            if f['turns'] <= 0:
                self.status_effects.pop('frozen', None)
        return messages
    
    def cast_magic(self, target):
        if not self.alive:
            return f"{self.colors['name']}{self.name}{self.colors['reset']} is dead and cannot cast magic!"
        
        magic = self.inventory.equipped_magic
        if not magic:
            return f"{self.colors['name']}{self.name}{self.colors['reset']} has no magic equipped!"
        
        if magic.mana > self.mana:
            return f"{self.colors['name']}{self.name}{self.colors['reset']} does not have enough mana to cast {magic.name}! Need {magic.mana}, have {self.mana}."
        
        # Deduct mana
        self.mana -= magic.mana
        
        # Cast the spell
        result, damage = magic.cast(self, target)
        
        # Give XP if target is killed
        if not target.alive:
            xp_gained = target.get_xp_reward()
            self.gain_xp(xp_gained)
            result += f"\n{self.colors['xp']}Gained {xp_gained} XP!{self.colors['reset']}"
        
        return result
    
    def use_item(self, item_name):
        """Use an item from inventory"""
        success, message = self.inventory.use_item(item_name, self)
        return message
    
    def equip_weapon(self, weapon_name):
        """Equip a weapon from inventory"""
        weapon = self.inventory.get_item(weapon_name)
        if not weapon or not isinstance(weapon, Weapon):
            return f"Cannot equip {weapon_name}"
        # Check stat requirement
        req_stat, req_value = weapon.get_requirement()
        if self.stats.get(req_stat, 0) < req_value:
            return f"You need {req_stat.capitalize()} {req_value} to equip {weapon.name}. (Current: {self.stats.get(req_stat,0)})"
        success, message = self.inventory.equip_weapon(weapon_name)
        return message
    
    def equip_armor(self, armor_name):
        """Equip armor from inventory"""
        armor = self.inventory.get_item(armor_name)
        if not armor or not isinstance(armor, Armor):
            return f"Cannot equip {armor_name}"
        # Check stat requirement
        if hasattr(armor, 'get_requirement'):
            req_stat, req_value = armor.get_requirement()
            if self.stats.get(req_stat, 0) < req_value:
                return f"You need {req_stat.capitalize()} {req_value} to equip {armor.name}. (Current: {self.stats.get(req_stat,0)})"
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
        return f"{self.colors['gold']}Gained {amount} gold! Total: {self.gold} 💰{self.colors['reset']}"
    
    def spend_gold(self, amount):
        """Spend gold if the character has enough"""
        if self.gold >= amount:
            self.gold -= amount
            return True, f"{self.colors['gold']}Spent {amount} gold. Remaining: {self.gold} 💰{self.colors['reset']}"
        else:
            return False, f"{Fore.RED}Not enough gold! You have {self.gold} but need {amount}.{self.colors['reset']}" 