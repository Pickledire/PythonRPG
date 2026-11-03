"""Settings persistence, difficulty, reaction time and the boss portraits."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from rpg.core.enemies import ENEMIES
from rpg.core.minigames import MinigameSpec
from rpg.core.session import Encounter, GameSession
from rpg.services.settings import OPTIONS, Settings, SettingsStore
from rpg.ui.widgets.ascii_animation import animation_exists, load_frames


class SettingsStoreTests(unittest.TestCase):
    def test_round_trip_and_bad_values_fall_back(self):
        folder = Path(tempfile.mkdtemp())
        store = SettingsStore(folder)
        self.assertEqual(store.load(), Settings())  # no file yet
        settings = Settings()
        settings.set("difficulty", "hard")
        settings.set("theme", "frost")
        settings.set("reduced_motion", True)
        store.save(settings)
        self.assertEqual(store.load(), settings)
        (folder / "settings.json").write_text(json.dumps({"difficulty": "nightmare", "turn_timer": 7}))
        loaded = store.load()
        self.assertEqual((loaded.difficulty, loaded.turn_timer), ("normal", Settings().turn_timer))
        (folder / "settings.json").write_text("{broken")
        self.assertEqual(store.load(), Settings())

    def test_every_default_is_an_option(self):
        defaults = Settings()
        for info in OPTIONS:
            if info.key != "turn_timer":  # follows config, which tests may change
                self.assertIn(getattr(defaults, info.key), [o.value for o in info.options], info.key)
        with self.assertRaises(ValueError):
            defaults.set("combat_speed", "ludicrous")


class DifficultyTests(unittest.TestCase):
    def session(self, difficulty):
        session = GameSession.new_game("T", "Human", rng=random.Random(5))
        session.difficulty = difficulty
        return session

    def test_enemies_scale_with_difficulty(self):
        hp = {d: self.session(d).create_story_enemy("orc")[0].max_hp for d in ("story", "normal", "hard")}
        self.assertLess(hp["story"], hp["normal"])
        self.assertLess(hp["normal"], hp["hard"])

    def test_rewards_and_trials(self):
        hard, story = self.session("hard"), self.session("story")
        enemy = ENEMIES.create("goblin", random.Random(1))
        self.assertGreater(hard.begin_combat(Encounter(enemy)).reward_multiplier, 1.0)
        spec = MinigameSpec.from_dict({"type": "stealth", "dc": 12})
        self.assertEqual(hard.minigame_check(spec).dc, 14)
        self.assertEqual(story.minigame_check(spec).dc, 10)

    def test_reaction_time_stretches_trials(self):
        normal, relaxed = self.session("normal"), self.session("normal")
        relaxed.reaction_time = 1.5
        spec = MinigameSpec.from_dict({"type": "qte"})
        self.assertAlmostEqual(relaxed.start_minigame(spec).window, normal.start_minigame(spec).window * 1.5)


class BossArtTests(unittest.TestCase):
    def test_every_intro_has_a_portrait(self):
        for template in ENEMIES.templates.values():
            if template.intro_lines:
                self.assertTrue(animation_exists(f"boss_{template.template_id}"), template.template_id)
                fps, frames = load_frames(f"boss_{template.template_id}")
                self.assertGreater(len(frames), 1)

    def test_titan_glow_recolors(self):
        _, fire = load_frames("boss_titan")
        _, ice = load_frames("boss_titan", (("glow", ("#000001", "#000002", "#000003", "#000004")),))
        styles = {str(span.style) for span in ice[0].spans}
        self.assertTrue(any(s.startswith("#00000") for s in styles))
        self.assertNotEqual({str(s.style) for s in fire[0].spans}, styles)


if __name__ == "__main__":
    unittest.main()
