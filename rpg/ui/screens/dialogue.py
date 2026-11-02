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
from rpg.core.dialogue import DialogueRunner, OpenShopRequest, StartCombatRequest, StepResult, VisualRequest
from rpg.core.session import Encounter
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.modals import ConfirmModal
from rpg.ui.widgets import EventLog, VisualEffect

CONTINUE = -1
LEAVE = -2


class DialogueScreen(Screen[None]):
    BINDINGS = [Binding(str(n), f"choose({n - 1})", show=False) for n in range(1, 10)] + [
        Binding("escape", "abandon", "Walk away"),
    ]

    def __init__(self, runner: DialogueRunner, title: str = "") -> None:
        super().__init__()
        self.runner = runner
        self.scene_title = title
        self._busy = True

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
        await self._render_choices()

    def _close(self) -> None:
        # Screen.dismiss pops whatever is on top, so only close when this scene is the active screen.
        if self.app.screen is self:
            self.dismiss(None)

    async def _choose(self, index: int) -> None:
        if index == LEAVE:
            self._close()
            return
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
                phase = await app.run_encounter(Encounter(enemy))
                if phase == Phase.DEFEAT:
                    return False
            elif isinstance(request, OpenShopRequest):
                from rpg.ui.screens.shop import ShopScreen

                await app.push_screen_wait(ShopScreen(request.mode))
            elif isinstance(request, VisualRequest):
                await self.query_one("#dialogue-fx", VisualEffect).play(request.name, request.duration)
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
        node = self.runner.node
        assert node is not None
        self.query_one("#dialogue-speaker", Label).update(node.speaker or "")
        self.query_one("#dialogue-speaker", Label).display = bool(node.speaker)
        text = Text()
        for i, line in enumerate(node.lines):
            if i:
                text.append("\n")
            text.append(line, style="#EDE4D3")
        self.query_one("#dialogue-lines", Static).update(text)
        self.query_one("#dialogue-scroll", VerticalScroll).scroll_home(animate=False)
        self.query_one("#dialogue-outcomes", EventLog).clear()
        self.query_one("#dialogue-outcomes", EventLog).display = False

    async def _render_choices(self) -> None:
        box = self.query_one("#dialogue-choices", Vertical)
        await box.remove_children()
        choices = self.runner.choices()
        if choices:
            buttons = [Button(f"{i}. {c.text}", id=f"choice-{i - 1}", classes="choice-button")
                       for i, c in enumerate(choices, 1)]
        elif self.runner.node and self.runner.node.choices:
            self.query_one("#dialogue-lines", Static).update(
                Text("There is nothing you can do right now.", style=MUTED_STYLE))
            buttons = [Button("Leave", id="choice-leave", classes="choice-button", variant="primary")]
        else:
            buttons = [Button("Continue", id="choice-continue", classes="choice-button", variant="primary")]
        await box.mount_all(buttons)
        buttons[0].focus()
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
        key = event.button.id.removeprefix("choice-")
        index = {"continue": CONTINUE, "leave": LEAVE}.get(key)
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
        if self._busy:
            return

        def answer(ok: bool | None) -> None:
            if ok:
                self._close()

        self.app.push_screen(ConfirmModal("Walk away from this scene? Progress in this conversation is lost.",
                                          "Walk away", "Stay"), answer)
