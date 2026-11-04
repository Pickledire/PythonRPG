"""Travel: pick a region, then walk (next door only) or take a carriage (anywhere, for a fare)."""

from __future__ import annotations

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from rpg.core.travel import TravelMode, TravelOption
from rpg.ui.palette import GOLD_STYLE, MUTED_STYLE
from rpg.ui.screens.modals import Choice, ChoiceModal

DANGER_STYLE = "#E8604F"


def option_text(option: TravelOption, player_level: int, gold: int) -> Text:
    region = option.region
    text = Text(region.name, style="bold")
    text.append("   next door" if option.walkable else f"   {option.roads} roads away", style=MUTED_STYLE)
    danger = region.min_level > player_level + 2
    text.append(f"\n  Creatures from level {region.min_level}", style=DANGER_STYLE if danger else MUTED_STYLE)
    if danger:
        text.append("  (dangerous for you)", style=DANGER_STYLE)
    text.append("\n  ")
    if option.walkable:
        text.append(f"On foot: {option.walk_hours} hours, the road can be risky", style="#C9BFAE")
        text.append("  ·  ", style=MUTED_STYLE)
    else:
        text.append("Too far to walk  ·  ", style=MUTED_STYLE)
    text.append(f"Carriage: {option.fare} gold, {option.carriage_hours} hours",
                style=GOLD_STYLE if gold >= option.fare else MUTED_STYLE)
    text.append("\n")  # a blank line between destinations
    return text


class TravelScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("t", "app.pop_screen", "Back", show=False)]

    def compose(self) -> ComposeResult:
        session = self.app.session
        yield Header(show_clock=False)
        with Vertical(id="travel-root"):
            yield Label(f"Travel from {session.place}", classes="screen-title")
            yield Label(f"You have {session.player.gold} gold. On foot you can reach the regions next door; "
                        "a carriage goes anywhere and is far safer.", classes="muted")
            player = session.player
            yield OptionList(*[Option(option_text(o, player.level, player.gold), id=o.region.region_id)
                               for o in session.travel_options()], id="travel-list")
            yield Label("Enter to choose a destination · Esc to stay", classes="muted")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    @on(OptionList.OptionSelected, "#travel-list")
    def picked(self, event: OptionList.OptionSelected) -> None:
        self._choose_mode(event.option_id)

    @work
    async def _choose_mode(self, region_id: str) -> None:
        app = self.app
        session = app.session
        option = next(o for o in session.travel_options() if o.region.region_id == region_id)
        choices = []
        if option.walkable:
            choices.append(Choice(f"Walk ({option.walk_hours} hours). The road can be dangerous.", TravelMode.WALK))
        affordable = session.player.gold >= option.fare
        carriage = f"Take the carriage: {option.fare} gold ({option.carriage_hours} hours). Almost always safe."
        if not affordable:
            carriage += f"  [You have {session.player.gold} gold]"
        choices.append(Choice(carriage, TravelMode.CARRIAGE, enabled=affordable))
        mode = await app.push_screen_wait(ChoiceModal(f"Travel to {option.region.name}", choices,
                                                      prompt=option.region.blurb))
        if mode is None:
            return
        self.dismiss(None)
        app.run_flow(app.travel_flow(region_id, mode))
