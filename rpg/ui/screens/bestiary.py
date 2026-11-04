"""The Bestiary: creatures you've met, by region, with what they can do and what folk say about them."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option

from rpg.core import bestiary
from rpg.ui.palette import MUTED_STYLE

HEADING = "bold #E0A458"
BODY = "#C9BFAE"


class BestiaryScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("b", "app.pop_screen", "Back", show=False)]

    def compose(self) -> ComposeResult:
        session = self.app.session
        self.groups = session.bestiary()
        self.entries = {e.template_id: e for group in self.groups.values() for e in group}
        totals = bestiary.totals(session.regions)
        yield Header(show_clock=False)
        with Vertical(id="bestiary-root"):
            yield Label(f"Bestiary · {len(self.entries)} creatures met", classes="screen-title")
            with Horizontal(id="bestiary-body"):
                options: list[Option] = []
                for group, items in self.groups.items():
                    if not items:
                        continue
                    region = session.regions.get(group)
                    title = region.name if region else bestiary.ELSEWHERE
                    count = f"  {len(items)} of {totals[group]}" if group in totals else ""
                    heading = Text(title, style="bold")
                    heading.append(count, style=MUTED_STYLE)
                    options.append(Option(heading, disabled=True))
                    for entry in items:
                        label = Text(f"  {entry.template.name}")
                        if not entry.defeated:
                            label.append("  (not yet beaten)", style=MUTED_STYLE)
                        options.append(Option(label, id=entry.template_id))
                yield OptionList(*options, id="bestiary-list")
                with VerticalScroll(id="bestiary-detail"):
                    yield Static(id="bestiary-text")
            yield Label("Up and down to browse · Esc to return", classes="muted")
        yield Footer()

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        options.focus()
        first = next((i for i in range(options.option_count) if not options.get_option_at_index(i).disabled), None)
        if first is None:
            self.query_one("#bestiary-text", Static).update(
                Text("You haven't met any creatures yet. Go hunting, and they'll be written down here.",
                     style=MUTED_STYLE))
        else:
            options.highlighted = first
            self._show(options.get_option_at_index(first).id)

    @on(OptionList.OptionHighlighted, "#bestiary-list")
    def highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id:
            self._show(event.option.id)

    def _show(self, template_id: str) -> None:
        entry = self.entries[template_id]
        self.query_one("#bestiary-text", Static).update(self.detail(entry))
        self.query_one("#bestiary-detail", VerticalScroll).scroll_home(animate=False)

    def detail(self, entry: bestiary.Entry) -> Text:
        session = self.app.session
        template = entry.template
        regions = [session.regions.get(r) for r in entry.habitats]
        text = Text(template.name, style="bold #EDE4D3")
        text.append(f"\n{template.enemy_type.title()}", style=MUTED_STYLE)
        if regions:
            text.append("  ·  lives in " + ", ".join(r.name for r in regions if r), style=MUTED_STYLE)
        text.append(f"\n\n{template.description}", style="italic " + BODY)

        # How tough it is where you'd meet it, at your level.
        here = next((r for r in regions if r and r.region_id == session.world.region), regions[0] if regions else None)
        level = max(session.player.level, here.min_level if here else template.level)
        hp, damage = bestiary.at_level(template.template_id, level)
        where = f" in {here.name}" if here else ""
        text.append(f"\n\nAt level {level}{where}: about {hp} health, hits for about {damage}.", style=BODY)

        text.append("\n\nWhat to know", style=HEADING)
        for line in bestiary.traits(template):
            text.append(f"\n  - {line}", style=BODY)

        text.append("\n\nWhat folk say", style=HEADING)
        if entry.defeated and entry.lore:
            text.append(f"\n  {entry.lore}", style=BODY)
        elif entry.defeated:
            text.append("\n  Nobody has much to say about this one.", style=MUTED_STYLE)
        else:
            text.append("\n  Defeat one to learn more.", style=MUTED_STYLE)

        times = "once" if entry.seen == 1 else f"{entry.seen} times"
        text.append(f"\n\nMet {times} · defeated {entry.defeated}", style=MUTED_STYLE)
        return text
