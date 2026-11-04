"""Whole-story checks: things no single scene can know are wrong.

``check_story`` returns (errors, warnings). Errors are broken content (a link to a scene that doesn't exist,
a quest stage that isn't defined, an ending nobody wrote). Warnings are probably mistakes: a flag that is
checked but never set (usually a typo), a scene nothing leads to, a quest nobody starts. Run it with
``python tools/story_check.py``.
"""

from __future__ import annotations

from rpg.core.dialogue import (
    DialogueError,
    DialogueNode,
    DialogueRepository,
    condition_problems,
    walk_conditions,
)
from rpg.core.endings import EndingBook
from rpg.core.quests import BoardEntry, QuestBook
from rpg.core.storydata import as_conditions

_QUEST_CONDITIONS = ("quest_active", "quest_not_started", "quest_done", "quest_failed")


def _node_conditions(node: DialogueNode) -> list[dict]:
    conditions = list(node.conditions) + [c for line in node.lines for c in line.conditions]
    for choice in node.choices:
        conditions += choice.conditions
    for effect in _node_effects(node):
        conditions += as_conditions(effect.get("if"))
    return list(walk_conditions(conditions))


def _node_effects(node: DialogueNode) -> list[dict]:
    effects = list(node.effects)
    for choice in node.choices:
        effects += choice.effects
    return [e for e in effects if isinstance(e, dict)]


def _targets(node: DialogueNode) -> set[str]:
    """Every scene this one can lead to."""
    found = {node.next_id} | {c.next_id for c in node.choices}
    for effect in _node_effects(node):
        found.add(effect.get("fled"))
        game = effect.get("minigame")
        if isinstance(game, dict):
            found |= {game.get(k) for k in ("success", "partial", "failure", "retreat")}
    return {t for t in found if isinstance(t, str) and t}


def check_story(repo: DialogueRepository, quests: QuestBook, endings: EndingBook, board: list[BoardEntry],
                board_errors: list[str] = ()) -> tuple[list[str], list[str]]:
    errors: list[str] = list(repo.validate()) + list(quests.errors) + list(endings.errors) + list(board_errors)
    warnings: list[str] = []

    nodes: dict[str, DialogueNode] = {}
    for node_id in repo.all_ids():
        try:
            nodes[node_id] = repo.load(node_id)
        except DialogueError:
            continue  # already reported by validate()
    yaml_ids = set(repo.yaml_ids())

    flags_set: set[str] = set()
    vars_written: set[str] = set()
    quests_moved: set[str] = set()
    endings_used: set[str] = set()
    reached: set[str] = set()
    reads: list[tuple[str, str, str]] = []  # (where, kind, name) for flags and vars read in YAML content

    def check_quest_ref(where: str, quest_id, stage=None) -> None:
        quest = quests.get(str(quest_id))
        if quest is None:
            errors.append(f"{where}: unknown quest '{quest_id}'")
        elif stage is not None and not quest.has_stage(str(stage)):
            errors.append(f"{where}: quest '{quest_id}' has no stage '{stage}'")

    def check_conditions(where: str, conditions: list[dict], track_reads: bool) -> None:
        for cond in walk_conditions(conditions):
            errors.extend(f"{where}: {p}" for p in condition_problems(cond))
            for key in _QUEST_CONDITIONS:
                if key in cond:
                    check_quest_ref(where, cond[key])
            if "quest_at" in cond:
                try:
                    quest_id, stage = cond["quest_at"]
                    check_quest_ref(where, quest_id, stage)
                except (TypeError, ValueError):
                    errors.append(f"{where}: quest_at must be [quest, stage]")
            for key in ("visited", "not_visited"):
                if key in cond and cond[key] not in nodes:
                    errors.append(f"{where}: {key} names missing scene '{cond[key]}'")
            if track_reads:
                for key in ("flag_set", "flag_not_set"):
                    if key in cond:
                        reads.append((where, "flag", str(cond[key])))
                if "flag_is" in cond and isinstance(cond["flag_is"], list) and cond["flag_is"]:
                    reads.append((where, "flag", str(cond["flag_is"][0])))
                if "var" in cond:
                    name = str(cond["var"]).split()[0] if isinstance(cond["var"], str) else str(cond["var"][0])
                    reads.append((where, "var", name))

    for node_id, node in nodes.items():
        where = f"{repo.file_of(node_id)} ({node_id.rsplit('/', 1)[-1]})" if node_id in yaml_ids else node_id
        reached |= _targets(node)
        check_conditions(where, _node_conditions(node), node_id in yaml_ids)
        for effect in _node_effects(node):
            if "set_flag" in effect and isinstance(effect["set_flag"], list) and effect["set_flag"]:
                flags_set.add(str(effect["set_flag"][0]))
            if isinstance(effect.get("minigame"), dict) and effect["minigame"].get("flag"):
                flags_set.add(str(effect["minigame"]["flag"]))
            for key in ("set_var", "add_var"):
                if key in effect and isinstance(effect[key], list) and effect[key]:
                    vars_written.add(str(effect[key][0]))
            for key in ("start_quest", "complete_quest", "fail_quest"):
                if key in effect:
                    check_quest_ref(where, effect[key])
                    quests_moved.add(str(effect[key]))
            if "quest_stage" in effect:
                try:
                    quest_id, stage = effect["quest_stage"]
                    check_quest_ref(where, quest_id, stage)
                    quests_moved.add(str(quest_id))
                except (TypeError, ValueError):
                    errors.append(f"{where}: quest_stage must be [quest, stage]")
            if "end_game" in effect:
                endings_used.add(str(effect["end_game"]))
                if str(effect["end_game"]) not in endings:
                    errors.append(f"{where}: unknown ending '{effect['end_game']}'")

    for entry in board:
        where = f"board.yaml ({entry.key})"
        for start in [entry.start_node] + [s for _, s in entry.routes]:
            reached.add(start)
            if not repo.exists(start):
                errors.append(f"{where}: start scene '{start}' is missing")
        check_conditions(where, list(entry.conditions) + [c for conds, _ in entry.routes for c in conds], True)

    for ending_id, definition in endings.endings.items():
        check_conditions(f"endings.yaml ({ending_id})", [c for line in definition.epilogue for c in line.conditions],
                         True)

    # ---------------------------------------------------------------- warnings
    for where, kind, name in reads:
        if kind == "flag" and name not in flags_set:
            warnings.append(f"{where}: flag '{name}' is checked but nothing sets it (a typo?)")
        if kind == "var" and name not in vars_written:
            warnings.append(f"{where}: number '{name}' is checked but nothing changes it (a typo?)")
    for node_id in sorted(yaml_ids - reached):
        warnings.append(f"{repo.file_of(node_id)}: scene '{node_id.rsplit('/', 1)[-1]}' can't be reached")
    for quest_id in sorted(set(quests.quests) - quests_moved):
        warnings.append(f"quest '{quest_id}' is never started")
    for ending_id in sorted(set(endings.endings) - endings_used):
        warnings.append(f"ending '{ending_id}' is never triggered")
    return sorted(set(errors)), sorted(set(warnings))
