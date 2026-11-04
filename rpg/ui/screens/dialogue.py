"""Dialogue scenes for quests and campfire encounters."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from rpg.core.combat import Phase
from rpg.core.dialogue import (
    DialogueRunner,
    EndGameRequest,
    MinigameRequest,
    OpenShopRequest,
    StartCombatRequest,
    StepResult,
    VisualRequest,
)
from rpg.core.session import Encounter
from rpg.ui.menus import ARROW_BINDINGS, cycle_focus
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.modals import ConfirmModal
from rpg.ui.widgets import EventLog, VisualEffect

CONTINUE = -1
LEAVE = -2
END = -3


class DialogueScreen(Screen[None]):
    BINDINGS = ARROW_BINDINGS + [Binding(str(n), f"choose({n - 1})", show=False) for n in range(1, 10)] + [
        Binding("escape", "abandon", "Walk away"),
    ]

    def action_menu_move(self, step: int) -> None:
        cycle_focus(self, step)

    def __init__(self, runner: DialogueRunner, title: str = "") -> None:
        super().__init__()
        self.runner = runner
        self.scene_title = title
        self._busy = True
        self._ending: str | None = None  # set when a scene ends the game; the next button rolls the ending
        # The game as it was when this conversation began: an ending autosaves this, so a surprise
        # ending (the house in Emberwick) costs a reload, not the run.
        self.checkpoint = runner.ctx.snapshot() if hasattr(runner.ctx, "snapshot") else None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="dialogue-root"):
            yield Label(self.scene_title, id="dialogue-scene", classes="muted")
            yield Label("", id="dialogue-speaker")
            yield VisualEffect(id="dialogue-fx")
            with VerticalScroll(id="dialogue-scroll"):
                yield Static(id="dialogue-lines")
            yield EventLog(id="dialogue-outcomes", max_lines=50)
            yield Vertical(id="dialogue-choices")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#dialogue-outcomes", EventLog).display = False
        self.app.run_flow(self._begin())

    # ------------------------------------------------------------ flow (runs as an app worker)
    async def _begin(self) -> None:
        await self._after_enter(self.runner.start())

    async def _after_enter(self, result: StepResult) -> None:
        if self.runner.finished:
            self._show_outcomes(result)
            self._render_blocked()
            return
        self._render_node()
        if not await self._process(result):
            return
        if self.runner.redirected:  # a minigame on this node decided where the story goes
            await self._after_enter(self.runner.proceed())
            return
        await self._render_choices()

    def _close(self) -> None:
        # Screen.dismiss pops whatever is on top, so only close when this scene is the active screen.
        if self.app.screen is self:
            self.dismiss(None)

    async def _choose(self, index: int) -> None:
        if index == LEAVE:
            self._close()
            return
        if index == END:
            await self.app.ending_flow(self._ending, self.checkpoint)
            return
        # Outcomes of the choice (and of the node it leads to) replace the previous node's outcomes.
        log = self.query_one("#dialogue-outcomes", EventLog)
        log.clear()
        log.display = False
        if index != CONTINUE:
            result = self.runner.choose(index)
            if not await self._process(result):
                return
        result = self.runner.proceed()
        if self.runner.finished and not result.events and not self.runner.blocked_reason:
            self._close()
            return
        await self._after_enter(result)

    async def _process(self, result: StepResult) -> bool:
        """Show outcomes and fulfil UI requests. Returns False if the player died (screen is gone)."""
        self._show_outcomes(result)
        app = self.app
        for request in result.requests:
            if isinstance(request, StartCombatRequest):
                enemy, notes = app.session.create_story_enemy(request.enemy_id)
                self._show_outcomes(StepResult(notes))
                phase = await app.run_encounter(Encounter(enemy, ambush=request.ambush, opener=request.opener))
                if phase == Phase.DEFEAT:
                    return False
                if phase == Phase.FLED:
                    self.runner.resolve_flight(request)
            elif isinstance(request, MinigameRequest):
                outcome, events = await app.minigame_flow(request.spec, request.allow_retreat)
                self._show_outcomes(StepResult(events))
                self.runner.resolve_minigame(request, outcome.outcome if outcome else None)
            elif isinstance(request, OpenShopRequest):
                from rpg.ui.screens.shop import ShopScreen

                await app.push_screen_wait(ShopScreen(request.mode))
            elif isinstance(request, VisualRequest):
                await self.query_one("#dialogue-fx", VisualEffect).play(request.name, request.duration)
            elif isinstance(request, EndGameRequest):
                self._ending = request.ending_id
        await app.resolve_level_ups()
        app.touch()
        return True

    # ------------------------------------------------------------ rendering
    def _show_outcomes(self, result: StepResult) -> None:
        if not result.events:
            return
        log = self.query_one("#dialogue-outcomes", EventLog)
        log.display = True
        log.add(result.events)
        self.app.touch()

    def _render_node(self) -> None:
        assert self.runner.node is not None
        speaker = self.runner.speaker
        self.query_one("#dialogue-speaker", Label).update(speaker)
        self.query_one("#dialogue-speaker", Label).display = bool(speaker)
        text = Text()
        gap = "\n\n" if self.runner.node.paragraphs else "\n"
        for i, line in enumerate(self.runner.lines()):
            if i:
                text.append(gap)
            text.append(line, style="#EDE4D3")
        self.query_one("#dialogue-lines", Static).update(text)
        self.query_one("#dialogue-scroll", VerticalScroll).scroll_home(animate=False)

    async def _render_choices(self) -> None:
        box = self.query_one("#dialogue-choices", Vertical)
        await box.remove_children()
        menu = self.runner.menu()
        if self._ending:
            buttons = [Button("Continue", id="choice-end", classes="choice-button", variant="primary")]
        elif any(entry.available for entry in menu):
            buttons = []
            for entry in menu:
                if entry.available:
                    # Plain Text, never markup: story text like "[Gnome] ..." must show as written.
                    buttons.append(Button(Text(f"{entry.index + 1}. {entry.text}"), id=f"choice-{entry.index}",
                                          classes="choice-button"))
                else:
                    locked = Button(Text(f"   {entry.text}  [{entry.reason}]"),
                                    classes="choice-button choice-locked", disabled=True)
                    locked.tooltip = entry.reason
                    buttons.append(locked)
        elif self.runner.node and self.runner.node.choices:
            self.query_one("#dialogue-lines", Static).update(
                Text("There is nothing you can do right now.", style=MUTED_STYLE))
            buttons = [Button("Leave", id="choice-leave", classes="choice-button", variant="primary")]
        else:
            buttons = [Button("Continue", id="choice-continue", classes="choice-button", variant="primary")]
        await box.mount_all(buttons)
        next(b for b in buttons if not b.disabled).focus()
        self._busy = False

    def _render_blocked(self) -> None:
        reason = self.runner.blocked_reason
        if reason:
            self.query_one("#dialogue-lines", Static).update(Text(reason, style="italic #E3B85C"))
        box = self.query_one("#dialogue-choices", Vertical)
        box.remove_children()
        button = Button("Leave", id="choice-leave", classes="choice-button", variant="primary")
        box.mount(button)
        button.focus()
        self._busy = False

    # ------------------------------------------------------------ input
    @on(Button.Pressed, ".choice-button")
    def pressed(self, event: Button.Pressed) -> None:
        key = (event.button.id or "").removeprefix("choice-")
        if not key:
            return
        index = {"continue": CONTINUE, "leave": LEAVE, "end": END}.get(key)
        self._start_choice(int(key) if index is None else index)

    def action_choose(self, index: int) -> None:
        if self.query(f"#choice-{index}"):
            self._start_choice(index)

    def _start_choice(self, index: int) -> None:
        if self._busy:
            return
        self._busy = True
        for button in self.query(".choice-button").results(Button):
            button.disabled = True
        self.app.run_flow(self._choose(index))

    def action_abandon(self) -> None:
        if self._busy or self._ending:
            return

        def answer(ok: bool | None) -> None:
            if ok:
                self._close()

        self.app.push_screen(ConfirmModal("Walk away from this scene? Progress in this conversation is lost.",
                                          "Walk away", "Stay"), answer)
