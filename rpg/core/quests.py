"""Quests as data: the journal's quests, and the quest board's destinations.

Journal quests live in ``story/quests/*.yaml``::

    inn_rats:
      title: Rats in the Cellar
      giver: Brannoc
      stages:                      # in order; the first is where the quest starts
        started: Brannoc wants the rats out of his cellar.
        cleared: The cellar is clear. Tell Brannoc.
        done: You cleared Brannoc's cellar.    # "done" and "failed" end the quest

Scenes move quests along with the ``start_quest``, ``quest_stage``, ``complete_quest`` and ``fail_quest``
effects, and check them with ``quest_active``, ``quest_at``, ``quest_done`` and the other quest conditions.

The quest board (``story/board.yaml``) lists the places you can set out for from the hub::

    - key: emberwick_inn
      title: The Banked Fire
      blurb: Emberwick's inn.
      start: emberwick/inn/start
      if: {...}                    # optional: only listed while this holds
      routes:                      # optional: start somewhere else while a condition holds
        - {if: {flag_set: arena_created}, start: fighters/arena}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rpg.core.storydata import StoryDataError, as_conditions, load_yaml

DONE = "done"
FAILED = "failed"
FINAL_STAGES = (DONE, FAILED)


@dataclass(frozen=True)
class QuestDef:
    quest_id: str
    title: str
    giver: str = ""
    stages: tuple[tuple[str, str], ...] = ()

    @property
    def first_stage(self) -> str:
        for key, _ in self.stages:
            if key not in FINAL_STAGES:
                return key
        return "started"

    def has_stage(self, stage: str) -> bool:
        return stage in FINAL_STAGES or any(key == stage for key, _ in self.stages)

    def stage_text(self, stage: str) -> str:
        for key, text in self.stages:
            if key == stage:
                return text
        return {DONE: "Complete.", FAILED: "Failed."}.get(stage, "")


class QuestBook:
    def __init__(self, quests: dict[str, QuestDef] | None = None, errors: list[str] | None = None) -> None:
        self.quests = quests or {}
        self.errors = errors or []

    def __contains__(self, quest_id: str) -> bool:
        return quest_id in self.quests

    def get(self, quest_id: str) -> QuestDef | None:
        return self.quests.get(quest_id)

    def title(self, quest_id: str) -> str:
        quest = self.quests.get(quest_id)
        return quest.title if quest else quest_id

    @classmethod
    def load(cls, directory: Path) -> "QuestBook":
        quests: dict[str, QuestDef] = {}
        errors: list[str] = []
        if not Path(directory).is_dir():
            return cls()
        for path in sorted(Path(directory).rglob("*.yaml")):
            try:
                raw = load_yaml(path) or {}
                if not isinstance(raw, dict):
                    raise StoryDataError(f"{path.name}: a quest file must be a mapping of quest ids")
                for quest_id, data in raw.items():
                    if quest_id in quests:
                        errors.append(f"{path.name}: quest '{quest_id}' is defined twice")
                        continue
                    stages = data.get("stages") or {}
                    if not isinstance(stages, dict) or not stages:
                        errors.append(f"{path.name}: quest '{quest_id}' needs at least one stage")
                        continue
                    quests[str(quest_id)] = QuestDef(str(quest_id), str(data.get("title") or quest_id),
                                                     str(data.get("giver") or ""),
                                                     tuple((str(k), str(v)) for k, v in stages.items()))
            except (StoryDataError, AttributeError) as exc:
                errors.append(str(exc))
        return cls(quests, errors)


# ------------------------------------------------------------------ the quest board
@dataclass(frozen=True)
class BoardEntry:
    key: str
    title: str
    blurb: str
    start_node: str
    conditions: tuple[dict, ...] = ()
    routes: tuple[tuple[tuple[dict, ...], str], ...] = field(default=())  # (conditions, start) pairs


def load_board(path: Path) -> tuple[list[BoardEntry], list[str]]:
    if not Path(path).is_file():
        return [], []
    errors: list[str] = []
    try:
        raw = load_yaml(Path(path)) or []
    except StoryDataError as exc:
        return [], [str(exc)]
    entries = []
    for item in raw if isinstance(raw, list) else []:
        try:
            routes = tuple((tuple(as_conditions(r.get("if"))), str(r["start"])) for r in item.get("routes") or [])
            entries.append(BoardEntry(str(item["key"]), str(item["title"]), str(item.get("blurb") or ""),
                                      str(item["start"]), tuple(as_conditions(item.get("if"))), routes))
        except (KeyError, TypeError, AttributeError, StoryDataError) as exc:
            errors.append(f"{Path(path).name}: bad board entry {item!r}: {exc}")
    return entries, errors
