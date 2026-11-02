"""Character creation: name and race."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from rpg import config
from rpg.core.catalog import ITEMS
from rpg.core.session import GameSession
from rpg.ui.palette import MUTED_STYLE

RACE_STYLES = {"Human": "bold #EDE4D3", "Elf": "bold #86B57F", "Orc": "bold #D9574B", "Dwarf": "bold #F2C46D"}


class CreateCharacterScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="create-root"):
            yield Label("Welcome, brave adventurer! Let's create your character.", classes="screen-title")
            yield Label("Name", classes="field-label")
            yield Input(placeholder="Enter your character's name", max_length=20, id="name")
            yield Label("Race", classes="field-label")
            with Horizontal(id="race-row"):
                yield OptionList(*[Option(Text(race, style=RACE_STYLES.get(race, "bold")), id=race)
                                   for race in config.RACES], id="race-list")
                yield Static(id="race-preview")
            yield Label("", id="create-error")
            with Horizontal(classes="button-row"):
                yield Button("Begin Adventure", variant="primary", id="begin")
                yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#race-list", OptionList).highlighted = 0
        self.query_one("#name", Input).focus()
        self._show_race(next(iter(config.RACES)))

    @on(OptionList.OptionHighlighted, "#race-list")
    def race_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self._show_race(event.option_id)

    @on(OptionList.OptionSelected, "#race-list")
    def race_selected(self) -> None:
        self.query_one("#begin", Button).focus()

    def _show_race(self, race: str | None) -> None:
        if not race:
            return
        data = config.RACES[race]
        text = Text()
        text.append(f"{race}\n", style=RACE_STYLES.get(race, "bold"))
        text.append(f"{data['blurb']}\n\n", style="italic")
        for label, key in (("Health", "health"), ("Strength", "strength"), ("Agility", "agility"),
                           ("Intelligence", "intelligence")):
            value = data[key]
            scale = 150 if key == "health" else 16
            bar = "█" * round(12 * value / scale)
            text.append(f"{label:<13}", style=MUTED_STYLE)
            text.append(f"{value:>4} ", style="bold")
            text.append(f"{bar}\n", style="#E0A458")
        text.append("\nStarting kit\n", style="bold")
        for template_id in data["starting_items"]:
            item = ITEMS.create(template_id)
            text.append(f"  • {item.name}", style="")
            text.append(f"  {item.summary()}\n", style=MUTED_STYLE)
        for template_id, qty in config.STARTING_CONSUMABLES.items():
            text.append(f"  • {ITEMS.create(template_id).name} ×{qty}\n")
        text.append(f"  • {config.STARTING_GOLD} gold\n")
        self.query_one("#race-preview", Static).update(text)

    @on(Input.Submitted, "#name")
    def name_submitted(self) -> None:
        self.query_one("#race-list", OptionList).focus()

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#begin")
    def begin(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        options = self.query_one("#race-list", OptionList)
        error = self.query_one("#create-error", Label)
        if not name:
            error.update("Please enter a name for your hero.")
            self.query_one("#name", Input).focus()
            return
        if options.highlighted is None:
            error.update("Choose a race.")
            return
        race = options.get_option_at_index(options.highlighted).id
        session = GameSession.new_game(name, race, rng=self.app.make_rng())
        self.app.start_session(session, welcome=True)
