"""Colors for rich text rendered from Python (log lines, badges, bars).

Layout, borders and widget colors live in ``styles.tcss``; this module covers text that is
built in code. Change these to re-skin the logs without touching any screen.
"""

from __future__ import annotations

from rich.text import Text
from textual.theme import Theme

from rpg.core.effects import DAMAGE_OVER_TIME, EFFECT_INFO, EffectKind, StatusEffect
from rpg.core.events import LogEvent, Tone

EMBER_THEME = Theme(
    name="ember",
    primary="#E0A458",
    secondary="#9C7A54",
    accent="#D9734E",
    foreground="#EDE4D3",
    background="#14110E",
    surface="#1D1915",
    panel="#2A231D",
    success="#86B57F",
    warning="#E3B85C",
    error="#D9574B",
    dark=True,
)

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

GOLD_STYLE = "bold #F2C46D"
MUTED_STYLE = "#8F8574"
GOOD_STYLE = "#9FD08F"
BAD_STYLE = "#E8604F"


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
