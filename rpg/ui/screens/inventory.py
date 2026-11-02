"""Inventory: browse by category, inspect, equip, use and discard."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static, Tab, Tabs

from rpg.core.items import Consumable, ItemKind
from rpg.ui.palette import BAD_STYLE, MUTED_STYLE, requirements_text
from rpg.ui.screens.modals import ConfirmModal
from rpg.ui.widgets import ItemTable, PlayerPanel
from rpg.ui.widgets.item_table import ItemRow

FILTERS = [("all", "All", None), ("weapon", "Weapons", ItemKind.WEAPON), ("armor", "Armor", ItemKind.ARMOR),
           ("spell", "Spells", ItemKind.SPELL), ("consumable", "Consumables", ItemKind.CONSUMABLE),
           ("misc", "Curios", ItemKind.MISC)]


def item_details(item, player) -> Text:
    text = Text()
    text.append(item.name + "\n", style="bold #E0A458")
    for line in item.details():
        if line.startswith("Requires ") and item.requirements:
            text.append("Requires ")
            text.append_text(requirements_text(item, player, long=True))
            text.append("\n")
        else:
            text.append(line + "\n")
    ok, reason = player.meets_requirement(item)
    if not ok:
        text.append(reason.replace("Requires ", "Not yet usable: ") + "\n", style=BAD_STYLE)
    if player.inventory.is_equipped(item):
        text.append("Equipped\n", style="bold #86B57F")
    return text


class InventoryScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("e", "equip", "Equip"),
                Binding("u", "use", "Use"), Binding("d", "drop", "Discard")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(classes="split-root"):
            yield PlayerPanel()
            with Vertical(classes="split-main"):
                yield Label("Inventory", classes="screen-title")
                yield Tabs(*[Tab(label, id=f"f-{key}") for key, label, _ in FILTERS], id="inv-filter")
                yield ItemTable(id="inv-table")
                with Horizontal(classes="detail-row"):
                    yield Static(id="inv-detail", classes="detail-pane")
                    with Vertical(classes="detail-actions"):
                        yield Button("Equip", variant="primary", id="equip")
                        yield Button("Use", variant="success", id="use")
                        yield Button("Discard", variant="error", id="drop")
                        yield Button("Back", id="back")
                yield Label("", id="inv-capacity", classes="muted")
        yield Footer()

    def __init__(self) -> None:
        super().__init__()
        self._kind: ItemKind | None = None

    def on_mount(self) -> None:
        self.reload()
        self.query_one(ItemTable).focus()

    @property
    def player(self):
        return self.app.session.player

    def reload(self) -> None:
        stacks = [s for s in self.player.inventory if self._kind is None or s.item.kind == self._kind]
        rows = [ItemRow(s.item.uid, s.item, s.quantity) for s in stacks]
        self.query_one(ItemTable).load(rows, self.player)
        inv = self.player.inventory
        self.query_one("#inv-capacity", Label).update(f"{len(inv)}/{inv.capacity} slots used")
        self._show_selected()
        self.app.touch()

    def _show_selected(self) -> None:
        row = self.query_one(ItemTable).selected_row
        detail = self.query_one("#inv-detail", Static)
        equip, use, drop = (self.query_one(f"#{i}", Button) for i in ("equip", "use", "drop"))
        if row is None:
            detail.update(Text("Nothing here.", style=MUTED_STYLE))
            equip.disabled = use.disabled = drop.disabled = True
            return
        item = row.item
        detail.update(item_details(item, self.player))
        equippable = item.kind in (ItemKind.WEAPON, ItemKind.ARMOR, ItemKind.SPELL)
        equip.disabled = not equippable or self.player.inventory.is_equipped(item)
        use.disabled = not isinstance(item, Consumable)
        drop.disabled = self.player.inventory.is_equipped(item)

    @on(Tabs.TabActivated, "#inv-filter")
    def filter_changed(self, event: Tabs.TabActivated) -> None:
        key = event.tab.id.removeprefix("f-")
        self._kind = next(kind for k, _, kind in FILTERS if k == key)
        self.reload()

    @on(DataTable.RowHighlighted)
    def highlighted(self) -> None:
        self._show_selected()

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#equip")
    def action_equip(self) -> None:
        row = self.query_one(ItemTable).selected_row
        if row is None or row.item.kind not in (ItemKind.WEAPON, ItemKind.ARMOR, ItemKind.SPELL):
            return
        try:
            self.notify(self.app.session.equip(row.item))
        except (ValueError, TypeError, KeyError) as exc:
            self.notify(str(exc), severity="error")
        self.reload()

    @on(Button.Pressed, "#use")
    def action_use(self) -> None:
        row = self.query_one(ItemTable).selected_row
        if row is None or not isinstance(row.item, Consumable):
            return
        try:
            for event in self.app.session.use_item(row.item):
                self.notify(event.text)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
        self.reload()

    @on(Button.Pressed, "#drop")
    def action_drop(self) -> None:
        row = self.query_one(ItemTable).selected_row
        if row is None:
            return

        def confirmed(ok: bool | None) -> None:
            if ok:
                try:
                    self.notify(self.app.session.drop_item(row.item).text)
                except ValueError as exc:
                    self.notify(str(exc), severity="error")
                self.reload()

        self.app.push_screen(ConfirmModal(f"Discard one {row.item.name}? It will be lost forever.", "Discard", "Keep"),
                             confirmed)
