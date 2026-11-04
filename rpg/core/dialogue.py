"""Data-driven branching dialogue: the story engine.

Scenes ("nodes") are written in YAML under ``dialogues/`` (many per file, see ``storydata``) or, for older
content, one JSON file each (``dialogues/tavern/intro.json`` is ``tavern/intro``). Scene schema::

    speaker: Brannoc                  # optional
    lines:                            # plain strings, or {text, if} for lines that only show sometimes
      - "Shut the door. You're letting the winter in."
      - {text: "He eyes your beard with approval.", if: {race: Dwarf}}
    if: {quest_active: inn_rats}      # optional ("conditions" also works): the scene is blocked unless it holds
    effects: [{add_gold: 10}]         # applied on entering the scene
    next: counter                     # optional: where "Continue" goes when there are no choices
    paragraphs: false                 # optional: YAML scenes put a blank line between lines unless told not to
    choices:
      - text: "Buy the cottage. (500 gold)"
        next: key
        if: {min_gold: 500}
        locked: true                  # show it greyed out with a reason instead of hiding it
        effects: [{add_gold: -500}]   # ("locked: Your own reason" overrides the reason)

Text may use ``{name}``, ``{race}``, ``{level}``, ``{gold}`` and ``{var.some.key}``.

**Rewards pay once.** Rewarding effects (``give_xp``, ``give_item``, ``unlock_shop``, positive ``add_gold`` and
``stat_change``, ``set_<stat>``, ``add_var``) fire the first time a scene or choice is reached and never again;
everything else (costs, flags, fights, shops, healing, time) fires every time. Put ``repeat: true`` on a
scene or choice to pay its rewards every time (a shop counter), or ``once: true`` to fire *all* its effects
only once. Any effect may carry its own ``if:``.

Conditions (one mapping may hold several; all must pass):
flag_set, flag_not_set, flag_is [k, v], var ("rep.brannoc >= 3", or [key, op, value]), min_kills, min_level,
min_gold, min_stat [stat, value], min_skill [skill, value], has_item, has_lockpick, race (a name or a list),
not_race, visited, not_visited, first_visit (true/false, the scene being entered), quest_active,
quest_not_started, quest_done, quest_failed, quest_at [quest, stage], time_at, time_gte, time_between [a, b]
(wraps midnight), and the combinators any, all and not.

Effects: set_flag [k, v], remove_flag, set_var [k, v], add_var [k, delta], set_health, heal, full_rest,
set_mana, set_<stat> for any attribute, stat_change [stat, delta], add_gold, give_xp, advance_time, set_time,
give_item (id, name or spec dict), unlock_shop (item id), open_shop ("general"/"magic"), start_combat (enemy id
or name; "ambush": true if the enemy strikes first, "opener": 0.2 to start it missing 20% of its health,
"fled": scene to go to if you run), damage (HP lost, never below 1), visual (+ "duration"), minigame (below),
start_quest, quest_stage [quest, stage], complete_quest, fail_quest, end_game (an ending id, see
``story/endings.yaml``).

Minigames::

    {"minigame": {"type": "stealth", "dc": 12, "title": "Hide!", "intro": "...",
                  "success": "vault/overheard", "partial": "vault/half_heard", "failure": "vault/discovered",
                  "retreat": "vault/hall", "flag": "vault_hide", "duration": 20}}

``type`` is qte, lockpick, timing, memory, balance or stealth (tuning keys for each are the keyword
arguments of its class in ``rpg/core/minigames``). The outcome picks the next node (``partial`` falls back to
``success``); ``retreat`` lets the player back out at the briefing; ``flag`` stores the outcome as a story flag.

UI-facing effects (combat, shops, visuals, endings) are returned as *requests*; the UI fulfils them and
then calls ``proceed()``.
"""

from __future__ import annotations

import json
import operator
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from rpg import config
from rpg.core.attributes import Attribute
from rpg.core.catalog import ITEMS, UnknownItemError
from rpg.core.enemies import ENEMIES, UnknownEnemyError
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.minigames import MinigameSpec, MinigameSpecError, Outcome
from rpg.core.progression import grant_item
from rpg.core.quests import DONE, FAILED, FINAL_STAGES, QuestBook
from rpg.core.skills import Skill, skill_rating
from rpg.core.storydata import StoryDataError, as_conditions, load_scene_file
from rpg.core.world import WorldState


class DialogueError(Exception):
    pass


class DialogueContext(Protocol):
    player: Player
    world: WorldState
    rng: random.Random


@dataclass
class Line:
    text: str
    conditions: list[dict] = field(default_factory=list)


@dataclass
class DialogueChoice:
    text: str
    next_id: str | None = None
    effects: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)
    locked: bool | str = False  # show greyed out (with this reason, if a string) when the conditions fail
    repeat: bool = False
    once: bool = False


@dataclass
class DialogueNode:
    node_id: str
    speaker: str = ""
    lines: list[Line] = field(default_factory=list)
    choices: list[DialogueChoice] = field(default_factory=list)
    effects: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)
    next_id: str | None = None
    repeat: bool = False
    once: bool = False
    paragraphs: bool = False  # a blank line between lines (YAML scenes default to this)

    @classmethod
    def from_dict(cls, node_id: str, data: dict) -> "DialogueNode":
        def conditions(item: dict) -> list[dict]:
            return as_conditions(item.get("conditions")) + as_conditions(item.get("if"))

        lines = []
        for line in data.get("lines") or []:
            if isinstance(line, dict):
                lines.append(Line(str(line.get("text", "")), as_conditions(line.get("if"))))
            else:
                lines.append(Line(str(line)))
        choices = []
        for c in data.get("choices") or []:
            locked = c.get("locked", False)
            choices.append(DialogueChoice(str(c.get("text", "...")), c.get("next"), list(c.get("effects") or []),
                                          conditions(c), locked if isinstance(locked, str) else bool(locked),
                                          bool(c.get("repeat", False)), bool(c.get("once", False))))
        return cls(
            node_id=node_id,
            speaker=str(data.get("speaker") or ""),
            lines=lines,
            choices=choices,
            effects=list(data.get("effects") or []),
            conditions=conditions(data),
            next_id=data.get("next"),
            repeat=bool(data.get("repeat", False)),
            once=bool(data.get("once", False)),
            paragraphs=bool(data.get("paragraphs", False)),
        )


# ------------------------------------------------------------------ requests to the UI
@dataclass(frozen=True)
class StartCombatRequest:
    enemy_id: str
    ambush: bool = False
    opener: float = 0.0
    fled: str | None = None  # scene to go to if the player runs away


@dataclass(frozen=True)
class OpenShopRequest:
    mode: str


@dataclass(frozen=True)
class VisualRequest:
    name: str
    duration: float = 1.2


@dataclass(frozen=True)
class EndGameRequest:
    ending_id: str


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


Request = StartCombatRequest | OpenShopRequest | VisualRequest | MinigameRequest | EndGameRequest


@dataclass
class StepResult:
    events: list[LogEvent] = field(default_factory=list)
    requests: list[Request] = field(default_factory=list)


@dataclass(frozen=True)
class MenuEntry:
    """One choice as the player sees it: available (``index`` is what ``choose`` takes) or locked."""
    choice: DialogueChoice
    text: str
    index: int | None
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.index is not None


# ------------------------------------------------------------------ repository
class DialogueRepository:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self._cache: dict[str, DialogueNode] = {}
        self._yaml: dict[str, dict] | None = None
        self._yaml_files: dict[str, str] = {}  # node id -> the file that defines it
        self.file_errors: list[str] = []

    # -------------------------------------------------- YAML scenes (loaded once, on first use)
    def _yaml_index(self) -> dict[str, dict]:
        if self._yaml is None:
            self._yaml, self.file_errors = {}, []
            if self.base_dir.is_dir():
                for path in sorted(self.base_dir.rglob("*.yaml")):
                    scope = path.relative_to(self.base_dir).with_suffix("").as_posix()
                    try:
                        scenes = load_scene_file(path, scope)
                    except StoryDataError as exc:
                        self.file_errors.append(f"{scope}.yaml: {exc}")
                        continue
                    for node_id, data in scenes.items():
                        self._yaml[node_id] = data
                        self._yaml_files[node_id] = f"{scope}.yaml"
        return self._yaml

    def yaml_ids(self) -> list[str]:
        return sorted(self._yaml_index())

    def file_of(self, node_id: str) -> str:
        return self._yaml_files.get(node_id, f"{node_id}.json")

    # -------------------------------------------------- lookup
    def path_for(self, node_id: str) -> Path:
        rel = node_id if node_id.endswith(".json") else f"{node_id}.json"
        path = (self.base_dir / rel).resolve()
        if self.base_dir.resolve() not in path.parents:
            raise DialogueError(f"Dialogue id escapes the dialogue folder: {node_id}")
        return path

    def load(self, node_id: str) -> DialogueNode:
        if node_id in self._cache:
            return self._cache[node_id]
        index = self._yaml_index()
        if node_id in index:
            node = DialogueNode.from_dict(node_id, index[node_id])
        else:
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
        if not isinstance(node_id, str):
            return False
        if node_id in self._yaml_index():
            return True
        try:
            return self.path_for(node_id).is_file()
        except DialogueError:
            return False

    def json_ids(self) -> list[str]:
        if not self.base_dir.is_dir():
            return []
        return sorted(p.relative_to(self.base_dir).with_suffix("").as_posix() for p in self.base_dir.rglob("*.json"))

    def all_ids(self) -> list[str]:
        return sorted(set(self.json_ids()) | set(self._yaml_index()))

    def random_id(self, category: str, rng: random.Random) -> str | None:
        folder = self.base_dir / "random" / category
        if not folder.is_dir():
            return None
        candidates = sorted(p.stem for p in folder.glob("*.json"))
        return f"random/{category}/{rng.choice(candidates)}" if candidates else None

    def validate(self) -> list[str]:
        """Content lint for single scenes (see ``rpg.core.storycheck`` for whole-story checks)."""
        self._yaml_index()
        problems: list[str] = list(self.file_errors)
        for node_id in sorted(set(self.json_ids()) & set(self._yaml_index())):
            problems.append(f"{node_id}: defined in both {node_id}.json and {self.file_of(node_id)}")
        for node_id in self.all_ids():
            try:
                node = self.load(node_id)
            except DialogueError as exc:
                problems.append(str(exc))
                continue
            problems += [f"{node_id}: {p}" for p in node_problems(node, self)]
        return problems


def node_problems(node: DialogueNode, repo: DialogueRepository) -> list[str]:
    problems: list[str] = []
    all_effects = list(node.effects)
    all_conditions = list(node.conditions) + [c for line in node.lines for c in line.conditions]
    if node.next_id and not repo.exists(node.next_id):
        problems.append(f"next points to missing '{node.next_id}'")
    for choice in node.choices:
        all_effects += choice.effects
        all_conditions += choice.conditions
        if choice.next_id and not repo.exists(choice.next_id):
            problems.append(f"choice '{choice.text[:40]}' points to missing '{choice.next_id}'")
    for effect in all_effects:
        if not isinstance(effect, dict):
            problems.append(f"effect must be a mapping, not {effect!r}")
            continue
        all_conditions += as_conditions(effect.get("if"))
        if not any(key in effect for key in PRIMARY_EFFECTS):
            problems.append(f"unknown effect '{', '.join(effect)}'")
        for key, value in effect.items():
            if key not in KNOWN_EFFECTS:
                problems.append(f"unknown effect '{key}'")
            elif key == "start_combat":
                try:
                    ENEMIES.resolve(str(value))
                except UnknownEnemyError:
                    problems.append(f"unknown enemy '{value}'")
            elif key == "fled" and not repo.exists(value):
                problems.append(f"fled points to missing '{value}'")
            elif key == "unlock_shop" and value not in ITEMS:
                problems.append(f"unlock_shop names unknown item id '{value}'")
            elif key == "minigame":
                if not isinstance(value, dict):
                    problems.append("minigame must be an object")
                    continue
                problems += [f"minigame {p}" for p in MinigameSpec.problems(value)]
                for outcome in ("success", "partial", "failure", "retreat"):
                    target = value.get(outcome)
                    if target and not repo.exists(target):
                        problems.append(f"minigame {outcome} points to missing '{target}'")
    for cond in walk_conditions(all_conditions):
        problems += condition_problems(cond)
    return problems


SET_STAT_EFFECTS = {f"set_{attribute.value}": attribute for attribute in Attribute}

# Keys that name what an effect does (the others are options of those).
PRIMARY_EFFECTS = {
    "set_flag", "remove_flag", "set_var", "add_var", "set_health", "heal", "full_rest", "set_mana", "set_stamina",
    *SET_STAT_EFFECTS, "stat_change", "add_gold", "give_xp", "advance_time", "set_time", "give_item",
    "unlock_shop", "open_shop", "start_combat", "visual", "damage", "minigame",
    "start_quest", "quest_stage", "complete_quest", "fail_quest", "end_game",
}
KNOWN_EFFECTS = PRIMARY_EFFECTS | {"ambush", "opener", "fled", "duration", "if"}
REWARD_EFFECTS = {"give_xp", "give_item", "unlock_shop", "add_var", *SET_STAT_EFFECTS}

KNOWN_CONDITIONS = {
    "flag_set", "flag_not_set", "flag_is", "var", "min_kills", "min_level", "min_gold", "min_stat", "min_skill",
    "has_item", "has_lockpick", "race", "not_race", "visited", "not_visited", "first_visit", "quest_active",
    "quest_not_started", "quest_done", "quest_failed", "quest_at", "time_at", "time_gte", "time_between",
    "any", "all", "not",
}


def is_reward(effect: dict) -> bool:
    if any(key in effect for key in REWARD_EFFECTS):
        return True
    try:
        if "add_gold" in effect:
            return int(effect["add_gold"]) > 0
        if "stat_change" in effect:
            return int(effect["stat_change"][1]) > 0
    except (TypeError, ValueError, IndexError):
        return False
    return False


# ------------------------------------------------------------------ text
_TEMPLATE = re.compile(r"\{(name|race|level|gold|var\.[\w.]+)\}")


def render_text(ctx: DialogueContext, text: str) -> str:
    """Fill in ``{name}``, ``{race}``, ``{level}``, ``{gold}`` and ``{var.key}``; anything else is left alone."""
    player = ctx.player

    def fill(match: re.Match) -> str:
        key = match.group(1)
        if key.startswith("var."):
            value = ctx.world.var(key[4:])
            return str(int(value)) if float(value).is_integer() else str(value)
        return str({"name": player.name, "race": player.race, "level": player.level, "gold": player.gold}[key])

    return _TEMPLATE.sub(fill, text)


def render_lines(ctx: DialogueContext, lines: list[Line], here: str | None = None) -> list[str]:
    return [render_text(ctx, line.text) for line in lines if check_conditions(ctx, line.conditions, here)]


# ------------------------------------------------------------------ conditions
_VAR_EXPR = re.compile(r"^\s*([\w.]+)\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
_OPS = {">=": operator.ge, "<=": operator.le, "==": operator.eq, "!=": operator.ne, ">": operator.gt, "<": operator.lt}


def parse_var(spec: Any) -> tuple[str, Any, float]:
    """``"rep.brannoc >= 3"`` or ``["rep.brannoc", ">=", 3]`` -> (key, op, value)."""
    if isinstance(spec, str):
        match = _VAR_EXPR.match(spec)
        if not match:
            raise ValueError(f"can't read var condition '{spec}' (expected 'name >= 3')")
        key, op, value = match.groups()
    else:
        key, op, value = spec
    if op not in _OPS:
        raise ValueError(f"unknown comparison '{op}'")
    return str(key), _OPS[op], float(value)


def walk_conditions(conditions: list[dict]):
    """Every condition mapping, including those nested in any/all/not."""
    for cond in conditions or []:
        if not isinstance(cond, dict):
            continue
        yield cond
        for key in ("any", "all", "not"):
            if key in cond:
                yield from walk_conditions(as_conditions(cond[key]))


def condition_problems(cond: dict) -> list[str]:
    problems = [f"unknown condition '{key}'" for key in cond if key not in KNOWN_CONDITIONS]
    if "var" in cond:
        try:
            parse_var(cond["var"])
        except (ValueError, TypeError) as exc:
            problems.append(str(exc))
    for key in ("race", "not_race"):
        if key in cond:
            names = cond[key] if isinstance(cond[key], list) else [cond[key]]
            problems += [f"unknown race '{n}'" for n in names if n not in config.RACES]
    return problems


def check_conditions(ctx: DialogueContext, conditions: list[dict], here: str | None = None) -> bool:
    for cond in conditions or []:
        if not _check_one(ctx, cond, here):
            return False
    return True


def _quest_stage(ctx: DialogueContext, quest_id: str) -> str | None:
    return ctx.world.quests.get(str(quest_id))


def _check_one(ctx: DialogueContext, cond: dict, here: str | None = None) -> bool:
    world, player = ctx.world, ctx.player
    flags, bell = world.flags, world.bell
    try:
        if "flag_set" in cond and not flags.get(cond["flag_set"]):
            return False
        if "flag_not_set" in cond and flags.get(cond["flag_not_set"]):
            return False
        if "flag_is" in cond:
            key, value = cond["flag_is"]
            if flags.get(str(key)) != value:
                return False
        if "var" in cond:
            key, op, value = parse_var(cond["var"])
            if not op(world.var(key), value):
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
        if "has_lockpick" in cond and bool(player.lockpicks()) != bool(cond["has_lockpick"]):
            return False
        if "min_gold" in cond and player.gold < int(cond["min_gold"]):
            return False
        if "has_item" in cond and player.inventory.find_by_name(str(cond["has_item"])) is None:
            return False
        if "race" in cond:
            races = cond["race"] if isinstance(cond["race"], list) else [cond["race"]]
            if player.race not in races:
                return False
        if "not_race" in cond:
            races = cond["not_race"] if isinstance(cond["not_race"], list) else [cond["not_race"]]
            if player.race in races:
                return False
        if "visited" in cond and not world.visits.get(str(cond["visited"])):
            return False
        if "not_visited" in cond and world.visits.get(str(cond["not_visited"])):
            return False
        if "first_visit" in cond:
            first = here is not None and world.visits.get(here, 0) <= 1
            if first != bool(cond["first_visit"]):
                return False
        if "quest_active" in cond and _quest_stage(ctx, cond["quest_active"]) in (None, *FINAL_STAGES):
            return False
        if "quest_not_started" in cond and _quest_stage(ctx, cond["quest_not_started"]) is not None:
            return False
        if "quest_done" in cond and _quest_stage(ctx, cond["quest_done"]) != DONE:
            return False
        if "quest_failed" in cond and _quest_stage(ctx, cond["quest_failed"]) != FAILED:
            return False
        if "quest_at" in cond:
            quest_id, stage = cond["quest_at"]
            if _quest_stage(ctx, quest_id) != str(stage):
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
        if "all" in cond and not check_conditions(ctx, as_conditions(cond["all"]), here):
            return False
        if "any" in cond and not any(_check_one(ctx, c, here) for c in as_conditions(cond["any"])):
            return False
        if "not" in cond and check_conditions(ctx, as_conditions(cond["not"]), here):
            return False
    except (TypeError, ValueError, IndexError, StoryDataError):
        return False
    return True


def describe_unmet(ctx: DialogueContext, conditions: list[dict], here: str | None = None) -> str:
    """A short reason for the first condition that fails, for greyed-out choices."""
    for cond in conditions or []:
        if _check_one(ctx, cond, here):
            continue
        try:
            if "min_gold" in cond and ctx.player.gold < int(cond["min_gold"]):
                return f"Requires {int(cond['min_gold'])} gold"
            if "min_stat" in cond:
                stat, minimum = cond["min_stat"]
                return f"Requires {Attribute(str(stat).lower()).label} {int(minimum)}"
            if "min_skill" in cond:
                skill, minimum = cond["min_skill"]
                return f"Requires {str(skill).title()} {int(minimum)}"
            if "min_level" in cond:
                return f"Requires level {int(cond['min_level'])}"
            if "has_item" in cond:
                return f"Requires {cond['has_item']}"
            if "has_lockpick" in cond:
                return "Requires a lockpick"
            if "race" in cond:
                races = cond["race"] if isinstance(cond["race"], list) else [cond["race"]]
                return " or ".join(races) + " only"
        except (TypeError, ValueError, IndexError):
            pass
        return "Not available"
    return ""


# ------------------------------------------------------------------ effects
def apply_effects(ctx: DialogueContext, effects: list[dict], claim: str | None = None, *,
                  repeat: bool = False, once: bool = False) -> StepResult:
    """Apply ``effects``. With a ``claim`` key, rewards (or everything, with ``once``) only pay the first time."""
    result = StepResult()
    claimed = claim is not None and claim in ctx.world.claimed
    if once and claimed:
        return result
    for effect in effects or []:
        if not isinstance(effect, dict):
            continue
        if claim is not None and claimed and not repeat and is_reward(effect):
            continue
        if "if" in effect and not check_conditions(ctx, as_conditions(effect["if"])):
            continue
        try:
            _apply_one(ctx, effect, result)
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            result.events.append(LogEvent(f"(Ignored malformed effect {effect}: {exc})", Tone.SYSTEM))
    if claim is not None and effects:
        ctx.world.claimed.add(claim)
    return result


def _quests(ctx: DialogueContext) -> QuestBook:
    return getattr(ctx, "quests", None) or QuestBook()


def _set_quest(ctx: DialogueContext, quest_id: str, stage: str, say) -> None:
    book = _quests(ctx)
    quests = ctx.world.quests
    previous = quests.get(quest_id)
    if previous == stage or previous in FINAL_STAGES:
        return  # finished quests stay finished
    quests[quest_id] = stage
    title = book.title(quest_id)
    if stage == DONE:
        say(LogEvent(f"Quest complete: {title}", Tone.REWARD))
    elif stage == FAILED:
        say(LogEvent(f"Quest failed: {title}", Tone.WARNING))
    elif previous is None:
        say(LogEvent(f"New quest: {title}", Tone.STORY))
    else:
        say(LogEvent(f"Journal updated: {title}", Tone.STORY))


def _apply_one(ctx: DialogueContext, effect: dict, out: StepResult) -> None:
    player, world = ctx.player, ctx.world
    say = out.events.append
    if "set_flag" in effect:
        key, value = effect["set_flag"]
        world.flags[str(key)] = value
    elif "remove_flag" in effect:
        world.flags.pop(str(effect["remove_flag"]), None)
    elif "set_var" in effect:
        key, value = effect["set_var"]
        world.vars[str(key)] = float(value) if not float(value).is_integer() else int(value)
    elif "add_var" in effect:
        key, delta = effect["add_var"]
        total = world.var(str(key)) + float(delta)
        world.vars[str(key)] = int(total) if float(total).is_integer() else total
    elif "set_health" in effect:
        player.hp = max(1, min(player.max_hp, int(effect["set_health"])))
        say(LogEvent(f"Your health is now {player.hp}.", Tone.HEAL))
    elif "heal" in effect:
        say(LogEvent(f"You recover {player.heal(int(effect['heal']))} HP.", Tone.HEAL))
    elif "full_rest" in effect:
        player.hp, player.mana = player.max_hp, player.max_mana
        say(LogEvent("You wake rested: full health and mana.", Tone.HEAL))
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
                                               float(effect.get("opener", 0.0)), effect.get("fled")))
    elif "damage" in effect:
        lost = player.lose_hp(min(int(effect["damage"]), player.hp - 1))
        say(LogEvent(f"You lose {lost} HP.", Tone.DAMAGE))
    elif "minigame" in effect:
        try:
            out.requests.append(MinigameRequest.from_dict(dict(effect["minigame"])))
        except MinigameSpecError as exc:
            say(LogEvent(f"(Broken minigame: {exc})", Tone.SYSTEM))
    elif "start_quest" in effect:
        quest_id = str(effect["start_quest"])
        if quest_id not in world.quests:
            quest = _quests(ctx).get(quest_id)
            _set_quest(ctx, quest_id, quest.first_stage if quest else "started", say)
    elif "quest_stage" in effect:
        quest_id, stage = effect["quest_stage"]
        _set_quest(ctx, str(quest_id), str(stage), say)
    elif "complete_quest" in effect:
        _set_quest(ctx, str(effect["complete_quest"]), DONE, say)
    elif "fail_quest" in effect:
        _set_quest(ctx, str(effect["fail_quest"]), FAILED, say)
    elif "end_game" in effect:
        out.requests.append(EndGameRequest(str(effect["end_game"])))
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

    # -------------------------------------------------- what the player sees
    @property
    def speaker(self) -> str:
        return render_text(self.ctx, self.node.speaker) if self.node else ""

    def lines(self) -> list[str]:
        if self.node is None:
            return []
        return render_lines(self.ctx, self.node.lines, self.node.node_id)

    def _here(self) -> str | None:
        return self.node.node_id if self.node else None

    def choices(self) -> list[DialogueChoice]:
        if self.node is None or self.finished:
            return []
        return [c for c in self.node.choices if check_conditions(self.ctx, c.conditions, self._here())]

    def menu(self) -> list[MenuEntry]:
        """Choices in order: the available ones, plus locked ones that ask to be shown greyed out."""
        if self.node is None or self.finished:
            return []
        entries, index = [], 0
        for choice in self.node.choices:
            text = render_text(self.ctx, choice.text)
            if check_conditions(self.ctx, choice.conditions, self._here()):
                entries.append(MenuEntry(choice, text, index))
                index += 1
            elif choice.locked:
                reason = choice.locked if isinstance(choice.locked, str) else \
                    describe_unmet(self.ctx, choice.conditions, self._here())
                entries.append(MenuEntry(choice, text, None, reason))
        return entries

    @property
    def is_terminal(self) -> bool:
        """True when the current node offers nothing to choose (show a Continue button)."""
        return not self.choices()

    # -------------------------------------------------- moving through the story
    def choose(self, index: int) -> StepResult:
        options = self.choices()
        if not 0 <= index < len(options):
            raise IndexError(index)
        choice = options[index]
        assert self.node is not None
        self._pending_next = choice.next_id
        claim = f"{self.node.node_id}#{self.node.choices.index(choice)}"
        return apply_effects(self.ctx, choice.effects, claim, repeat=choice.repeat, once=choice.once)

    def resolve_minigame(self, request: MinigameRequest, outcome: Outcome | None) -> None:
        """Route the conversation by a minigame's outcome (``None`` = the player backed out)."""
        if request.flag:
            self.ctx.world.flags[request.flag] = outcome.value if outcome else "retreat"
        self._redirect(request.next_node(outcome))

    def resolve_flight(self, request: StartCombatRequest) -> None:
        """The player ran from a fight that names where running leads."""
        self._redirect(request.fled)

    def _redirect(self, target: str | None) -> None:
        if target:
            self._pending_next = target
            self._redirected = True

    @property
    def redirected(self) -> bool:
        """A minigame or a fled fight on the current node chose where to go next; call ``proceed()``."""
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
        world = self.ctx.world
        world.visits[node_id] = world.visits.get(node_id, 0) + 1
        world.advance(1)  # every scene takes an hour
        self._pending_next = node.next_id
        return apply_effects(self.ctx, node.effects, node_id, repeat=node.repeat, once=node.once)
