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
        import traceback
        print(f"\nAn error occurred: {e}")
        print("Full traceback:")
        traceback.print_exc()
        print("Please report this bug!")
        input("Press any key to continue . . .")

if __name__ == "__main__":
    main()

    


  