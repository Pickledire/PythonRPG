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
    buy_price_multiplier,
    dodge_chance,
    dot_resistance,
    flee_chance,
    heal_power,
    hit_chance,
    player_crit_chance,
    sell_ratio,
    spell_power,
    status_resist_chance,
    weapon_attribute_bonus,
)
from rpg.core.skills import TRAITS, Skill, player_traits, skill_check
from rpg.ui.palette import ATTRIBUTE_COLORS, MUTED_STYLE, attribute_bar
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
        bonus = weapon_attribute_bonus(p.attributes, weapon)
        low = int((base + bonus) * (1 - config.PLAYER_DAMAGE_VARIANCE))
        high = int((base + bonus) * (1 + config.PLAYER_DAMAGE_VARIANCE))

        section("Identity")
        table.add_row("Name", p.name)
        table.add_row("Race", p.race)
        table.add_row("Level", f"{p.level}  ({p.xp}/{p.xp_required} XP)")
        table.add_row("Kills", str(p.kills))
        table.add_row("", "")
        section("Attributes")
        for attribute, value in p.attributes.items():
            table.add_row(Text(attribute.label, style=ATTRIBUTE_COLORS[attribute]),
                          Text.assemble((f"{value:<4}", "bold"), attribute_bar(attribute, value, 10),
                                        (f"  {attribute.description}", MUTED_STYLE)))
        table.add_row("Unspent points", str(p.stat_points))
        table.add_row("", "")
        section("Combat")
        table.add_row("Attack damage", f"{low}–{high}  ({weapon.name if weapon else 'bare fists'})")
        a = p.attributes
        table.add_row("Hit chance", f"{hit_chance(a.dexterity) * 100:.0f}%")
        table.add_row("Crit chance", f"{player_crit_chance(a) * 100:.0f}%  (×{config.CRIT_MULTIPLIER})")
        table.add_row("Dodge chance", f"{dodge_chance(a.agility) * 100:.0f}%")
        table.add_row("Flee chance", f"{flee_chance(a.agility, False) * 100:.0f}% · {flee_chance(a.agility, True) * 100:.0f}% vs bosses")
        mitigation = 1 - armor_mitigation(p.effective_defense(DamageType.PHYSICAL))
        magic_mitigation = 1 - armor_mitigation(p.effective_defense(DamageType.MAGIC))
        table.add_row("Damage blocked", f"{mitigation * 100:.0f}% physical · {magic_mitigation * 100:.0f}% magic")
        table.add_row("Affliction resist", f"{dot_resistance(a.vitality) * 100:.0f}% less poison/burn/bleed damage")
        table.add_row("Status resist", f"{status_resist_chance(a.wisdom) * 100:.0f}% chance to shrug off a harmful effect")
        if p.spell:
            power = (heal_power(p.spell.power, a.wisdom) if p.spell.spell_type.value == "heal"
                     else spell_power(p.spell.power, a.intelligence))
            table.add_row("Equipped spell", f"{p.spell.name}  (power {power}, {p.spell.mana_cost} MP)")
        multiplier = buy_price_multiplier(a.charisma)
        table.add_row("Shop prices", f"×{multiplier:.2f} when buying · sell for {sell_ratio(a.charisma) * 100:.0f}% of value")
        table.add_row("", "")
        section("Skills")
        for skill in Skill:
            check = skill_check(p, skill, 0)
            sources = ", ".join(f"{src.label} {src.amount:+d}" for src in check.sources)
            table.add_row(skill.label, Text.assemble((f"{check.rating:<4}", "bold"),
                                                     (sources or skill.description, MUTED_STYLE)))
        traits = sorted(player_traits(p))
        if traits:
            table.add_row("Traits", Text(", ".join(TRAITS[t].label if t in TRAITS else t for t in traits),
                                         style="#C99BE8"))
        if p.skill_primes:
            primes = ", ".join(f"{Skill(k).label} +{v}" for k, v in p.skill_primes.items())
            table.add_row("Primed", Text(primes + " (next trial)", style="#9FD08F"))
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
