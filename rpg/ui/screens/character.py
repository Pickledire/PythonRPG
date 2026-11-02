"""Character sheet: attributes, derived combat numbers, progress and stat point spending."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from rpg import config
from rpg.core.entities import DamageType
from rpg.core.formulas import (
    armor_mitigation,
    heal_power,
    hit_chance,
    player_crit_chance,
    spell_power,
    weapon_attribute_bonus,
)
from rpg.ui.palette import MUTED_STYLE
from rpg.ui.widgets import PlayerPanel


class CharacterScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("p", "spend", "Spend points")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(classes="split-root"):
            yield PlayerPanel()
            with Vertical(classes="split-main"):
                yield Label("Character", classes="screen-title")
                with VerticalScroll(id="sheet-scroll"):
                    yield Static(id="sheet")
                with Horizontal(classes="button-row"):
                    yield Button("Spend stat points", variant="primary", id="spend")
                    yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.watch(self.app, "revision", lambda *_: self.refresh_sheet(), init=True)

    def refresh_sheet(self) -> None:
        session = self.app.session
        if session is None:
            return
        p, world = session.player, session.world
        self.query_one("#spend", Button).disabled = p.stat_points == 0

        table = Table.grid(padding=(0, 2))
        table.add_column(style=MUTED_STYLE)
        table.add_column(style="bold")

        def section(title: str) -> None:
            table.add_row(Text(title, style="bold #E0A458"), "")

        weapon = p.weapon if p.weapon and not p.weapon.is_broken else None
        base = weapon.effective_damage if weapon else config.UNARMED_DAMAGE
        bonus = weapon_attribute_bonus(p.attributes, weapon.weapon_class if weapon else None)
        low = int((base + bonus) * (1 - config.PLAYER_DAMAGE_VARIANCE))
        high = int((base + bonus) * (1 + config.PLAYER_DAMAGE_VARIANCE))

        section("Identity")
        table.add_row("Name", p.name)
        table.add_row("Race", p.race)
        table.add_row("Level", f"{p.level}  ({p.xp}/{p.xp_required} XP)")
        table.add_row("Kills", str(p.kills))
        table.add_row("", "")
        section("Attributes")
        table.add_row("Strength", f"{p.attributes.strength}   melee damage, crit chance")
        table.add_row("Agility", f"{p.attributes.agility}   accuracy, ranged damage")
        table.add_row("Intelligence", f"{p.attributes.intelligence}   spell power, staves")
        table.add_row("Unspent points", str(p.stat_points))
        table.add_row("", "")
        section("Combat")
        table.add_row("Attack damage", f"{low}–{high}  ({weapon.name if weapon else 'bare fists'})")
        table.add_row("Hit chance", f"{hit_chance(p.attributes.agility) * 100:.0f}%")
        table.add_row("Crit chance", f"{player_crit_chance(p.attributes.strength) * 100:.0f}%  (×{config.CRIT_MULTIPLIER})")
        mitigation = 1 - armor_mitigation(p.effective_defense(DamageType.PHYSICAL))
        magic_mitigation = 1 - armor_mitigation(p.effective_defense(DamageType.MAGIC))
        table.add_row("Damage blocked", f"{mitigation * 100:.0f}% physical · {magic_mitigation * 100:.0f}% magic")
        if p.spell:
            power = (heal_power(p.spell.power, p.attributes.intelligence) if p.spell.spell_type.value == "heal"
                     else spell_power(p.spell.power, p.attributes.intelligence))
            table.add_row("Equipped spell", f"{p.spell.name}  (power {power}, {p.spell.mana_cost} MP)")
        table.add_row("", "")
        section("World")
        table.add_row("Time", world.time_label)
        bosses = ", ".join(sorted(b.replace("_", " ").title() for b in world.bosses_defeated)) or "none yet"
        table.add_row("Bosses slain", bosses)
        upcoming = session.pending_boss()
        next_boss = next(((lvl, b) for lvl, b in sorted(config.MILESTONE_BOSSES) if b not in world.bosses_defeated), None)
        if upcoming:
            table.add_row("Next hunt", Text(f"{upcoming.replace('_', ' ').title()} awaits!", style="bold #E8604F"))
        elif next_boss:
            table.add_row("Next boss", f"{next_boss[1].replace('_', ' ').title()} at level {next_boss[0]}")
        self.query_one("#sheet", Static).update(table)

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#spend")
    def action_spend(self) -> None:
        self._spend()

    @work
    async def _spend(self) -> None:
        await self.app.resolve_level_ups()
