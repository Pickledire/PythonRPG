"""Player settings: stored in ``settings.json`` next to the save slots, separate from any one save.

Every option is a choice from a fixed list (``OPTIONS``), so the settings screen can be built from data
and a hand-edited file can never put the game in a strange state: unknown values fall back to the default.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from rpg import config


@dataclass(frozen=True)
class Option:
    value: object
    label: str
    blurb: str = ""


@dataclass(frozen=True)
class SettingInfo:
    key: str
    group: str
    label: str
    description: str
    options: tuple[Option, ...]


THEMES = ("ember", "frost", "verdant", "grave", "high_contrast")

OPTIONS: tuple[SettingInfo, ...] = (
    SettingInfo("theme", "Look", "Theme", "Colors of the whole interface. Also available from Ctrl+P.", (
        Option("ember", "Ember", "Warm firelight. The default."),
        Option("frost", "Frost", "Cold blues and pale steel."),
        Option("verdant", "Verdant", "Moss, bark and lantern gold."),
        Option("grave", "Grave", "Muted violets for long nights."),
        Option("high_contrast", "High contrast", "Black, white and bright gold."),
    )),
    SettingInfo("difficulty", "Challenge", "Difficulty",
                "Scales new enemies, rewards and trial difficulty. Takes effect from the next fight.", tuple(
                    Option(key, d["label"], d["blurb"]) for key, d in config.DIFFICULTIES.items())),
    SettingInfo("turn_timer", "Challenge", "Turn timer", "Seconds to act in combat before you hesitate.", (
        Option(0, "Off"), Option(30, "30 seconds"), Option(20, "20 seconds"), Option(10, "10 seconds"),
    )),
    SettingInfo("reaction_time", "Challenge", "Trial reaction time",
                "More time for quick-time prompts, mishaps, needles and rune sequences.", (
                    Option(1.0, "Normal"), Option(1.25, "Relaxed (+25%)"), Option(1.5, "Generous (+50%)"),
                )),
    SettingInfo("combat_speed", "Pacing", "Combat log speed", "How quickly the battle log plays out.", (
        Option("slow", "Slow"), Option("normal", "Normal"), Option("fast", "Fast"),
    )),
    SettingInfo("intro_speed", "Pacing", "Boss intro speed", "How quickly a boss's story lines appear.", (
        Option("slow", "Slow"), Option("normal", "Normal"), Option("fast", "Fast"),
    )),
    SettingInfo("skip_intros", "Pacing", "Skip boss intros", "Show the whole intro at once.", (
        Option(False, "Off"), Option(True, "On"),
    )),
    SettingInfo("reduced_motion", "Accessibility", "Reduced motion",
                "Freeze animations (campfire, boss art, scene effects) on their first frame.", (
                    Option(False, "Off"), Option(True, "On"),
                )),
)
INFO = {info.key: info for info in OPTIONS}

# Multipliers on combat pacing delays and seconds per boss intro line.
COMBAT_SPEED = {"slow": 1.6, "normal": 1.0, "fast": 0.45}
INTRO_LINE_SECONDS = {"slow": 1.2, "normal": 0.85, "fast": 0.45}


@dataclass
class Settings:
    theme: str = "ember"
    difficulty: str = "normal"
    turn_timer: int = field(default_factory=lambda: config.TURN_TIMER_SECONDS)
    reaction_time: float = 1.0
    combat_speed: str = "normal"
    intro_speed: str = "normal"
    skip_intros: bool = False
    reduced_motion: bool = False

    def options_for(self, key: str) -> tuple[Option, ...]:
        return INFO[key].options

    def label_for(self, key: str) -> str:
        value = getattr(self, key)
        return next((o.label for o in INFO[key].options if o.value == value), str(value))

    def set(self, key: str, value: object) -> None:
        if key not in INFO:
            raise KeyError(key)
        if key != "theme" and value not in [o.value for o in INFO[key].options]:
            raise ValueError(f"{value!r} is not an option for {key}")
        setattr(self, key, value)

    @property
    def combat_delay(self) -> float:
        return COMBAT_SPEED.get(self.combat_speed, 1.0)

    @property
    def intro_line_seconds(self) -> float:
        return INTRO_LINE_SECONDS.get(self.intro_speed, INTRO_LINE_SECONDS["normal"])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        settings = cls()
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if f.name == "theme":  # any registered theme name (Ctrl+P offers Textual's built-ins too)
                if isinstance(value, str):
                    settings.theme = value
            elif value in [o.value for o in INFO[f.name].options]:
                setattr(settings, f.name, value)
        return settings


class SettingsStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.path = Path(directory or config.SAVE_DIR) / "settings.json"

    def load(self) -> Settings:
        try:
            return Settings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, AttributeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".settings-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(settings.to_dict(), handle, indent=2)
            os.replace(temp, self.path)
        except OSError:
            Path(temp).unlink(missing_ok=True)
            raise
