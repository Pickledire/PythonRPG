"""The bestiary: every creature you've met, what it can do, where it lives, and what folk say about it.

What you've met is remembered in ``WorldState.bestiary`` ({creature id: {"seen": n, "defeated": n}}). Lore lives
in ``story/bestiary.yaml`` and shows once you've defeated one. Traits are described in plain words from the
creature's template, so new creatures explain themselves without extra writing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from rpg.core.effects import EffectKind
from rpg.core.enemies import ENEMIES, MAGIC_ARMOR_SHARE, EnemyTemplate
from rpg.core.items import SpellType
from rpg.core.regions import RegionMap
from rpg.core.storydata import StoryDataError, load_yaml
from rpg.core.world import WorldState

ELSEWHERE = "Elsewhere"

ON_HIT = {
    EffectKind.BLEED: "make you bleed", EffectKind.POISON: "poison you", EffectKind.BURN: "set you on fire",
    EffectKind.FROZEN: "freeze you in place (you lose a turn)", EffectKind.BLIND: "blind you (you miss more often)",
    EffectKind.WEAKEN: "weaken you (you deal less damage)", EffectKind.VULNERABLE: "expose you (you take more damage)",
    EffectKind.SILENCE: "silence you (no spells)",
}
SPELL_WORDS = {
    SpellType.DAMAGE: "a damaging spell", SpellType.HEAL: "heals itself", SpellType.SHIELD: "puts up a ward",
    SpellType.BLIND: "blinds you (you miss more often)", SpellType.POISON: "poisons you",
    SpellType.BURN: "sets you on fire", SpellType.BLEED: "makes you bleed",
    SpellType.FREEZE: "freezes you in place (you lose a turn)", SpellType.REGEN: "regenerates",
    SpellType.HASTE: "speeds itself up (acts twice a turn)", SpellType.WEAKEN: "weakens you (you deal less damage)",
    SpellType.VULNERABLE: "exposes you (you take more damage)", SpellType.SILENCE: "silences you (no spells)",
    SpellType.CLEANSE: "shakes off its ailments",
}
IMMUNE_WORDS = {
    EffectKind.POISON: "poison", EffectKind.BLEED: "bleeding", EffectKind.BURN: "fire", EffectKind.FROZEN: "freezing",
    EffectKind.BLIND: "blinding", EffectKind.SILENCE: "silence", EffectKind.WEAKEN: "weakening",
    EffectKind.VULNERABLE: "exposure",
}


def load_lore(path: Path) -> tuple[dict[str, str], list[str]]:
    if not Path(path).is_file():
        return {}, []
    try:
        raw = load_yaml(Path(path)) or {}
    except StoryDataError as exc:
        return {}, [str(exc)]
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}, []


def record(world: WorldState, template_id: str, *, defeated: bool = False) -> bool:
    """Count a meeting (or a kill). Returns True the first time a creature is met."""
    entry = world.bestiary.setdefault(template_id, {"seen": 0, "defeated": 0})
    first = entry["seen"] == 0
    if defeated:
        entry["defeated"] += 1
        entry["seen"] = max(entry["seen"], 1)
    else:
        entry["seen"] += 1
    return first


def habitats(regions: RegionMap, template_id: str) -> list[str]:
    """Regions (in map order) where hunting can turn it up."""
    return [r.region_id for r in regions.regions.values() if any(e == template_id for e, _ in r.hunt)]


def traits(template: EnemyTemplate) -> list[str]:
    """What a player should know, in plain words."""
    lines: list[str] = []
    resist = dict(template.resist)
    for kind, words in (("physical", "weapons"), ("magic", "spells")):
        share = resist.get(kind, 0.0)
        if share > 0:
            lines.append(f"Shrugs off {round(share * 100)}% of damage from {words}.")
        elif share < 0:
            lines.append(f"Weak to {words}: takes {round(-share * 100)}% more damage from them.")
    low, high = template.defense if isinstance(template.defense, tuple) else (template.defense, template.defense)
    if (low + high) / 2 >= template.level * 0.7 + 6:
        lines.append(f"Heavily armoured. Spells ignore {round((1 - MAGIC_ARMOR_SHARE) * 100)}% of armour; "
                     "blades don't.")
    elif high <= 2:
        lines.append("Barely armoured.")
    for spec in template.on_hit:
        lines.append(f"Its attacks have a {round(spec.chance * 100)}% chance to {ON_HIT.get(spec.kind, spec.kind.value)}.")
    for make in template.spellbook:
        spell = make()
        words = SPELL_WORDS.get(spell.spell_type, spell.spell_type.value)
        if spell.drain:
            words += ", and heals itself with it"
        lines.append(f"Casts {spell.name}: {words}.")
    if template.regen_pct:
        lines.append(f"Heals {round(template.regen_pct * 100)}% of its health every turn (not while burning).")
    if template.lifesteal:
        lines.append(f"Heals itself for {round(template.lifesteal * 100)}% of the damage it deals.")
    if template.thorns:
        lines.append(f"Cuts back: {round(template.thorns * 100)}% of weapon damage comes back at you.")
    for spec in template.starts_with:
        lines.append({EffectKind.HASTE: "Starts the fight fast (acts twice at first).",
                      EffectKind.SHIELD: "Starts the fight behind a ward."}.get(spec.kind, f"Starts with {spec.kind.value}."))
    immune = [IMMUNE_WORDS[k] for k in template.immune if k in IMMUNE_WORDS]
    if immune:
        lines.append("Immune to " + _join(immune) + ".")
    return lines or ["Nothing unusual. Hit it until it stops."]


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


@dataclass
class Entry:
    template: EnemyTemplate
    seen: int
    defeated: int
    habitats: list[str] = field(default_factory=list)
    lore: str = ""

    @property
    def template_id(self) -> str:
        return self.template.template_id


def entries(world: WorldState, regions: RegionMap, lore: dict[str, str]) -> dict[str, list[Entry]]:
    """Creatures met, grouped by the first region (in map order) they live in; the rest under ELSEWHERE."""
    groups: dict[str, list[Entry]] = {r: [] for r in regions.regions}
    groups[ELSEWHERE] = []
    for template_id, counts in world.bestiary.items():
        template = ENEMIES.templates.get(template_id)
        if template is None or not counts.get("seen"):
            continue
        homes = habitats(regions, template_id)
        groups[homes[0] if homes else ELSEWHERE].append(
            Entry(template, int(counts.get("seen", 0)), int(counts.get("defeated", 0)), homes, lore.get(template_id, "")))
    for items in groups.values():
        items.sort(key=lambda e: (e.template.level, e.template.name))
    return groups


def totals(regions: RegionMap) -> dict[str, int]:
    """How many different creatures each region holds (for "4 of 15 met")."""
    return {r.region_id: len(r.hunt) for r in regions.regions.values()}


def at_level(template_id: str, level: int) -> tuple[int, int]:
    """About how much health it has and how hard it hits at ``level`` (no elite modifiers)."""
    enemy = ENEMIES.create(template_id, random.Random(0), level)
    return enemy.max_hp, enemy.base_damage
