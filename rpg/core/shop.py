"""Rotating shops with buying, selling and repairs."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from rpg import config
from rpg.core.catalog import GENERAL_SHOP_COUNTS, GENERAL_SHOP_POOLS, ITEMS, MAGIC_SHOP_COUNTS, MAGIC_SHOP_SPELLS
from rpg.core.entities import Player
from rpg.core.inventory import InventoryFullError
from rpg.core.items import Armor, Item, ItemKind, Weapon


class ShopMode(str, Enum):
    GENERAL = "general"
    MAGIC = "magic"


SHOP_NAMES = {
    ShopMode.GENERAL: "Merchant's Emporium",
    ShopMode.MAGIC: "Collegium Arcana — Spellwright's Stall",
}

UNLIMITED = 99


class ShopError(Exception):
    pass


@dataclass
class Offer:
    item: Item  # display sample; buyers receive a clone
    price: int
    stock: int

    @property
    def sold_out(self) -> bool:
        return self.stock <= 0


class Shop:
    def __init__(self, mode: ShopMode = ShopMode.GENERAL) -> None:
        self.mode = mode
        self.offers: list[Offer] = []
        self._seed: int | None = None

    @property
    def name(self) -> str:
        return SHOP_NAMES[self.mode]

    def rotate(self, seed: int, unlocks: set[str] | None = None) -> bool:
        """Restock from the pools. Only happens when the seed (world time) changes, so purchases stick."""
        if seed == self._seed:
            return False
        self._seed = seed
        rng = random.Random(seed * 7919 + (1 if self.mode == ShopMode.MAGIC else 0))
        self.offers = []
        if self.mode == ShopMode.GENERAL:
            for category, count in GENERAL_SHOP_COUNTS.items():
                pool = GENERAL_SHOP_POOLS[category]
                for template_id in rng.sample(pool, k=min(count, len(pool))):
                    self._offer(template_id, UNLIMITED if category == "consumable" else 1)
            for template_id in sorted(unlocks or ()):
                if template_id in ITEMS and not any(o.item.template_id == template_id for o in self.offers):
                    self._offer(template_id, 1)
        else:
            for template_id in rng.sample(MAGIC_SHOP_SPELLS, k=min(MAGIC_SHOP_COUNTS["spell"], len(MAGIC_SHOP_SPELLS))):
                self._offer(template_id, 1)
            pool = GENERAL_SHOP_POOLS["consumable"]
            for template_id in rng.sample(pool, k=min(MAGIC_SHOP_COUNTS["consumable"], len(pool))):
                self._offer(template_id, UNLIMITED)
        return True

    def _offer(self, template_id: str, stock: int) -> None:
        item = ITEMS.create(template_id)
        self.offers.append(Offer(item, item.value, stock))

    def offers_of_kind(self, kind: ItemKind | None = None) -> list[Offer]:
        return [o for o in self.offers if kind is None or o.item.kind == kind]

    # ------------------------------------------------------------ transactions
    def buy(self, player: Player, offer: Offer) -> Item:
        if offer not in self.offers:
            raise ShopError("That item is no longer on sale.")
        if offer.sold_out:
            raise ShopError(f"{offer.item.name} is sold out.")
        if player.gold < offer.price:
            raise ShopError(f"You need {offer.price}g but only have {player.gold}g.")
        purchase = offer.item.clone()
        try:
            player.inventory.add(purchase)
        except InventoryFullError:
            raise ShopError("Your inventory is full.") from None
        player.spend_gold(offer.price)
        offer.stock -= 1
        return purchase

    @staticmethod
    def sell(player: Player, item: Item) -> int:
        if player.inventory.find(item.uid) is None:
            raise ShopError(f"You don't have {item.name}.")
        if player.inventory.is_equipped(item):
            raise ShopError(f"Unequip {item.name} before selling it.")
        player.inventory.remove(item.uid, 1)
        price = item.sell_price
        player.add_gold(price)
        return price

    @staticmethod
    def repair_cost(item: Item) -> int:
        if not isinstance(item, (Weapon, Armor)) or item.missing_durability <= 0:
            return 0
        fraction = item.missing_durability / item.max_durability
        return max(1, int(round(max(item.value, 20) * config.REPAIR_COST_RATIO * fraction)))

    def repair(self, player: Player, item: Item) -> int:
        cost = self.repair_cost(item)
        if cost == 0:
            raise ShopError(f"{item.name} doesn't need repairs.")
        if not player.spend_gold(cost):
            raise ShopError(f"Repairs cost {cost}g; you have {player.gold}g.")
        item.repair()  # type: ignore[union-attr]
        return cost
