"""Briefing before a trial: your skill against the difficulty, where it comes from, and a last chance to
drink a tonic. Returns True to begin, False to back out."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from rpg.core.minigames import MinigameKind, MinigameSpec
from rpg.core.skills import SKILL_INFO, TRAITS
from rpg.ui.palette import MUTED_STYLE

ODDS_STYLES = {"Trivial": "bold #7FD1A8", "Favorable": "bold #9FD08F", "Even": "bold #E3B85C",
               "Risky": "bold #E58A6F", "Dire": "bold #E8604F"}
RELEVANT_TRAITS = {
    MinigameKind.STEALTH: ("small_frame", "heavy_step", "breathless", "smoldering", "keen_senses"),
    MinigameKind.LOCKPICK: ("tinker",),
    MinigameKind.QTE: ("keen_senses", "quickened"),
    MinigameKind.BALANCE: ("stoneborn",),
    MinigameKind.MEMORY: ("eidetic",),
    MinigameKind.TIMING: ("steady_hands",),
}


class MinigameBriefing(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "back", "Back out"), Binding("enter", "begin", "Begin", show=False)]

    def __init__(self, spec: MinigameSpec, allow_retreat: bool = True) -> None:
        super().__init__()
        self.spec = spec
        self.allow_retreat = allow_retreat

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box -briefing"):
            yield Label(self.spec.display_title, classes="modal-title")
            if self.spec.intro:
                yield Static(Text(self.spec.intro, style="italic #EDE4D3"), classes="modal-prompt")
            yield Static(id="brief-check", classes="briefing-section")
            yield Static(Text.assemble(("Controls  ", "bold"), (self.spec.game_class.controls, MUTED_STYLE)),
                         classes="briefing-section")
            yield Vertical(id="brief-tonics")
            with Horizontal(classes="modal-buttons"):
                yield Button("Begin", variant="primary", id="begin")
                if self.allow_retreat:
                    yield Button("Back out", id="back")

    async def on_mount(self) -> None:
        await self.refresh_brief()
        self.query_one("#begin", Button).focus()

    async def refresh_brief(self) -> None:
        session = self.app.session
        player = session.player
        check = session.minigame_check(self.spec)
        info = SKILL_INFO[check.skill]

        text = Text()
        text.append(f"{info.label} ", style="bold #E0A458")
        text.append(f"{check.rating}", style="bold")
        text.append(f"  vs difficulty {check.dc}  ", style=MUTED_STYLE)
        text.append(check.odds_label, style=ODDS_STYLES[check.odds_label])
        text.append(f"\n{info.description}\n", style=MUTED_STYLE)
        parts = [f"{a.short} {player.attributes.get(a)}×{int(w * 100)}%" for a, w in info.weights.items()]
        text.append("\nAttributes  ", style="bold")
        text.append(" + ".join(parts), style=MUTED_STYLE)
        text.append(f"  = {check.base}")
        for source in check.sources:
            text.append(f"\n{source.label:<12}", style="bold")
            text.append(f"{source.amount:+d}", style="#9FD08F" if source.amount > 0 else "#E8604F")
        traits = [t for t in RELEVANT_TRAITS.get(self.spec.kind, ()) if check.has(t)]
        for trait in traits:
            text.append(f"\n✧ {TRAITS[trait].label}  ", style="bold #C99BE8")
            text.append(TRAITS[trait].description, style=MUTED_STYLE)
        if self.spec.kind == MinigameKind.LOCKPICK:
            picks = player.lockpicks()
            text.append("\n\nLockpicks  ", style="bold")
            if picks:
                text.append(f"{len(picks)} carried · using {picks[0].name} first", style="#EDE4D3")
            else:
                text.append("none! Buy some at the Emporium.", style="bold #E8604F")
        self.query_one("#brief-check", Static).update(text)
        self.query_one("#begin", Button).disabled = self.spec.kind == MinigameKind.LOCKPICK and not player.lockpicks()

        box = self.query_one("#brief-tonics", Vertical)
        await box.remove_children()
        primed = player.skill_primes.get(check.skill.value, 0)
        buttons = []
        for tonic in session.skill_tonics(check.skill.value):
            qty = player.inventory.find(tonic.uid).quantity
            button = Button(f"Use {tonic.name} ×{qty}  (+{tonic.potency} {info.label})", id=f"tonic-{tonic.uid}",
                            classes="tonic-button")
            button.disabled = primed >= tonic.potency
            buttons.append(button)
        if buttons:
            await box.mount_all(buttons)
        box.display = bool(buttons)

    @on(Button.Pressed, ".tonic-button")
    async def use_tonic(self, event: Button.Pressed) -> None:
        session = self.app.session
        uid = event.button.id.removeprefix("tonic-")
        stack = session.player.inventory.find(uid)
        if stack is None:
            return
        for line in session.use_item(stack.item):
            self.notify(line.text)
        self.app.touch()
        await self.refresh_brief()
        self.query_one("#begin", Button).focus()

    @on(Button.Pressed, "#begin")
    def action_begin(self) -> None:
        if not self.query_one("#begin", Button).disabled:
            self.dismiss(True)

    @on(Button.Pressed, "#back")
    def action_back(self) -> None:
        if self.allow_retreat:
            self.dismiss(False)
