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

 



  