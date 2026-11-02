"""Epic RPG Adventure — a turn-based fantasy RPG for the terminal, built on Textual.

Package layout:
    rpg.core      Pure game rules (no UI imports). Unit-testable on its own.
    rpg.services  Infrastructure such as save/load persistence.
    rpg.ui        The Textual application: screens, widgets and styles.
"""

__version__ = "2.0.0"
