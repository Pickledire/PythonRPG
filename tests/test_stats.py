"""The seven attributes and what they do."""

import random
import unittest

from rpg import config
from rpg.core.attributes import Attribute
from rpg.core.catalog import ITEMS
from rpg.core.combat import CombatSession, Hesitate
from rpg.core.dialogue import apply_effects, check_conditions
from rpg.core.effects import EffectKind, EffectSpec, StatusEffect
from rpg.core.entities import Player
from rpg.core.formulas import dodge_chance, flee_chance, weapon_attribute_bonus
from rpg.core.session import GameSession
from tests.helpers import ScriptedRandom, make_enemy, make_player


class DerivedPoolTests(unittest.TestCase):
    def test_hp_and_mana_come_from_vitality_and_wisdom(self):
        for race, data in config.RACES.items():
            player = Player.create("T", race)
            self.assertEqual(player.max_hp, data["base_hp"] + data["vitality"] * config.HP_PER_VITALITY, race)
            self.assertEqual(player.max_mana, config.BASE_MANA + data["wisdom"] * config.MANA_PER_WISDOM, race)

    def test_changing_vitality_and_wisdom_moves_pools(self):
        player = make_player()
        hp, mana = player.max_hp, player.max_mana
        player.change_attribute(Attribute.VITALITY, 2)
        player.change_attribute(Attribute.WISDOM, -2)
        self.assertEqual(player.max_hp, hp + 2 * config.HP_PER_VITALITY)
        self.assertEqual(player.hp, player.max_hp)
        self.assertEqual(player.max_mana, mana - 2 * config.MANA_PER_WISDOM)
        self.assertLessEqual(player.mana, player.max_mana)


class CombatStatTests(unittest.TestCase):
    def test_weapon_scaling_by_type(self):
        player = make_player()
        player.attributes.dexterity, player.attributes.strength, player.attributes.intelligence = 20, 5, 5
        dagger, axe, staff = ITEMS.create("halfling_dagger"), ITEMS.create("axe"), ITEMS.create("oak_staff")
        self.assertGreater(weapon_attribute_bonus(player.attributes, dagger), weapon_attribute_bonus(player.attributes, axe))
        player.attributes.intelligence = 20
        self.assertGreater(weapon_attribute_bonus(player.attributes, staff), weapon_attribute_bonus(player.attributes, axe))

    def test_agility_dodges(self):
        player, enemy = make_player(), make_enemy("orc")
        player.attributes.agility = 50  # capped at 25%
        self.assertEqual(dodge_chance(50), 0.25)
        enemy.spellbook = []
        combat = CombatSession(player, enemy, ScriptedRandom(values=[0.80]))  # under to-hit, inside the dodge band
        combat.start()
        combat.act(Hesitate())
        events = combat.enemy_turn()
        self.assertTrue(any("dodge" in e.text for e in events))
        self.assertEqual(player.hp, player.max_hp)

    def test_vitality_reduces_damage_over_time(self):
        tough, frail = make_player(), make_player()
        tough.attributes.vitality, frail.attributes.vitality = 30, 0
        for player in (tough, frail):
            player.add_effect(StatusEffect(EffectKind.POISON, 2, 20))
            enemy = make_enemy(max_hp=500)
            enemy.add_effect(StatusEffect(EffectKind.FROZEN, 1))
            combat = CombatSession(player, enemy, ScriptedRandom(default=0.99))
            combat.start()
        self.assertEqual(frail.max_hp - frail.hp, 20)
        self.assertEqual(tough.max_hp - tough.hp, 14)

    def test_wisdom_resists_harmful_effects(self):
        player = make_player()
        player.attributes.wisdom = 30
        combat = CombatSession(player, make_enemy(), ScriptedRandom(values=[0.1]))
        events = combat._apply(player, EffectSpec(EffectKind.POISON, 5, 3), "test", roll=False)
        self.assertIn("resists", events[0].text)
        self.assertNotIn(EffectKind.POISON, player.effects)
        # Beneficial effects are never resisted
        combat._apply(player, EffectSpec(EffectKind.SHIELD, 0.3, 2), "test", roll=False)
        self.assertIn(EffectKind.SHIELD, player.effects)

    def test_agility_improves_escape(self):
        self.assertGreater(flee_chance(16, False), flee_chance(8, False))
        self.assertLess(flee_chance(10, True), flee_chance(10, False))


class DialogueStatTests(unittest.TestCase):
    def setUp(self):
        self.session = GameSession.new_game("T", "Human", rng=random.Random(1))

    def test_min_stat_condition(self):
        self.assertTrue(check_conditions(self.session, [{"min_stat": ["charisma", 12]}]))
        self.assertFalse(check_conditions(self.session, [{"min_stat": ["charisma", 13]}]))

    def test_set_and_change_any_attribute(self):
        p = self.session.player
        hp = p.max_hp
        apply_effects(self.session, [{"set_vitality": 14}, {"stat_change": ["dexterity", 3]}, {"set_charisma": 2}])
        self.assertEqual(p.attributes.vitality, 14)
        self.assertEqual(p.max_hp, hp + 4 * config.HP_PER_VITALITY)
        self.assertEqual(p.attributes.dexterity, 13)
        self.assertEqual(p.attributes.charisma, 2)


class OldSaveTests(unittest.TestCase):
    def test_three_attribute_saves_get_race_defaults(self):
        session = GameSession.new_game("Brenden", "Orc", rng=random.Random(1))
        data = session.to_dict()
        data["player"]["attributes"] = {"strength": 18, "agility": 10, "intelligence": 5}
        for stack in data["player"]["inventory"]["stacks"]:
            stack["item"].pop("requirements", None)
            stack["item"]["requirement"] = {"attribute": "agility", "minimum": 99}  # pre-rework format
        loaded = GameSession.from_dict(data)
        attrs = loaded.player.attributes
        self.assertEqual((attrs.strength, attrs.vitality, attrs.charisma), (18, 14, 7))
        axe = loaded.player.weapon
        self.assertEqual([r.attribute for r in axe.requirements], [Attribute.STRENGTH])


if __name__ == "__main__":
    unittest.main()
