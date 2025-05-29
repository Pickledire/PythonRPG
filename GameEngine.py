import random
import os
from Character import Character
from Enemy import Enemy, EnemyFactory
from Weapon import Weapon
from Item import Consumable, Armor
from config import RACE_STATS
from Shop import Shop

class GameEngine:
    """Main game engine that handles the game loop and combat"""
    
    def __init__(self):
        self.player = None
        self.current_enemy = None
        self.game_running = True
        self.in_combat = False
        self.shop = Shop()
    
    def clear_screen(self):
        """Clear the console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_title(self):
        """Display the game title"""
        print("=" * 50)
        print("🗡️  EPIC RPG ADVENTURE  ⚔️")
        print("=" * 50)
        print()
    
    def create_character(self):
        """Character creation process"""
        self.clear_screen()
        self.display_title()
        
        print("Welcome, brave adventurer!")
        print("Let's create your character...\n")
        
        # Get character name
        while True:
            name = input("Enter your character's name: ").strip()
            if name:
                break
            print("Please enter a valid name!")
        
        # Choose race
        print("\nChoose your race:")
        races = list(RACE_STATS.keys())
        for i, race in enumerate(races, 1):
            race_stats = RACE_STATS[race]
            print(f"{i}. {race} - STR:{race_stats['strength']} AGI:{race_stats['agility']} INT:{race_stats['intelligence']} HP:{race_stats['health']}")
        
        while True:
            try:
                choice = int(input(f"\nEnter your choice (1-{len(races)}): "))
                if 1 <= choice <= len(races):
                    selected_race = races[choice - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(races)}")
            except ValueError:
                print("Please enter a valid number!")
        
        # Create character
        self.player = Character(name, selected_race)
        
        print(f"\n🎉 Welcome, {self.player}!")
        print(self.player.get_status())
        input("\nPress Enter to continue...")
    
    def main_menu(self):
        """Display the main menu"""
        while self.game_running:
            self.clear_screen()
            self.display_title()
            
            if self.player:
                print(f"Playing as: {self.player}")
                print(f"Health: {self.player.health}/{self.player.max_health}")
                print(f"Gold: {self.player.gold} 💰")
                print()
            
            print("What would you like to do?")
            print("1. 🗡️  Find an enemy to fight")
            print("2. 📦 Check inventory")
            print("3. 📊 View character status")
            print("4. 🏪 Visit shop")
            print("5. 💾 Save game")
            print("6. 📁 Load game")
            print("7. ❌ Quit game")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == "1":
                self.start_combat()
            elif choice == "2":
                self.show_inventory_menu()
            elif choice == "3":
                self.show_character_status()
            elif choice == "4":
                self.visit_shop()
            elif choice == "5":
                self.save_game()
            elif choice == "6":
                self.load_game()
            elif choice == "7":
                self.quit_game()
            else:
                print("Invalid choice! Please try again.")
                input("Press Enter to continue...")
    
    def start_combat(self):
        """Start a combat encounter"""
        if not self.player.alive:
            print("You are dead! Game over!")
            input("Press Enter to continue...")
            return
        
        # Generate random enemy
        self.current_enemy = EnemyFactory.create_random_enemy()
        self.in_combat = True
        
        print(f"\n⚔️ A wild {self.current_enemy.name} appears!")
        print(self.current_enemy.get_info())
        input("Press Enter to start combat...")
        
        self.combat_loop()
    
    def combat_loop(self):
        """Main combat loop"""
        while self.in_combat and self.player.alive and self.current_enemy.alive:
            self.clear_screen()
            self.display_title()
            
            # Show combat status
            print("=== COMBAT ===")
            print(f"Player: {self.player.name} (HP: {self.player.health}/{self.player.max_health})")
            print(f"Enemy: {self.current_enemy}")
            print()
            
            # Player turn
            self.player_turn()
            
            if not self.current_enemy.alive:
                break
            
            # Enemy turn
            if self.current_enemy.alive:
                self.enemy_turn()
            
            if not self.player.alive:
                break
            
            input("\nPress Enter to continue...")
        
        # Combat ended
        self.end_combat()
    
    def player_turn(self):
        """Handle player's turn in combat"""
        print("Your turn! Choose an action:")
        print("1. ⚔️ Attack")
        print("2. 🧪 Use item")
        print("3. 🏃 Try to flee")
        
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            result = self.player.attack(self.current_enemy)
            print(f"\n{result}")
        elif choice == "2":
            self.use_item_in_combat()
        elif choice == "3":
            if self.try_flee():
                return
        else:
            print("Invalid choice! You lose your turn.")
    
    def enemy_turn(self):
        """Handle enemy's turn in combat"""
        print(f"\n{self.current_enemy.name}'s turn!")
        result = self.current_enemy.attack(self.player)
        print(result)
    
    def use_item_in_combat(self):
        """Use an item during combat"""
        consumables = self.player.inventory.get_consumables()
        
        if not consumables:
            print("You have no usable items!")
            return
        
        print("\nAvailable items:")
        for i, item in enumerate(consumables, 1):
            print(f"{i}. {item.name}")
        
        try:
            choice = int(input("Choose an item (0 to cancel): "))
            if choice == 0:
                return
            if 1 <= choice <= len(consumables):
                item = consumables[choice - 1]
                result = self.player.use_item(item.name)
                print(f"\n{result}")
            else:
                print("Invalid choice!")
        except ValueError:
            print("Invalid input!")
    
    def try_flee(self):
        """Attempt to flee from combat"""
        flee_chance = 0.7  # 70% chance to flee
        if random.random() < flee_chance:
            print("You successfully fled from combat!")
            self.in_combat = False
            return True
        else:
            print("You couldn't escape!")
            return False
    
    def end_combat(self):
        """Handle end of combat"""
        self.in_combat = False
        
        if not self.player.alive:
            print("\n💀 GAME OVER! You have been defeated!")
            print("Better luck next time, adventurer...")
            self.game_running = False
        elif not self.current_enemy.alive:
            xp_reward = self.current_enemy.get_xp_reward()
            gold_reward = self.current_enemy.get_gold_reward()
            
            print(f"\n🎉 Victory! You defeated the {self.current_enemy.name}!")
            print(f"You gained {xp_reward} XP and {gold_reward} gold!")
            
            self.player.gain_xp(xp_reward)
            self.player.add_gold(gold_reward)
            
            # Chance for loot
            self.give_loot()
        
        input("Press Enter to continue...")
    
    def give_loot(self):
        """Give random loot after combat"""
        loot_chance = 0.6  # 60% chance for loot
        
        if random.random() < loot_chance:
            loot_type = random.choice(['weapon', 'consumable', 'armor'])
            
            if loot_type == 'weapon':
                weapons = [
                    Weapon("Steel Sword", 20, 120, "A sharp steel blade", 100),
                    Weapon("Magic Staff", 18, 80, "A staff crackling with energy", 150, "magic"),
                    Weapon("War Hammer", 25, 150, "A heavy two-handed hammer", 120)
                ]
                loot = random.choice(weapons)
            elif loot_type == 'consumable':
                consumables = [
                    Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25),
                    Consumable("Greater Health Potion", "heal", 100, "Restores 100 HP", 50)
                ]
                loot = random.choice(consumables)
            else:  # armor
                armors = [
                    Armor("Leather Armor", 5, 100, "Basic leather protection", 50),
                    Armor("Chain Mail", 8, 150, "Interlocked metal rings", 100),
                    Armor("Plate Armor", 12, 200, "Heavy metal plates", 200)
                ]
                loot = random.choice(armors)
            
            success, message = self.player.inventory.add_item(loot)
            print(f"\n💰 Loot found: {loot.name}!")
            print(message)
    
    def show_inventory_menu(self):
        """Show inventory management menu"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(self.player.show_inventory())
            print("\nInventory Options:")
            print("1. Equip weapon")
            print("2. Equip armor")
            print("3. Use item")
            print("4. Back to main menu")
            
            choice = input("Enter your choice: ").strip()
            
            if choice == "1":
                self.equip_weapon_menu()
            elif choice == "2":
                self.equip_armor_menu()
            elif choice == "3":
                self.use_item_menu()
            elif choice == "4":
                break
            else:
                print("Invalid choice!")
                input("Press Enter to continue...")
    
    def equip_weapon_menu(self):
        """Menu for equipping weapons"""
        weapons = self.player.inventory.get_weapons()
        
        if not weapons:
            print("You have no weapons to equip!")
            input("Press Enter to continue...")
            return
        
        print("\nAvailable weapons:")
        for i, weapon in enumerate(weapons, 1):
            print(f"{i}. {weapon}")
        
        try:
            choice = int(input("Choose a weapon to equip (0 to cancel): "))
            if choice == 0:
                return
            if 1 <= choice <= len(weapons):
                weapon = weapons[choice - 1]
                result = self.player.equip_weapon(weapon.name)
                print(f"\n{result}")
            else:
                print("Invalid choice!")
        except ValueError:
            print("Invalid input!")
        
        input("Press Enter to continue...")
    
    def equip_armor_menu(self):
        """Menu for equipping armor"""
        armors = []
        for inv_item in self.player.inventory.items:
            if isinstance(inv_item['item'], Armor):
                armors.append(inv_item['item'])
        
        if not armors:
            print("You have no armor to equip!")
            input("Press Enter to continue...")
            return
        
        print("\nAvailable armor:")
        for i, armor in enumerate(armors, 1):
            print(f"{i}. {armor}")
        
        try:
            choice = int(input("Choose armor to equip (0 to cancel): "))
            if choice == 0:
                return
            if 1 <= choice <= len(armors):
                armor = armors[choice - 1]
                result = self.player.equip_armor(armor.name)
                print(f"\n{result}")
            else:
                print("Invalid choice!")
        except ValueError:
            print("Invalid input!")
        
        input("Press Enter to continue...")
    
    def use_item_menu(self):
        """Menu for using items"""
        consumables = self.player.inventory.get_consumables()
        
        if not consumables:
            print("You have no usable items!")
            input("Press Enter to continue...")
            return
        
        print("\nAvailable items:")
        for i, item in enumerate(consumables, 1):
            print(f"{i}. {item.name} - {item.description}")
        
        try:
            choice = int(input("Choose an item to use (0 to cancel): "))
            if choice == 0:
                return
            if 1 <= choice <= len(consumables):
                item = consumables[choice - 1]
                result = self.player.use_item(item.name)
                print(f"\n{result}")
            else:
                print("Invalid choice!")
        except ValueError:
            print("Invalid input!")
        
        input("Press Enter to continue...")
    
    def show_character_status(self):
        """Display detailed character status"""
        self.clear_screen()
        self.display_title()
        
        print(self.player.get_status())
        
        weapon = self.player.inventory.equipped_weapon
        if weapon:
            print(f"\nWeapon Details: {weapon}")
            print(f"Effective Damage: {weapon.get_effective_damage()}")
        
        armor = self.player.inventory.equipped_armor
        if armor:
            print(f"\nArmor Details: {armor}")
        
        input("\nPress Enter to continue...")
    
    def visit_shop(self):
        """Shop system implementation"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print("🏪 Welcome to Merchant's Emporium!")
            print(f"Your gold: {self.player.gold} 💰\n")
            
            print("What would you like to do?")
            print("1. 🗡️  Browse weapons")
            print("2. 🛡️  Browse armor")
            print("3. 🧪 Browse consumables")
            print("4. 📋 View all items")
            print("5. 💰 Sell items")
            print("6. 🚪 Leave shop")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == "1":
                self.shop_category("weapon")
            elif choice == "2":
                self.shop_category("armor")
            elif choice == "3":
                self.shop_category("consumable")
            elif choice == "4":
                self.shop_category(None)
            elif choice == "5":
                self.sell_items_menu()
            elif choice == "6":
                print("Thank you for visiting! Come back anytime!")
                input("Press Enter to continue...")
                break
            else:
                print("Invalid choice!")
                input("Press Enter to continue...")
    
    def shop_category(self, item_type):
        """Browse a specific category in the shop"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(f"🏪 Merchant's Emporium - Your gold: {self.player.gold} 💰")
            
            available_items = self.shop.display_items(item_type)
            
            if not available_items:
                input("Press Enter to go back...")
                break
            
            print(f"\n0. Go back")
            choice = input(f"\nEnter item number to buy (0 to go back): ").strip()
            
            try:
                item_choice = int(choice)
                if item_choice == 0:
                    break
                elif 1 <= item_choice <= len(available_items):
                    success, message = self.shop.buy_item(item_choice, available_items, self.player)
                    print(f"\n{message}")
                    input("Press Enter to continue...")
                    if success:
                        # Refresh the display after purchase
                        continue
                else:
                    print("Invalid item number!")
                    input("Press Enter to continue...")
            except ValueError:
                print("Please enter a valid number!")
                input("Press Enter to continue...")
    
    def sell_items_menu(self):
        """Menu for selling items to the shop"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(f"🏪 Sell Items - Your gold: {self.player.gold} 💰")
            
            sellable_items = self.shop.get_sellable_items(self.player)
            
            if not sellable_items:
                print("You have no items to sell!")
                input("Press Enter to go back...")
                break
            
            print("\nItems you can sell:")
            for i, sell_item in enumerate(sellable_items, 1):
                item = sell_item['item']
                quantity = sell_item['quantity']
                sell_price = sell_item['sell_price']
                print(f"{i}. {item.name} x{quantity} - Sell for {sell_price}💰 each")
                if item.description:
                    print(f"    {item.description}")
            
            print("0. Go back")
            choice = input("\nEnter item number to sell (0 to go back): ").strip()
            
            try:
                item_choice = int(choice)
                if item_choice == 0:
                    break
                elif 1 <= item_choice <= len(sellable_items):
                    item_to_sell = sellable_items[item_choice - 1]['item']
                    success, message = self.shop.sell_item(self.player, item_to_sell.name)
                    print(f"\n{message}")
                    input("Press Enter to continue...")
                else:
                    print("Invalid item number!")
                    input("Press Enter to continue...")
            except ValueError:
                print("Please enter a valid number!")
                input("Press Enter to continue...")
    
    def save_game(self):
        """Save game functionality"""
        print("\n💾 Save game functionality coming soon!")
        input("Press Enter to continue...")
    
    def load_game(self):
        """Load game functionality"""
        print("\n📁 Load game functionality coming soon!")
        input("Press Enter to continue...")
    
    def quit_game(self):
        """Quit the game"""
        print("\nThanks for playing! Goodbye, adventurer!")
        self.game_running = False
    
    def start_game(self):
        """Start the main game"""
        self.clear_screen()
        self.display_title()
        
        print("Welcome to Epic RPG Adventure!")
        print("Prepare yourself for an epic journey...")
        input("Press Enter to begin...")
        
        self.create_character()
        self.main_menu() 