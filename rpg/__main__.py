"""Entry point: ``python -m rpg``."""

from rpg.ui.app import RPGApp


def main() -> None:
    RPGApp().run()


if __name__ == "__main__":
    main()
