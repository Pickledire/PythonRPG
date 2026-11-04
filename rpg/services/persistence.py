"""JSON save slots with atomic writes and migration of saves from the original game (v1)."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rpg import config
from rpg.core.catalog import ITEMS
from rpg.core.effects import StatusEffect
from rpg.core.items import ItemKind
from rpg.core.session import GameSession


class SaveError(Exception):
    pass


@dataclass(frozen=True)
class SlotInfo:
    slot: int
    exists: bool
    name: str = ""
    race: str = ""
    level: int = 0
    saved_at: str = ""
    legacy: bool = False
    error: str = ""

    @property
    def label(self) -> str:
        slot = "Autosave" if self.slot == config.AUTOSAVE_SLOT else f"Slot {self.slot}"
        if not self.exists:
            return f"{slot} — empty"
        if self.error:
            return f"{slot} — unreadable ({self.error})"
        when = f" · {self.saved_at}" if self.saved_at else ""
        legacy = " · from the original game" if self.legacy else ""
        return f"{slot} — {self.name}, level {self.level} {self.race}{when}{legacy}"


class SaveManager:
    def __init__(self, directory: Path | None = None, slots: int = config.SAVE_SLOTS) -> None:
        self.directory = Path(directory or config.SAVE_DIR)
        self.slots = slots

    def path(self, slot: int) -> Path:
        if slot == config.AUTOSAVE_SLOT:
            return self.directory / "autosave.json"
        if not 1 <= slot <= self.slots:
            raise SaveError(f"Slot must be between 1 and {self.slots}")
        return self.directory / f"slot{slot}.json"

    # ------------------------------------------------------------ listing
    def list_slots(self, include_autosave: bool = False) -> list[SlotInfo]:
        """The player's slots; with ``include_autosave``, the autosave first (when there is one)."""
        infos = [self.slot_info(slot) for slot in range(1, self.slots + 1)]
        if include_autosave:
            auto = self.slot_info(config.AUTOSAVE_SLOT)
            if auto.exists:
                infos.insert(0, auto)
        return infos

    def slot_info(self, slot: int) -> SlotInfo:
        path = self.path(slot)
        if not path.is_file():
            return SlotInfo(slot, False)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if int(data.get("version", 1)) < 2:
                p = data.get("player", {})
                return SlotInfo(slot, True, p.get("name", "?"), p.get("race", "?"), int(p.get("level", 1)), legacy=True)
            p = data["player"]
            return SlotInfo(slot, True, p["name"], p["race"], int(p["level"]), data.get("saved_at", ""))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return SlotInfo(slot, True, error=type(exc).__name__)

    def any_saves(self) -> bool:
        return any(info.exists and not info.error for info in self.list_slots(include_autosave=True))

    # ------------------------------------------------------------ save / load
    def save(self, session: GameSession, slot: int) -> Path:
        return self.save_payload(session.to_dict(), slot)

    def save_payload(self, payload: dict, slot: int) -> Path:
        """Write save data (``GameSession.to_dict()`` or a ``snapshot()`` taken earlier) to a slot."""
        path = self.path(slot)
        payload = dict(payload, saved_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".slot{slot}-", suffix=".json", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, path)  # atomic: a crash mid-save never corrupts the old file
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
        return path

    def load(self, slot: int) -> GameSession:
        path = self.path(slot)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SaveError(f"Slot {slot} is empty.") from None
        except (OSError, ValueError) as exc:
            raise SaveError(f"Slot {slot} could not be read: {exc}") from None
        try:
            if int(data.get("version", 1)) < 2:
                data = migrate_v1(data)
            return GameSession.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise SaveError(f"Slot {slot} is damaged: {exc}") from None

    def delete(self, slot: int) -> None:
        self.path(slot).unlink(missing_ok=True)


# ------------------------------------------------------------------ migration from the original game
_V1_KIND = {"weapon": ItemKind.WEAPON, "armor": ItemKind.ARMOR, "consumable": ItemKind.CONSUMABLE, "magic": ItemKind.SPELL}


def _migrate_item(old: dict) -> dict:
    kind = _V1_KIND.get(old.get("type", ""), ItemKind.MISC)
    template_id = ITEMS.find_id_by_name(old.get("name", "")) or f"legacy:{old.get('name', 'item')}"
    item = {"kind": kind.value, "template_id": template_id, "name": old.get("name", "Item"),
            "value": int(old.get("value", 0)), "description": old.get("description", "")}
    if kind == ItemKind.WEAPON:
        item.update(damage=int(old.get("damage", 1)), weapon_class=old.get("weapon_type", "melee"),
                    max_durability=int(old.get("max_durability", 100)), durability=int(old.get("durability", 100)))
        if template_id in ITEMS:
            item["on_hit"] = ITEMS.create(template_id).to_dict().get("on_hit")
    elif kind == ItemKind.ARMOR:
        item.update(defense=int(old.get("defense", 0)), max_durability=int(old.get("max_durability", 100)),
                    durability=int(old.get("durability", 100)))
    elif kind == ItemKind.CONSUMABLE:
        effect = old.get("effect_type", "heal")
        item.update(effect=effect if effect in ("heal", "mana", "restore", "cure") else "heal",
                    potency=int(old.get("effect_value", 0)))
    elif kind == ItemKind.SPELL:
        item.update(spell_type=old.get("spell_type", "damage"), power=int(old.get("damage", 0)),
                    mana_cost=int(old.get("mana", 10)))
        if template_id in ITEMS:
            item["inflicts"] = ITEMS.create(template_id).to_dict().get("inflicts")
    return item


def migrate_v1(data: dict) -> dict:
    """Convert a save written by the original terminal game into the v2 format."""
    p = data.get("player", {})
    inv = p.get("inventory", {})
    stacks, by_name = [], {}
    for index, entry in enumerate(inv.get("items", [])):
        old = entry.get("item")
        if not old:
            continue
        item = _migrate_item(old)
        qty = max(1, int(entry.get("quantity", 1)))
        if item["kind"] in ("consumable", "misc"):
            item["uid"] = f"legacy{index}"
            stacks.append({"item": item, "quantity": qty})
            by_name.setdefault(item["name"], item["uid"])
        else:
            for n in range(qty):  # old saves stacked gear; split into individual items
                copy = dict(item, uid=f"legacy{index}_{n}")
                stacks.append({"item": copy, "quantity": 1})
                by_name.setdefault(copy["name"], copy["uid"])

    equipped = {}
    for slot, key in (("weapon", "equipped_weapon"), ("armor", "equipped_armor"), ("spell", "equipped_magic")):
        name = inv.get(key)
        equipped[slot] = by_name.get(name) if name else None

    effects = []
    for kind, raw in (p.get("status_effects") or {}).items():
        mapped = {"shield": ("shield", raw.get("reduction_pct", 0.35)), "blind": ("blind", raw.get("accuracy_penalty", 0.25)),
                  "frozen": ("frozen", 0), "burn": ("burn", raw.get("damage", 6)), "poison": ("poison", raw.get("damage", 5))}
        if kind in mapped:
            effects.append(StatusEffect.from_dict({"kind": mapped[kind][0], "turns": raw.get("turns", 1),
                                                   "potency": mapped[kind][1]}).to_dict())

    old_flags = data.get("flags", {})
    bosses = {boss for flag, boss in (("level_10_boss", "titan"), ("level_15_boss", "elder_dragon"),
                                      ("level_20_boss", "earth_eater_worm"), ("level_25_boss", "rat_king"))
              if old_flags.get(flag)}
    quest_flags = dict(data.get("quest_flags", {}))
    unlocks = quest_flags.pop("shop_unlocks", [])
    return {
        "version": config.SAVE_VERSION,
        "player": {
            "name": p.get("name") or "Adventurer", "race": p.get("race") or "Human",
            "level": int(p.get("level", 1)), "xp": int(p.get("xp", 0)), "gold": int(p.get("gold", 0)),
            "hp": int(p.get("health", 100)), "max_hp": int(p.get("max_health", 100)),
            "mana": int(p.get("mana", 100)), "max_mana": int(p.get("max_mana", 100)),
            "attributes": p.get("stats", {}), "stat_points": 0, "kills": int(p.get("kills", 0)),
            "effects": effects,
            "inventory": {"stacks": stacks, "equipped": equipped},
        },
        "world": {
            "bell": int(data.get("world_bells", config.START_BELL)), "flags": quest_flags,
            "shop_unlocks": [ITEMS.find_id_by_name(u) or u for u in unlocks if (ITEMS.find_id_by_name(u) or u) in ITEMS],
            "bosses_defeated": sorted(bosses), "ghost_horror_seen": bool(old_flags.get("ghost_horror", False)),
        },
    }
