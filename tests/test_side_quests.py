"""The side questlines: the story bot can finish every one (strong or weak hero), plus the engine pieces they
introduced (future placeholders, handing items over, strict YAML, region-strength quest fights)."""

import random
import tempfile
import textwrap
import unittest
from pathlib import Path

from rpg.core import storybot
from rpg.core.dialogue import DialogueRepository, apply_effects, check_conditions
from rpg.core.session import GameSession
from rpg.core.storydata import StoryDataError, load_yaml

QUESTLINES = {
    "brennhold_finch": "brennhold_finch", "ashwood_stag": "ashwood_stag", "glassmere_book": "glassmere_book",
    "aegis_brew": "aegis_brew", "barrow_count": "barrow_count", "frost_hunt": "frost_hunt",
    "cliffs_lights": "cliffs_lights", "marches_wedding": "marches_wedding", "valoria_lesson": "valoria_lesson",
    "ember_pilgrim": "ember_pilgrim", "titanfell_map": "titanfell_map",
}
RACES = ("Human", "Dwarf", "Elf", "Orc", "Halfling", "Gnome", "Druid", "Beastkin", "Dragonkin", "Revenant")


class StoryBotTests(unittest.TestCase):
    def test_every_questline_can_be_finished(self):
        for key, quest in QUESTLINES.items():
            entry = storybot.board_entry(key)
            for seed in range(6):
                run = storybot.play(entry, quest, seed, race=RACES[seed % len(RACES)])
                self.assertTrue(run.finished, f"{key} seed {seed}: stuck after {run.steps} steps")
                self.assertEqual(run.problems, [], key)

    def test_a_weak_poor_hero_can_finish_them_too(self):
        original = storybot.capable_hero
        storybot.capable_hero = lambda seed, race="Human", stats=20, gold=5000: original(seed, race, 8, 150)
        try:
            for key, quest in QUESTLINES.items():
                run = storybot.play(storybot.board_entry(key), quest, 3, race="Human", max_steps=800)
                self.assertTrue(run.finished, f"{key}: a weak hero got stuck")
        finally:
            storybot.capable_hero = original

    def test_each_questline_is_listed_only_in_its_region(self):
        session = GameSession.new_game("T", "Human", rng=random.Random(1))
        for key in QUESTLINES:
            entry = storybot.board_entry(key)
            session.world.region = entry.where[0]
            self.assertIn(key, [e.key for e in session.board()])
            session.world.region = "hearthlands"
            self.assertNotIn(key, [e.key for e in session.board()])


class EnginePieceTests(unittest.TestCase):
    def setUp(self):
        self.session = GameSession.new_game("T", "Human", rng=random.Random(1))

    def test_future_content_is_never_available_and_shows_its_reason(self):
        self.assertFalse(check_conditions(self.session, [{"future": "iron_company_guild"}]))
        base = Path(tempfile.mkdtemp())
        (base / "s.yaml").write_text(textwrap.dedent("""
            a:
              choices:
                - {text: Show your token, if: {future: iron_company_guild}, locked: Iron Company members only}
                - {text: Later, if: {future: something}, locked: true}
                - {text: Leave}
        """), encoding="utf-8")
        self.session.dialogues = DialogueRepository(base)
        runner = self.session.dialogue("s/a")
        runner.start()
        self.assertEqual([(e.text, e.reason) for e in runner.menu() if not e.available],
                         [("Show your token", "Iron Company members only"), ("Later", "Not yet")])

    def test_handing_over_a_quest_item(self):
        apply_effects(self.session, [{"give_item": "Clockwork Finch"}])
        self.assertTrue(check_conditions(self.session, [{"has_item": "Clockwork Finch"}]))
        events = apply_effects(self.session, [{"take_item": "Clockwork Finch"}]).events
        self.assertEqual(events[0].text, "You hand over the Clockwork Finch.")
        self.assertFalse(check_conditions(self.session, [{"has_item": "Clockwork Finch"}]))
        self.assertEqual(apply_effects(self.session, [{"take_item": "Clockwork Finch"}]).events, [])  # nothing left

    def test_story_files_refuse_duplicate_keys(self):
        path = Path(tempfile.mkdtemp()) / "x.yaml"
        path.write_text("a:\n  if: {flag_set: x, flag_set: y}\n", encoding="utf-8")
        with self.assertRaises(StoryDataError):
            load_yaml(path)

    def test_quest_fights_are_as_strong_as_the_region(self):
        self.session.world.region = "frostreach"  # starts at level 25
        enemy, _ = self.session.create_story_enemy("wolf")
        self.assertGreaterEqual(enemy.level, 25)
        self.session.world.region = "hearthlands"
        enemy, _ = self.session.create_story_enemy("wolf")
        self.assertEqual(enemy.level, 1)


if __name__ == "__main__":
    unittest.main()
