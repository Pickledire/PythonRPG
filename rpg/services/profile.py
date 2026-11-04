"""The meta profile: what this player has seen across all their runs (starting with endings).

Stored in ``profile.json`` next to the save slots. It belongs to the player, not to any one save, so it
survives new characters and deleted slots.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rpg import config


@dataclass
class EndingRecord:
    title: str
    count: int = 0
    first_seen: str = ""
    first_hero: str = ""


@dataclass
class Profile:
    endings: dict[str, EndingRecord] = field(default_factory=dict)

    def record_ending(self, ending_id: str, title: str, hero: str) -> bool:
        """Count an ending. Returns True if this player has never seen it before."""
        record = self.endings.get(ending_id)
        new = record is None
        if new:
            record = self.endings[ending_id] = EndingRecord(title, 0, datetime.now().strftime("%Y-%m-%d"), hero)
        record.count += 1
        return new

    def to_dict(self) -> dict:
        return {"endings": {key: vars(record) for key, record in self.endings.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        endings = {}
        for key, raw in (data.get("endings") or {}).items():
            try:
                endings[str(key)] = EndingRecord(str(raw.get("title", key)), int(raw.get("count", 1)),
                                                 str(raw.get("first_seen", "")), str(raw.get("first_hero", "")))
            except (AttributeError, TypeError, ValueError):
                continue
        return cls(endings)


class ProfileStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.path = Path(directory or config.SAVE_DIR) / "profile.json"

    def load(self) -> Profile:
        try:
            return Profile.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError):
            return Profile()

    def save(self, profile: Profile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".profile-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(profile.to_dict(), fh, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
