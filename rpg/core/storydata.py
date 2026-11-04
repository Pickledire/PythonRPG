"""Loading story files (YAML) and resolving the node references inside them.

Story content is written in YAML: many scenes per file, comments allowed. A scene's id is its file path
(without the extension) plus its key, so ``start`` in ``dialogues/emberwick/inn.yaml`` is
``emberwick/inn/start``. Inside a file, a reference without a slash (``next: cellar``) means a scene in the
same file; a reference with a slash is a full id (``next: emberwick/cellar/stairs``) and may also point at an
old JSON scene.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class StoryDataError(Exception):
    pass


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StoryDataError(f"{path.name}: {exc}") from None
    except OSError as exc:
        raise StoryDataError(f"{path.name}: {exc}") from None


def as_conditions(value: Any) -> list[dict]:
    """``if:`` may be one condition mapping or a list of them (all must hold)."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [c for c in value if isinstance(c, dict)]
    raise StoryDataError(f"conditions must be a mapping or a list, not {value!r}")


def resolve_ref(ref: Any, scope: str) -> Any:
    """``cellar`` -> ``<scope>/cellar``; full ids (containing a slash) are left alone."""
    if isinstance(ref, str) and ref and "/" not in ref:
        return f"{scope}/{ref}"
    return ref


_REF_CONDITIONS = ("visited", "not_visited")
_NESTED_CONDITIONS = ("any", "all", "not")
_MINIGAME_TARGETS = ("success", "partial", "failure", "retreat")


def resolve_conditions(conditions: list[dict], scope: str) -> list[dict]:
    out = []
    for cond in conditions:
        cond = dict(cond)
        for key in _REF_CONDITIONS:
            if key in cond:
                cond[key] = resolve_ref(cond[key], scope)
        for key in _NESTED_CONDITIONS:
            if key in cond:
                cond[key] = resolve_conditions(as_conditions(cond[key]), scope)
        out.append(cond)
    return out


def resolve_effects(effects: list[dict], scope: str) -> list[dict]:
    out = []
    for effect in effects or []:
        if not isinstance(effect, dict):
            out.append(effect)
            continue
        effect = dict(effect)
        if "fled" in effect:
            effect["fled"] = resolve_ref(effect["fled"], scope)
        if isinstance(effect.get("minigame"), dict):
            game = dict(effect["minigame"])
            for key in _MINIGAME_TARGETS:
                if key in game:
                    game[key] = resolve_ref(game[key], scope)
            effect["minigame"] = game
        if "if" in effect:
            effect["if"] = resolve_conditions(as_conditions(effect["if"]), scope)
        out.append(effect)
    return out


def resolve_lines(lines: list, scope: str) -> list:
    out = []
    for line in lines or []:
        if isinstance(line, dict) and "if" in line:
            line = dict(line, **{"if": resolve_conditions(as_conditions(line["if"]), scope)})
        out.append(line)
    return out


def resolve_node(data: dict, scope: str) -> dict:
    """Turn every same-file reference in one scene into a full id."""
    data = dict(data)
    if "next" in data:
        data["next"] = resolve_ref(data["next"], scope)
    for key in ("if", "conditions"):
        if key in data:
            data[key] = resolve_conditions(as_conditions(data[key]), scope)
    data["effects"] = resolve_effects(data.get("effects") or [], scope)
    data["lines"] = resolve_lines(data.get("lines") or [], scope)
    choices = []
    for choice in data.get("choices") or []:
        choice = dict(choice)
        if "next" in choice:
            choice["next"] = resolve_ref(choice["next"], scope)
        for key in ("if", "conditions"):
            if key in choice:
                choice[key] = resolve_conditions(as_conditions(choice[key]), scope)
        choice["effects"] = resolve_effects(choice.get("effects") or [], scope)
        choices.append(choice)
    data["choices"] = choices
    return data


def load_scene_file(path: Path, scope: str) -> dict[str, dict]:
    """Every scene in one YAML file, keyed by full id. Keys starting with ``_`` are file settings:
    ``_defaults`` is merged into every scene (for example a shared ``speaker``)."""
    raw = load_yaml(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise StoryDataError(f"{path.name}: a scene file must be a mapping of scene names")
    defaults = raw.get("_defaults") or {}
    if not isinstance(defaults, dict):
        raise StoryDataError(f"{path.name}: _defaults must be a mapping")
    scenes = {}
    for key, data in raw.items():
        if str(key).startswith("_"):
            continue
        if not isinstance(data, dict):
            raise StoryDataError(f"{path.name}: scene '{key}' must be a mapping")
        if "/" in str(key):
            raise StoryDataError(f"{path.name}: scene name '{key}' may not contain '/'")
        scenes[f"{scope}/{key}"] = resolve_node({"paragraphs": True, **defaults, **data}, scope)
    return scenes
