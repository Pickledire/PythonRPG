"""RichLog that understands rule-layer ``LogEvent`` objects."""

from __future__ import annotations

from collections.abc import Iterable

from rich.text import Text
from textual.widgets import RichLog

from rpg.core.events import LogEvent
from rpg.ui.palette import event_text


class EventLog(RichLog):
    DEFAULT_CSS = """
    EventLog { background: $surface; padding: 0 1; scrollbar-size-vertical: 1; }
    """

    def __init__(self, *, id: str | None = None, classes: str | None = None, max_lines: int = 500) -> None:
        super().__init__(id=id, classes=classes, wrap=True, markup=False, highlight=False, max_lines=max_lines,
                         auto_scroll=True, min_width=20)  # wrap to the log, however narrow

    def add(self, events: LogEvent | Iterable[LogEvent]) -> None:
        if isinstance(events, LogEvent):
            events = [events]
        for event in events:
            self.write(event_text(event))

    def add_text(self, text: str | Text, style: str = "") -> None:
        self.write(Text(text, style=style) if isinstance(text, str) else text)

    def divider(self, label: str = "") -> None:
        line = f"── {label} " if label else ""
        self.write(Text(line + "─" * max(0, 40 - len(line)), style="#4A4036"))
