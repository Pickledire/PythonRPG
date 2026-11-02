"""Sidebar HUD showing the player's vitals, attributes and equipment.

It watches ``app.revision`` so any screen that mutates game state only has to call ``app.touch()``.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from rpg.ui.palette import GOLD_STYLE, MUTED_STYLE, effect_badges
from rpg.ui.widgets.stat_bar import StatBar


class PlayerPanel(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("", id="pp-name", classes="panel-title")
        yield Label("", id="pp-sub", classes="panel-subtitle")
        yield StatBar("HP", thresholds=True, id="pp-hp", classes="-hp")
        yield StatBar("MP", id="pp-mp", classes="-mp")
        yield StatBar("XP", id="pp-xp", classes="-xp")
        yield Static(id="pp-gold")
        yield Static(id="pp-attrs", classes="panel-section")
        yield Static(id="pp-gear", classes="panel-section")
        yield Static(id="pp-effects", classes="panel-section")
        yield Static(id="pp-points")

    def on_mount(self) -> None:
        self.border_title = "Adventurer"
        self.watch(self.app, "revision", lambda *_: self.sync(), init=True)

    def sync(self) -> None:
        session = getattr(self.app, "session", None)
        if session is None:
            return
        p = session.player
        self.query_one("#pp-name", Label).update(p.name)
        self.query_one("#pp-sub", Label).update(f"Level {p.level} {p.race}")
        self.query_one("#pp-hp", StatBar).set(p.hp, p.max_hp)
        self.query_one("#pp-mp", StatBar).set(p.mana, p.max_mana)
        self.query_one("#pp-xp", StatBar).set(p.xp, p.xp_required)
        self.query_one("#pp-gold", Static).update(Text(f"◆ {p.gold} gold", style=GOLD_STYLE))

        attrs = Text()
        for i, (attribute, value) in enumerate(p.attributes.items()):
            if i:
                attrs.append("\n" if i == 4 else "  ")
            attrs.append(f"{attribute.short} ", style=MUTED_STYLE)
            attrs.append(f"{value:<2}", style="bold")
        self.query_one("#pp-attrs", Static).update(attrs)

        gear = Text()
        for label, item in (("Weapon", p.weapon), ("Armor", p.armor), ("Spell", p.spell)):
            gear.append(f"{label:<7}", style=MUTED_STYLE)
            if item is None:
                gear.append("—\n", style=MUTED_STYLE)
            else:
                broken = getattr(item, "is_broken", False)
                gear.append(item.name + (" (broken)" if broken else "") + "\n", style="bold red" if broken else "")
        gear.rstrip()
        self.query_one("#pp-gear", Static).update(gear)
        self.query_one("#pp-effects", Static).update(effect_badges(p.effects))
        points = self.query_one("#pp-points", Static)
        points.update(Text(f"★ {p.stat_points} stat point(s) to spend", style="bold #F2C46D") if p.stat_points else "")
        points.display = bool(p.stat_points)
