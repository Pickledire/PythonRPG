"""Encounter intro: a quick card for regular foes, a cinematic reveal for bosses."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from rpg.core.session import Encounter
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.widgets import VisualEffect


def big_text(text: str, width: int = 120, font: str = "standard") -> str:
    try:
        import pyfiglet

        return pyfiglet.figlet_format(text, font=font, width=max(40, width)).rstrip()
    except Exception:  # pyfiglet is optional
        return text.upper()


class EncounterScreen(Screen[None]):
    BINDINGS = [Binding("enter,space", "advance", "Continue")]
    AUTO_FOCUS = ""  # the Fight button is hidden during a boss reveal; keys go to the screen until it shows

    def __init__(self, encounter: Encounter) -> None:
        super().__init__(classes="-boss" if encounter.enemy.is_boss or encounter.has_intro else "")
        self.encounter = encounter
        enemy = encounter.enemy
        title = enemy.description.rstrip(".").lower() if enemy.description else "a fearsome creature"
        self.lines = [line.format(name=enemy.name, title=title) for line in enemy.template.intro_lines]
        self._shown = 0
        self._timer = None

    def compose(self) -> ComposeResult:
        enemy = self.encounter.enemy
        with Vertical(id="encounter-root"):
            if self.lines:
                yield Label(enemy.template.intro_title or "A FOE APPEARS", id="encounter-banner")
                yield VisualEffect(id="encounter-fx")
                yield Static("", id="encounter-story")
                yield Static("", id="encounter-name")
            else:
                yield Label("⚔  A WILD FOE APPEARS  ⚔", id="encounter-banner")
                yield Static(Text(enemy.name, style="bold"), id="encounter-name")
            yield Static("", id="encounter-info")
            with Center():
                yield Button("Fight!", variant="error", id="fight")
        yield Footer()

    def on_mount(self) -> None:
        if self.lines:
            fight = self.query_one("#fight", Button)
            fight.display = False
            fight.disabled = True  # disabled widgets can't take focus, so Enter/Space reach the screen
            self.query_one("#encounter-info", Static).display = False
            self._timer = self.set_interval(0.6, self._reveal_line)
            self.run_worker(self.query_one("#encounter-fx", VisualEffect).play("quake", 0.8))
        else:
            self._show_info()

    def _reveal_line(self) -> None:
        if self._shown >= len(self.lines):
            self._finish_reveal()
            return
        self._shown += 1
        self._render_story()

    def _render_story(self) -> None:
        text = Text()
        for i, line in enumerate(self.lines[: self._shown]):
            if i:
                text.append("\n")
            text.append(line, style="#EDE4D3")
        self.query_one("#encounter-story", Static).update(text)

    def _finish_reveal(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._shown = len(self.lines)
        self._render_story()
        name = self.query_one("#encounter-name", Static)
        name.update(Text(big_text(self.encounter.enemy.name, self.size.width - 4), style="bold #F2C46D"))
        self._show_info()

    def _show_info(self) -> None:
        enemy = self.encounter.enemy
        text = Text(justify="center")
        for i, line in enumerate(enemy.info_lines()):
            if i:
                text.append("\n")
            text.append(line, style=MUTED_STYLE if i else "")
        if self.encounter.reward_multiplier > 1:
            text.append(f"\nRisky hunt: rewards ×{self.encounter.reward_multiplier:g}", style="bold #E3B85C")
        info = self.query_one("#encounter-info", Static)
        info.update(text)
        info.display = True
        fight = self.query_one("#fight", Button)
        fight.display = True
        fight.disabled = False
        fight.focus()

    def action_advance(self) -> None:
        if self._timer is not None:
            self._finish_reveal()
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#fight")
    def fight(self) -> None:
        self.dismiss(None)
