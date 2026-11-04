"""Arrow-key navigation for screens whose choices are buttons (dialogue, menus, confirmations).

Add ``ARROW_BINDINGS`` to a screen's ``BINDINGS`` and give it an ``action_menu_move`` that calls
``cycle_focus``. Up/Left go to the previous button, Down/Right to the next, wrapping round; Enter presses
the focused button as usual. Minigame screens don't use this: they have their own controls.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button

ARROW_BINDINGS = [
    Binding("up", "menu_move(-1)", "Previous", show=False),
    Binding("left", "menu_move(-1)", "Previous", show=False),
    Binding("down", "menu_move(1)", "Next", show=False),
    Binding("right", "menu_move(1)", "Next", show=False),
]


def _shown(widget: Widget) -> bool:
    return all(node.display for node in widget.ancestors_with_self if isinstance(node, Widget))


def cycle_focus(screen: Screen, step: int) -> None:
    """Move focus ``step`` buttons along the screen's usable buttons, wrapping round."""
    buttons = [b for b in screen.query(Button) if not b.disabled and _shown(b)]
    if not buttons:
        return
    focused = screen.focused
    if focused in buttons:
        index = (buttons.index(focused) + step) % len(buttons)
    else:
        index = 0 if step > 0 else len(buttons) - 1
    buttons[index].focus()
