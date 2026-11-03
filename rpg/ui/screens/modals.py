"""Modal dialogs. Each returns its result through ``dismiss`` so flows can ``await push_screen_wait(...)``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from rpg.core.attributes import Attribute
from rpg.core.entities import Player
from rpg.core.items import Item
from rpg.core.progression import VictoryReport
from rpg.ui.palette import ATTRIBUTE_COLORS, GOLD_STYLE, MUTED_STYLE, event_text, requirements_text

T = TypeVar("T")


@dataclass
class Choice(Generic[T]):
    label: str | Text
    value: T
    enabled: bool = True


class ChoiceModal(ModalScreen[Any]):
    """Pick one option from a list. Escape returns None when ``cancellable``."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, choices: list[Choice], prompt: str = "", cancellable: bool = True) -> None:
        super().__init__()
        self.title_text = title
        self.prompt = prompt
        self.choices = choices
        self.cancellable = cancellable

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Label(self.title_text, classes="modal-title")
            if self.prompt:
                yield Static(self.prompt, classes="modal-prompt")
            yield OptionList(*[Option(c.label, id=f"opt{i}", disabled=not c.enabled) for i, c in enumerate(self.choices)],
                             id="modal-options")
            if self.cancellable:
                yield Label("Enter to choose · Esc to cancel", classes="modal-hint")
            else:
                yield Label("Enter to choose", classes="modal-hint")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        options.focus()
        first = next((i for i, c in enumerate(self.choices) if c.enabled), None)
        if first is not None:
            options.highlighted = first

    @on(OptionList.OptionSelected)
    def chosen(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.choices[event.option_index].value)

    def action_cancel(self) -> None:
        if self.cancellable:
            self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", "No"), Binding("y", "yes", "Yes"), Binding("n", "no", "No")]

    def __init__(self, question: str, yes: str = "Yes", no: str = "No") -> None:
        super().__init__()
        self.question, self.yes_label, self.no_label = question, yes, no

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box -small"):
            yield Static(self.question, classes="modal-prompt")
            with Horizontal(classes="modal-buttons"):
                yield Button(self.yes_label, variant="primary", id="yes")
                yield Button(self.no_label, id="no")

    def on_mount(self) -> None:
        self.query_one("#yes", Button).focus()

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


class MessageModal(ModalScreen[None]):
    BINDINGS = [Binding("escape,enter", "close", "Close")]

    def __init__(self, title: str, body: str | Text) -> None:
        super().__init__()
        self.title_text, self.body = title, body

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box -small"):
            yield Label(self.title_text, classes="modal-title")
            yield Static(self.body, classes="modal-prompt")
            with Horizontal(classes="modal-buttons"):
                yield Button("OK", variant="primary", id="ok")

    def on_mount(self) -> None:
        self.query_one("#ok", Button).focus()

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class LevelUpModal(ModalScreen[Attribute]):
    """Spend one stat point. The flow re-opens it while points remain."""

    BINDINGS = [Binding(str(i), f"pick('{attr.value}')", attr.label, show=False)
                for i, attr in enumerate(Attribute, 1)]

    def __init__(self, player: Player) -> None:
        super().__init__()
        self.player = player

    def compose(self) -> ComposeResult:
        p = self.player
        options = []
        for i, attr in enumerate(Attribute, 1):
            value = p.attributes.get(attr)
            label = Text(f"{i}. ", style=MUTED_STYLE)
            label.append(f"{attr.label:<13}", style=f"bold {ATTRIBUTE_COLORS[attr]}")
            label.append(f"{value:>3} → {value + 1:<3}", style="bold #F2C46D")
            label.append(f"  {attr.description}", style=MUTED_STYLE)
            options.append(Option(label, id=attr.value))
        with Vertical(classes="modal-box -levelup"):
            yield Label(f"★ Level {p.level}!", classes="modal-title")
            yield Static(f"You have {p.stat_points} stat point{'s' if p.stat_points != 1 else ''} to spend. "
                         "Choose an attribute to improve:", classes="modal-prompt")
            yield OptionList(*options, id="levelup-options")
            yield Label("Enter or 1–7 to choose", classes="modal-hint")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        options.highlighted = 0
        options.focus()

    @on(OptionList.OptionSelected, "#levelup-options")
    def chosen(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(Attribute(event.option_id))

    def action_pick(self, value: str) -> None:
        self.dismiss(Attribute(value))


class VictoryModal(ModalScreen[None]):
    BINDINGS = [Binding("escape,enter", "close", "Continue")]

    def __init__(self, report: VictoryReport) -> None:
        super().__init__()
        self.report = report

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box -victory"):
            yield Label("VICTORY", classes="modal-title -victory")
            yield Static(Text(f"{self.report.enemy_name} has fallen.", style="bold"), classes="modal-prompt")
            body = Text()
            for i, event in enumerate(self.report.events):
                if i:
                    body.append("\n")
                body.append_text(event_text(event))
            yield Static(body, classes="victory-rewards")
            with Horizontal(classes="modal-buttons"):
                yield Button("Continue", variant="primary", id="ok")

    def on_mount(self) -> None:
        self.query_one("#ok", Button).focus()

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


def item_choice_label(item: Item, player: Player) -> Text:
    text = Text(item.name, style="bold")
    text.append(f"  ({item.kind.label})", style=MUTED_STYLE)
    text.append(f"\n  {item.summary()}", style="")
    if item.requirements:
        text.append("\n  Requires ")
        text.append_text(requirements_text(item, player, long=True))
    if item.description:
        text.append(f"\n  {item.description}", style=MUTED_STYLE)
    return text


def trophy_modal(items: list[Item], player: Player) -> ChoiceModal:
    return ChoiceModal("Choose your trophy", [Choice(item_choice_label(item, player), item) for item in items],
                       prompt="The fallen leave behind a legendary hoard. You can carry one piece.", cancellable=False)


def gold_text(amount: int) -> Text:
    return Text(f"◆ {amount} gold", style=GOLD_STYLE)
