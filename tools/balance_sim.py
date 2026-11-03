"""Balance simulator: bots play the real rules engine (no UI, no quests) and report how the numbers behave.

    python tools/balance_sim.py progression --runs 40     # every race x build, hunt from level 1 to the Rat King
    python tools/balance_sim.py arena                     # fixed-level duels against every enemy
    python tools/balance_sim.py gear                      # static tables: weapon, armor and spell efficiency

The combat bot plays like a careful human: potions when low, cures when it matters, picks between attacking and
each castable spell by expected value, keeps damage-over-time ticking, wards against heavy hitters. The
progression bot hunts, rests, shops (upgrades, potions, repairs), sells junk and spends stat points by build.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import config  # noqa: E402
from rpg.core.attributes import Attribute  # noqa: E402
from rpg.core.catalog import GENERAL_SHOP_POOLS, ITEMS, MAGIC_SHOP_SPELLS  # noqa: E402
from rpg.core.combat import Attack, CastSpell, CombatSession, Flee, Phase, UseItem  # noqa: E402
from rpg.core.effects import CLEANSABLE, DAMAGE_OVER_TIME, EffectKind  # noqa: E402
from rpg.core.enemies import ENEMIES, Enemy  # noqa: E402
from rpg.core.entities import DamageType, Player  # noqa: E402
from rpg.core.catalog import bonus_value  # noqa: E402
from rpg.core.combat import caster_multiplier, mana_cost  # noqa: E402
from rpg.core.formulas import (  # noqa: E402
    armor_mitigation,
    heal_multiplier,
    heal_power,
    hit_chance,
    player_crit_chance,
    spell_power,
    weapon_attribute_bonus,
    xp_to_next,
)
from rpg.core.items import Accessory, Armor, Consumable, ConsumableEffect, Spell, SpellType, Weapon  # noqa: E402
from rpg.core.session import Encounter, GameSession  # noqa: E402
from rpg.core.shop import Shop, ShopError, ShopMode  # noqa: E402

A = Attribute

# ------------------------------------------------------------------ builds
BUILDS: dict[str, dict[Attribute, float]] = {
    # stat point weights: the next point goes to the attribute furthest below its share
    "warrior": {A.STRENGTH: 4, A.VITALITY: 3, A.DEXTERITY: 1, A.AGILITY: 1},
    "ranger": {A.DEXTERITY: 4, A.AGILITY: 2, A.VITALITY: 2, A.STRENGTH: 1},
    "mage": {A.INTELLIGENCE: 4, A.WISDOM: 3, A.VITALITY: 2},
    "spellblade": {A.STRENGTH: 3, A.INTELLIGENCE: 3, A.VITALITY: 2, A.WISDOM: 1},
}
NATIVE_BUILD = {"Human": "warrior", "Elf": "mage", "Orc": "warrior", "Dwarf": "warrior", "Druid": "mage",
                "Halfling": "ranger", "Gnome": "mage", "Dragonkin": "warrior", "Beastkin": "ranger",
                "Revenant": "spellblade"}
CASTERS = {"mage", "spellblade"}


def spend_points(player: Player, build: str) -> None:
    weights = BUILDS[build]
    total = sum(weights.values())
    while player.stat_points > 0:
        best = min(weights, key=lambda a: player.attributes.get(a) / (weights[a] / total))
        player.spend_stat_point(best)


# ------------------------------------------------------------------ evaluation helpers
def attack_value(player: Player, weapon: Weapon | None, enemy: Enemy | None = None) -> float:
    base = weapon.effective_damage if weapon and not weapon.is_broken else config.UNARMED_DAMAGE
    raw = (base + weapon_attribute_bonus(player.attributes, weapon if weapon and not weapon.is_broken else None))
    raw *= 1 + player.passive("weapon_damage")
    crit = player_crit_chance(player.attributes) + player.passive("crit")
    blind = enemy.has_effect(EffectKind.BLIND) if enemy else False
    per_hit = raw * (1 + crit * (config.CRIT_MULTIPLIER + player.passive("crit_damage") - 1))
    if enemy is not None:
        magic = weapon is not None and weapon.weapon_class.value == "magic"
        per_hit = enemy.mitigate(int(per_hit), DamageType.MAGIC if magic else DamageType.PHYSICAL)
        if enemy.has_effect(EffectKind.VULNERABLE):
            per_hit *= 1 + enemy.effects[EffectKind.VULNERABLE].potency
    else:
        per_hit *= armor_mitigation(8)
    on_hit = 0.0
    if weapon and weapon.on_hit:
        on_hit = weapon.on_hit.chance * max(weapon.on_hit.potency * weapon.on_hit.turns, 15) * 0.6
    to_hit = min(0.99, hit_chance(player.attributes.dexterity, player.blind_penalty(), blind) + player.passive("accuracy"))
    return to_hit * (per_hit + on_hit)


def incoming_estimate(enemy: Enemy) -> float:
    return enemy.base_damage + enemy.attributes.strength * 0.3 + enemy.attributes.agility * 0.2


def effect_worth(player: Player, spec, enemy: Enemy, turns_left: float, weapon_value: float, on_self: bool) -> float:
    """Damage-equivalent value of applying ``spec`` right now."""
    if spec is None:
        return 0.0
    kind = spec.kind
    target = player if on_self else enemy
    if target.has_effect(kind) or (not on_self and enemy.immune(kind)):
        return 0.0
    turns = min(spec.turns, turns_left)
    mult = caster_multiplier(player)
    incoming = incoming_estimate(enemy)
    if kind in DAMAGE_OVER_TIME:
        return spec.chance * spec.potency * mult * turns * 0.9
    if kind == EffectKind.FROZEN:
        return spec.chance * incoming * (0.5 if enemy.is_boss else 1.0)
    if kind in (EffectKind.BLIND, EffectKind.WEAKEN):
        return spec.chance * incoming * spec.potency * turns
    if kind == EffectKind.VULNERABLE:
        return spec.chance * weapon_value * spec.potency * turns * 1.3
    if kind == EffectKind.SILENCE:
        return incoming * 0.4 * turns if enemy.spellbook else 0.0
    if kind == EffectKind.HASTE:
        return weapon_value * turns * 0.9 if turns_left > 2 else 0.0
    if kind == EffectKind.SHIELD:
        hard = incoming > player.max_hp * 0.1
        return incoming * spec.potency * turns if hard else 0.0
    if kind == EffectKind.REGEN:
        missing = player.max_hp - player.hp
        return min(missing, spec.potency * heal_multiplier(player.attributes.wisdom) * spec.turns) * 0.6
    return 0.0


def spell_value(player: Player, spell: Spell, enemy: Enemy, fight_turns_left: float, weapon_value: float) -> float:
    t = spell.spell_type
    if t == SpellType.DAMAGE:
        raw = spell.power * caster_multiplier(player)
        value = enemy.mitigate(int(raw), DamageType.MAGIC)
        if enemy.has_effect(EffectKind.VULNERABLE):
            value *= 1 + enemy.effects[EffectKind.VULNERABLE].potency
        if spell.drain:
            value += min(player.max_hp - player.hp, value * spell.drain) * 0.7
    elif t in (SpellType.HEAL, SpellType.CLEANSE):
        return 0.0  # handled as emergencies
    else:
        value = effect_worth(player, spell.primary_effect(), enemy, fight_turns_left, weapon_value, spell.targets_self)
    value += effect_worth(player, spell.inflicts, enemy, fight_turns_left, weapon_value, False)
    value += effect_worth(player, spell.self_effect, enemy, fight_turns_left, weapon_value, True)
    return value


# ------------------------------------------------------------------ the combat bot
@dataclass
class FightStats:
    turns: int = 0
    potions: int = 0
    mana_potions: int = 0
    spells: Counter = field(default_factory=Counter)
    attacks: int = 0
    hp_lost: int = 0


def best_heal_item(player: Player) -> Consumable | None:
    missing = player.max_hp - player.hp
    heals = [s.item for s in player.inventory.consumables()
             if s.item.effect in (ConsumableEffect.HEAL, ConsumableEffect.RESTORE)]
    if not heals:
        return None
    adequate = [h for h in heals if h.potency >= missing * 0.6]
    return min(adequate, key=lambda h: h.potency) if adequate else max(heals, key=lambda h: h.potency)


def choose_action(combat: CombatSession, build: str, stats: FightStats):
    p, e = combat.player, combat.enemy
    hp_ratio = p.hp / p.max_hp
    danger = incoming_estimate(e) * 1.5 > p.hp
    if hp_ratio < 0.35 or danger:
        heal_spell = next((s for s, ok, _ in combat.castable_spells() if ok and s.spell_type == SpellType.HEAL), None)
        if heal_spell and heal_power(heal_spell.power, p.attributes.wisdom) >= p.max_hp * 0.25:
            return CastSpell(heal_spell.uid)
        potion = best_heal_item(p)
        if potion:
            stats.potions += 1
            return UseItem(potion.uid)
    dots = sum(p.effects[k].potency for k in DAMAGE_OVER_TIME if k in p.effects)
    debuffed = any(k in p.effects for k in (EffectKind.WEAKEN, EffectKind.VULNERABLE, EffectKind.SILENCE))
    if dots >= p.max_hp * 0.06 or debuffed:
        purify = next((s for s, ok, _ in combat.castable_spells() if ok and s.spell_type == SpellType.CLEANSE), None)
        if purify:
            return CastSpell(purify.uid)
        cure = next((s.item for s in p.inventory.consumables() if s.item.effect == ConsumableEffect.CURE), None)
        if cure and (dots >= p.max_hp * 0.06 or EffectKind.SILENCE in p.effects):
            return UseItem(cure.uid)
    if build in CASTERS and p.mana < p.max_mana * 0.15:
        mana = next((s.item for s in p.inventory.consumables()
                     if s.item.effect in (ConsumableEffect.MANA, ConsumableEffect.RESTORE)), None)
        if mana and e.hp > incoming_estimate(e):
            stats.mana_potions += 1
            return UseItem(mana.uid)
    weapon_value = attack_value(p, p.weapon, e)
    turns_left = max(1.0, e.hp / max(1.0, weapon_value))
    best, best_value = Attack(), weapon_value
    threshold = 1.0 if build in CASTERS else 1.25  # martial builds only cast when it clearly beats a swing
    for spell, ok, _ in combat.castable_spells():
        if not ok or spell.spell_type in (SpellType.HEAL, SpellType.CLEANSE):
            continue
        value = spell_value(p, spell, e, turns_left, weapon_value)
        if build not in CASTERS:
            value *= min(1.0, p.mana / max(1, mana_cost(p, spell) * 3))  # martial builds ration their mana
        if value > best_value * threshold:
            best, best_value = CastSpell(spell.uid), value
    if isinstance(best, CastSpell):
        stats.spells[next(s.name for s in p.inventory.spells() if s.uid == best.spell_uid)] += 1
    else:
        stats.attacks += 1
    return best


def fight(session: GameSession, encounter: Encounter, build: str) -> tuple[Phase, FightStats]:
    combat = session.begin_combat(encounter)
    stats = FightStats()
    start_hp = session.player.hp
    combat.start()
    guard = 0
    while not combat.is_over and guard < 400:
        guard += 1
        if combat.phase == Phase.PLAYER_TURN:
            stats.turns += 1
            result = combat.act(choose_action(combat, build, stats))
            if not result.accepted:
                combat.act(Attack())
        elif combat.pending_qte:
            # A player with average reflexes lands most prompts: model it with the reflexes edge.
            trigger = combat.pending_qte
            check = session.minigame_check(session.qte_spec(trigger))
            p_hit = max(0.2, min(0.97, 0.78 + check.edge * 0.03))
            prompts = trigger.prompts
            hits = sum(session.rng.random() < p_hit for _ in range(prompts))
            combat.resolve_qte(hits / prompts)
        else:
            combat.enemy_turn()
    if guard >= 400 and not combat.is_over:
        combat.phase = Phase.FLED
    stats.hp_lost = max(0, start_hp - session.player.hp)
    phase = combat.phase
    session.conclude_combat(combat)
    return phase, stats


# ------------------------------------------------------------------ shopping
def gear_score(player: Player, item) -> float:
    """Score at full durability (worn gear gets repaired, not replaced)."""
    if isinstance(item, Weapon):
        fresh = item.clone()
        fresh.repair()
        return attack_value(player, fresh)
    if isinstance(item, Armor):
        return item.defense + item.passives.get("armor", 0)
    return 0.0


USELESS_PASSIVES = {"warrior": ("spell_power", "mana_cost", "max_mana", "mana_regen"),
                    "ranger": ("spell_power", "mana_cost", "max_mana", "mana_regen"),
                    "mage": ("weapon_damage", "lifesteal", "execute", "crit", "crit_damage"),
                    "spellblade": ()}


def jewelry_score(build: str, item) -> float:
    if not isinstance(item, Accessory):
        return 0.0
    score = bonus_value(item) - sum(item.passives.get(k, 0) * 600 for k in USELESS_PASSIVES[build])
    for key in ("gold_find", "xp_gain"):
        score -= item.passives.get(key, 0) * 300
    return score


def maybe_equip(player: Player, item, build: str = "warrior") -> None:
    if not player.meets_requirement(item)[0]:
        return
    if isinstance(item, Accessory):
        slot = player.inventory.slot_for(item)
        current = player.inventory.equipped[slot]
        if current is None or jewelry_score(build, item) > jewelry_score(build, current) * 1.1:
            player.equip(item)
        return
    if not isinstance(item, (Weapon, Armor)):
        return
    current = player.weapon if isinstance(item, Weapon) else player.armor
    if current is None or gear_score(player, item) > gear_score(player, current) * 1.05:
        player.equip(item)


def potion_for_level(level: int) -> str:
    return "health_potion" if level < 6 else "greater_health_potion" if level < 13 else "superior_health_potion"


def visit_shops(session: GameSession, build: str, log: dict) -> None:
    p = session.player
    shop = session.shop(ShopMode.GENERAL)
    # sell junk gear and loot
    for stack in list(p.inventory):
        item = stack.item
        if isinstance(item, (Weapon, Armor, Accessory)) and not p.inventory.is_equipped(item):
            Shop.sell(p, item)
    # repairs
    for item in (p.weapon, p.armor):
        if item and item.durability < item.max_durability * 0.5:
            cost = Shop.repair_cost(item, p)
            if p.gold >= cost:
                shop.repair(p, item)
                log["repair_gold"] += cost
    reserve = 40 + p.level * 6
    # upgrades: weapon then armor
    for kind_cls, current in ((Weapon, p.weapon), (Armor, p.armor)):
        best_offer, best_score = None, gear_score(p, current) * 1.1 if current else 0
        for offer in shop.offers:
            item = offer.item
            if isinstance(item, kind_cls) and not offer.sold_out and p.meets_requirement(item)[0]:
                price = Shop.price_for(offer, p)
                if price <= p.gold - reserve and gear_score(p, item) > best_score:
                    best_offer, best_score = offer, gear_score(p, item)
        if best_offer:
            bought = shop.buy(p, best_offer)
            p.equip(bought)
            log["gear_gold"] += best_offer.price
            log["purchases"].append((p.level, bought.name))
    # jewelry
    for offer in list(shop.offers):
        item = offer.item
        if isinstance(item, Accessory) and not offer.sold_out and p.meets_requirement(item)[0]:
            current = p.inventory.equipped[p.inventory.slot_for(item)]
            better = current is None or jewelry_score(build, item) > jewelry_score(build, current) * 1.2
            price = Shop.price_for(offer, p)
            if better and jewelry_score(build, item) > 40 and price <= p.gold - reserve * 2:
                p.equip(shop.buy(p, offer))
                log["gear_gold"] += price
                log["purchases"].append((p.level, item.name))
    # spells
    want_spells = build in CASTERS or p.attributes.wisdom >= 12
    known = {s.template_id for s in p.inventory.spells()}
    for offer in list(shop.offers):
        item = offer.item
        if isinstance(item, Spell) and item.template_id not in known and p.meets_requirement(item)[0]:
            useful = item.spell_type == SpellType.HEAL or want_spells
            price = Shop.price_for(offer, p)
            if useful and not offer.sold_out and price <= p.gold - reserve:
                shop.buy(p, offer)
                log["spell_gold"] += price
                log["purchases"].append((p.level, item.name))
    # potions
    target = 4 + p.level // 6
    potion_id = potion_for_level(p.level)
    have = sum(s.quantity for s in p.inventory.consumables()
               if s.item.effect in (ConsumableEffect.HEAL, ConsumableEffect.RESTORE))
    offer = next((o for o in shop.offers if o.item.template_id == potion_id), None) or next(
        (o for o in shop.offers if o.item.template_id == "health_potion"), None)
    while offer and have < target and p.gold >= Shop.price_for(offer, p):
        try:
            shop.buy(p, offer)
        except ShopError:
            break
        have += 1
        log["potion_gold"] += Shop.price_for(offer, p)
    if build in CASTERS:
        mana = next((o for o in shop.offers
                     if isinstance(o.item, Consumable) and o.item.effect == ConsumableEffect.MANA), None)
        have_mana = sum(s.quantity for s in p.inventory.consumables() if s.item.effect == ConsumableEffect.MANA)
        while mana and have_mana < 3 and p.gold >= Shop.price_for(mana, p) + reserve // 2:
            try:
                shop.buy(p, mana)
            except ShopError:
                break
            have_mana += 1
            log["potion_gold"] += Shop.price_for(mana, p)


# ------------------------------------------------------------------ a whole run
def play_run(race: str, build: str, seed: int, max_level: int = 27, max_fights: int = 900,
             difficulty: str = "normal", revive: bool = False) -> dict:
    """One playthrough. ``revive`` keeps going after a defeat (recording it) so later content gets measured."""
    rng = random.Random(seed)
    session = GameSession.new_game("Bot", race, rng=rng)
    session.difficulty = difficulty
    p = session.player
    log = defaultdict(float)
    log.update({"race": race, "build": build, "seed": seed, "purchases": [], "bosses": {}, "level_at_fight": [],
                "death": None, "fights": 0, "turns": [], "hp_lost_pct": [], "potions": 0, "spells": Counter(),
                "attacks": 0, "gold_curve": {}, "flee": 0, "level_fights": Counter(), "losses_by_enemy": Counter(),
                "fights_by_enemy": Counter(), "boss_turns": {}, "deaths": [], "boss_attempts": Counter(),
                "band": defaultdict(lambda: {"fights": 0, "turns": 0, "lost": 0.0, "defeats": 0})})
    for _ in range(max_fights):
        spend_points(p, build)
        if p.hp < p.max_hp * 0.6 or (build in CASTERS and p.mana < p.max_mana * 0.35):
            report = session.rest()
            if report.ambush:
                phase, stats = fight(session, Encounter(report.ambush), build)
                _record(log, report.ambush, phase, stats, p)
                if phase == Phase.DEFEAT:
                    log["deaths"].append((p.level, report.ambush.template_id))
                    log["death"] = log["death"] or (p.level, report.ambush.template_id)
                    if not revive:
                        break
                    p.full_restore()
                    visit_shops(session, build, log)
            visit_shops(session, build, log)  # regroup in town after a defeat
            visit_shops(session, build, log)
        encounter = session.create_hunt()
        phase, stats = fight(session, encounter, build)
        _record(log, encounter.enemy, phase, stats, p)
        for stack in list(p.inventory):
            maybe_equip(p, stack.item, build)
        if encounter.enemy.is_boss:
            boss = encounter.enemy.template_id
            log["boss_attempts"][boss] += 1
            log["bosses"][boss] = (phase.value, p.level)
            log["boss_turns"][boss] = stats.turns
            if phase != Phase.VICTORY and log["boss_attempts"][boss] >= 12:
                session.world.bosses_defeated.add(boss)  # hopelessly stuck: skip so later content is measured
                log["bosses"][boss] = ("stuck", p.level)
        if phase == Phase.DEFEAT:
            log["deaths"].append((p.level, encounter.enemy.template_id))
            log["death"] = log["death"] or (p.level, encounter.enemy.template_id)
            if not revive:
                break
            p.full_restore()
            visit_shops(session, build, log)  # regroup in town after a defeat
        log["gold_curve"].setdefault(p.level, p.gold)
        if p.level >= max_level and "rat_king" in session.world.bosses_defeated:
            break
    log["final_level"] = p.level
    log["final_gear"] = (p.weapon.name if p.weapon else None, p.armor.name if p.armor else None)
    log["final_attrs"] = p.attributes.to_dict()
    return log


def _record(log, enemy, phase, stats, player):
    band = log["band"][(player.level - 1) // 5 * 5 + 1]
    band["fights"] += 1
    band["turns"] += stats.turns
    band["lost"] += stats.hp_lost / player.max_hp
    band["defeats"] += phase == Phase.DEFEAT
    log["fights"] += 1
    log["level_fights"][player.level] += 1
    log["turns"].append(stats.turns)
    log["hp_lost_pct"].append(stats.hp_lost / player.max_hp)
    log["potions"] += stats.potions
    log["spells"].update(stats.spells)
    log["attacks"] += stats.attacks
    log["fights_by_enemy"][enemy.template_id] += 1
    if phase == Phase.DEFEAT:
        log["losses_by_enemy"][enemy.template_id] += 1
    if phase == Phase.FLED:
        log["flee"] += 1


# ------------------------------------------------------------------ reports
BOSS_ORDER = [b for _, b in sorted(config.MILESTONE_BOSSES)]


def progression(runs: int, races: list[str], builds: list[str] | None, difficulty: str, out: Path | None) -> None:
    rows = []
    for race in races:
        for build in builds or [NATIVE_BUILD[race]]:
            results = [play_run(race, build, seed, difficulty=difficulty) for seed in range(runs)]
            rows.append(summarise(race, build, results))
            if out:
                out.mkdir(parents=True, exist_ok=True)
                (out / f"{race}_{build}.json").write_text(json.dumps(results, default=str), encoding="utf-8")
    print_table(rows)


def summarise(race: str, build: str, results: list[dict]) -> dict:
    deaths = [r["death"] for r in results if r["death"]]
    row = {"race": race, "build": build, "runs": len(results),
           "survive%": 100 * (1 - len(deaths) / len(results)),
           "median_death_lvl": statistics.median([d[0] for d in deaths]) if deaths else None,
           "fights_to_25": statistics.median([r["fights"] for r in results if r["final_level"] >= 25] or [0]),
           "avg_turns": statistics.mean(t for r in results for t in r["turns"]),
           "hp_lost%": 100 * statistics.mean(h for r in results for h in r["hp_lost_pct"]),
           "spell_share%": 100 * sum(sum(r["spells"].values()) for r in results)
           / max(1, sum(sum(r["spells"].values()) + r["attacks"] for r in results))}
    for boss in BOSS_ORDER:
        reached = [r for r in results if boss in r["bosses"]]
        wins = [r for r in reached if r["bosses"][boss][0] == "victory"]
        row[boss] = f"{len(wins)}/{len(reached)}"
    killers = Counter(d[1] for d in deaths)
    row["killers"] = ", ".join(f"{k}:{v}" for k, v in killers.most_common(3))
    return row


def print_table(rows: list[dict]) -> None:
    cols = ["race", "build", "survive%", "median_death_lvl", "fights_to_25", "avg_turns", "hp_lost%",
            "spell_share%", *BOSS_ORDER, "killers"]
    print(" | ".join(cols))
    for row in rows:
        cells = []
        for c in cols:
            v = row.get(c)
            cells.append(f"{v:.1f}" if isinstance(v, float) else str(v))
        print(" | ".join(cells))


# ------------------------------------------------------------------ arena: fixed-level duels
def make_player_at(race: str, build: str, level: int, rng: random.Random) -> Player:
    p = Player.create("Bot", race)
    p.gain_xp(sum(xp_to_next(i) for i in range(1, level)))
    spend_points(p, build)
    budget = 60 * level + 40 * level * level // 4  # rough gold a player has spent on gear by now
    pools = [ITEMS.create(t) for t in GENERAL_SHOP_POOLS["weapon"] + GENERAL_SHOP_POOLS["armor"]]
    for cls in (Weapon, Armor):
        options = [i for i in pools if isinstance(i, cls) and p.meets_requirement(i)[0] and i.value <= budget / 2]
        if options:
            best = max(options, key=lambda i: gear_score(p, i))
            if cls is Armor or gear_score(p, best) > gear_score(p, p.weapon or best) * 0.99:
                p.inventory.add(best)
                p.equip(best)
    if build in CASTERS:
        spells = [ITEMS.create(t) for t in set(GENERAL_SHOP_POOLS["spell"] + MAGIC_SHOP_SPELLS)]
        for s in sorted(spells, key=lambda s: -s.value):
            if p.meets_requirement(s)[0] and s.value <= budget / 2:
                p.inventory.add(s)
    p.inventory.add(ITEMS.create(potion_for_level(level)), 3)
    return p


def arena(runs: int, races: list[str], levels: list[int]) -> None:
    enemies = [t for t in ENEMIES.templates if t not in ("stone_sentinel",)]
    print("level | race/build | enemy | win% | avg turns | hp lost%")
    for level in levels:
        for race in races:
            build = NATIVE_BUILD[race]
            for enemy_id in enemies:
                wins, turns, lost = 0, [], []
                for seed in range(runs):
                    rng = random.Random(seed)
                    session = GameSession(make_player_at(race, build, level, rng), rng=rng)
                    enemy = ENEMIES.create(enemy_id, rng, level)
                    phase, stats = fight(session, Encounter(enemy), build)
                    wins += phase == Phase.VICTORY
                    turns.append(stats.turns)
                    lost.append(stats.hp_lost / session.player.max_hp)
                print(f"{level} | {race}/{build} | {enemy_id} | {100 * wins / runs:.0f} | {statistics.mean(turns):.1f} | "
                      f"{100 * statistics.mean(lost):.0f}")


# ------------------------------------------------------------------ static gear tables
def gear(level_attrs: int) -> None:
    from rpg.core.attributes import Attributes
    print(f"Weapons at {level_attrs} in every attribute (expected damage per swing vs DEF 3):")
    p = Player("Bot", "Human", Attributes(*(level_attrs,) * 7), 100, 100)
    rows = []
    for tid in ITEMS.ids():
        item = ITEMS.create(tid)
        if isinstance(item, Weapon):
            rows.append((attack_value(p, item), item))
    for value, item in sorted(rows, key=lambda r: -r[0]):
        reqs = ", ".join(f"{r.attribute.short}{r.minimum}" for r in item.requirements)
        print(f"  {value:6.1f}  {item.name:<26} dmg {item.damage:>3} {('finesse' if item.finesse else item.weapon_class.value):<8} "
              f"{item.value:>4}g  {reqs}")
    print("\nArmor (defense, damage multiplier, value):")
    for tid in ITEMS.ids():
        item = ITEMS.create(tid)
        if isinstance(item, Armor):
            reqs = ", ".join(f"{r.attribute.short}{r.minimum}" for r in item.requirements)
            print(f"  {item.name:<22} DEF {item.defense:>3}  x{armor_mitigation(item.defense):.2f}  {item.value:>4}g  {reqs}")
    print(f"\nSpells at INT/WIS {level_attrs} (damage or effect value per mana):")
    for tid in ITEMS.ids():
        item = ITEMS.create(tid)
        if isinstance(item, Spell):
            if item.spell_type == SpellType.DAMAGE:
                dmg = spell_power(item.power, level_attrs)
                extra = f" + {item.inflicts.describe()}" if item.inflicts else ""
                print(f"  {item.name:<24} dmg {dmg:>4}  {item.mana_cost:>3} MP  {dmg / max(1, item.mana_cost):5.2f}/MP{extra}")
            elif item.spell_type == SpellType.HEAL:
                heal = heal_power(item.power, level_attrs)
                print(f"  {item.name:<24} heal {heal:>3}  {item.mana_cost:>3} MP  {heal / max(1, item.mana_cost):5.2f}/MP")
            else:
                e = item.primary_effect()
                print(f"  {item.name:<24} {e.describe() if e else item.spell_type.value:<28} {item.mana_cost:>3} MP")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["progression", "arena", "gear"])
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--races", default=",".join(config.RACES))
    parser.add_argument("--builds", default="", help="comma list; default is each race's native build")
    parser.add_argument("--levels", default="1,5,10,15,20,25")
    parser.add_argument("--difficulty", default="normal")
    parser.add_argument("--attrs", type=int, default=14)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    races = args.races.split(",")
    if args.mode == "progression":
        progression(args.runs, races, args.builds.split(",") if args.builds else None, args.difficulty, args.out)
    elif args.mode == "arena":
        arena(args.runs, races, [int(x) for x in args.levels.split(",")])
    else:
        gear(args.attrs)


if __name__ == "__main__":
    main()
