"""The battle screen. Drives a ``CombatSession`` step by step and paces the log."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ProgressBar

from rpg import config
from rpg.core.combat import Action, Attack, CastSpell, CombatSession, Flee, Hesitate, Phase, UseItem
from rpg.core.events import LogEvent
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.screens.modals import Choice, ChoiceModal
from rpg.ui.widgets import CombatantCard, EventLog

ENEMY_DELAY = 0.55
EVENT_DELAY = 0.12

OUTCOME_TEXT = {
    Phase.VICTORY: ("Victory!", "bold #F2C46D"),
    Phase.DEFEAT: ("You have fallen...", "bold #E8604F"),
    Phase.FLED: ("You escaped.", "bold #C9BFAE"),
}


class CombatScreen(Screen[Phase]):
    BINDINGS = [
        Binding("1,a", "attack", "Attack"),
        Binding("2,m", "cast", "Cast"),
        Binding("3,u", "item", "Item"),
        Binding("4,f", "flee", "Flee"),
    ]

    def __init__(self, combat: CombatSession) -> None:
        super().__init__(classes="-boss" if combat.enemy.is_boss else "")
        self.combat = combat
        self._busy = True
        self._remaining = float(config.TURN_TIMER_SECONDS)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="combat-root"):
            with Horizontal(id="arena"):
                yield CombatantCard(self.combat.player, id="player-card")
                yield Label("VS", id="versus")
                yield CombatantCard(self.combat.enemy, id="enemy-card")
            yield EventLog(id="combat-log")
            with Horizontal(id="turn-row"):
                yield Label("", id="turn-label")
                yield ProgressBar(total=max(1, config.TURN_TIMER_SECONDS), show_eta=False, show_percentage=False,
                                  id="turn-timer")
            with Horizontal(id="combat-actions"):
                yield Button("1 · Attack", variant="error", id="attack", classes="combat-button")
                yield Button("2 · Cast", variant="primary", id="cast", classes="combat-button")
                yield Button("3 · Item", variant="success", id="item", classes="combat-button")
                yield Button("4 · Flee", variant="warning", id="flee", classes="combat-button")
            with Horizontal(id="combat-done"):
                yield Button("Continue", variant="primary", id="done")
        yield Footer()

    # ------------------------------------------------------------ lifecycle
    def on_mount(self) -> None:
        log = self.query_one("#combat-log", EventLog)
        log.border_title = "Battle log"
        self.query_one("#combat-done").display = False
        timer = self.query_one("#turn-timer", ProgressBar)
        timer.display = config.TURN_TIMER_SECONDS > 0
        log.add(self.combat.start())
        self._sync()
        if config.TURN_TIMER_SECONDS > 0:
            self.set_interval(0.1, self._tick_timer)
        if self.combat.is_over:
            self._finish()
        elif self.combat.phase == Phase.ENEMY_TURN:
            self.run_worker(self._enemy_phase())
        else:
            self._player_ready()

    def _sync(self) -> None:
        self.query_one("#player-card", CombatantCard).sync()
        self.query_one("#enemy-card", CombatantCard).sync()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self.query(".combat-button").results(Button):
            button.disabled = busy
        if not busy:
            self.query_one("#flee", Button).disabled = not self.combat.allow_flee

    def _player_ready(self) -> None:
        log = self.query_one("#combat-log", EventLog)
        log.divider(f"Round {self.combat.round}")
        flee = f" · flee {int(self.combat.flee_chance * 100)}%" if self.combat.allow_flee else " · no escape"
        self.query_one("#turn-label", Label).update(Text.assemble(("Your turn", "bold #9FD08F"), (flee, MUTED_STYLE)))
        self._remaining = float(config.TURN_TIMER_SECONDS)
        self._refresh_turn_timer()
        self._set_busy(False)
        self.query_one("#attack", Button).focus()

    def _tick_timer(self) -> None:
        if self._busy or self.combat.phase != Phase.PLAYER_TURN or self.app.screen is not self:
            return
        self._remaining -= 0.1
        self._refresh_turn_timer()
        if self._remaining <= 0:
            self._submit(Hesitate())

    def _refresh_turn_timer(self) -> None:
        bar = self.query_one("#turn-timer", ProgressBar)
        bar.update(total=max(1, config.TURN_TIMER_SECONDS), progress=max(0.0, self._remaining))
        bar.set_class(self._remaining <= 5, "-urgent")

    async def _write(self, events: list[LogEvent], paced: bool = True) -> None:
        log = self.query_one("#combat-log", EventLog)
        for event in events:
            log.add(event)
            self._sync()
            if paced:
                await asyncio.sleep(EVENT_DELAY)

    # ------------------------------------------------------------ turn handling
    def _submit(self, action: Action) -> None:
        if self._busy or self.combat.phase != Phase.PLAYER_TURN:
            return
        self._set_busy(True)
        self.run_worker(self._resolve(action))

    async def _resolve(self, action: Action) -> None:
        result = self.combat.act(action)
        await self._write(result.events, paced=result.accepted)
        if not result.accepted:
            self._set_busy(False)
            return
        if self.combat.is_over:
            self._finish()
            return
        await self._enemy_phase()

    async def _enemy_phase(self) -> None:
        self._set_busy(True)
        self.query_one("#turn-label", Label).update(Text(f"{self.combat.enemy.name}'s turn...", style="bold #E58A6F"))
        while self.combat.phase == Phase.ENEMY_TURN:
            await asyncio.sleep(ENEMY_DELAY)
            await self._write(self.combat.enemy_turn())
        self.app.touch()
        if self.combat.is_over:
            self._finish()
        else:
            self._player_ready()

    def _finish(self) -> None:
        self._set_busy(True)
        self._sync()
        self.app.touch()
        text, style = OUTCOME_TEXT[self.combat.phase]
        self.query_one("#turn-label", Label).update(Text(text, style=style))
        self.query_one("#turn-timer", ProgressBar).display = False
        self.query_one("#combat-actions").display = False
        self.query_one("#combat-done").display = True
        self.query_one("#done", Button).focus()

    # ------------------------------------------------------------ actions
    @on(Button.Pressed, "#attack")
    def action_attack(self) -> None:
        self._submit(Attack())

    @on(Button.Pressed, "#flee")
    def action_flee(self) -> None:
        self._submit(Flee())

    @on(Button.Pressed, "#cast")
    def action_cast(self) -> None:
        if not self._busy and self.combat.phase == Phase.PLAYER_TURN:
            self.run_worker(self._pick_spell())

    @on(Button.Pressed, "#item")
    def action_item(self) -> None:
        if not self._busy and self.combat.phase == Phase.PLAYER_TURN:
            self.run_worker(self._pick_item())

    async def _pick_spell(self) -> None:
        spells = self.combat.castable_spells()
        if not spells:
            self.notify("You don't know any spells. Buy some at the shop!", severity="warning")
            return
        equipped = self.combat.player.spell
        choices = []
        for spell, ok, reason in spells:
            label = Text(spell.name, style="bold")
            if spell is equipped:
                label.append("  ★", style="#F2C46D")
            label.append(f"  {spell.summary()}", style=MUTED_STYLE)
            if not ok:
                label.append(f"  — {reason}", style="#E8604F")
            choices.append(Choice(label, spell, ok))
        choices.sort(key=lambda c: (c.value is not equipped, not c.enabled))
        spell = await self.app.push_screen_wait(
            ChoiceModal("Cast a spell", choices, prompt=f"Mana {self.combat.player.mana}/{self.combat.player.max_mana}"))
        if spell is not None:
            self._submit(CastSpell(spell.uid))

    async def _pick_item(self) -> None:
        items = self.combat.usable_items()
        if not items:
            self.notify("You have no usable items.", severity="warning")
            return
        choices = [Choice(Text.assemble((f"{item.name} ×{qty}", "bold"), (f"  {item.summary()}", MUTED_STYLE)), item)
                   for item, qty in items]
        item = await self.app.push_screen_wait(ChoiceModal("Use an item", choices))
        if item is not None:
            self._submit(UseItem(item.uid))

    @on(Button.Pressed, "#done")
    def done(self) -> None:
        self.dismiss(self.combat.phase)
