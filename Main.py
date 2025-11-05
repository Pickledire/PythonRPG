import os
import sys
import subprocess
from pathlib import Path
import builtins

def ensure_dependencies():
    """Ensure required Python packages are installed on the user's machine.
    Tries to import modules and, if missing, installs from requirements.txt using the current interpreter.
    """
    try:
        import colorama  # noqa: F401
        import textual  # noqa: F401
        import pyfiglet  # noqa: F401
        return
    except Exception:
        pass

    # Fallback: install from requirements.txt next to this file
    req_path = Path(__file__).with_name('requirements.txt')
    if req_path.exists():
        try:
            print("\nSetting up dependencies (one-time)...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "-r", str(req_path)])
            # Ensure pyfiglet is present even if not in requirements.txt
            try:
                import pyfiglet  # noqa: F401
            except Exception:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "pyfiglet"]) 
        except Exception as e:
            print(f"Failed to auto-install dependencies: {e}")
            print("Please run: python3 -m pip install -r requirements.txt")
    else:
        # As a last resort, try installing core deps directly
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "colorama", "textual>=3.3.0", "pyfiglet"]) 
        except Exception as e:
            print(f"Failed to auto-install core packages: {e}")

def main():
    """Main function to start the RPG game"""
    try:
        original_input = builtins.input
        def _dev_input(prompt: str = ""):
            s = original_input(prompt)
            if isinstance(s, str) and s.strip() == "/exit":
                try:
                    os.system('cls' if os.name == 'nt' else 'clear')
                except Exception:
                    pass
                sys.exit(0)
            return s
        builtins.input = _dev_input

        ensure_dependencies()
        # Import after ensuring deps so optional packages are available
        from GameEngine import GameEngine
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

    


  