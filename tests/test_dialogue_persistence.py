"""Dialogue engine, real dialogue content, and save/load."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from rpg import config
from rpg.core.dialogue import (
    DialogueRepository,
    OpenShopRequest,
    StartCombatRequest,
    VisualRequest,
    apply_effects,
    check_conditions,
)
from rpg.core.effects import EffectKind, StatusEffect
from rpg.core.session import QUESTS, GameSession
from rpg.services.persistence import SaveError, SaveManager



def write_nodes(base: Path, nodes: dict[str, dict]) -> None:
    for node_id, data in nodes.items():
        path = base / f"{node_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")


class DialogueContentTests(unittest.TestCase):
    def test_shipped_dialogue_is_valid(self):
        repo = DialogueRepository(config.DIALOGUE_DIR)
        self.assertEqual(repo.validate(), [])

    def test_every_quest_starts(self):
        repo = DialogueRepository(config.DIALOGUE_DIR)
        for quest in QUESTS:
            self.assertTrue(repo.exists(quest.start_node), quest.start_node)

    def test_random_encounters_exist(self):
        repo = DialogueRepository(config.DIALOGUE_DIR)
        rng = random.Random(1)
        self.assertTrue(repo.random_id("good", rng).startswith("random/good/"))
        self.assertTrue(repo.random_id("bad", rng).startswith("random/bad/"))


class DialogueEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.session = GameSession.new_game("T", "Human", rng=random.Random(1), dialogue_dir=self.tmp)

    def test_conditions(self):
        world, player = self.session.world, self.session.player
        world.flags["met"] = True
        world.bell = 23
        self.assertTrue(check_conditions(self.session, [{"flag_set": "met"}, {"time_between": [22, 2]}]))
        self.assertFalse(check_conditions(self.session, [{"flag_not_set": "met"}]))
        self.assertFalse(check_conditions(self.session, [{"min_kills": 1}]))
        player.kills = 1
        self.assertTrue(check_conditions(self.session, [{"min_kills": 1}, {"has_item": "Health Potion"}]))

    def test_effects(self):
        p = self.session.player
        result = apply_effects(self.session, [
            {"set_flag": ["arena_created", True]}, {"set_health": 999}, {"set_mana": 300},
            {"stat_change": ["strength", 2]}, {"add_gold": 15}, {"give_item": "Spark"},
            {"give_item": {"name": "Rusty Key", "type": "misc"}}, {"unlock_shop": "titan_hammer"},
            {"start_combat": "Orc"}, {"open_shop": "magic"}, {"visual": "quake", "duration": 0.5},
            {"set_stamina": 3}, {"give_xp": 120},
        ])
        self.assertTrue(self.session.world.flags["arena_created"])
        self.assertEqual(p.hp, p.max_hp)
        gain = config.MANA_GAIN_PER_LEVEL
        self.assertEqual((p.mana, p.max_mana), (300 + gain, 300 + gain))  # set_mana, then the level-up
        self.assertEqual(p.attributes.strength, 12)
        self.assertEqual(p.gold, config.STARTING_GOLD + 15)
        self.assertIsNotNone(p.inventory.find_by_name("Spark"))
        self.assertIsNotNone(p.inventory.find_by_name("Rusty Key"))
        self.assertIn("titan_hammer", self.session.world.shop_unlocks)
        self.assertEqual(p.level, 2)
        self.assertEqual(result.requests, [StartCombatRequest("Orc"), OpenShopRequest("magic"), VisualRequest("quake", 0.5)])

    def test_runner_walks_graph_and_applies_node_effects(self):
        write_nodes(self.tmp, {
            "q/start": {"speaker": "Guide", "lines": ["Hi"], "effects": [{"add_gold": 5}],
                        "choices": [{"text": "Fight", "next": "q/end", "effects": [{"start_combat": "goblin"}]},
                                    {"text": "Secret", "conditions": [{"flag_set": "nope"}]}]},
            "q/end": {"lines": ["Bye"]},
        })
        runner = self.session.dialogue("q/start")
        bell = self.session.world.bell
        runner.start()
        self.assertEqual(self.session.player.gold, config.STARTING_GOLD + 5)
        self.assertEqual(self.session.world.bell, bell + 1)
        self.assertEqual([c.text for c in runner.choices()], ["Fight"])
        step = runner.choose(0)
        self.assertEqual(step.requests, [StartCombatRequest("goblin")])
        runner.proceed()
        self.assertEqual(runner.node.node_id, "q/end")
        self.assertTrue(runner.is_terminal)
        runner.proceed()
        self.assertTrue(runner.finished)

    def test_missing_and_blocked_nodes_do_not_crash(self):
        write_nodes(self.tmp, {"q/locked": {"lines": ["x"], "conditions": [{"flag_set": "key"}]}})
        runner = self.session.dialogue("q/missing")
        runner.start()
        self.assertTrue(runner.finished)
        self.assertIsNotNone(runner.blocked_reason)
        runner = self.session.dialogue("q/locked")
        runner.start()
        self.assertEqual(runner.blocked_reason, "You cannot do this right now.")

    def test_path_traversal_is_rejected(self):
        runner = self.session.dialogue("../../etc/passwd")
        runner.start()
        self.assertTrue(runner.finished)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.saves = SaveManager(self.dir)

    def test_round_trip(self):
        session = GameSession.new_game("Ari", "Elf", rng=random.Random(1))
        p = session.player
        p.gain_xp(130)
        p.weapon.durability = 33
        p.add_effect(StatusEffect(EffectKind.SHIELD, 2, 0.35))
        session.world.flags["arena_created"] = True
        session.world.shop_unlocks.add("titan_hammer")
        session.world.bosses_defeated.add("titan")
        self.saves.save(session, 2)
        loaded = self.saves.load(2)
        self.assertEqual(loaded.player.to_dict(), p.to_dict())
        self.assertEqual(loaded.world.to_dict(), session.world.to_dict())
        self.assertEqual(loaded.player.weapon.durability, 33)
        self.assertEqual(self.saves.slot_info(2).name, "Ari")
        self.assertFalse(list(self.dir.glob(".slot*")))  # no temp files left behind

    def test_empty_and_corrupt_slots(self):
        with self.assertRaises(SaveError):
            self.saves.load(1)
        (self.dir / "slot1.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(SaveError):
            self.saves.load(1)
        self.assertTrue(self.saves.slot_info(1).error)

    def test_migrates_original_game_saves(self):
        legacy = {
            "version": 1, "world_bells": 5,
            "flags": {"level_10_boss": True, "ghost_horror": True},
            "quest_flags": {"arena_created": True},
            "player": {
                "name": "Old", "race": "Dwarf", "level": 11, "xp": 40, "gold": 999,
                "stats": {"strength": 14, "agility": 7, "intelligence": 12},
                "health": 50, "max_health": 220, "mana": 30, "max_mana": 200, "kills": 12,
                "inventory": {
                    "items": [
                        {"item": {"name": "Plate Armor", "type": "armor", "value": 225, "defense": 24,
                                  "durability": 150, "max_durability": 200}, "quantity": 2},
                        {"item": {"name": "Fireball", "type": "magic", "value": 200, "damage": 67, "mana": 20,
                                  "spell_type": "damage"}, "quantity": 1},
                        {"item": {"name": "Health Potion", "type": "consumable", "value": 25,
                                  "effect_type": "heal", "effect_value": 50}, "quantity": 4},
                    ],
                    "equipped_armor": "Plate Armor", "equipped_magic": "Fireball",
                },
            },
        }
        (self.dir / "slot3.json").write_text(json.dumps(legacy), encoding="utf-8")
        self.assertTrue(self.saves.slot_info(3).legacy)
        session = self.saves.load(3)
        p = session.player
        self.assertEqual((p.name, p.level, p.gold, p.kills), ("Old", 11, 999, 12))
        self.assertEqual(len([s for s in p.inventory if s.item.name == "Plate Armor"]), 2)
        self.assertEqual(p.armor.name, "Plate Armor")
        self.assertEqual(p.spell.name, "Fireball")
        self.assertEqual(session.world.bosses_defeated, {"titan"})
        self.assertTrue(session.world.ghost_horror_seen)
        self.assertTrue(session.world.flags["arena_created"])


if __name__ == "__main__":
    unittest.main()
