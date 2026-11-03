"""Turn-based combat as a step-wise state machine.

The UI drives a ``CombatSession`` one step at a time so it can pace the log and animate bars:

    session.start()                       -> events; phase becomes PLAYER_TURN (or ENEMY_TURN if frozen)
    session.act(Attack())                 -> ActionResult; rejected actions don't spend the turn
                                             (a hasted player stays in PLAYER_TURN for a second action)
    while session.phase is ENEMY_TURN:
        session.enemy_turn()              -> events; ends at the start of the player's next turn
        if session.pending_qte:           -> a boss telegraphed a big move (see ``QTETrigger``):
            session.resolve_qte(score)       play the quick-time event, then report how it went (0..1)
    session.phase in (VICTORY, DEFEAT, FLED) -> combat is over

Damage pipeline (both sides): raw -> attacker Weakened (-) -> defender armor (% from defense, magic halves it)
-> defender resistance -> ward -> defender Exposed (+). Equipment passives (``rpg.core.passives``) hook in at
the obvious places: crit, accuracy, lifesteal, thorns, execute, regeneration, mana cost, immunities...
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from rpg import config
from rpg.core.effects import (
    CLEANSABLE,
    DAMAGE_OVER_TIME,
    EFFECT_INFO,
    END_OF_TURN_DECAY,
    EffectKind,
    EffectSpec,
    StatusEffect,
)
from rpg.core.enemies import Enemy, QTETrigger
from rpg.core.entities import Combatant, DamageType, Player
from rpg.core.events import LogEvent, Tone
from rpg.core.formulas import (
    armor_penetration,
    enemy_crit_chance,
    enemy_spell_multiplier,
    flee_chance,
    heal_multiplier,
    hit_chance,
    player_crit_chance,
    spell_multiplier,
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
EXECUTE_THRESHOLD = 0.3


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


def mana_cost(player: Player, spell: Spell) -> int:
    return max(1, int(round(spell.mana_cost * (1 - player.passive("mana_cost")))))


def caster_multiplier(caster: Combatant) -> float:
    """How strongly a caster's spells hit (and how hard their spell DoTs tick)."""
    if isinstance(caster, Player):
        return spell_multiplier(caster.attributes.intelligence) * (1 + caster.passive("spell_power"))
    if isinstance(caster, Enemy):
        return enemy_spell_multiplier(caster.level)
    return 1.0


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
        self.pending_qte: QTETrigger | None = None
        self._opening: list[LogEvent] = []  # shown at the top of the log by start()
        self._fired_qtes: set[int] = set()
        self._haste_used = False
        self.ambushed = False

    def ambush(self) -> None:
        """The enemy acts first (the player was discovered while hiding). Call before ``start``."""
        self.ambushed = True

    def opening_strike(self, fraction: float) -> list[LogEvent]:
        """Sneak attack: the enemy starts the fight missing ``fraction`` of its health."""
        dealt = self.enemy.lose_hp(int(self.enemy.max_hp * max(0.0, min(0.9, fraction))))
        events = [LogEvent(f"You strike from hiding! {self.enemy.name} takes {dealt} damage before it can react.",
                           Tone.CRIT)] if dealt else []
        self._opening += events
        return events

    # ------------------------------------------------------------ public API
    @property
    def is_over(self) -> bool:
        return self.phase in FINISHED

    def start(self) -> list[LogEvent]:
        if self._started:
            raise CombatError("Combat already started")
        self._started = True
        opening = list(self._opening)
        p = self.player
        if p.passive("start_ward"):
            p.add_effect(StatusEffect(EffectKind.SHIELD, 2, p.passive("start_ward"), "Opening ward"))
            opening.append(LogEvent(f"A ward flares around you ({int(p.passive('start_ward') * 100)}%).", Tone.STATUS))
        if p.passive("start_haste"):
            p.add_effect(StatusEffect(EffectKind.HASTE, 1, 1, "Opening haste"))
            opening.append(LogEvent("You move with uncanny speed!", Tone.STATUS))
        if self.ambushed:
            self.phase = Phase.ENEMY_TURN
            return self._record(opening + [LogEvent(f"{self.enemy.name} catches you off guard and strikes first!",
                                                    Tone.WARNING)])
        events = opening + [LogEvent(f"{self.enemy.name} engages you!", Tone.SYSTEM)]
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
        elif not self.player.alive:  # an enemy's thorns
            self.phase = Phase.DEFEAT
            result.events.append(LogEvent("Your wounds overcome you.", Tone.DAMAGE))
        elif self.player.has_effect(EffectKind.HASTE) and not self._haste_used and not isinstance(action, Hesitate):
            self._haste_used = True
            result.events.append(LogEvent("Hasted: you act again!", Tone.STATUS))
        else:
            result.events += self._decay(self.player)
            self.phase = Phase.ENEMY_TURN
        result.events = self._record(result.events)
        return result

    def enemy_turn(self) -> list[LogEvent]:
        if self.phase != Phase.ENEMY_TURN:
            raise CombatError(f"Not the enemy's turn ({self.phase.value})")
        if self.pending_qte:
            raise CombatError("Resolve the pending quick-time event first")
        events, skip = self._tick(self.enemy)
        if not self.enemy.alive:
            return self._record(events + self._victory())
        if not skip:
            trigger = self._next_qte()
            if trigger:
                # The telegraphed move *is* the enemy's action this turn; the UI plays it, then resolve_qte().
                self.pending_qte = trigger
                events.append(LogEvent(trigger.telegraph.format(name=self.enemy.name), Tone.WARNING))
                return self._record(events)
            events += self._enemy_act()
            if self.enemy.has_effect(EffectKind.HASTE) and self.player.alive and self.enemy.alive:
                events.append(LogEvent(f"{self.enemy.name} moves again!", Tone.WARNING))
                events += self._enemy_act()
        if not self.enemy.alive:
            return self._record(events + self._victory())
        return self._record(events + self._end_enemy_turn())

    def resolve_qte(self, score: float) -> list[LogEvent]:
        """Apply a quick-time event's outcome (``score`` 0..1 from the minigame) and finish the enemy turn."""
        trigger = self.pending_qte
        if trigger is None:
            raise CombatError("No quick-time event is pending")
        self.pending_qte = None
        p, e = self.player, self.enemy
        events: list[LogEvent] = []
        if score >= trigger.success_score:
            events.append(LogEvent(trigger.success_text.format(name=e.name), Tone.PLAYER))
            if trigger.counter_damage:
                dealt = e.lose_hp(max(1, int(e.max_hp * trigger.counter_damage)))
                events.append(LogEvent(f"You punish the opening for {dealt} damage!", Tone.CRIT))
            if trigger.stagger and e.alive:
                e.add_effect(StatusEffect(EffectKind.FROZEN, 1, 0, "Staggered"))
                events.append(LogEvent(f"{e.name} is staggered and loses its next turn!", Tone.STATUS))
        else:
            partial = score >= trigger.partial_score
            share = trigger.fail_damage * (0.5 if partial else 1.0)
            dealt = p.lose_hp(max(1, int(p.max_hp * share)))
            text = trigger.partial_text if partial else trigger.fail_text
            events.append(LogEvent(f"{text.format(name=e.name)} You take {dealt} damage!", Tone.DAMAGE))
            if trigger.fail_effect and not partial and p.alive:
                events += self._apply(p, trigger.fail_effect, e.name, roll=False)
        if not e.alive:
            return self._record(events + self._victory())
        if not p.alive:
            self.phase = Phase.DEFEAT
            events.append(LogEvent(f"{e.name} has struck you down.", Tone.DAMAGE))
            return self._record(events)
        return self._record(events + self._end_enemy_turn())

    def castable_spells(self) -> list[tuple[Spell, bool, str]]:
        """Every known spell with whether it can be cast right now and why not."""
        options = []
        silenced = self.player.has_effect(EffectKind.SILENCE)
        for spell in self.player.inventory.spells():
            ok, reason = self.player.meets_requirement(spell)
            cost = mana_cost(self.player, spell)
            if ok and silenced:
                ok, reason = False, "You are silenced"
            elif ok and self.player.mana < cost:
                ok, reason = False, f"Needs {cost} mana"
            options.append((spell, ok, reason))
        return options

    def usable_items(self) -> list[tuple[Consumable, int]]:
        return [(s.item, s.quantity) for s in self.player.inventory.consumables()  # type: ignore[misc]
                if s.item.usable_in_combat]

    @property
    def flee_chance(self) -> float:
        return min(0.95, flee_chance(self.player.attributes.agility, self.enemy.is_boss) + self.player.passive("flee"))

    # ------------------------------------------------------------ turn structure
    def _record(self, events: list[LogEvent]) -> list[LogEvent]:
        self.log.extend(events)
        return events

    def _next_qte(self) -> QTETrigger | None:
        for index, trigger in enumerate(self.enemy.template.qte_triggers):
            if index not in self._fired_qtes and self.enemy.hp_ratio <= trigger.hp_below:
                self._fired_qtes.add(index)
                return trigger
        return None

    def _end_enemy_turn(self) -> list[LogEvent]:
        if not self.player.alive:
            self.phase = Phase.DEFEAT
            return [LogEvent(f"{self.enemy.name} has struck you down.", Tone.DAMAGE)]
        return self._decay(self.enemy) + self._begin_player_turn()

    def _begin_player_turn(self) -> list[LogEvent]:
        self.round += 1
        self._haste_used = False
        events, skip = self._tick(self.player)
        if not self.player.alive:
            self.phase = Phase.DEFEAT
            events.append(LogEvent("Your wounds overcome you.", Tone.DAMAGE))
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
            dealt = who.lose_hp(max(1, int(round(effect.potency * who.dot_multiplier()))))
            effect.turns -= 1
            events.append(LogEvent(f"{who.name} {verbs[kind].format(n=dealt)}.", Tone.STATUS))
            if effect.turns <= 0:
                who.remove_effect(kind)
                events.append(LogEvent(f"{who.name} is no longer {effect.info.label.lower()}ed."
                                       if kind != EffectKind.BLEED else f"{who.name}'s bleeding stops.", Tone.INFO))
            if not who.alive:
                events.append(LogEvent(f"{who.name} succumbs to {effect.info.label.lower()}!", Tone.DAMAGE))
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
            if EffectKind.BURN in who.effects:  # fire seals the wounds closed
                events.append(LogEvent(f"The flames stop {who.name} from regenerating!", Tone.STATUS))
            else:
                healed = who.heal(max(5, int(who.max_hp * who.regen_pct)))
                events.append(LogEvent(f"{who.name} regenerates {healed} HP!", Tone.HEAL))
        if isinstance(who, Player):
            if who.passive("regen_pct") and who.hp < who.max_hp:
                healed = who.heal(max(1, int(who.max_hp * who.passive("regen_pct"))))
                if healed:
                    events.append(LogEvent(f"Your gear mends you for {healed} HP.", Tone.HEAL))
            if who.passive("mana_regen"):
                who.restore_mana(int(who.passive("mana_regen")))

        frozen = who.effects.get(EffectKind.FROZEN)
        if frozen:
            frozen.turns -= 1
            if frozen.turns <= 0:
                who.remove_effect(EffectKind.FROZEN)
            events.append(LogEvent(f"{who.name} is frozen solid and cannot act!", Tone.STATUS))
            return events, True
        return events, False

    def _decay(self, who: Combatant) -> list[LogEvent]:
        events = []
        endings = {EffectKind.SHIELD: "{n}'s ward fades.", EffectKind.BLIND: "{n} can see clearly again.",
                   EffectKind.HASTE: "{n} slows down.", EffectKind.WEAKEN: "{n} recovers their strength.",
                   EffectKind.VULNERABLE: "{n} is no longer exposed.", EffectKind.SILENCE: "{n} can cast again."}
        for kind in END_OF_TURN_DECAY:
            effect = who.effects.get(kind)
            if not effect:
                continue
            effect.turns -= 1
            if effect.turns <= 0:
                who.remove_effect(kind)
                events.append(LogEvent(endings[kind].format(n=who.name), Tone.INFO))
        return events

    def _victory(self) -> list[LogEvent]:
        self.phase = Phase.VICTORY
        return [LogEvent(f"{self.enemy.name} has been defeated!", Tone.REWARD)]

    # ------------------------------------------------------------ damage and effects
    def _hit(self, attacker: Combatant, target: Combatant, raw: float, damage_type: DamageType,
             penetration: float = 0.0) -> int:
        weaken = attacker.effects.get(EffectKind.WEAKEN)
        if weaken:
            raw *= 1 - weaken.potency
        dealt = target.take_hit(max(1, int(raw)), damage_type, penetration)
        exposed = target.effects.get(EffectKind.VULNERABLE)
        if exposed and target.alive:
            dealt += target.lose_hp(int(dealt * exposed.potency))
        return dealt

    def _apply(self, target: Combatant, spec: EffectSpec, source: str, roll: bool = True,
               scale: float = 1.0) -> list[LogEvent]:
        if roll and not spec.roll(self.rng):
            return []
        info = EFFECT_INFO[spec.kind]
        if target.immune(spec.kind):
            return [LogEvent(f"{target.name} is immune to {info.label.lower()}!", Tone.MISS)]
        if info.harmful and target.status_resist() and self.rng.random() < target.status_resist():
            return [LogEvent(f"{target.name} resists the {info.label.lower()}!", Tone.MISS)]
        if spec.kind == EffectKind.FROZEN and isinstance(target, Enemy) and target.is_boss and self.rng.random() < 0.5:
            return [LogEvent(f"{target.name} shrugs off the frost!", Tone.MISS)]
        effect = spec.create(source)
        if spec.kind in DAMAGE_OVER_TIME or spec.kind == EffectKind.REGEN:
            effect.potency = max(1, round(effect.potency * scale))
        effect = target.add_effect(effect)
        text = {
            EffectKind.POISON: f"{target.name} is poisoned ({int(effect.potency)}/turn)!",
            EffectKind.BURN: f"Flames cling to {target.name} ({int(effect.potency)}/turn)!",
            EffectKind.BLEED: f"{target.name} is bleeding ({int(effect.potency)}/turn)!",
            EffectKind.REGEN: f"{target.name} begins to regenerate ({int(effect.potency)}/turn).",
            EffectKind.SHIELD: f"A ward shimmers around {target.name} ({int(effect.potency * 100)}% for {effect.turns} turns).",
            EffectKind.BLIND: f"{target.name} staggers, vision clouded!",
            EffectKind.FROZEN: f"{target.name} is frozen in place!",
            EffectKind.HASTE: f"{target.name} is hasted!",
            EffectKind.WEAKEN: f"{target.name} is weakened ({int(effect.potency * 100)}% less damage).",
            EffectKind.VULNERABLE: f"{target.name} is exposed ({int(effect.potency * 100)}% more damage taken).",
            EffectKind.SILENCE: f"{target.name} is silenced!",
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

        to_hit = hit_chance(p.attributes.dexterity, p.blind_penalty(), e.has_effect(EffectKind.BLIND))
        if self.rng.random() > min(0.99, to_hit + p.passive("accuracy")):
            events.insert(0, LogEvent(f"You swing at {e.name} with {weapon_name} but miss!", Tone.MISS))
            return ActionResult(events)

        weapon_class = weapon.weapon_class if weapon else None
        raw = (base + weapon_attribute_bonus(p.attributes, weapon)) * (1 + p.passive("weapon_damage"))
        raw *= 1 + self.rng.uniform(-config.PLAYER_DAMAGE_VARIANCE, config.PLAYER_DAMAGE_VARIANCE)
        if e.hp_ratio < EXECUTE_THRESHOLD:
            raw *= 1 + p.passive("execute")
        crit = self._crit(player_crit_chance(p.attributes) + p.passive("crit"))
        if crit:
            raw *= config.CRIT_MULTIPLIER + p.passive("crit_damage")
        damage_type = DamageType.MAGIC if weapon_class == WeaponClass.MAGIC else DamageType.PHYSICAL
        dealt = self._hit(p, e, raw, damage_type)
        tone = Tone.CRIT if crit else Tone.PLAYER
        events.insert(0, LogEvent(f"You hit {e.name} with {weapon_name} for {dealt} damage" +
                                  (" — CRITICAL!" if crit else "!"), tone))
        if p.passive("lifesteal"):
            healed = p.heal(int(dealt * p.passive("lifesteal")))
            if healed:
                events.append(LogEvent(f"You drain {healed} HP.", Tone.HEAL))
        if e.thorns and damage_type == DamageType.PHYSICAL:
            reflected = p.lose_hp(max(1, int(dealt * e.thorns)))
            events.append(LogEvent(f"{e.name}'s spines bite back for {reflected} damage!", Tone.DAMAGE))
        if weapon and weapon.on_hit and e.alive:
            events += self._apply(e, weapon.on_hit, weapon.name, scale=1 + p.passive("dot_power"))
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
        if p.has_effect(EffectKind.SILENCE):
            return ActionResult([LogEvent("You are silenced and cannot cast!", Tone.WARNING)], accepted=False)
        cost = mana_cost(p, spell)
        if not p.spend_mana(cost):
            return ActionResult([LogEvent(f"Not enough mana for {spell.name} ({cost} needed).", Tone.WARNING)],
                                accepted=False)
        return ActionResult(self._resolve_spell(p, e, spell, caster_is_player=True))

    def _resolve_spell(self, caster: Combatant, target: Combatant, spell: Spell, caster_is_player: bool) -> list[LogEvent]:
        tone = Tone.PLAYER if caster_is_player else Tone.ENEMY
        who = "You cast" if caster_is_player else f"{caster.name} casts"
        power = caster_multiplier(caster)
        dot_scale = power * (1 + caster.passive("dot_power"))
        heal_scale = (heal_multiplier(caster.attributes.wisdom) * (1 + caster.passive("healing"))
                      if isinstance(caster, Player) else power)
        events: list[LogEvent] = []
        t = spell.spell_type
        if t == SpellType.DAMAGE:
            penetration = armor_penetration(caster.level, caster.is_boss) if isinstance(caster, Enemy) else 0.0
            dealt = self._hit(caster, target, spell.power * power, DamageType.MAGIC, penetration)
            events.append(LogEvent(f"{who} {spell.name} on {target.name} for {dealt} damage!",
                                   tone if caster_is_player else Tone.DAMAGE))
            if spell.drain:
                healed = caster.heal(int(dealt * spell.drain))
                if healed:
                    drainer = "You drain" if caster_is_player else f"{caster.name} drains"
                    events.append(LogEvent(f"{drainer} {healed} HP.", Tone.HEAL))
        elif t == SpellType.HEAL:
            base = spell.power if spell.power > 0 else config.DEFAULT_HEAL_POTENCY
            healed = caster.heal(int(base * heal_scale))
            events.append(LogEvent(f"{who} {spell.name} and recovers {healed} HP.", Tone.HEAL))
        elif t == SpellType.CLEANSE:
            removed = caster.cleanse()
            names = ", ".join(EFFECT_INFO[k].label.lower() for k in removed) or "nothing to purge"
            events.append(LogEvent(f"{who} {spell.name}: {names}.", Tone.HEAL))
        else:
            effect = spell.primary_effect()
            recipient = caster if spell.targets_self else target
            events.append(LogEvent(f"{who} {spell.name}!", tone))
            if effect:
                scale = heal_scale if effect.kind == EffectKind.REGEN else dot_scale
                events += self._apply(recipient, effect, spell.name, roll=False, scale=scale)
        if spell.inflicts and target.alive:
            events += self._apply(target, spell.inflicts, spell.name, scale=dot_scale)
        if spell.self_effect and caster.alive:
            scale = heal_scale if spell.self_effect.kind == EffectKind.REGEN else 1.0
            events += self._apply(caster, spell.self_effect, spell.name, roll=False, scale=scale)
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
        spell = None if e.has_effect(EffectKind.SILENCE) else e.choose_spell(p, self.rng)
        if spell:
            return self._resolve_spell(e, p, spell, caster_is_player=False)

        roll, to_hit = self.rng.random(), hit_chance(e.attributes.agility, e.blind_penalty())
        if roll > to_hit:
            return [LogEvent(f"{e.name} swings at you but misses!", Tone.MISS)]
        if roll > to_hit - p.dodge():
            return [LogEvent(f"You dodge {e.name}'s attack!", Tone.PLAYER)]
        raw = e.base_damage + e.attributes.strength * 0.3 + e.attributes.agility * 0.2
        raw *= 1 + self.rng.uniform(-config.ENEMY_DAMAGE_VARIANCE, config.ENEMY_DAMAGE_VARIANCE)
        crit = self._crit(enemy_crit_chance(e.attributes.strength))
        if crit:
            raw *= config.CRIT_MULTIPLIER
        dealt = self._hit(e, p, raw, DamageType.PHYSICAL, armor_penetration(e.level, e.is_boss))
        events = [LogEvent(f"{e.name} hits you for {dealt} damage" + (" — CRITICAL!" if crit else "!"),
                           Tone.CRIT if crit else Tone.DAMAGE)]
        if e.lifesteal:
            healed = e.heal(int(dealt * e.lifesteal))
            if healed:
                events.append(LogEvent(f"{e.name} feeds on your blood (+{healed} HP).", Tone.WARNING))
        if p.passive("thorns") and e.alive:
            reflected = e.lose_hp(max(1, int(dealt * p.passive("thorns"))))
            events.append(LogEvent(f"Your thorns bite back for {reflected} damage.", Tone.PLAYER))
        armor = p.armor
        if armor and armor.wear():
            events.append(LogEvent(f"Your {armor.name} is shattered!", Tone.WARNING))
        if p.alive:
            for spec in e.on_hit:
                events += self._apply(p, spec, e.name, scale=enemy_spell_multiplier(e.level) ** 0.5)
        return events


# ------------------------------------------------------------------ consumables (shared with the inventory screen)
def consumable_blocker(player: Player, item: Consumable) -> str | None:
    """Reason a consumable would be wasted right now, or None if it is useful."""
    if item.effect == ConsumableEffect.HEAL and player.hp >= player.max_hp:
        return "You're already at full health."
    if item.effect == ConsumableEffect.MANA and player.mana >= player.max_mana:
        return "Your mana is already full."
    if item.effect == ConsumableEffect.RESTORE and player.hp >= player.max_hp and player.mana >= player.max_mana:
        return "You're already fully restored."
    if item.effect == ConsumableEffect.CURE and not any(k in player.effects for k in CLEANSABLE):
        return "You have no afflictions to cure."
    if item.effect == ConsumableEffect.LOCKPICK:
        return "Lockpicks are used when you pick a lock."
    if item.effect == ConsumableEffect.SKILL_BOOST and player.skill_primes.get(item.skill or "", 0) >= item.potency:
        return "You're already primed for that."
    return None


def apply_consumable(player: Player, item: Consumable) -> list[LogEvent]:
    """Apply an already-removed consumable's effect to the player."""
    boost = 1 + player.passive("healing")
    if item.effect == ConsumableEffect.HEAL:
        return [LogEvent(f"You drink the {item.name} and recover {player.heal(int(item.potency * boost))} HP.",
                         Tone.HEAL)]
    if item.effect == ConsumableEffect.MANA:
        return [LogEvent(f"You drink the {item.name} and recover {player.restore_mana(item.potency)} mana.", Tone.MANA)]
    if item.effect == ConsumableEffect.RESTORE:
        hp, mp = player.heal(int(item.potency * boost)), player.restore_mana(item.potency)
        return [LogEvent(f"You drink the {item.name}: +{hp} HP, +{mp} mana.", Tone.HEAL)]
    if item.effect == ConsumableEffect.SKILL_BOOST and item.skill:
        from rpg.core.skills import Skill

        label = Skill(item.skill).label
        amount = player.prime_skill(item.skill, item.potency)
        return [LogEvent(f"You use the {item.name}: +{amount} {label} for your next {label.lower()} trial.",
                         Tone.REWARD)]
    removed = player.cleanse()
    names = ", ".join(k.value for k in removed) or "nothing"
    return [LogEvent(f"You take the {item.name}. Cured: {names}.", Tone.HEAL)]
