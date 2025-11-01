import random
import os
from colorama import init, Fore, Back, Style
from Character import Character
from Enemy import Enemy, EnemyFactory, Boss
from Weapon import Weapon
from Item import Consumable, Armor
from config import RACE_STATS
from Shop import Shop
# Initialize colorama for cross-platform color support (Windows, macOS, Linux)
# autoreset=True automatically resets colors after each print statement
init(autoreset=True)

class GameEngine:
    """Main game engine that handles the game loop and combat"""
    
    def __init__(self):
        self.player = None
        self.current_enemy = None
        self.game_running = True
        self.in_combat = False
        self.shop = Shop()
        self.level_10_boss = False
        
        # Color scheme
        self.colors = {
            'title': Fore.CYAN + Style.BRIGHT,
            'header': Fore.YELLOW + Style.BRIGHT,
            'success': Fore.GREEN + Style.BRIGHT,
            'error': Fore.RED + Style.BRIGHT,
            'warning': Fore.YELLOW,
            'info': Fore.BLUE,
            'combat': Fore.MAGENTA + Style.BRIGHT,
            'gold': Fore.YELLOW + Style.BRIGHT,
            'health': Fore.RED + Style.BRIGHT,
            'mana': Fore.BLUE + Style.BRIGHT,
            'xp': Fore.GREEN,
            'weapon': Fore.CYAN,
            'armor': Fore.BLUE,
            'magic': Fore.MAGENTA + Style.BRIGHT,
            'item': Fore.MAGENTA,
            'enemy': Fore.RED,
            'player': Fore.GREEN,
            'menu': Fore.WHITE + Style.BRIGHT,
            'border': Fore.CYAN + Style.BRIGHT,
            'reset': Style.RESET_ALL
        }
    
    def clear_screen(self):
        """Clear the console screen and set fullscreen-like appearance"""
        os.system('cls' if os.name == 'nt' else 'clear')
        # Try to maximize terminal window (Windows specific) - much larger size
        if os.name == 'nt':
            os.system('mode con: cols=160 lines=50')
    
    def print_border(self, char="═", length=120, color=None):
        """Print a decorative border"""
        if color is None:
            color = self.colors['border']
        if len(char) == 1:
            print(color + char * length + self.colors['reset'])
        else:
            # For special characters like ╔, ╚, just print them once
            print(color + char + self.colors['reset'])
    
    def print_centered(self, text, width=120, color=None):
        """Print centered text"""
        if color is None:
            color = self.colors['title']
        padding = (width - len(text)) // 2
        print(color + " " * padding + text + self.colors['reset'])
    
    def display_title(self):
        """Display the game title with enhanced styling"""
        self.print_border("═", 120)
        self.print_centered("🗡️  EPIC RPG ADVENTURE  ⚔️", 120, self.colors['title'])
        self.print_border("═", 120)
        print()
    
    def display_health_bar(self, current, maximum, width=50, label="Health"):
        """Display a visual health bar"""
        if maximum == 0:
            percentage = 0
        else:
            percentage = current / maximum
        
        filled = int(width * percentage)
        empty = width - filled
        
        # Color based on health percentage
        if percentage > 0.6:
            bar_color = self.colors['success']
        elif percentage > 0.3:
            bar_color = self.colors['warning']
        else:
            bar_color = self.colors['error']
        
        bar = bar_color + "█" * filled + Fore.WHITE + "░" * empty + self.colors['reset']
        print(f"{label}: [{bar}] {current}/{maximum}")
    
    def display_xp_bar(self, current, required, width=50):
        """Display a visual XP bar"""
        if required == 0:
            percentage = 0
        else:
            percentage = current / required
        
        filled = int(width * percentage)
        empty = width - filled
        
        bar = self.colors['xp'] + "█" * filled + Fore.WHITE + "░" * empty + self.colors['reset']
        print(f"XP: [{bar}] {current}/{required}")
    
    def create_character(self):
        """Character creation process"""
        self.clear_screen()
        self.display_title()
        
        print("\n" * 2)
        self.print_centered("Welcome, brave adventurer!", 120, self.colors['header'])
        self.print_centered("Let's create your character...", 120, self.colors['info'])
        print("\n" * 3)
        
        # Get character name
        while True:
            name = input(f"{self.colors['menu']}Enter your character's name: {self.colors['reset']}").strip()
            if name:
                break
            print(f"{self.colors['error']}Please enter a valid name!{self.colors['reset']}")
        
        # Choose race
        print("\n" * 2)
        self.print_border("─", 100)
        self.print_centered("Choose your race:", 120, self.colors['header'])
        self.print_border("─", 100)
        print("\n")
        
        races = list(RACE_STATS.keys())
        for i, race in enumerate(races, 1):
            race_stats = RACE_STATS[race]
            race_color = self.colors['success'] if race == 'Human' else self.colors['info']
            race_text = f"{i}. {race} - STR:{race_stats['strength']} AGI:{race_stats['agility']} INT:{race_stats['intelligence']} HP:{race_stats['health']}"
            self.print_centered(race_text, 120, race_color)
        
        print("\n" * 2)
        while True:
            try:
                choice = int(input(f"{self.colors['menu']}Enter your choice (1-{len(races)}): {self.colors['reset']}"))
                if 1 <= choice <= len(races):
                    selected_race = races[choice - 1]
                    break
                else:
                    print(f"{self.colors['error']}Please enter a number between 1 and {len(races)}{self.colors['reset']}")
            except ValueError:
                print(f"{self.colors['error']}Please enter a valid number!{self.colors['reset']}")
        
        # Create character
        self.player = Character(name, selected_race)
        
        print("\n" * 2)
        self.print_border("═", 100)
        self.print_centered(f"🎉 Welcome, {self.player}!", 120, self.colors['success'])
        self.print_border("═", 100)
        print(self.player.get_status())
        input(f"\n{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def main_menu(self):
        """Display the main menu"""
        while self.game_running:
            self.clear_screen()
            self.display_title()
            
            if self.player:
                # Player status box - wider layout
                self.print_border("═", 100, self.colors['border'])
                print(f"{self.colors['border']}║ {self.colors['player']}Playing as: {self.player}{self.colors['reset']}")
                
                # Health bar
                print(f"{self.colors['border']}║ {self.colors['reset']}", end="")
                self.display_health_bar(self.player.health, self.player.max_health, 40, "Health")
                
                # XP bar
                print(f"{self.colors['border']}║ {self.colors['reset']}", end="")
                self.display_xp_bar(self.player.xp, self.player.xp_required(), 40)
                
                print(f"{self.colors['border']}║ {self.colors['gold']}Gold: {self.player.gold} 💰{self.colors['reset']}")
                self.print_border("═", 100, self.colors['border'])
                print("\n" * 2)
            
            # Menu options - centered layout
            self.print_border("─", 80, self.colors['header'])
            self.print_centered("What would you like to do?", 120, self.colors['header'])
            self.print_border("─", 80, self.colors['header'])
            print()
            
            menu_options = [
                ("1", "🗡️  Find an enemy to fight", self.colors['combat']),
                ("2", "📦 Check inventory", self.colors['item']),
                ("3", "📊 View character status", self.colors['info']),
                ("4", "🏪 Visit shop", self.colors['gold']),
                ("5", "💾 Save game", self.colors['warning']),
                ("6", "📁 Load game", self.colors['warning']),
                ("7", "❌ Quit game", self.colors['error'])
            ]

            # Center the menu options
            for num, text, color in menu_options:
                option_text = f"{num}. {text}"
                self.print_centered(option_text, 120, color)
            
            print("\n" * 2)
            choice = input(f"{self.colors['menu']}Enter your choice: {self.colors['reset']}").strip()
            
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
                print(f"{self.colors['error']}Invalid choice! Please try again.{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def display_boss_intro(self):
        """Display an epic boss introduction with narrative storytelling"""
        self.clear_screen()
        
        # Extra spacing for dramatic effect
        print("\n" * 2)
        
        boss_name = self.current_enemy.name
        boss_title = self.current_enemy.description if self.current_enemy.description else "a fearsome creature"
        
        # Narrative story intro
        story_lines = [
            "As you adventure around looking for enemies to slay, you find yourself entering a dark cave.",
            "The air grows cold and heavy as you venture deeper into its depths...",
            "",
            f"Walking further in, you see {boss_name}, {boss_title.lower()}.",
            "",
            "The ground shakes as it rises to stand at your arrival.",
            "You have never seen anything this massive before.",
            "",
            f"Its eyes burn with ancient power as {boss_name} turns to face you.",
            "The very walls of the cave tremble with each movement it makes.",
            "",
            "This is not just an enemy... This is a Titan."
        ]
        
        # Display the story with minimal colors (mostly white, some yellow)
        for line in story_lines:
            if line:
                self.print_centered(line, 120, Fore.WHITE)
            else:
                print()  # Empty line for spacing
        
        print("\n" * 2)
        
        # Boss name reveal with accent color
        self.print_border("═", 100, Fore.YELLOW)
        self.print_centered(f"{boss_name}", 120, Fore.RED + Style.BRIGHT)
        self.print_border("═", 100, Fore.YELLOW)
        
        print("\n" * 2)
        
        # Final warning in yellow
        self.print_centered("⚠️  Prepare yourself, adventurer... This will be your greatest challenge yet!  ⚠️", 120, Fore.YELLOW + Style.BRIGHT)
        
        print("\n" * 2)
        
        # Get ready message in white
        self.print_centered("GET READY TO FIGHT!", 120, Fore.WHITE + Style.BRIGHT)
        
        print("\n" * 2)
        input(f"{Fore.WHITE}Press Enter to begin the battle...{Style.RESET_ALL}")
    
    def start_combat(self):
        """Start a combat encounter"""
        if not self.player.alive:
            print(f"{self.colors['error']}You are dead! Game over!{self.colors['reset']}")
            input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            return
        
        # Generate random enemy based on player level
        player_level = self.player.level if self.player else 1
        self.current_enemy = EnemyFactory.create_random_enemy(player_level, self)
        self.in_combat = True
        
        # Check if boss and show epic intro
        if isinstance(self.current_enemy, Boss):
            self.display_boss_intro()
        else:
            print()
            self.print_border("⚔", 60, self.colors['combat'])
            print(f"{self.colors['combat']}⚔️ A wild {self.colors['enemy']}{self.current_enemy.name}{self.colors['combat']} appears!{self.colors['reset']}")
            self.print_border("⚔", 60, self.colors['combat'])
            print(self.current_enemy.get_info())
            input(f"{self.colors['menu']}Press Enter to start combat...{self.colors['reset']}")
        
        self.combat_loop()
    
    def combat_loop(self):
        """Main combat loop"""
        while self.in_combat and self.player.alive and self.current_enemy.alive:
            self.clear_screen()
            self.display_title()
            
            # Show combat status
            self.print_border("═", 120, self.colors['combat'])
            self.print_centered("⚔️ COMBAT ⚔️", 120, self.colors['combat'])
            self.print_border("═", 120, self.colors['combat'])
            print("\n" * 2)
            
            # Create a side-by-side layout for player and enemy
            # Player status (left side)
            print(f"{self.colors['player']}🛡️ {self.player.name} (Level {self.player.level}){self.colors['reset']}")
            self.display_health_bar(self.player.health, self.player.max_health, 60, "Player Health")
            
            print("\n" * 2)
            
            # Enemy status (right side)
            print(f"{self.colors['enemy']}👹 {self.current_enemy.name}{self.colors['reset']}")
            self.display_health_bar(self.current_enemy.health, self.current_enemy.max_health, 60, "Enemy Health")
            
            print("\n" * 2)
            self.print_border("─", 100, self.colors['combat'])
            print()
            
            # Player turn
            self.player_turn()
            
            # Check if player fled or enemy died
            if not self.in_combat or not self.current_enemy.alive:
                break
            
            # Enemy turn
            if self.current_enemy.alive:
                self.enemy_turn()
            
            if not self.player.alive:
                break
            
            input(f"\n{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
        
        # Combat ended
        self.end_combat()
    
    def player_turn(self):
        """Handle player's turn in combat"""
        print(f"{self.colors['header']}Your turn! Choose an action:{self.colors['reset']}")
        
        combat_options = [
            ("1", "⚔️ Attack", self.colors['combat']),
            ("2", "🧪 Use item", self.colors['item']),
            ("3", "🏃 Try to flee", self.colors['warning']),
            ("4", "🔮 Cast magic", self.colors['magic'])
        ]
        
        for num, text, color in combat_options:
            print(f"{self.colors['menu']}{num}. {color}{text}{self.colors['reset']}")
        
        choice = input(f"\n{self.colors['menu']}Enter your choice: {self.colors['reset']}").strip()
        
        if choice == "1":
            result = self.player.attack(self.current_enemy)
            print(f"\n{self.colors['combat']}{result}{self.colors['reset']}")
        elif choice == "2":
            self.use_item_in_combat()
        elif choice == "3":
            if self.try_flee():
                return
        elif choice == "4":
            result = self.player.cast_magic(self.current_enemy)
            print(f"\n{self.colors['magic']}{result}{self.colors['reset']}")
        else:
            print(f"{self.colors['error']}Invalid choice! You lose your turn.{self.colors['reset']}")
    
    def enemy_turn(self):
        """Handle enemy's turn in combat"""
        print(f"\n{self.colors['enemy']}{self.current_enemy.name}'s turn!{self.colors['reset']}")
        result = self.current_enemy.attack(self.player)
        print(f"{self.colors['enemy']}{result}{self.colors['reset']}")
    
    def use_item_in_combat(self):
        """Use an item during combat"""
        consumables = self.player.inventory.get_consumables()
        
        if not consumables:
            print(f"{self.colors['warning']}You have no usable items!{self.colors['reset']}")
            return
        
        print(f"\n{self.colors['header']}Available items:{self.colors['reset']}")
        self.print_border("─", 40, self.colors['item'])
        
        for i, item in enumerate(consumables, 1):
            print(f"{self.colors['menu']}{i}. {self.colors['item']}{item.name}{self.colors['reset']}")
        
        try:
            choice = int(input(f"\n{self.colors['menu']}Choose an item (0 to cancel): {self.colors['reset']}"))
            if choice == 0:
                return
            if 1 <= choice <= len(consumables):
                item = consumables[choice - 1]
                result = self.player.use_item(item.name)
                print(f"\n{self.colors['success']}{result}{self.colors['reset']}")
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
        except ValueError:
            print(f"{self.colors['error']}Invalid input!{self.colors['reset']}")
    
    def try_flee(self):
        """Attempt to flee from combat"""
        flee_chance = 0.7  # 70% chance to flee
        if random.random() < flee_chance:
            print(f"{self.colors['success']}You successfully fled from combat!{self.colors['reset']}")
            self.in_combat = False
            return True
        else:
            print(f"{self.colors['error']}You couldn't escape!{self.colors['reset']}")
            return False
    
    def end_combat(self):
        """Handle end of combat"""
        self.in_combat = False
        
        if not self.player.alive:
            print()
            self.print_border("☠", 60, self.colors['error'])
            print(f"{self.colors['error']}💀 GAME OVER! You have been defeated!{self.colors['reset']}")
            print(f"{self.colors['warning']}Better luck next time, adventurer...{self.colors['reset']}")
            self.print_border("☠", 60, self.colors['error'])
            self.game_running = False
        elif not self.current_enemy.alive:
            xp_reward = self.current_enemy.get_xp_reward()
            gold_reward = self.current_enemy.get_gold_reward()
            
            print()
            self.print_border("═", 60, self.colors['success'])
            print(f"{self.colors['success']}Victory! You defeated the {self.current_enemy.name}!{self.colors['reset']}")
            print(f"{self.colors['xp']}You gained {xp_reward} XP{self.colors['reset']} and {self.colors['gold']}{gold_reward} gold!{self.colors['reset']}")
            self.print_border("═", 60, self.colors['success'])
            
            self.player.gain_xp(xp_reward)
            self.player.add_gold(gold_reward)
            
            # Chance for loot
            self.give_loot()

            # Special boss reward at level 10
            if isinstance(self.current_enemy, Boss):
                self.grant_boss_reward()
        
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")

    def grant_boss_reward(self):
        """Offer the player a choice of one of three Titan rewards after defeating the boss."""
        print("\n")
        self.print_border("═", 100, self.colors['gold'])
        self.print_centered("Choose your Titan Reward", 120, self.colors['gold'])
        self.print_border("═", 100, self.colors['gold'])
        print()

        # Define rewards
        titan_hammer = Weapon("Titan Hammer", 40, 200, "A colossal hammer forged with Titan power", 0, "melee")
        titan_dagger = Weapon("Titan Claw Dagger", 28, 160, "A razor-fast dagger carved from Titan claws", 0, "melee")
        titans_curse = Magic("Titan's Curse", "An ancient curse that devastates foes", 45, 35, 0)

        # Show lightweight requirement hints
        req_h_name, req_h_val = titan_hammer.get_requirement()
        req_d_name, req_d_val = titan_dagger.get_requirement()
        req_c_name, req_c_val = titans_curse.get_requirement()

        options = [
            ("1", f"{self.colors['weapon']}Titan Hammer{self.colors['reset']} - requires {req_h_name.capitalize()} {req_h_val}+"),
            ("2", f"{self.colors['weapon']}Titan Claw Dagger{self.colors['reset']} - requires {req_d_name.capitalize()} {req_d_val}+"),
            ("3", f"{self.colors['magic']}Titan's Curse{self.colors['reset']} - requires {req_c_name.capitalize()} {req_c_val}+"),
        ]

        for num, text in options:
            self.print_centered(f"{num}. {text}", 120, self.colors['menu'])

        print()
        while True:
            choice = input(f"{self.colors['menu']}Enter your choice (1-3): {self.colors['reset']}").strip()
            if choice == "1":
                self.player.inventory.add_item(titan_hammer)
                print(f"\n{self.colors['success']}You received the Titan Hammer!{self.colors['reset']}")
                break
            elif choice == "2":
                self.player.inventory.add_item(titan_dagger)
                print(f"\n{self.colors['success']}You received the Titan Claw Dagger!{self.colors['reset']}")
                break
            elif choice == "3":
                self.player.inventory.add_item(titans_curse)
                print(f"\n{self.colors['success']}You received Titan's Curse!{self.colors['reset']}")
                break
            else:
                print(f"{self.colors['error']}Invalid choice, please enter 1, 2, or 3.{self.colors['reset']}")
    
    def give_loot(self):
        """Give random loot after combat"""
        loot_chance = 0.5  # 50% chance for loot

        if isinstance(self.current_enemy, Boss):
            loot_chance = 1.0 # Bosses always drop loot
            print(f"{self.colors['info']}The {self.current_enemy.name} drops a powerful item!{self.colors['reset']}")
            
        
        if random.random() < loot_chance:
            loot_type = random.choice(['weapon', 'consumable', 'armor'])
            
            if loot_type == 'weapon':
                weapons = [
                    Weapon("Steel Sword", 20, 120, "A sharp steel blade", 100),
                    Weapon("Magic Staff", 18, 80, "A staff crackling with energy", 150, "magic"),
                    Weapon("War Hammer", 25, 150, "A heavy two-handed hammer", 120)
                ]
                loot = random.choice(weapons)
                loot_color = self.colors['weapon']
            elif loot_type == 'consumable':
                consumables = [
                    Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25),
                    Consumable("Greater Health Potion", "heal", 100, "Restores 100 HP", 50)
                ]
                loot = random.choice(consumables)
                loot_color = self.colors['item']
            else:  # armor
                armors = [
                    Armor("Leather Armor", 5, 100, "Basic leather protection", 50),
                    Armor("Chain Mail", 8, 150, "Interlocked metal rings", 100),
                    Armor("Plate Armor", 12, 200, "Heavy metal plates", 200),
                    Armor("Cracked Iron Armor", 3, 30, "Medium half broken plate", 25)
                ]
                loot = random.choice(armors)
                loot_color = self.colors['armor']
            
            success, message = self.player.inventory.add_item(loot)
            print(f"\n{self.colors['gold']}💰 Loot found: {loot_color}{loot.name}{self.colors['reset']}!")
            print(f"{self.colors['info']}{message}{self.colors['reset']}")
            # Show item stats and requirements
            if hasattr(loot, 'damage'):
                # Weapon
                req_txt = ""
                if hasattr(loot, 'get_requirement'):
                    stat, val = loot.get_requirement()
                    req_txt = f" | Req: {stat.capitalize()} {val}+"
                print(f"{self.colors['weapon']}Stats: Damage {loot.damage}, Durability {loot.max_durability}{req_txt}{self.colors['reset']}")
            elif hasattr(loot, 'defense'):
                # Armor
                req_txt = ""
                if hasattr(loot, 'get_requirement'):
                    stat, val = loot.get_requirement()
                    req_txt = f" | Req: {stat.capitalize()} {val}+"
                print(f"{self.colors['armor']}Stats: Defense {loot.defense}, Durability {loot.max_durability}{req_txt}{self.colors['reset']}")
    
    def show_inventory_menu(self):
        """Show inventory management menu"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(self.player.show_inventory())
            print()
            
            self.print_border("─", 50, self.colors['header'])
            print(f"{self.colors['header']}Inventory Options:{self.colors['reset']}")
            self.print_border("─", 50, self.colors['header'])
            
            inventory_options = [
                ("1", "⚔️ Equip weapon", self.colors['weapon']),
                ("2", "🛡️ Equip armor", self.colors['armor']),
                ("3", "🔮 Equip magic", self.colors['magic']),
                ("4", "🧪 Use item", self.colors['item']),
                ("5", "🔙 Back to main menu", self.colors['warning'])
            ]
            
            for num, text, color in inventory_options:
                print(f"{self.colors['menu']}{num}. {color}{text}{self.colors['reset']}")
            
            choice = input(f"\n{self.colors['menu']}Enter your choice: {self.colors['reset']}").strip()
            
            if choice == "1":
                self.equip_weapon_menu()
            elif choice == "2":
                self.equip_armor_menu()
            elif choice == "3":
                self.equip_magic_menu()
            elif choice == "4":
                self.use_item_menu()
            elif choice == "5":
                break
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def equip_weapon_menu(self):
        """Menu for equipping weapons"""
        weapons = self.player.inventory.get_weapons()
        
        if not weapons:
            print(f"{self.colors['warning']}You have no weapons to equip!{self.colors['reset']}")
            input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            return
        
        print(f"\n{self.colors['header']}Available weapons:{self.colors['reset']}")
        self.print_border("─", 60, self.colors['weapon'])
        
        for i, weapon in enumerate(weapons, 1):
            print(f"{self.colors['menu']}{i}. {self.colors['weapon']}{weapon}{self.colors['reset']}")
        
        try:
            choice = int(input(f"\n{self.colors['menu']}Choose a weapon to equip (0 to cancel): {self.colors['reset']}"))
            if choice == 0:
                return
            if 1 <= choice <= len(weapons):
                weapon = weapons[choice - 1]
                result = self.player.equip_weapon(weapon.name)
                print(f"\n{self.colors['success']}{result}{self.colors['reset']}")
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
        except ValueError:
            print(f"{self.colors['error']}Invalid input!{self.colors['reset']}")
        
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def equip_armor_menu(self):
        """Menu for equipping armor"""
        armors = []
        for inv_item in self.player.inventory.items:
            if isinstance(inv_item['item'], Armor):
                armors.append(inv_item['item'])
        
        if not armors:
            print(f"{self.colors['warning']}You have no armor to equip!{self.colors['reset']}")
            input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            return
        
        print(f"\n{self.colors['header']}Available armor:{self.colors['reset']}")
        self.print_border("─", 60, self.colors['armor'])
        
        for i, armor in enumerate(armors, 1):
            print(f"{self.colors['menu']}{i}. {self.colors['armor']}{armor}{self.colors['reset']}")
        
        try:
            choice = int(input(f"\n{self.colors['menu']}Choose armor to equip (0 to cancel): {self.colors['reset']}"))
            if choice == 0:
                return
            if 1 <= choice <= len(armors):
                armor = armors[choice - 1]
                result = self.player.equip_armor(armor.name)
                print(f"\n{self.colors['success']}{result}{self.colors['reset']}")
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
        except ValueError:
            print(f"{self.colors['error']}Invalid input!{self.colors['reset']}")
        
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def equip_magic_menu(self):
        """Menu for equipping magic"""
        magic_items = self.player.inventory.get_magic()
        
        if not magic_items:
            print(f"{self.colors['warning']}You have no magic to equip!{self.colors['reset']}")
            input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            return
        
        print(f"\n{self.colors['header']}Available magic:{self.colors['reset']}")
        self.print_border("─", 60, self.colors['magic'])
        
        for i, magic in enumerate(magic_items, 1):
            print(f"{self.colors['menu']}{i}. {self.colors['magic']}{magic}{self.colors['reset']}")
        
        try:
            choice = int(input(f"\n{self.colors['menu']}Choose magic to equip (0 to cancel): {self.colors['reset']}"))
            if choice == 0:
                return
            if 1 <= choice <= len(magic_items):
                magic = magic_items[choice - 1]
                result = self.player.inventory.equip_magic(magic.name)
                if result[0]:
                    print(f"\n{self.colors['success']}{result[1]}{self.colors['reset']}")
                else:
                    print(f"\n{self.colors['error']}{result[1]}{self.colors['reset']}")
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
        except ValueError:
            print(f"{self.colors['error']}Invalid input!{self.colors['reset']}")
        
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def use_item_menu(self):
        """Menu for using items"""
        consumables = self.player.inventory.get_consumables()
        
        if not consumables:
            print(f"{self.colors['warning']}You have no usable items!{self.colors['reset']}")
            input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            return
        
        print(f"\n{self.colors['header']}Available items:{self.colors['reset']}")
        self.print_border("─", 60, self.colors['item'])
        
        for i, item in enumerate(consumables, 1):
            print(f"{self.colors['menu']}{i}. {self.colors['item']}{item.name}{self.colors['reset']} - {self.colors['info']}{item.description}{self.colors['reset']}")
        
        try:
            choice = int(input(f"\n{self.colors['menu']}Choose an item to use (0 to cancel): {self.colors['reset']}"))
            if choice == 0:
                return
            if 1 <= choice <= len(consumables):
                item = consumables[choice - 1]
                result = self.player.use_item(item.name)
                print(f"\n{self.colors['success']}{result}{self.colors['reset']}")
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
        except ValueError:
            print(f"{self.colors['error']}Invalid input!{self.colors['reset']}")
        
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def show_character_status(self):
        """Display detailed character status"""
        self.clear_screen()
        self.display_title()
        
        print(self.player.get_status())
        
        weapon = self.player.inventory.equipped_weapon
        if weapon:
            print(f"\n{self.colors['weapon']}Weapon Details: {weapon}{self.colors['reset']}")
            print(f"{self.colors['info']}Effective Damage: {weapon.get_effective_damage()}{self.colors['reset']}")
        
        armor = self.player.inventory.equipped_armor
        if armor:
            print(f"\n{self.colors['armor']}Armor Details: {armor}{self.colors['reset']}")
        
        input(f"\n{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def visit_shop(self):
        """Shop system implementation"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(f"{self.colors['gold']}🏪 Welcome to Merchant's Emporium!{self.colors['reset']}")
            print(f"{self.colors['gold']}Your gold: {self.player.gold} 💰{self.colors['reset']}")
            print()
            
            self.print_border("─", 50, self.colors['header'])
            print(f"{self.colors['header']}What would you like to do?{self.colors['reset']}")
            self.print_border("─", 50, self.colors['header'])
            
            shop_options = [
                ("1", "🗡️  Browse weapons", self.colors['weapon']),
                ("2", "🛡️  Browse armor", self.colors['armor']),
                ("3", "🔮 Browse magic", self.colors['magic']),
                ("4", "🧪 Browse consumables", self.colors['item']),
                ("5", "📋 View all items", self.colors['info']),
                ("6", "💰 Sell items", self.colors['warning']),
                ("7", "🚪 Leave shop", self.colors['error'])
            ]
            
            for num, text, color in shop_options:
                print(f"{self.colors['menu']}{num}. {color}{text}{self.colors['reset']}")
            
            choice = input(f"\n{self.colors['menu']}Enter your choice: {self.colors['reset']}").strip()
            
            if choice == "1":
                self.shop_category("weapon")
            elif choice == "2":
                self.shop_category("armor")
            elif choice == "3":
                self.shop_category("magic")
            elif choice == "4":
                self.shop_category("consumable")
            elif choice == "5":
                self.shop_category(None)
            elif choice == "6":
                self.sell_items_menu()
            elif choice == "7":
                print(f"{self.colors['success']}Thank you for visiting! Come back anytime!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
                break
            else:
                print(f"{self.colors['error']}Invalid choice!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def shop_category(self, item_type):
        """Browse a specific category in the shop"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(f"{self.colors['gold']}🏪 Merchant's Emporium - Your gold: {self.player.gold} 💰{self.colors['reset']}")
            print()
            
            available_items = self.shop.display_items(item_type)
            
            if not available_items:
                print(f"{self.colors['warning']}No items available in this category!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to go back...{self.colors['reset']}")
                break
            
            print(f"\n{self.colors['menu']}0. {self.colors['warning']}Go back{self.colors['reset']}")
            choice = input(f"\n{self.colors['menu']}Enter item number to buy (0 to go back): {self.colors['reset']}").strip()
            
            try:
                item_choice = int(choice)
                if item_choice == 0:
                    break
                elif 1 <= item_choice <= len(available_items):
                    success, message = self.shop.buy_item(item_choice, available_items, self.player)
                    if success:
                        print(f"\n{self.colors['success']}{message}{self.colors['reset']}")
                    else:
                        print(f"\n{self.colors['error']}{message}{self.colors['reset']}")
                    input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
                    if success:
                        # Refresh the display after purchase
                        continue
                else:
                    print(f"{self.colors['error']}Invalid item number!{self.colors['reset']}")
                    input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            except ValueError:
                print(f"{self.colors['error']}Please enter a valid number!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def sell_items_menu(self):
        """Menu for selling items to the shop"""
        while True:
            self.clear_screen()
            self.display_title()
            
            print(f"{self.colors['gold']}🏪 Sell Items - Your gold: {self.player.gold} 💰{self.colors['reset']}")
            print()
            
            sellable_items = self.shop.get_sellable_items(self.player)
            
            if not sellable_items:
                print(f"{self.colors['warning']}You have no items to sell!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to go back...{self.colors['reset']}")
                break
            
            print(f"{self.colors['header']}Items you can sell:{self.colors['reset']}")
            self.print_border("─", 60, self.colors['header'])
            
            for i, sell_item in enumerate(sellable_items, 1):
                item = sell_item['item']
                quantity = sell_item['quantity']
                sell_price = sell_item['sell_price']
                
                # Color code by item type
                if hasattr(item, 'damage'):  # Weapon
                    item_color = self.colors['weapon']
                elif hasattr(item, 'defense'):  # Armor
                    item_color = self.colors['armor']
                else:  # Consumable
                    item_color = self.colors['item']
                
                print(f"{self.colors['menu']}{i}. {item_color}{item.name}{self.colors['reset']} x{quantity} - "
                      f"{self.colors['gold']}Sell for {sell_price}💰 each{self.colors['reset']}")
                if item.description:
                    print(f"    {self.colors['info']}{item.description}{self.colors['reset']}")
            
            print(f"\n{self.colors['menu']}0. {self.colors['warning']}Go back{self.colors['reset']}")
            choice = input(f"\n{self.colors['menu']}Enter item number to sell (0 to go back): {self.colors['reset']}").strip()
            
            try:
                item_choice = int(choice)
                if item_choice == 0:
                    break
                elif 1 <= item_choice <= len(sellable_items):
                    item_to_sell = sellable_items[item_choice - 1]['item']
                    success, message = self.shop.sell_item(self.player, item_to_sell.name)
                    if success:
                        print(f"\n{self.colors['success']}{message}{self.colors['reset']}")
                    else:
                        print(f"\n{self.colors['error']}{message}{self.colors['reset']}")
                    input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
                else:
                    print(f"{self.colors['error']}Invalid item number!{self.colors['reset']}")
                    input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
            except ValueError:
                print(f"{self.colors['error']}Please enter a valid number!{self.colors['reset']}")
                input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def save_game(self):
        """Save game functionality"""
        print(f"\n{self.colors['warning']}💾 Save game functionality coming soon!{self.colors['reset']}")
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def load_game(self):
        """Load game functionality"""
        print(f"\n{self.colors['warning']}📁 Load game functionality coming soon!{self.colors['reset']}")
        input(f"{self.colors['menu']}Press Enter to continue...{self.colors['reset']}")
    
    def quit_game(self):
        """Quit the game"""
        print()
        self.print_border("═", 60, self.colors['header'])
        print(f"{self.colors['success']}Thanks for playing! Goodbye, adventurer!{self.colors['reset']}")
        self.print_border("═", 60, self.colors['header'])
        self.game_running = False
    
    def start_game(self):
        """Start the main game"""
        self.display_startup_screen()
        self.create_character()
        self.main_menu()

    def display_startup_screen(self):
        """Display an enhanced startup screen"""
        self.clear_screen()
        
        
        print("\n" * 5)
                # ASCII art title
        title_art = [
            "███████╗██████╗ ██╗ ██████╗    ██████╗ ██████╗  ██████╗ ",
            "██╔════╝██╔══██╗██║██╔════╝    ██╔══██╗██╔══██╗██╔════╝ ",
            "█████╗  ██████╔╝██║██║         ██████╔╝██████╔╝██║  ███╗",
            "██╔══╝  ██╔═══╝ ██║██║         ██╔══██╗██╔═══╝ ██║   ██║",
            "███████╗██║     ██║╚██████╗    ██║  ██║██║     ╚██████╔╝",
            "╚══════╝╚═╝     ╚═╝ ╚═════╝    ╚═╝  ╚═╝╚═╝      ╚═════╝ "
        ]
        
        print()
        for line in title_art:
            self.print_centered(line, 120, self.colors['title'])
        
        print("\n" * 2)
        self.print_border("═", 120)
        self.print_centered("⚔️  A D V E N T U R E  A W A I T S  ⚔️", 120, self.colors['header'])
        self.print_border("═", 120)
        print("\n" * 2)
        
        # Create a welcome box
        welcome_text = [
            "Welcome to Epic RPG Adventure!",
            "Prepare yourself for an epic journey filled with danger and glory...",
            "Choose your race, equip powerful weapons, and battle fearsome enemies!",
            "Explore shops, manage your inventory, and become a legendary hero!"
        ]
        
        for text in welcome_text:
            self.print_centered(text, 120, self.colors['info'])
        
        print("\n" * 3)
        self.print_centered("Press Enter to begin your adventure...", 120, self.colors['menu'])
        input() 