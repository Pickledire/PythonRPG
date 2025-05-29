#!/usr/bin/env python3
"""
Epic RPG Adventure - Main Entry Point

An improved turn-based RPG game with:
- Character creation with multiple races
- Inventory management system
- Turn-based combat with strategy
- Equipment system (weapons and armor)
- Leveling and progression
- Random loot and enemies

Author: Enhanced by AI Assistant
"""

from GameEngine import GameEngine

def main():
    """Main function to start the RPG game"""
    try:
        # Create and start the game engine
        game = GameEngine()
        game.start_game()
        
    except KeyboardInterrupt:
        print("\n\nGame interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please report this bug!")

if __name__ == "__main__":
    main()

 



  