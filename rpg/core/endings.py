"""Endings: the scenes that end a run.

Endings live in ``story/endings.yaml`` and are triggered by the ``end_game`` effect::

    a_house_in_emberwick:
      title: A House in Emberwick
      epilogue:                         # shown after THE END; lines may have an "if" like scene lines
        - You lived in the cottage at the end of the lane for a long time.
        - {text: "Brannoc brought the chair.", if: {var: "rep.brannoc >= 4"}}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rpg.core.dialogue import DialogueContext, Line, render_lines
from rpg.core.storydata import StoryDataError, as_conditions, load_yaml


@dataclass(frozen=True)
class EndingDef:
    ending_id: str
    title: str
    epilogue: tuple[Line, ...] = ()


@dataclass(frozen=True)
class Ending:
    """An ending as this run earned it."""
    ending_id: str
    title: str
    epilogue: list[str] = field(default_factory=list)


class EndingBook:
    def __init__(self, endings: dict[str, EndingDef] | None = None, errors: list[str] | None = None) -> None:
        self.endings = endings or {}
        self.errors = errors or []

    def __contains__(self, ending_id: str) -> bool:
        return ending_id in self.endings

    def resolve(self, ctx: DialogueContext, ending_id: str) -> Ending:
        definition = self.endings.get(ending_id) or EndingDef(ending_id, ending_id.replace("_", " ").title())
        return Ending(ending_id, definition.title, render_lines(ctx, list(definition.epilogue)))

    @classmethod
    def load(cls, path: Path) -> "EndingBook":
        if not Path(path).is_file():
            return cls()
        try:
            raw = load_yaml(Path(path)) or {}
        except StoryDataError as exc:
            return cls(errors=[str(exc)])
        endings, errors = {}, []
        for ending_id, data in (raw if isinstance(raw, dict) else {}).items():
            try:
                lines = tuple(Line(str(item.get("text", "")), as_conditions(item.get("if"))) if isinstance(item, dict)
                              else Line(str(item)) for item in data.get("epilogue") or [])
                endings[str(ending_id)] = EndingDef(str(ending_id), str(data.get("title") or ending_id), lines)
            except (AttributeError, StoryDataError) as exc:
                errors.append(f"{Path(path).name}: ending '{ending_id}': {exc}")
        return cls(endings, errors)
