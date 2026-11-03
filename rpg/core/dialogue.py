"""Data-driven branching dialogue (quests and campfire encounters).

Dialogue nodes are JSON files under ``dialogues/``; a node id is its path without ``.json``
(``"tavern/intro"``). Node schema::

    {
      "speaker": "Barkeep",                     # optional
      "lines": ["...", "..."],
      "conditions": [{"flag_set": "x"}],         # optional, node is blocked if any fails
      "effects": [{"add_gold": 10}],             # optional, applied on entering the node
      "choices": [
        {"text": "...", "next": "tavern/bar", "effects": [...], "conditions": [...]}
      ]
    }

Conditions: flag_set, flag_not_set, flag_is [k, v], min_kills, min_level, min_gold, min_stat [stat, value]
(e.g. ["charisma", 12] for a persuasion branch), min_skill [skill, value] (e.g. ["stealth", 14]),
has_item, has_lockpick (true), time_at, time_gte, time_between [a, b] (wraps midnight).
Effects: set_flag [k, v], remove_flag, set_health, heal, set_mana, set_<stat> for any attribute
(set_strength, set_dexterity, set_agility, set_vitality, set_intelligence, set_wisdom, set_charisma),
stat_change [stat, delta], add_gold, give_xp, advance_time, set_time,
give_item (id, name or spec dict), unlock_shop (item id), open_shop ("general"/"magic"),
start_combat (enemy id or name; add "ambush": true if the enemy strikes first, or "opener": 0.2 to start it
missing 20% of its health), damage (HP lost, never below 1), visual (+ "duration"),
minigame (see below).

Minigames::

    {"minigame": {"type": "stealth", "dc": 12, "title": "Hide!", "intro": "...",
                  "success": "vault/overheard", "partial": "vault/half_heard", "failure": "vault/discovered",
                  "retreat": "vault/hall", "flag": "vault_hide", "duration": 20}}

``type`` is qte, lockpick, timing, memory, balance or stealth (tuning keys for each are the keyword
arguments of its class in ``rpg/core/minigames``). The outcome picks the next node (``partial`` falls back to
``success``); ``retreat`` lets the player back out at the briefing; ``flag`` stores the outcome as a story flag.

UI-facing effects (combat, shops, visuals) are returned as *requests*; the UI fulfils them and
then calls ``proceed()``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rpg.core.attributes import Attribute
from rpg.core.catalog import ITEMS, UnknownItemError
from rpg.core.enemies import ENEMIES, UnknownEnemyError
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.minigames import MinigameSpec, MinigameSpecError, Outcome
from rpg.core.progression import grant_item
from rpg.core.skills import Skill, skill_rating
from rpg.core.world import WorldState


class DialogueError(Exception):
    pass


class DialogueContext(Protocol):
    player: Player
    world: WorldState
    rng: random.Random


@dataclass
class DialogueChoice:
    text: str
    next_id: str | None = None
    effects: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)


@dataclass
class DialogueNode:
    node_id: str
    speaker: str = ""
    lines: list[str] = field(default_factory=list)
    choices: list[DialogueChoice] = field(default_factory=list)
    effects: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, node_id: str, data: dict) -> "DialogueNode":
        return cls(
            node_id=node_id,
            speaker=str(data.get("speaker") or ""),
            lines=[str(line) for line in data.get("lines", [])],
            choices=[
                DialogueChoice(str(c.get("text", "...")), c.get("next"), list(c.get("effects") or []),
                               list(c.get("conditions") or []))
                for c in data.get("choices", [])
            ],
            effects=list(data.get("effects") or []),
            conditions=list(data.get("conditions") or []),
        )


# ------------------------------------------------------------------ requests to the UI
@dataclass(frozen=True)
class StartCombatRequest:
    enemy_id: str
    ambush: bool = False
    opener: float = 0.0


@dataclass(frozen=True)
class OpenShopRequest:
    mode: str


@dataclass(frozen=True)
class VisualRequest:
    name: str
    duration: float = 1.2


@dataclass(frozen=True)
class MinigameRequest:
    spec: MinigameSpec
    success: str | None = None
    partial: str | None = None
    failure: str | None = None
    retreat: str | None = None
    flag: str | None = None

    @property
    def allow_retreat(self) -> bool:
        return self.retreat is not None

    def next_node(self, outcome: Outcome | None) -> str | None:
        if outcome is None:
            return self.retreat
        if outcome == Outcome.PARTIAL:
            return self.partial or self.success
        return self.success if outcome == Outcome.SUCCESS else self.failure

    @classmethod
    def from_dict(cls, data: dict) -> "MinigameRequest":
        return cls(MinigameSpec.from_dict(data), data.get("success"), data.get("partial"), data.get("failure"),
                   data.get("retreat"), data.get("flag"))


Request = StartCombatRequest | OpenShopRequest | VisualRequest | MinigameRequest


@dataclass
class StepResult:
    events: list[LogEvent] = field(default_factory=list)
    requests: list[Request] = field(default_factory=list)


# ------------------------------------------------------------------ repository
class DialogueRepository:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self._cache: dict[str, DialogueNode] = {}

    def path_for(self, node_id: str) -> Path:
        rel = node_id if node_id.endswith(".json") else f"{node_id}.json"
        path = (self.base_dir / rel).resolve()
        if self.base_dir.resolve() not in path.parents:
            raise DialogueError(f"Dialogue id escapes the dialogue folder: {node_id}")
        return path

    def load(self, node_id: str) -> DialogueNode:
        if node_id in self._cache:
            return self._cache[node_id]
        path = self.path_for(node_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise DialogueError(f"Missing dialogue node '{node_id}'") from None
        except json.JSONDecodeError as exc:
            raise DialogueError(f"Malformed dialogue '{node_id}': {exc}") from None
        node = DialogueNode.from_dict(node_id, data)
        self._cache[node_id] = node
        return node

    def exists(self, node_id: str) -> bool:
        try:
            return self.path_for(node_id).is_file()
        except DialogueError:
            return False

    def all_ids(self) -> list[str]:
        if not self.base_dir.is_dir():
            return []
        return sorted(p.relative_to(self.base_dir).with_suffix("").as_posix() for p in self.base_dir.rglob("*.json"))

    def random_id(self, category: str, rng: random.Random) -> str | None:
        folder = self.base_dir / "random" / category
        if not folder.is_dir():
            return None
        candidates = sorted(p.stem for p in folder.glob("*.json"))
        return f"random/{category}/{rng.choice(candidates)}" if candidates else None

    def validate(self) -> list[str]:
        """Content lint: unreadable files, dangling ``next`` links, unknown enemies, effects and items."""
        problems: list[str] = []
        for node_id in self.all_ids():
            try:
                node = self.load(node_id)
            except DialogueError as exc:
                problems.append(str(exc))
                continue
            all_effects = list(node.effects)
            for choice in node.choices:
                all_effects += choice.effects
                if choice.next_id and not self.exists(choice.next_id):
                    problems.append(f"{node_id}: choice '{choice.text[:40]}' points to missing '{choice.next_id}'")
            for effect in all_effects:
                for key, value in effect.items():
                    if key not in KNOWN_EFFECTS:
                        problems.append(f"{node_id}: unknown effect '{key}'")
                    elif key == "start_combat":
                        try:
                            ENEMIES.resolve(str(value))
                        except UnknownEnemyError:
                            problems.append(f"{node_id}: unknown enemy '{value}'")
                    elif key == "unlock_shop" and value not in ITEMS:
                        problems.append(f"{node_id}: unlock_shop names unknown item id '{value}'")
                    elif key == "minigame":
                        if not isinstance(value, dict):
                            problems.append(f"{node_id}: minigame must be an object")
                            continue
                        problems += [f"{node_id}: minigame {p}" for p in MinigameSpec.problems(value)]
                        for outcome in ("success", "partial", "failure", "retreat"):
                            target = value.get(outcome)
                            if target and not self.exists(target):
                                problems.append(f"{node_id}: minigame {outcome} points to missing '{target}'")
        return problems


SET_STAT_EFFECTS = {f"set_{attribute.value}": attribute for attribute in Attribute}

KNOWN_EFFECTS = {
    "set_flag", "remove_flag", "set_health", "heal", "set_mana", "set_stamina", *SET_STAT_EFFECTS,
    "stat_change", "add_gold", "give_xp", "advance_time", "set_time", "give_item",
    "unlock_shop", "open_shop", "start_combat", "ambush", "opener", "visual", "duration", "damage", "minigame",
}


# ------------------------------------------------------------------ conditions
def check_conditions(ctx: DialogueContext, conditions: list[dict]) -> bool:
    for cond in conditions or []:
        if not _check_one(ctx, cond):
            return False
    return True


def _check_one(ctx: DialogueContext, cond: dict) -> bool:
    flags, bell, player = ctx.world.flags, ctx.world.bell, ctx.player
    try:
        if "flag_set" in cond and not flags.get(cond["flag_set"]):
            return False
        if "flag_not_set" in cond and flags.get(cond["flag_not_set"]):
            return False
        if "min_kills" in cond and player.kills < int(cond["min_kills"]):
            return False
        if "min_level" in cond and player.level < int(cond["min_level"]):
            return False
        if "min_stat" in cond:
            stat, minimum = cond["min_stat"]
            if player.attributes.get(str(stat).lower()) < int(minimum):
                return False
        if "min_skill" in cond:
            skill, minimum = cond["min_skill"]
            if skill_rating(player, Skill(str(skill).lower())) < int(minimum):
                return False
        if "flag_is" in cond:
            key, value = cond["flag_is"]
            if flags.get(str(key)) != value:
                return False
        if "has_lockpick" in cond and bool(player.lockpicks()) != bool(cond["has_lockpick"]):
            return False
        if "min_gold" in cond and player.gold < int(cond["min_gold"]):
            return False
        if "has_item" in cond and player.inventory.find_by_name(str(cond["has_item"])) is None:
            return False
        if "time_at" in cond and bell != int(cond["time_at"]):
            return False
        if "time_gte" in cond and bell < int(cond["time_gte"]):
            return False
        if "time_between" in cond:
            start, end = (int(v) for v in cond["time_between"][:2])
            inside = start <= bell <= end if start <= end else (bell >= start or bell <= end)
            if not inside:
                return False
    except (TypeError, ValueError, IndexError):
        return False
    return True


# ------------------------------------------------------------------ effects
def apply_effects(ctx: DialogueContext, effects: list[dict]) -> StepResult:
    result = StepResult()
    for effect in effects or []:
        try:
            _apply_one(ctx, effect, result)
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            result.events.append(LogEvent(f"(Ignored malformed effect {effect}: {exc})", Tone.SYSTEM))
    return result


def _apply_one(ctx: DialogueContext, effect: dict, out: StepResult) -> None:
    player, world = ctx.player, ctx.world
    say = out.events.append
    if "set_flag" in effect:
        key, value = effect["set_flag"]
        world.flags[str(key)] = value
    elif "remove_flag" in effect:
        world.flags.pop(str(effect["remove_flag"]), None)
    elif "set_health" in effect:
        player.hp = max(1, min(player.max_hp, int(effect["set_health"])))
        say(LogEvent(f"Your health is now {player.hp}.", Tone.HEAL))
    elif "heal" in effect:
        say(LogEvent(f"You recover {player.heal(int(effect['heal']))} HP.", Tone.HEAL))
    elif "set_mana" in effect:
        amount = max(0, int(effect["set_mana"]))
        player.max_mana = max(player.max_mana, amount)
        player.mana = amount
        say(LogEvent(f"Your mana is now {amount}.", Tone.MANA))
    elif "set_stamina" in effect:
        pass  # legacy effect from the original game; stamina no longer exists
    elif any(k in effect for k in SET_STAT_EFFECTS):
        key = next(k for k in SET_STAT_EFFECTS if k in effect)
        attribute = SET_STAT_EFFECTS[key]
        value = player.set_attribute(attribute, int(effect[key]))
        say(LogEvent(f"Your {attribute.value} is now {value}.", Tone.REWARD))
    elif "stat_change" in effect:
        stat, delta = effect["stat_change"]
        try:
            attribute = Attribute(str(stat).lower())
        except ValueError:
            say(LogEvent(f"(Unknown stat '{stat}')", Tone.SYSTEM))
            return
        new = player.change_attribute(attribute, int(delta))
        sign = "+" if int(delta) >= 0 else ""
        say(LogEvent(f"{attribute.label} {sign}{int(delta)} (now {new}).", Tone.REWARD if int(delta) >= 0 else Tone.WARNING))
    elif "add_gold" in effect:
        amount = int(effect["add_gold"])
        player.add_gold(amount)
        say(LogEvent(f"{'+' if amount >= 0 else ''}{amount} gold.", Tone.GOLD))
    elif "give_xp" in effect:
        amount = int(effect["give_xp"])
        levels = player.gain_xp(amount)
        say(LogEvent(f"+{amount} XP.", Tone.XP))
        if levels:
            say(LogEvent(f"Level up! You are now level {player.level}.", Tone.REWARD))
    elif "advance_time" in effect:
        world.advance(int(effect["advance_time"]))
    elif "set_time" in effect:
        world.set_time(int(effect["set_time"]))
    elif "give_item" in effect:
        say(grant_item(player, ITEMS.from_spec(effect["give_item"])))
    elif "unlock_shop" in effect:
        template_id = str(effect["unlock_shop"])
        if template_id not in ITEMS:
            found = ITEMS.find_id_by_name(template_id)
            if not found:
                raise UnknownItemError(template_id)
            template_id = found
        world.shop_unlocks.add(template_id)
        say(LogEvent(f"The merchant will now stock {ITEMS.create(template_id).name}.", Tone.GOLD))
    elif "open_shop" in effect:
        out.requests.append(OpenShopRequest(str(effect["open_shop"])))
    elif "visual" in effect:
        out.requests.append(VisualRequest(str(effect["visual"]), float(effect.get("duration", 1.2))))
    elif "start_combat" in effect:
        out.requests.append(StartCombatRequest(str(effect["start_combat"]), bool(effect.get("ambush", False)),
                                               float(effect.get("opener", 0.0))))
    elif "damage" in effect:
        lost = player.lose_hp(min(int(effect["damage"]), player.hp - 1))
        say(LogEvent(f"You lose {lost} HP.", Tone.DAMAGE))
    elif "minigame" in effect:
        try:
            out.requests.append(MinigameRequest.from_dict(dict(effect["minigame"])))
        except MinigameSpecError as exc:
            say(LogEvent(f"(Broken minigame: {exc})", Tone.SYSTEM))
    else:
        say(LogEvent(f"(Unknown dialogue effect: {', '.join(effect)})", Tone.SYSTEM))


# ------------------------------------------------------------------ runner
class DialogueRunner:
    """Walks a dialogue graph one node at a time without any UI knowledge."""

    def __init__(self, ctx: DialogueContext, repository: DialogueRepository, start_id: str) -> None:
        self.ctx = ctx
        self.repository = repository
        self.start_id = start_id
        self.node: DialogueNode | None = None
        self.finished = False
        self.blocked_reason: str | None = None
        self._pending_next: str | None = None
        self._redirected = False

    def start(self) -> StepResult:
        return self._enter(self.start_id)

    def choices(self) -> list[DialogueChoice]:
        if self.node is None or self.finished:
            return []
        return [c for c in self.node.choices if check_conditions(self.ctx, c.conditions)]

    @property
    def is_terminal(self) -> bool:
        """True when the current node offers nothing to choose (show a Continue button)."""
        return not self.choices()

    def choose(self, index: int) -> StepResult:
        options = self.choices()
        if not 0 <= index < len(options):
            raise IndexError(index)
        choice = options[index]
        self._pending_next = choice.next_id
        return apply_effects(self.ctx, choice.effects)

    def resolve_minigame(self, request: MinigameRequest, outcome: Outcome | None) -> None:
        """Route the conversation by a minigame's outcome (``None`` = the player backed out)."""
        if request.flag:
            self.ctx.world.flags[request.flag] = outcome.value if outcome else "retreat"
        target = request.next_node(outcome)
        if target:
            self._pending_next = target
            self._redirected = True

    @property
    def redirected(self) -> bool:
        """A minigame on the current node chose where to go next; call ``proceed()``."""
        return self._redirected

    def proceed(self) -> StepResult:
        """Move to the chosen node (or end the conversation)."""
        next_id, self._pending_next = self._pending_next, None
        self._redirected = False
        if not next_id:
            self.finished = True
            return StepResult()
        return self._enter(next_id)

    def _enter(self, node_id: str) -> StepResult:
        try:
            node = self.repository.load(node_id)
        except DialogueError as exc:
            self.finished = True
            self.blocked_reason = "This path is not written yet..."
            return StepResult([LogEvent(str(exc), Tone.SYSTEM)])
        if not check_conditions(self.ctx, node.conditions):
            self.finished = True
            self.blocked_reason = "You cannot do this right now."
            return StepResult()
        self.node = node
        self.ctx.world.advance(1)  # every scene takes an hour
        return apply_effects(self.ctx, node.effects)
