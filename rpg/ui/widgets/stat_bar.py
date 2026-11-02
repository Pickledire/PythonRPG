"""A one-line labelled resource bar (HP, mana, XP) that is skinnable from TCSS.

Style it with component classes, e.g.::

    StatBar.-hp .statbar--fill { color: $error; }
    StatBar.-low .statbar--fill { color: red; }
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


class StatBar(Widget):
    COMPONENT_CLASSES = {"statbar--label", "statbar--fill", "statbar--empty", "statbar--value"}

    DEFAULT_CSS = """
    StatBar { height: 1; width: 1fr; }
    StatBar > .statbar--label { color: $text-muted; text-style: bold; }
    StatBar > .statbar--fill { color: $success; }
    StatBar > .statbar--empty { color: $panel-lighten-2; }
    StatBar > .statbar--value { color: $text; }
    """

    value: reactive[int] = reactive(0)
    maximum: reactive[int] = reactive(1)

    def __init__(self, label: str, *, thresholds: bool = False, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self.label = label
        self.thresholds = thresholds  # color the bar by how full it is (HP)

    def set(self, value: int, maximum: int) -> None:
        self.maximum = max(1, int(maximum))
        self.value = max(0, min(int(value), self.maximum))
        if self.thresholds:
            ratio = self.value / self.maximum
            self.set_class(ratio <= 0.3, "-low")
            self.set_class(0.3 < ratio <= 0.6, "-mid")

    def render(self) -> Text:
        label = f"{self.label:<4}"
        value_text = f" {self.value}/{self.maximum}"
        width = max(4, self.size.width - len(label) - len(value_text) - 1)
        filled = round(width * self.value / self.maximum) if self.maximum else 0
        text = Text(no_wrap=True, overflow="crop")
        text.append(label + " ", style=self.get_component_rich_style("statbar--label"))
        text.append("█" * filled, style=self.get_component_rich_style("statbar--fill"))
        text.append("░" * (width - filled), style=self.get_component_rich_style("statbar--empty"))
        text.append(value_text, style=self.get_component_rich_style("statbar--value"))
        return text
