"""The end of a run: cut to black, THE END, then the epilogue one line at a time."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from rpg import config
from rpg.core.endings import Ending
from rpg.ui.menus import ARROW_BINDINGS, cycle_focus
from rpg.ui.palette import MUTED_STYLE

BLACK_SECONDS = 2.2  # the cut to black before anything appears
TITLE_SECONDS = 2.0
LINE_SECONDS = 1.6


class EndingScreen(Screen[None]):
    BINDINGS = ARROW_BINDINGS + [Binding("space", "skip", "Skip", show=False),
                                 Binding("enter", "skip", "Skip", show=False)]

    def action_menu_move(self, step: int) -> None:
        cycle_focus(self, step)

    def __init__(self, ending: Ending, hero: str, first_time: bool, endings_found: int, autosaved: bool) -> None:
        super().__init__()
        self.ending = ending
        self.hero = hero
        self.first_time = first_time
        self.endings_found = endings_found
        self.autosaved = autosaved
        self._shown = 0  # epilogue lines revealed so far
        self._timer = None
        self._done = False

    def compose(self) -> ComposeResult:
        with Vertical(id="ending-root"):
            yield Static(id="ending-end")
            yield Static(id="ending-title")
            yield Static(id="ending-lines")
            yield Static(id="ending-meta")
            with Center():
                with Vertical(id="ending-menu"):
                    yield Button("Load the autosave", variant="primary", id="ending-load")
                    yield Button("New character", id="ending-new")
                    yield Button("Title screen", id="ending-title-screen")

    def on_mount(self) -> None:
        self.query_one("#ending-menu").display = False
        self._timer = self.set_timer(BLACK_SECONDS, self._show_end)

    # ------------------------------------------------------------ the reveal
    def _show_end(self) -> None:
        self.query_one("#ending-end", Static).update(Text("THE END", style="bold #EDE4D3"))
        self._timer = self.set_timer(TITLE_SECONDS, self._show_title)

    def _show_title(self) -> None:
        self.query_one("#ending-title", Static).update(Text(self.ending.title, style="italic #E0A458"))
        self._timer = self.set_timer(TITLE_SECONDS, self._next_line)

    def _next_line(self) -> None:
        if self._shown >= len(self.ending.epilogue):
            self._finish()
            return
        self._shown += 1
        self._render_lines()
        self._timer = self.set_timer(LINE_SECONDS, self._next_line)

    def _render_lines(self) -> None:
        text = Text(justify="center")
        for i, line in enumerate(self.ending.epilogue[:self._shown]):
            if i:
                text.append("\n\n")
            text.append(line, style="#C9BFAE")
        self.query_one("#ending-lines", Static).update(text)

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        if self._timer is not None:
            self._timer.stop()
        found = f"Endings discovered: {self.endings_found}"
        note = "A new ending." if self.first_time else "You've found this ending before."
        self.query_one("#ending-meta", Static).update(Text(f"{note}\n{found}", style=MUTED_STYLE, justify="center"))
        load = self.query_one("#ending-load", Button)
        load.display = self.autosaved
        self.query_one("#ending-menu").display = True
        (load if self.autosaved else self.query_one("#ending-new", Button)).focus()

    def action_skip(self) -> None:
        """Show everything at once."""
        if self._done:
            return
        if self._timer is not None:
            self._timer.stop()
        self.query_one("#ending-end", Static).update(Text("THE END", style="bold #EDE4D3"))
        self.query_one("#ending-title", Static).update(Text(self.ending.title, style="italic #E0A458"))
        self._shown = len(self.ending.epilogue)
        self._render_lines()
        self._finish()

    # ------------------------------------------------------------ after
    @on(Button.Pressed, "#ending-load")
    def load(self) -> None:
        app = self.app
        try:
            session = app.saves.load(config.AUTOSAVE_SLOT)
        except Exception as exc:  # noqa: BLE001 - any failure here should just be reported
            app.notify(f"Couldn't load the autosave: {exc}", severity="error")
            return
        session.rng = app.make_rng()
        app.start_session(session)
        app.notify("Loaded the autosave.")

    @on(Button.Pressed, "#ending-new")
    def new(self) -> None:
        from rpg.ui.screens.create_character import CreateCharacterScreen

        self.app.push_screen(CreateCharacterScreen())

    @on(Button.Pressed, "#ending-title-screen")
    def title(self) -> None:
        from rpg.ui.screens.title import TitleScreen

        self.app.run_flow(self.app.reset_to(TitleScreen()))
