"""Shop: buy by category, sell, and repair worn gear."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static, Tab, Tabs

from rpg.core.formulas import buy_price_multiplier, sell_ratio
from rpg.core.items import Armor, ItemKind, Weapon
from rpg.core.shop import Shop, ShopError, ShopMode
from rpg.ui.palette import GOLD_STYLE, MUTED_STYLE
from rpg.ui.screens.inventory import item_details
from rpg.ui.widgets import ItemTable, PlayerPanel, VisualEffect
from rpg.ui.widgets.item_table import ItemRow

BUY_TABS = {
    ShopMode.GENERAL: [("weapon", "Weapons"), ("armor", "Armor"), ("spell", "Spells"), ("consumable", "Potions")],
    ShopMode.MAGIC: [("spell", "Spells"), ("consumable", "Potions")],
}
GREETINGS = {
    ShopMode.GENERAL: "“Welcome, traveler! Finest steel this side of Valoria.”",
    ShopMode.MAGIC: "“Mind the glyphs. They bite.”",
}


class ShopScreen(Screen[None]):
    BINDINGS = [Binding("escape", "leave", "Leave"), Binding("b", "transact", "Buy / Sell / Repair")]

    def __init__(self, mode: str | ShopMode = ShopMode.GENERAL) -> None:
        super().__init__()
        try:
            self.mode = ShopMode(mode)
        except ValueError:
            self.mode = ShopMode.GENERAL
        self.tab = BUY_TABS[self.mode][0][0]
        self.offer_by_key: dict = {}

    @property
    def shop(self) -> Shop:
        return self.app.session.shop(self.mode)

    @property
    def player(self):
        return self.app.session.player

    def compose(self) -> ComposeResult:
        tabs = [Tab(label, id=f"t-{key}") for key, label in BUY_TABS[self.mode]] + [Tab("Sell", id="t-sell")]
        if self.mode == ShopMode.GENERAL:
            tabs.append(Tab("Repair", id="t-repair"))
        yield Header(show_clock=False)
        with Horizontal(classes="split-root"):
            yield PlayerPanel()
            with Vertical(classes="split-main"):
                yield Label("", id="shop-title", classes="screen-title")
                yield Static(Text(GREETINGS[self.mode], style="italic #C9BFAE"), id="shop-greeting")
                yield VisualEffect(id="shop-fx")
                yield Tabs(*tabs, id="shop-tabs")
                yield ItemTable(price_label="Price", id="shop-table")
                with Horizontal(classes="detail-row"):
                    yield Static(id="shop-detail", classes="detail-pane")
                    with Vertical(classes="detail-actions"):
                        yield Button("Buy", variant="primary", id="transact")
                        yield Button("Leave", id="leave")
        yield Footer()

    def on_mount(self) -> None:
        cha = self.player.attributes.charisma
        multiplier = buy_price_multiplier(cha)
        deal = "no haggling" if multiplier == 1 else (f"{(1 - multiplier) * 100:.0f}% off" if multiplier < 1
                                                      else f"{(multiplier - 1) * 100:.0f}% markup")
        self.query_one("#shop-title", Label).update(
            f"◆ {self.shop.name}   ·   Charisma {cha}: {deal}, sells at {sell_ratio(cha) * 100:.0f}%")
        self.run_worker(self.query_one("#shop-fx", VisualEffect).play("glyphs" if self.mode == ShopMode.MAGIC else "banner",
                                                                      0.6, rows=1))
        self.reload()
        self.query_one(ItemTable).focus()

    def reload(self) -> None:
        shop, player = self.shop, self.player
        rows: list[ItemRow] = []
        self.offer_by_key = {}
        if self.tab == "sell":
            for stack in player.inventory:
                note = "(equipped)" if player.inventory.is_equipped(stack.item) else ""
                rows.append(ItemRow(stack.item.uid, stack.item, stack.quantity, price=Shop.sell_price_for(stack.item, player), note=note))
            action = "Sell"
        elif self.tab == "repair":
            for stack in player.inventory:
                item = stack.item
                if isinstance(item, (Weapon, Armor)) and item.missing_durability > 0:
                    rows.append(ItemRow(item.uid, item, 1, price=Shop.repair_cost(item, player),
                                        note="(broken)" if item.is_broken else ""))
            action = "Repair"
        else:
            for index, offer in enumerate(shop.offers_of_kind(ItemKind(self.tab))):
                if offer.sold_out:
                    continue
                key = f"offer{index}"
                self.offer_by_key[key] = offer
                rows.append(ItemRow(key, offer.item, price=Shop.price_for(offer, player), stock=offer.stock))
            action = "Buy"
        self.query_one(ItemTable).load(rows, player)
        self.query_one("#transact", Button).label = action
        self.app.touch()
        self._show_selected()

    def _show_selected(self) -> None:
        row = self.query_one(ItemTable).selected_row
        detail = self.query_one("#shop-detail", Static)
        button = self.query_one("#transact", Button)
        if row is None:
            empty = {"sell": "You have nothing to sell.", "repair": "All of your gear is in good condition."}
            detail.update(Text(empty.get(self.tab, "Sold out. Come back after the bell turns."), style=MUTED_STYLE))
            button.disabled = True
            return
        text = item_details(row.item, self.player)
        gold = self.player.gold
        if self.tab == "sell":
            text.append(f"\nSell for {row.price}g", style=GOLD_STYLE)
            button.disabled = self.player.inventory.is_equipped(row.item)
            if button.disabled:
                text.append("\nUnequip it before selling.", style=MUTED_STYLE)
        else:
            verb = "Repair" if self.tab == "repair" else "Price"
            text.append(f"\n{verb}: {row.price}g · you have {gold}g", style=GOLD_STYLE)
            button.disabled = (row.price or 0) > gold
            if self.tab != "repair":
                ok, reason = self.player.meets_requirement(row.item)
                if not ok:
                    text.append(f"\nYou can buy it, but can't use it yet. {reason}", style=MUTED_STYLE)
        detail.update(text)

    @on(Tabs.TabActivated, "#shop-tabs")
    def tab_changed(self, event: Tabs.TabActivated) -> None:
        self.tab = event.tab.id.removeprefix("t-")
        self.reload()

    @on(DataTable.RowHighlighted)
    def highlighted(self) -> None:
        self._show_selected()

    @on(Button.Pressed, "#transact")
    def action_transact(self) -> None:
        row = self.query_one(ItemTable).selected_row
        if row is None:
            return
        try:
            if self.tab == "sell":
                price = self.shop.sell(self.player, row.item)
                self.notify(f"Sold {row.item.name} for {price}g.")
            elif self.tab == "repair":
                cost = self.shop.repair(self.player, row.item)
                self.notify(f"{row.item.name} repaired for {cost}g.")
            else:
                item = self.shop.buy(self.player, self.offer_by_key[row.key])
                self.notify(f"Purchased {item.name}!")
        except (ShopError, KeyError) as exc:
            self.notify(str(exc), severity="error")
        self.reload()

    @on(Button.Pressed, "#leave")
    def action_leave(self) -> None:
        self.dismiss(None)
