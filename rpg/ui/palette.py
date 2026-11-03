"""Colors for rich text rendered from Python (log lines, badges, bars).

Layout, borders and widget colors live in ``styles.tcss``; this module covers text that is
built in code. Change these to re-skin the logs without touching any screen.
"""

from __future__ import annotations

from rich.text import Text
from textual.theme import Theme

from rpg.core.attributes import Attribute
from rpg.core.effects import DAMAGE_OVER_TIME, EFFECT_INFO, EffectKind, StatusEffect
from rpg.core.events import LogEvent, Tone

# Focused buttons: no white reverse-video block; styles.tcss gives them a colored edge instead.
THEME_VARIABLES = {"button-focus-text-style": "bold", "block-cursor-text-style": "bold"}


def _theme(name: str, primary: str, secondary: str, accent: str, foreground: str, background: str, surface: str,
           panel: str, success: str, warning: str, error: str) -> Theme:
    return Theme(name=name, primary=primary, secondary=secondary, accent=accent, foreground=foreground,
                 background=background, surface=surface, panel=panel, success=success, warning=warning,
                 error=error, dark=True, variables=dict(THEME_VARIABLES))


EMBER_THEME = _theme("ember", "#E0A458", "#9C7A54", "#D9734E", "#EDE4D3", "#14110E", "#1D1915", "#2A231D",
                     "#86B57F", "#E3B85C", "#D9574B")
# Themes offered on the settings screen (see rpg/services/settings.py THEMES).
THEMES = [
    EMBER_THEME,
    _theme("frost", "#8FC7E8", "#6A8CA8", "#A7D8F0", "#E3ECF2", "#0E1318", "#151C23", "#1E2832",
           "#86C5A8", "#E8D27A", "#E07A7A"),
    _theme("verdant", "#9CC77A", "#6E8F55", "#C8D86A", "#E6EDD9", "#10140E", "#171D14", "#212A1C",
           "#86B57F", "#E3C25C", "#D96B4B"),
    _theme("grave", "#B8A9C9", "#7D7290", "#9E8FB5", "#E2DDE8", "#111014", "#18161D", "#221F29",
           "#8FB59A", "#D8C27A", "#C9606A"),
    _theme("high_contrast", "#FFD25E", "#FFFFFF", "#FF9E3D", "#FFFFFF", "#000000", "#0A0A0A", "#1A1A1A",
           "#6CFF8A", "#FFD25E", "#FF5C5C"),
]

TONE_STYLES: dict[Tone, str] = {
    Tone.INFO: "#C9BFAE",
    Tone.SYSTEM: "italic #8F8574",
    Tone.PLAYER: "#9FD08F",
    Tone.ENEMY: "#E58A6F",
    Tone.DAMAGE: "bold #E8604F",
    Tone.CRIT: "bold #FFB347",
    Tone.MISS: "italic #8F8574",
    Tone.HEAL: "#7FD1A8",
    Tone.MANA: "#7FA8E0",
    Tone.STATUS: "#C99BE8",
    Tone.WARNING: "#E3B85C",
    Tone.REWARD: "bold #F2C46D",
    Tone.LOOT: "#E0A458",
    Tone.GOLD: "bold #F2C46D",
    Tone.XP: "#9FD08F",
    Tone.STORY: "#EDE4D3",
}

EFFECT_STYLES: dict[EffectKind, str] = {
    EffectKind.POISON: "bold #8FD14F",
    EffectKind.BURN: "bold #FF8C42",
    EffectKind.BLEED: "bold #E8604F",
    EffectKind.REGEN: "bold #7FD1A8",
    EffectKind.SHIELD: "bold #7FA8E0",
    EffectKind.BLIND: "bold #A99FBF",
    EffectKind.FROZEN: "bold #9EDCF2",
}

# One color per attribute so lists and bars of stats are easy to tell apart.
ATTRIBUTE_COLORS: dict[Attribute, str] = {
    Attribute.STRENGTH: "#E8604F",  # red
    Attribute.DEXTERITY: "#F2C46D",  # gold
    Attribute.AGILITY: "#86B57F",  # green
    Attribute.VITALITY: "#E58AA0",  # rose
    Attribute.INTELLIGENCE: "#7FA8E0",  # blue
    Attribute.WISDOM: "#C99BE8",  # violet
    Attribute.CHARISMA: "#7FD1C8",  # teal
}

GOLD_STYLE = "bold #F2C46D"
MUTED_STYLE = "#8F8574"
GOOD_STYLE = "#9FD08F"
BAD_STYLE = "#E8604F"


def attribute_bar(attribute: Attribute, value: int, width: int = 18) -> Text:
    """``██████████░░░░░░░░``: filled in the attribute's color on a dim track (20 = full)."""
    filled = max(0, min(width, round(value / 20 * width)))
    return Text.assemble(("█" * filled, ATTRIBUTE_COLORS[attribute]), ("░" * (width - filled), "#3A322A"))


def event_text(event: LogEvent) -> Text:
    return Text(event.text, style=TONE_STYLES.get(event.tone, ""))


def effect_badges(effects: dict[EffectKind, StatusEffect]) -> Text:
    """Compact colored badges, harmful effects first."""
    if not effects:
        return Text("No effects", style=MUTED_STYLE)
    ordered = sorted(effects.values(), key=lambda e: (not EFFECT_INFO[e.kind].harmful, e.kind.value))
    text = Text()
    for i, effect in enumerate(ordered):
        if i:
            text.append("  ")
        style = EFFECT_STYLES.get(effect.kind, "bold")
        text.append(f"[{effect.badge()}]", style=style)
    return text


def is_dot(kind: EffectKind) -> bool:
    return kind in DAMAGE_OVER_TIME


def requirements_text(item, player, long: bool = False) -> Text:
    """Each requirement colored by whether the player meets it: "STR 14 · DEX 13"."""
    if not item.requirements:
        return Text("—", style=MUTED_STYLE)
    text = Text()
    for i, requirement in enumerate(item.requirements):
        if i:
            text.append(", " if long else " · ", style=MUTED_STYLE)
        met = requirement.met_by(player.attributes)
        text.append(requirement.describe() if long else requirement.short(), style=GOOD_STYLE if met else BAD_STYLE)
    return text
