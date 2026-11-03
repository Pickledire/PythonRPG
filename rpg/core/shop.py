"""Rotating shops with buying, selling and repairs."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from rpg import config
from rpg.core.catalog import (
    GENERAL_SHOP_COUNTS,
    GENERAL_SHOP_POOLS,
    GENERAL_SHOP_STAPLES,
    ITEMS,
    MAGIC_SHOP_COUNTS,
    MAGIC_SHOP_EXTRAS,
    MAGIC_SHOP_SPELLS,
)
from rpg.core.entities import Player
from rpg.core.formulas import buy_price_multiplier, sell_ratio
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

    def rotate(self, seed: int, unlocks: set[str] | None = None, level: int | None = None) -> bool:
        """Restock from the pools. Only happens when the seed (world time) changes, so purchases stick.

        With ``level``, gear is drawn from what suits that level (see ``stock_ceiling``): mostly affordable
        upgrades, with a little aspirational stock above.
        """
        if seed == self._seed:
            return False
        self._seed = seed
        rng = random.Random(seed * 7919 + (1 if self.mode == ShopMode.MAGIC else 0))
        self.offers = []
        if self.mode == ShopMode.GENERAL:
            for category, count in GENERAL_SHOP_COUNTS.items():
                stock = UNLIMITED if category == "consumable" else 1
                for template_id in self._pick(GENERAL_SHOP_POOLS[category], count, rng, level, category):
                    self._offer(template_id, stock)
            for template_id in GENERAL_SHOP_STAPLES:
                if not any(o.item.template_id == template_id for o in self.offers):
                    self._offer(template_id, UNLIMITED)
            for template_id in sorted(unlocks or ()):
                if template_id in ITEMS and not any(o.item.template_id == template_id for o in self.offers):
                    self._offer(template_id, 1)
        else:
            for template_id in self._pick(MAGIC_SHOP_SPELLS, MAGIC_SHOP_COUNTS["spell"], rng, level, "spell"):
                self._offer(template_id, 1)
            pool = GENERAL_SHOP_POOLS["consumable"]
            for template_id in rng.sample(pool, k=min(MAGIC_SHOP_COUNTS["consumable"], len(pool))):
                self._offer(template_id, UNLIMITED)
            for category, pool in MAGIC_SHOP_EXTRAS.items():
                for template_id in self._pick(pool, MAGIC_SHOP_COUNTS[category], rng, level, category):
                    self._offer(template_id, 1)
        return True

    @staticmethod
    def stock_ceiling(level: int) -> int:
        """Most expensive gear a shop usually stocks at this level (about two tiers of headroom)."""
        return 80 + level * 40

    def _pick(self, pool: list[str], count: int, rng: random.Random, level: int | None, category: str) -> list[str]:
        if level is None or category == "consumable":
            return rng.sample(pool, k=min(count, len(pool)))
        ceiling = self.stock_ceiling(level)
        fitting = [t for t in pool if ITEMS.create(t).value <= ceiling]
        if len(fitting) < count:
            fitting = sorted(pool, key=lambda t: ITEMS.create(t).value)[:max(count, len(fitting))]
        # Favour pieces near the top of what fits: that's where upgrades live.
        weights = [1 + ITEMS.create(t).value / ceiling * 3 for t in fitting]
        chosen: list[str] = []
        while fitting and len(chosen) < count:
            pick = rng.choices(fitting, weights=weights, k=1)[0]
            index = fitting.index(pick)
            fitting.pop(index)
            weights.pop(index)
            chosen.append(pick)
        return chosen

    def _offer(self, template_id: str, stock: int) -> None:
        item = ITEMS.create(template_id)
        self.offers.append(Offer(item, item.value, stock))

    def offers_of_kind(self, kind: ItemKind | None = None) -> list[Offer]:
        return [o for o in self.offers if kind is None or o.item.kind == kind]

    # ------------------------------------------------------------ prices (Charisma haggles)
    @staticmethod
    def price_for(offer: Offer, player: Player) -> int:
        return max(1, int(round(offer.price * buy_price_multiplier(player.attributes.charisma))))

    @staticmethod
    def sell_price_for(item: Item, player: Player) -> int:
        return max(1, int(item.value * sell_ratio(player.attributes.charisma)))

    # ------------------------------------------------------------ transactions
    def buy(self, player: Player, offer: Offer) -> Item:
        if offer not in self.offers:
            raise ShopError("That item is no longer on sale.")
        if offer.sold_out:
            raise ShopError(f"{offer.item.name} is sold out.")
        price = self.price_for(offer, player)
        if player.gold < price:
            raise ShopError(f"You need {price}g but only have {player.gold}g.")
        purchase = offer.item.clone()
        try:
            player.inventory.add(purchase)
        except InventoryFullError:
            raise ShopError("Your inventory is full.") from None
        player.spend_gold(price)
        offer.stock -= 1
        return purchase

    @classmethod
    def sell(cls, player: Player, item: Item) -> int:
        if player.inventory.find(item.uid) is None:
            raise ShopError(f"You don't have {item.name}.")
        if player.inventory.is_equipped(item):
            raise ShopError(f"Unequip {item.name} before selling it.")
        player.inventory.remove(item.uid, 1)
        price = cls.sell_price_for(item, player)
        player.add_gold(price)
        return price

    @staticmethod
    def repair_cost(item: Item, player: Player | None = None) -> int:
        if not isinstance(item, (Weapon, Armor)) or item.missing_durability <= 0:
            return 0
        fraction = item.missing_durability / item.max_durability
        cost = max(item.value, 20) * config.REPAIR_COST_RATIO * fraction
        if player is not None:
            cost *= buy_price_multiplier(player.attributes.charisma)
        return max(1, int(round(cost)))

    def repair(self, player: Player, item: Item) -> int:
        cost = self.repair_cost(item, player)
        if cost == 0:
            raise ShopError(f"{item.name} doesn't need repairs.")
        if not player.spend_gold(cost):
            raise ShopError(f"Repairs cost {cost}g; you have {player.gold}g.")
        item.repair()  # type: ignore[union-attr]
        return cost
