"""Quest board: pick a destination and start its dialogue."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from rpg.ui.palette import MUTED_STYLE


class QuestBoardScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="quest-root"):
            yield Label("Where will you seek adventure?", classes="screen-title")
            options = []
            for quest in self.app.session.board():
                prompt = Text(quest.title, style="bold")  # theme colour: stays readable when highlighted
                prompt.append(f"\n  {quest.blurb}", style=MUTED_STYLE)
                options.append(Option(prompt, id=quest.key))
            yield OptionList(*options, id="quest-list")
            yield Label("Enter to embark · Esc to return to camp", classes="muted")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    @on(OptionList.OptionSelected, "#quest-list")
    def embark(self, event: OptionList.OptionSelected) -> None:
        from rpg.ui.screens.dialogue import DialogueScreen

        session = self.app.session
        quest = next(q for q in session.board() if q.key == event.option_id)
        self.app.push_screen(DialogueScreen(session.dialogue(session.quest_start(quest)), title=quest.title))
