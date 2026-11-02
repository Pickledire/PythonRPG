"""Log events produced by the rules layer.

Rules never print. They return ``LogEvent`` objects and the UI decides how to show them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tone(str, Enum):
    INFO = "info"
    SYSTEM = "system"
    PLAYER = "player"
    ENEMY = "enemy"
    DAMAGE = "damage"
    CRIT = "crit"
    MISS = "miss"
    HEAL = "heal"
    MANA = "mana"
    STATUS = "status"
    WARNING = "warning"
    REWARD = "reward"
    LOOT = "loot"
    GOLD = "gold"
    XP = "xp"
    STORY = "story"


@dataclass(frozen=True)
class LogEvent:
    text: str
    tone: Tone = Tone.INFO


def log(text: str, tone: Tone = Tone.INFO) -> LogEvent:
    return LogEvent(text, tone)
