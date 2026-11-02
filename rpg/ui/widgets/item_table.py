"""DataTable of items used by the inventory and shop screens."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.widgets import DataTable

from rpg.core.entities import Player
from rpg.core.items import Item
from rpg.ui.palette import GOLD_STYLE, MUTED_STYLE, requirements_text


@dataclass
class ItemRow:
    key: str
    item: Item
    quantity: int = 1
    price: int | None = None  # shown in the price column (buy/sell/repair); None hides it
    stock: int | None = None
    note: str = ""


class ItemTable(DataTable):
    """Rows keyed by ``ItemRow.key``. ``selected_row`` returns the highlighted ``ItemRow``."""

    def __init__(self, *, price_label: str = "Value", id: str | None = None) -> None:
        super().__init__(id=id, cursor_type="row", zebra_stripes=True)
        self.price_label = price_label
        self._rows: dict[str, ItemRow] = {}

    def on_mount(self) -> None:
        self.add_columns(" ", "Item", "Type", "Stats", "Qty", self.price_label, "Requires")

    def load(self, rows: list[ItemRow], player: Player) -> None:
        previous = self.selected_row.key if self.selected_row else None
        self.clear()
        self._rows = {}
        for row in rows:
            item = row.item
            equipped = player.inventory.is_equipped(item)
            marker = Text("E", style="bold #86B57F") if equipped else Text(" ")
            requirement = requirements_text(item, player)
            qty = str(row.stock if row.stock is not None else row.quantity)
            if row.stock is not None and row.stock >= 99:
                qty = "∞"
            price = Text(f"{row.price}g" if row.price is not None else f"{item.value}g", style=GOLD_STYLE)
            name = Text(item.name, style="bold")
            if row.note:
                name.append(f"  {row.note}", style=MUTED_STYLE)
            self.add_row(marker, name, item.kind.label, Text(item.summary(), style=MUTED_STYLE), qty, price,
                         requirement, key=row.key)
            self._rows[row.key] = row
        if previous in self._rows:
            self.move_cursor(row=self.get_row_index(previous))

    @property
    def selected_row(self) -> ItemRow | None:
        if not self._rows or self.cursor_row < 0 or self.cursor_row >= self.row_count:
            return None
        key = self.coordinate_to_cell_key((self.cursor_row, 0)).row_key.value
        return self._rows.get(key)
