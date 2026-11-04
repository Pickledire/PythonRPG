"""Check the whole story for broken links, typos and dead ends.

    python tools/story_check.py

Exits with status 1 if there are errors.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import config  # noqa: E402
from rpg.core.dialogue import DialogueRepository  # noqa: E402
from rpg.core.storycheck import check_story  # noqa: E402
from rpg.core.session import BOARD_ERRORS, QUESTS, default_endings, default_questbook  # noqa: E402


def main() -> int:
    repo = DialogueRepository(config.DIALOGUE_DIR)
    errors, warnings = check_story(repo, default_questbook(), default_endings(), QUESTS, BOARD_ERRORS)

    print(f"{len(repo.yaml_ids())} YAML scenes, {len(repo.json_ids())} JSON scenes, "
          f"{len(default_questbook().quests)} quests, {len(default_endings().endings)} endings")
    for line in errors:
        print(f"ERROR    {line}")
    for line in warnings:
        print(f"warning  {line}")
    if not errors and not warnings:
        print("No problems found.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
