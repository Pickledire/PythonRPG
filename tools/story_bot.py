"""Play every side questline many times with random choices, and report how often it can be finished and
which scenes the bot never reached.

    python tools/story_bot.py              # 20 runs per questline
    python tools/story_bot.py --runs 50
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import config  # noqa: E402
from rpg.core.dialogue import DialogueRepository  # noqa: E402
from rpg.core.storybot import board_entry, play  # noqa: E402

QUESTLINES = {
    "emberwick_inn": "the_cottage", "brennhold_finch": "brennhold_finch", "ashwood_stag": "ashwood_stag",
    "glassmere_book": "glassmere_book", "aegis_brew": "aegis_brew", "barrow_count": "barrow_count",
    "frost_hunt": "frost_hunt", "cliffs_lights": "cliffs_lights", "marches_wedding": "marches_wedding",
    "valoria_lesson": "valoria_lesson", "ember_pilgrim": "ember_pilgrim", "titanfell_map": "titanfell_map",
}
RACES = ("Human", "Dwarf", "Elf", "Orc", "Halfling", "Gnome", "Druid", "Beastkin", "Dragonkin", "Revenant")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    repo = DialogueRepository(config.DIALOGUE_DIR)
    failed = False
    for key, quest in QUESTLINES.items():
        entry = board_entry(key)
        prefix = entry.start_node.rsplit("/", 1)[0] + "/"
        scenes = {s for s in repo.yaml_ids() if s.startswith(prefix)}
        seen: set[str] = set()
        done, steps, problems = 0, [], []
        for seed in range(args.runs):
            run = play(entry, quest, seed, race=RACES[seed % len(RACES)])
            seen |= run.visited
            problems += run.problems
            if run.finished:
                done += 1
                steps.append(run.steps)
        if quest == "the_cottage":  # the house ends the game; the bot reaching it is the finish
            done = sum(1 for p in problems if "ended at" in p)
            problems = [p for p in problems if "ended at" not in p]
        missed = sorted(s.rsplit("/", 1)[-1] for s in scenes - seen)
        average = f", about {sum(steps) // len(steps)} steps" if steps else ""
        print(f"{key:18} finished {done}/{args.runs}{average}; reached {len(scenes & seen)}/{len(scenes)} scenes")
        if missed:
            print(f"{'':18} never reached: {', '.join(missed)}")
        for problem in sorted(set(problems)):
            print(f"{'':18} PROBLEM: {problem}")
        failed |= done == 0 or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
