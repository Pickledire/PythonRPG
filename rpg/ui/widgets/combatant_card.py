"""Card showing one side of a fight: name, bars and active effects."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from rpg.core.enemies import Enemy
from rpg.core.entities import Combatant, Player
from rpg.ui.palette import MUTED_STYLE, effect_badges
from rpg.ui.widgets.stat_bar import StatBar


class CombatantCard(Vertical):
    def __init__(self, combatant: Combatant, *, id: str | None = None) -> None:
        classes = "combatant-card " + ("-player" if isinstance(combatant, Player) else "-enemy")
        if isinstance(combatant, Enemy) and combatant.is_boss:
            classes += " -boss"
        super().__init__(id=id, classes=classes)
        self.combatant = combatant

    def compose(self) -> ComposeResult:
        yield Label("", classes="card-name")
        yield Label("", classes="card-sub")
        yield StatBar("HP", thresholds=True, classes="-hp card-hp")
        if isinstance(self.combatant, Player):
            yield StatBar("MP", classes="-mp card-mp")
        yield Static(classes="card-effects")
        yield Static(classes="card-extra")

    def on_mount(self) -> None:
        self.sync()

    def sync(self) -> None:
        c = self.combatant
        self.query_one(".card-name", Label).update(c.name)
        extra = Text()
        if isinstance(c, Player):
            sub = f"Level {c.level} {c.race}"
            weapon = c.weapon
            extra.append("Weapon ", style=MUTED_STYLE)
            extra.append(f"{weapon.name} ({weapon.durability}/{weapon.max_durability})" if weapon else "Bare fists")
            if c.armor:
                extra.append("\nArmor  ", style=MUTED_STYLE)
                extra.append(f"{c.armor.name} ({c.armor.durability}/{c.armor.max_durability})")
            self.query_one(".card-mp", StatBar).set(c.mana, c.max_mana)
        else:
            assert isinstance(c, Enemy)
            sub = c.enemy_type.capitalize() + (f" · Boss level {c.level}" if c.is_boss else "")
            extra.append(f"DMG {c.base_damage} · DEF {c.defense} · STR {c.attributes.strength} · AGI {c.attributes.agility}",
                         style=MUTED_STYLE)
            if c.affixes:
                extra.append("\n" + " · ".join(c.affixes), style="bold #E3B85C")
        self.query_one(".card-sub", Label).update(sub)
        self.query_one(".card-hp", StatBar).set(c.hp, c.max_hp)
        self.query_one(".card-effects", Static).update(effect_badges(c.effects))
        self.query_one(".card-extra", Static).update(extra)
