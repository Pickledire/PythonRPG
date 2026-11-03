"""Passive bonuses granted by worn equipment (amulets, rings, armor, weapons, trinkets).

An item lists them as ``passives={"regen_pct": 0.03, "immune_poison": 1}``. While the item is equipped the
player sums every passive (``Player.passive("regen_pct")``) and the rules read them at the matching hook:

=================  =========================================================  ======================
key                effect                                                      read by
=================  =========================================================  ======================
max_hp, max_mana   flat pool increase while worn                               Player.refresh_gear
regen_pct          heal this share of max HP at the start of your turn        combat tick
mana_regen         restore this much mana at the start of your turn           combat tick
crit               + critical hit chance                                       formulas
crit_damage        + critical damage multiplier                                combat
accuracy           + hit chance                                                combat
dodge              + chance to avoid weapon attacks                            Player.dodge
armor              + flat defense                                              Player.effective_defense
weapon_damage      + share of weapon damage                                    combat
spell_power        + share of spell damage and spell DoT strength             combat
healing            + share of all healing you cast or drink                    combat / consumables
lifesteal          heal this share of weapon damage dealt                      combat
thorns             reflect this share of weapon damage taken                   combat
execute            + damage against enemies below 30% HP                       combat
dot_power          + share of damage-over-time you inflict                     combat
dot_resist         - share of damage-over-time you take                        Player.dot_multiplier
status_resist      + chance to resist harmful effects                          Player.status_resist
resist_physical    - share of physical damage taken                            Player.mitigate
resist_magic       - share of magic damage taken                               Player.mitigate
mana_cost          - share of spell mana costs                                 combat
start_ward         start each fight behind a ward of this strength (2 turns)  combat start
start_haste        start each fight hasted (1 turn)                            combat start
flee               + chance to escape                                          combat
gold_find          + share of gold from victories                              progression
xp_gain            + share of XP from victories                                progression
immune_<effect>    immunity to that status effect (poison, burn, bleed, ...)  combat
=================  =========================================================  ======================
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg.core.effects import EFFECT_INFO, EffectInfo, EffectKind


@dataclass(frozen=True)
class PassiveInfo:
    label: str
    style: str  # "flat", "pct" or "flag"
    cap: float | None = None  # sums above this are clamped


PASSIVES: dict[str, PassiveInfo] = {
    "max_hp": PassiveInfo("Max HP", "flat"),
    "max_mana": PassiveInfo("Max mana", "flat"),
    "regen_pct": PassiveInfo("Regenerate HP/turn", "pct", 0.08),
    "mana_regen": PassiveInfo("Mana/turn", "flat"),
    "crit": PassiveInfo("Crit chance", "pct", 0.25),
    "crit_damage": PassiveInfo("Crit damage", "pct"),
    "accuracy": PassiveInfo("Accuracy", "pct", 0.2),
    "dodge": PassiveInfo("Dodge", "pct", 0.15),
    "armor": PassiveInfo("Armor", "flat"),
    "weapon_damage": PassiveInfo("Weapon damage", "pct"),
    "spell_power": PassiveInfo("Spell power", "pct"),
    "healing": PassiveInfo("Healing", "pct"),
    "lifesteal": PassiveInfo("Lifesteal", "pct", 0.3),
    "thorns": PassiveInfo("Thorns", "pct", 0.5),
    "execute": PassiveInfo("Damage vs wounded foes", "pct"),
    "dot_power": PassiveInfo("Damage-over-time power", "pct"),
    "dot_resist": PassiveInfo("Damage-over-time resistance", "pct", 0.6),
    "status_resist": PassiveInfo("Status resistance", "pct", 0.5),
    "resist_physical": PassiveInfo("Physical resistance", "pct", 0.4),
    "resist_magic": PassiveInfo("Magic resistance", "pct", 0.5),
    "mana_cost": PassiveInfo("Spell mana cost", "pct", 0.5),
    "start_ward": PassiveInfo("Opening ward", "pct", 0.6),
    "start_haste": PassiveInfo("Opening haste", "flag"),
    "flee": PassiveInfo("Escape chance", "pct"),
    "gold_find": PassiveInfo("Gold found", "pct"),
    "xp_gain": PassiveInfo("Experience", "pct"),
}
for _kind in EffectKind:
    if EFFECT_INFO[_kind].harmful:
        PASSIVES[f"immune_{_kind.value}"] = PassiveInfo(f"Immune to {EFFECT_INFO[_kind].label.lower()}", "flag")

# "less is better" passives are shown with a minus sign
NEGATIVE_DISPLAY = {"mana_cost"}


def passive_text(key: str, value: float) -> str:
    info = PASSIVES.get(key)
    if info is None:
        return f"{key} {value:g}"
    if info.style == "flag":
        return info.label
    if info.style == "pct":
        sign = "-" if key in NEGATIVE_DISPLAY else "+"
        return f"{info.label} {sign}{abs(value) * 100:g}%"
    return f"{info.label} {value:+g}"


def clamp_total(key: str, total: float) -> float:
    info = PASSIVES.get(key)
    if info and info.cap is not None:
        return min(info.cap, total)
    return total


def immunity_key(kind: EffectKind) -> str:
    return f"immune_{kind.value}"


def effect_info(kind: EffectKind) -> EffectInfo:
    return EFFECT_INFO[kind]
