"""Turn-based combat as a step-wise state machine.

The UI drives a ``CombatSession`` one step at a time so it can pace the log and animate bars:

    session.start()                       -> events; phase becomes PLAYER_TURN (or ENEMY_TURN if frozen)
    session.act(Attack())                 -> ActionResult; rejected actions don't spend the turn
    while session.phase is ENEMY_TURN:
        session.enemy_turn()              -> events; ends at the start of the player's next turn
    session.phase in (VICTORY, DEFEAT, FLED) -> combat is over
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from rpg import config
from rpg.core.effects import DAMAGE_OVER_TIME, END_OF_TURN_DECAY, EffectKind, EffectSpec
from rpg.core.enemies import Enemy
from rpg.core.entities import Combatant, DamageType, Player
from rpg.core.events import LogEvent, Tone
from rpg.core.formulas import (
    armor_penetration,
    enemy_crit_chance,
    heal_power,
    hit_chance,
    player_crit_chance,
    spell_power,
    weapon_attribute_bonus,
)
from rpg.core.items import Consumable, ConsumableEffect, Spell, SpellType, WeaponClass


class Phase(str, Enum):
    PLAYER_TURN = "player_turn"
    ENEMY_TURN = "enemy_turn"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"


FINISHED = (Phase.VICTORY, Phase.DEFEAT, Phase.FLED)


# ------------------------------------------------------------------ actions
@dataclass(frozen=True)
class Attack:
    pass


@dataclass(frozen=True)
class CastSpell:
    spell_uid: str


@dataclass(frozen=True)
class UseItem:
    item_uid: str


@dataclass(frozen=True)
class Flee:
    pass


@dataclass(frozen=True)
class Hesitate:
    """The turn timer ran out."""


Action = Attack | CastSpell | UseItem | Flee | Hesitate


@dataclass
class ActionResult:
    events: list[LogEvent] = field(default_factory=list)
    accepted: bool = True


class CombatError(Exception):
    pass


class CombatSession:
    def __init__(self, player: Player, enemy: Enemy, rng: random.Random | None = None,
                 reward_multiplier: float = 1.0, allow_flee: bool = True) -> None:
        self.player = player
        self.enemy = enemy
        self.rng = rng or random.Random()
        self.reward_multiplier = reward_multiplier
        self.allow_flee = allow_flee
        self.phase = Phase.PLAYER_TURN
        self.round = 0
        self.log: list[LogEvent] = []
        self._started = False

    # ------------------------------------------------------------ public API
    @property
    def is_over(self) -> bool:
        return self.phase in FINISHED

    def start(self) -> list[LogEvent]:
        if self._started:
            raise CombatError("Combat already started")
        self._started = True
        events = [LogEvent(f"⚔ {self.enemy.name} engages you!", Tone.SYSTEM)]
        events += self._begin_player_turn()
        return self._record(events)

    def act(self, action: Action) -> ActionResult:
        if self.phase != Phase.PLAYER_TURN:
            raise CombatError(f"Not the player's turn ({self.phase.value})")
        handler = {
            Attack: self._player_attack,
            CastSpell: self._player_cast,
            UseItem: self._player_use_item,
            Flee: self._player_flee,
            Hesitate: self._player_hesitate,
        }[type(action)]
        result: ActionResult = handler(action)
        if not result.accepted:
            return result
        if self.phase == Phase.FLED:
            return ActionResult(self._record(result.events))
        if not self.enemy.alive:
            result.events += self._victory()
        else:
            result.events += self._decay(self.player)
            self.phase = Phase.ENEMY_TURN
        result.events = self._record(result.events)
        return result

    def enemy_turn(self) -> list[LogEvent]:
        if self.phase != Phase.ENEMY_TURN:
            raise CombatError(f"Not the enemy's turn ({self.phase.value})")
        events, skip = self._tick(self.enemy)
        if not self.enemy.alive:
            return self._record(events + self._victory())
        if not skip:
            events += self._enemy_act()
            if not self.player.alive:
                self.phase = Phase.DEFEAT
                events.append(LogEvent(f"💀 {self.enemy.name} has struck you down.", Tone.DAMAGE))
                return self._record(events)
        events += self._decay(self.enemy)
        events += self._begin_player_turn()
        return self._record(events)

    def castable_spells(self) -> list[tuple[Spell, bool, str]]:
        """Every known spell with whether it can be cast right now and why not."""
        options = []
        for spell in self.player.inventory.spells():
            ok, reason = self.player.meets_requirement(spell)
            if ok and self.player.mana < spell.mana_cost:
                ok, reason = False, f"Needs {spell.mana_cost} mana"
            options.append((spell, ok, reason))
        return options

    def usable_items(self) -> list[tuple[Consumable, int]]:
        return [(s.item, s.quantity) for s in self.player.inventory.consumables()]  # type: ignore[misc]

    @property
    def flee_chance(self) -> float:
        return config.BOSS_FLEE_CHANCE if self.enemy.is_boss else config.FLEE_CHANCE

    # ------------------------------------------------------------ turn structure
    def _record(self, events: list[LogEvent]) -> list[LogEvent]:
        self.log.extend(events)
        return events

    def _begin_player_turn(self) -> list[LogEvent]:
        self.round += 1
        events, skip = self._tick(self.player)
        if not self.player.alive:
            self.phase = Phase.DEFEAT
            events.append(LogEvent("💀 Your wounds overcome you.", Tone.DAMAGE))
            return events
        if skip:
            events += self._decay(self.player)
            self.phase = Phase.ENEMY_TURN
        else:
            self.phase = Phase.PLAYER_TURN
        return events

    def _tick(self, who: Combatant) -> tuple[list[LogEvent], bool]:
        """Start-of-turn effects. Returns (events, turn_skipped)."""
        events: list[LogEvent] = []
        verbs = {EffectKind.POISON: "suffers {n} poison damage", EffectKind.BURN: "is scorched for {n} damage",
                 EffectKind.BLEED: "bleeds for {n} damage"}
        for kind in DAMAGE_OVER_TIME:
            effect = who.effects.get(kind)
            if not effect:
                continue
            dealt = who.lose_hp(int(effect.potency))
            effect.turns -= 1
            events.append(LogEvent(f"{who.name} {verbs[kind].format(n=dealt)}.", Tone.STATUS))
            if effect.turns <= 0:
                who.remove_effect(kind)
                events.append(LogEvent(f"{who.name} is no longer {effect.info.label.lower()}ed."
                                       if kind != EffectKind.BLEED else f"{who.name}'s bleeding stops.", Tone.INFO))
            if not who.alive:
                events.append(LogEvent(f"💀 {who.name} succumbs to {effect.info.label.lower()}!", Tone.DAMAGE))
                return events, True

        regen = who.effects.get(EffectKind.REGEN)
        if regen:
            healed = who.heal(int(regen.potency))
            regen.turns -= 1
            if regen.turns <= 0:
                who.remove_effect(EffectKind.REGEN)
            if healed:
                events.append(LogEvent(f"{who.name} regenerates {healed} HP.", Tone.HEAL))
        if isinstance(who, Enemy) and who.regen_pct and who.hp < who.max_hp:
            healed = who.heal(max(5, int(who.max_hp * who.regen_pct)))
            events.append(LogEvent(f"{who.name} regenerates {healed} HP!", Tone.HEAL))

        frozen = who.effects.get(EffectKind.FROZEN)
        if frozen:
            frozen.turns -= 1
            if frozen.turns <= 0:
                who.remove_effect(EffectKind.FROZEN)
            events.append(LogEvent(f"❄ {who.name} is frozen solid and cannot act!", Tone.STATUS))
            return events, True
        return events, False

    def _decay(self, who: Combatant) -> list[LogEvent]:
        events = []
        for kind in END_OF_TURN_DECAY:
            effect = who.effects.get(kind)
            if not effect:
                continue
            effect.turns -= 1
            if effect.turns <= 0:
                who.remove_effect(kind)
                text = f"{who.name}'s ward fades." if kind == EffectKind.SHIELD else f"{who.name} can see clearly again."
                events.append(LogEvent(text, Tone.INFO))
        return events

    def _victory(self) -> list[LogEvent]:
        self.phase = Phase.VICTORY
        return [LogEvent(f"🏆 {self.enemy.name} has been defeated!", Tone.REWARD)]

    # ------------------------------------------------------------ effects
    def _apply(self, target: Combatant, spec: EffectSpec, source: str, roll: bool = True) -> list[LogEvent]:
        if roll and not spec.roll(self.rng):
            return []
        if spec.kind == EffectKind.FROZEN and isinstance(target, Enemy) and target.is_boss and self.rng.random() < 0.5:
            return [LogEvent(f"{target.name} shrugs off the frost!", Tone.MISS)]
        effect = target.add_effect(spec.create(source))
        text = {
            EffectKind.POISON: f"{target.name} is poisoned ({int(effect.potency)}/turn)!",
            EffectKind.BURN: f"Flames cling to {target.name} ({int(effect.potency)}/turn)!",
            EffectKind.BLEED: f"{target.name} is bleeding ({int(effect.potency)}/turn)!",
            EffectKind.REGEN: f"{target.name} begins to regenerate.",
            EffectKind.SHIELD: f"A ward shimmers around {target.name} ({int(effect.potency * 100)}% for {effect.turns} turns).",
            EffectKind.BLIND: f"{target.name} staggers, vision clouded!",
            EffectKind.FROZEN: f"❄ {target.name} is frozen in place!",
        }[spec.kind]
        return [LogEvent(text, Tone.STATUS)]

    def _crit(self, chance: float) -> bool:
        return self.rng.random() < chance

    # ------------------------------------------------------------ player actions
    def _player_attack(self, _: Attack) -> ActionResult:
        p, e = self.player, self.enemy
        weapon = p.weapon if p.weapon and not p.weapon.is_broken else None
        events: list[LogEvent] = []
        base = weapon.effective_damage if weapon else config.UNARMED_DAMAGE
        weapon_name = weapon.name if weapon else "bare fists"
        if weapon and weapon.wear():
            events.append(LogEvent(f"Your {weapon.name} breaks! You'll fight barehanded until it's repaired.",
                                   Tone.WARNING))

        if self.rng.random() > hit_chance(p.attributes.agility, p.blind_penalty(), e.has_effect(EffectKind.BLIND)):
            events.insert(0, LogEvent(f"You swing at {e.name} with {weapon_name} but miss!", Tone.MISS))
            return ActionResult(events)

        weapon_class = weapon.weapon_class if weapon else None
        raw = (base + weapon_attribute_bonus(p.attributes, weapon_class))
        raw *= 1 + self.rng.uniform(-config.PLAYER_DAMAGE_VARIANCE, config.PLAYER_DAMAGE_VARIANCE)
        crit = self._crit(player_crit_chance(p.attributes.strength))
        if crit:
            raw *= config.CRIT_MULTIPLIER
        damage_type = DamageType.MAGIC if weapon_class == WeaponClass.MAGIC else DamageType.PHYSICAL
        dealt = e.take_hit(max(1, int(raw)), damage_type)
        tone = Tone.CRIT if crit else Tone.PLAYER
        events.insert(0, LogEvent(f"You hit {e.name} with {weapon_name} for {dealt} damage" +
                                  (" — CRITICAL!" if crit else "!"), tone))
        if weapon and weapon.on_hit and e.alive:
            events += self._apply(e, weapon.on_hit, weapon.name)
        return ActionResult(events)

    def _player_cast(self, action: CastSpell) -> ActionResult:
        p, e = self.player, self.enemy
        stack = p.inventory.find(action.spell_uid)
        if stack is None or not isinstance(stack.item, Spell):
            return ActionResult([LogEvent("You don't know that spell.", Tone.WARNING)], accepted=False)
        spell: Spell = stack.item
        ok, reason = p.meets_requirement(spell)
        if not ok:
            return ActionResult([LogEvent(f"You can't cast {spell.name}. {reason}", Tone.WARNING)], accepted=False)
        if not p.spend_mana(spell.mana_cost):
            return ActionResult([LogEvent(f"Not enough mana for {spell.name} ({spell.mana_cost} needed).",
                                          Tone.WARNING)], accepted=False)
        return ActionResult(self._resolve_spell(p, e, spell, p.attributes.intelligence, caster_is_player=True))

    def _resolve_spell(self, caster: Combatant, target: Combatant, spell: Spell, intelligence: int,
                       caster_is_player: bool) -> list[LogEvent]:
        tone = Tone.PLAYER if caster_is_player else Tone.ENEMY
        who = "You cast" if caster_is_player else f"{caster.name} casts"
        events: list[LogEvent] = []
        if spell.spell_type == SpellType.DAMAGE:
            penetration = 0.0
            if isinstance(caster, Enemy):
                penetration = armor_penetration(caster.base_damage, caster.attributes.strength, caster.is_boss)
            dealt = target.take_hit(spell_power(spell.power, intelligence), DamageType.MAGIC, penetration)
            events.append(LogEvent(f"{who} {spell.name} on {target.name} for {dealt} damage!",
                                   tone if caster_is_player else Tone.DAMAGE))
            if spell.inflicts and target.alive:
                events += self._apply(target, spell.inflicts, spell.name)
        elif spell.spell_type == SpellType.HEAL:
            healed = caster.heal(heal_power(spell.power, intelligence))
            events.append(LogEvent(f"{who} {spell.name} and recovers {healed} HP.", Tone.HEAL))
        else:
            effect = spell.primary_effect()
            recipient = caster if spell.targets_self else target
            events.append(LogEvent(f"{who} {spell.name}!", tone))
            if effect:
                events += self._apply(recipient, effect, spell.name, roll=False)
            if spell.inflicts and target.alive:
                events += self._apply(target, spell.inflicts, spell.name)
        return events

    def _player_use_item(self, action: UseItem) -> ActionResult:
        p = self.player
        stack = p.inventory.find(action.item_uid)
        if stack is None or not isinstance(stack.item, Consumable):
            return ActionResult([LogEvent("You don't have that item.", Tone.WARNING)], accepted=False)
        item: Consumable = stack.item
        problem = consumable_blocker(p, item)
        if problem:
            return ActionResult([LogEvent(problem, Tone.WARNING)], accepted=False)
        p.inventory.remove(item.uid, 1)
        return ActionResult(apply_consumable(p, item))

    def _player_flee(self, _: Flee) -> ActionResult:
        if not self.allow_flee:
            return ActionResult([LogEvent("There is no escape from this fight!", Tone.WARNING)], accepted=False)
        if self.rng.random() < self.flee_chance:
            self.phase = Phase.FLED
            return ActionResult([LogEvent("You slip away and escape the fight!", Tone.SYSTEM)])
        return ActionResult([LogEvent("You try to flee, but can't escape!", Tone.WARNING)])

    def _player_hesitate(self, _: Hesitate) -> ActionResult:
        return ActionResult([LogEvent(f"You hesitate too long — {self.enemy.name} seizes the moment!", Tone.WARNING)])

    # ------------------------------------------------------------ enemy actions
    def _enemy_act(self) -> list[LogEvent]:
        p, e = self.player, self.enemy
        spell = e.choose_spell(p, self.rng)
        if spell:
            return self._resolve_spell(e, p, spell, 0, caster_is_player=False)

        if self.rng.random() > hit_chance(e.attributes.agility, e.blind_penalty()):
            return [LogEvent(f"{e.name} swings at you but misses!", Tone.MISS)]
        raw = e.base_damage + e.attributes.strength * 0.3 + e.attributes.agility * 0.2
        raw *= 1 + self.rng.uniform(-config.ENEMY_DAMAGE_VARIANCE, config.ENEMY_DAMAGE_VARIANCE)
        crit = self._crit(enemy_crit_chance(e.attributes.strength))
        if crit:
            raw *= config.CRIT_MULTIPLIER
        penetration = armor_penetration(e.base_damage, e.attributes.strength, e.is_boss)
        dealt = p.take_hit(max(1, int(raw)), DamageType.PHYSICAL, penetration)
        events = [LogEvent(f"{e.name} hits you for {dealt} damage" + (" — CRITICAL!" if crit else "!"),
                           Tone.CRIT if crit else Tone.DAMAGE)]
        armor = p.armor
        if armor and armor.wear():
            events.append(LogEvent(f"Your {armor.name} is shattered!", Tone.WARNING))
        if p.alive:
            for spec in e.on_hit:
                events += self._apply(p, spec, e.name)
        return events


# ------------------------------------------------------------------ consumables (shared with the inventory screen)
def consumable_blocker(player: Player, item: Consumable) -> str | None:
    """Reason a consumable would be wasted right now, or None if it is useful."""
    from rpg.core.effects import CLEANSABLE

    if item.effect == ConsumableEffect.HEAL and player.hp >= player.max_hp:
        return "You're already at full health."
    if item.effect == ConsumableEffect.MANA and player.mana >= player.max_mana:
        return "Your mana is already full."
    if item.effect == ConsumableEffect.RESTORE and player.hp >= player.max_hp and player.mana >= player.max_mana:
        return "You're already fully restored."
    if item.effect == ConsumableEffect.CURE and not any(k in player.effects for k in CLEANSABLE):
        return "You have no afflictions to cure."
    return None


def apply_consumable(player: Player, item: Consumable) -> list[LogEvent]:
    """Apply an already-removed consumable's effect to the player."""
    if item.effect == ConsumableEffect.HEAL:
        return [LogEvent(f"You drink the {item.name} and recover {player.heal(item.potency)} HP.", Tone.HEAL)]
    if item.effect == ConsumableEffect.MANA:
        return [LogEvent(f"You drink the {item.name} and recover {player.restore_mana(item.potency)} mana.", Tone.MANA)]
    if item.effect == ConsumableEffect.RESTORE:
        hp, mp = player.heal(item.potency), player.restore_mana(item.potency)
        return [LogEvent(f"You drink the {item.name}: +{hp} HP, +{mp} mana.", Tone.HEAL)]
    removed = player.cleanse()
    names = ", ".join(k.value for k in removed) or "nothing"
    return [LogEvent(f"You take the {item.name}. Cured: {names}.", Tone.HEAL)]
