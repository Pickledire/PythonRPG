import random
from config import MIN_XP_REWARD, MAX_XP_REWARD, MIN_GOLD_REWARD, MAX_GOLD_REWARD

class Enemy:
    """Enhanced Enemy class with better AI and consistency"""
    
    def __init__(self, name, health, damage, enemy_type="monster", description=""):
        self.name = name
        self.max_health = health
        self.health = health
        self.base_damage = damage
        self.enemy_type = enemy_type
        self.description = description
        self.alive = True
        
        # Add some stats for variety
        self.stats = {
            'strength': random.randint(5, 15),
            'agility': random.randint(5, 15),
            'defense': random.randint(0, 5)
        }
    
    def __str__(self):
        if self.alive:
            return f"{self.name} (HP: {self.health}/{self.max_health})"
        else:
            return f"{self.name} (DEAD)"
    
    def __repr__(self):
        return self.__str__()
    
    def get_info(self):
        """Get detailed enemy information"""
        info = f"\n=== {self.name} ===\n"
        info += f"Type: {self.enemy_type}\n"
        info += f"Health: {self.health}/{self.max_health}\n"
        info += f"Base Damage: {self.base_damage}\n"
        info += f"Stats: STR:{self.stats['strength']} AGI:{self.stats['agility']} DEF:{self.stats['defense']}\n"
        if self.description:
            info += f"Description: {self.description}\n"
        return info
    
    def take_damage(self, damage):
        """Take damage with defense consideration"""
        defense = self.stats['defense']
        reduced_damage = max(1, damage - defense)  # Minimum 1 damage
        
        self.health -= reduced_damage
        if self.health <= 0:
            self.health = 0
            self.alive = False
        
        return reduced_damage
    
    def attack(self, target):
        """Attack a target with improved damage calculation"""
        if not self.alive:
            return f"{self.name} is dead and cannot attack!"
        
        # Calculate damage with stats
        strength_bonus = self.stats['strength'] * 0.3
        agility_bonus = self.stats['agility'] * 0.2
        
        # Add randomness
        damage_variance = random.uniform(-0.3, 0.3)
        final_damage = int((self.base_damage + strength_bonus + agility_bonus) * (1 + damage_variance))
        final_damage = max(1, final_damage)  # Minimum 1 damage
        
        # Apply damage to target
        actual_damage = target.take_damage(final_damage)
        
        result = f"{self.name} attacks {target.name} for {actual_damage} damage!"
        
        if not target.alive:
            result += f"\n💀 {self.name} has killed {target.name}!"
        
        return result
    
    def heal(self, amount):
        """Heal the enemy (for special abilities)"""
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        healed = self.health - old_health
        return healed
    
    def get_xp_reward(self):
        """Calculate XP reward based on enemy strength"""
        base_xp = random.randint(MIN_XP_REWARD, MAX_XP_REWARD)
        # Stronger enemies give more XP
        strength_multiplier = 1 + (self.stats['strength'] / 20)
        return int(base_xp * strength_multiplier)
    
    def get_gold_reward(self):
        """Calculate gold reward based on enemy strength"""
        base_gold = random.randint(MIN_GOLD_REWARD, MAX_GOLD_REWARD)
        # Stronger enemies give more gold
        strength_multiplier = 1 + (self.stats['strength'] / 30)
        return int(base_gold * strength_multiplier)


# Predefined enemy types for easy creation
class EnemyFactory:
    """Factory class to create different types of enemies"""
    
    @staticmethod
    def create_goblin():
        return Enemy("Goblin", 40, 8, "humanoid", "A small, green-skinned creature with sharp teeth")
    
    @staticmethod
    def create_orc():
        return Enemy("Orc Warrior", 80, 15, "humanoid", "A large, brutish warrior with crude armor")
    
    @staticmethod
    def create_skeleton():
        return Enemy("Skeleton", 35, 10, "undead", "Animated bones held together by dark magic")
    
    @staticmethod
    def create_troll():
        return Enemy("Cave Troll", 120, 20, "giant", "A massive creature with regenerative abilities")
    
    @staticmethod
    def create_dragon():
        return Enemy("Young Dragon", 200, 35, "dragon", "A fearsome winged beast with fiery breath")
    
    @staticmethod
    def create_random_enemy():
        """Create a random enemy"""
        enemy_types = [
            EnemyFactory.create_goblin,
            EnemyFactory.create_orc,
            EnemyFactory.create_skeleton,
            EnemyFactory.create_troll
        ]
        return random.choice(enemy_types)() 