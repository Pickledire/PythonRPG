"""Encounter intro: a quick card for regular foes, a cinematic reveal for bosses.

Bosses with a portrait in ``rpg/ui/assets/animations/boss_<id>.json`` (see ``tools/make_boss_art.py``) show it
animating beside the story for the whole intro.
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from rpg.core.session import Encounter
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.widgets import AsciiAnimation
from rpg.ui.widgets.ascii_animation import animation_exists

# Each Titan's cracks and eyes burn in its element's colors (dark -> bright).
TITAN_GLOW = {
    "fire": ("#7A1E0E", "#C2410C", "#F97316", "#FFD08A"),
    "ice": ("#1E4A6A", "#4F9AD0", "#9EDCF2", "#E3F6FF"),
    "earth": ("#3A4A12", "#6A8A1E", "#9CC74A", "#D8F2A0"),
    "wind": ("#2E5A5A", "#5AA8A0", "#9EE0D0", "#E8FFF8"),
    "shadow": ("#2A1A3A", "#5A3A7A", "#8A6AB0", "#C9B8E8"),
    "light": ("#7A6A1E", "#D9B83A", "#F2E08A", "#FFFFF0"),
    "darkness": ("#3A0A1A", "#7A1A3A", "#B8325A", "#F27A9A"),
    "chaos": ("#5A0A5A", "#B81EB8", "#F25AF2", "#FFC2FF"),
}


def big_text(text: str, width: int = 120, font: str = "standard") -> str:
    try:
        import pyfiglet

        return pyfiglet.figlet_format(text, font=font, width=max(40, width)).rstrip()
    except Exception:  # pyfiglet is optional
        return text.upper()


def boss_portrait(encounter: Encounter) -> AsciiAnimation | None:
    enemy = encounter.enemy
    name = f"boss_{enemy.template_id}"
    if not animation_exists(name):
        return None
    recolor = None
    if enemy.template_id == "titan":
        element = (enemy.description or "").rstrip(".").split()[-1:]
        glow = TITAN_GLOW.get(element[0].lower()) if element else None
        recolor = {"glow": glow} if glow else None
    return AsciiAnimation(name, recolor=recolor, id="encounter-art")


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
                portrait = boss_portrait(self.encounter)
                with Horizontal(id="encounter-stage", classes="-with-art" if portrait else ""):
                    if portrait:
                        yield portrait
                    with Vertical(id="encounter-text"):
                        yield Static("", id="encounter-story")
                        yield Static("", id="encounter-info")
                yield Static("", id="encounter-name")
            else:
                yield Label("═══  A WILD FOE APPEARS  ═══", id="encounter-banner")
                yield Static(Text(enemy.name, style="bold"), id="encounter-name")
                yield Static("", id="encounter-info")
            with Center():
                yield Button("Fight!", variant="error", id="fight")
        yield Footer()

    def on_mount(self) -> None:
        if not self.lines:
            self._show_info()
            return
        fight = self.query_one("#fight", Button)
        fight.display = False
        fight.disabled = True  # disabled widgets can't take focus, so Enter/Space reach the screen
        self.query_one("#encounter-info", Static).display = False
        settings = getattr(self.app, "settings", None)
        if settings and settings.skip_intros:
            self._finish_reveal()
            return
        seconds = settings.intro_line_seconds if settings else 0.85
        self._timer = self.set_interval(seconds, self._reveal_line)
        self._reveal_line()

    def _reveal_line(self) -> None:
        if self._shown >= len(self.lines):
            self._finish_reveal()
            return
        self._shown += 1
        while self._shown < len(self.lines) and not self.lines[self._shown - 1].strip():
            self._shown += 1  # blank lines don't cost a beat
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
