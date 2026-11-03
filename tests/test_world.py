"""Progression, enemies, hunts, shops and the campfire."""

import random
import unittest

from rpg import config
from rpg.core import campfire
from rpg.core.attributes import Attribute
from rpg.core.catalog import GENERAL_SHOP_COUNTS, ITEMS
from rpg.core.formulas import xp_to_next
from rpg.core.combat import CombatSession, Hesitate, Phase
from rpg.core.effects import EffectKind, StatusEffect
from rpg.core.enemies import AFFIXES, ENEMIES, UnknownEnemyError, apply_affix
from rpg.core.items import ItemKind
from rpg.core.progression import apply_victory, roll_victory
from rpg.core.session import GameSession
from rpg.core.shop import Shop, ShopError, ShopMode
from rpg.core.world import WorldState
from tests.helpers import ScriptedRandom, make_enemy, make_player


class ProgressionTests(unittest.TestCase):
    def test_gain_xp_levels_multiple_times(self):
        player = make_player()
        hp, mana = player.max_hp, player.max_mana
        levels = player.gain_xp(xp_to_next(1) + xp_to_next(2) + 10)
        self.assertEqual(levels, 2)
        self.assertEqual(player.level, 3)
        self.assertEqual(player.xp, 10)
        self.assertEqual(player.max_hp, hp + 2 * config.HEALTH_GAIN_PER_LEVEL)
        self.assertEqual(player.max_mana, mana + 2 * config.MANA_GAIN_PER_LEVEL)
        self.assertEqual(player.stat_points, 2)
        player.spend_stat_point(Attribute.AGILITY)
        self.assertEqual(player.attributes.agility, 10)
        player.spend_stat_point(Attribute.VITALITY)
        self.assertEqual(player.max_hp, hp + 2 * config.HEALTH_GAIN_PER_LEVEL + config.HP_PER_VITALITY)

    def test_victory_rewards_applied(self):
        player, enemy = make_player(), make_enemy()
        report = apply_victory(player, roll_victory(enemy, random.Random(2), multiplier=1.5))
        self.assertGreater(report.xp, 0)
        self.assertEqual(player.gold, config.STARTING_GOLD + report.gold)
        self.assertEqual(player.kills, 1)

    def test_bosses_offer_trophies_and_archmage_drops(self):
        report = roll_victory(make_enemy("elder_dragon"), random.Random(1))
        self.assertEqual([i.template_id for i in report.trophy_choices],
                         ["dragon_tooth_greatsword", "elder_scale_bow", "dragons_breath"])
        archmage = roll_victory(make_enemy("archmage"), random.Random(1))
        drops = {item.template_id: qty for item, qty in archmage.loot}
        self.assertEqual(drops.get("superior_health_potion"), 3)
        self.assertIn("mage_robes", drops)


class EnemyTests(unittest.TestCase):
    def test_dialogue_enemy_ids_resolve(self):
        for enemy_id in ("Orc", "Dire Wolf", "Spriggan", "Giant", "Ogre", "Minotaur", "Goblin", "horrid_monster",
                         "Rat_King", "Earth Eater Worm", "Valorian Warden", "Archmage", "Yjurgen"):
            ENEMIES.resolve(enemy_id)
        with self.assertRaises(UnknownEnemyError):
            ENEMIES.resolve("Dragon Emperor")

    def test_level_pools_scale(self):
        rng = random.Random(3)
        weak = {ENEMIES.random_for_level(1, rng).template_id for _ in range(200)}
        strong = {ENEMIES.random_for_level(15, rng).template_id for _ in range(200)}
        self.assertTrue(weak <= {"skeleton", "goblin", "wolf", "orc", "troll", "spriggan", "bandit"})
        self.assertIn("minotaur", strong)
        goblin_lvl12 = ENEMIES.random_for_level(12, random.Random(9))
        base = ENEMIES.templates[goblin_lvl12.template_id].hp
        if isinstance(base, int):
            self.assertGreater(goblin_lvl12.max_hp, base)

    def test_affixes_modify_enemy(self):
        def signature(e):
            return (e.base_damage, e.defense, e.attributes.agility, len(e.on_hit), len(e.effects), e.max_hp,
                    e.lifesteal, e.thorns, e.regen_pct, dict(e.resistances), len(e.spellbook))

        for affix in AFFIXES:
            enemy = make_enemy("orc")
            before = signature(enemy)
            apply_affix(enemy, affix)
            after = signature(enemy)
            self.assertNotEqual(before, after, affix.name)
            self.assertTrue(enemy.name.startswith(affix.name))

    def test_titans_get_random_names(self):
        names = {ENEMIES.create("titan", random.Random(i)).name for i in range(20)}
        self.assertGreater(len(names), 3)
        self.assertTrue(all(n.startswith("Titan: ") for n in names))

    def test_troll_regenerates(self):
        player, troll = make_player(), make_enemy("troll")
        troll.hp = 50
        combat = CombatSession(player, troll, ScriptedRandom(default=0.99))
        combat.start()
        combat.act(Hesitate())
        combat.enemy_turn()
        self.assertGreater(troll.hp, 50)


class HuntTests(unittest.TestCase):
    def test_milestone_bosses_forced_highest_first_until_defeated(self):
        session = GameSession.new_game("T", "Orc", rng=random.Random(1))
        self.assertIsNone(session.pending_boss())
        session.player.level = 26
        self.assertEqual(session.pending_boss(), "rat_king")
        encounter = session.create_hunt()
        self.assertTrue(encounter.is_milestone_boss)
        session.world.bosses_defeated.update({"rat_king", "earth_eater_worm"})
        self.assertEqual(session.pending_boss(), "elder_dragon")

    def test_risky_hunt_scales_and_boosts_rewards(self):
        session = GameSession.new_game("T", "Orc", rng=random.Random(4))
        encounter = session.create_hunt(risky=True)
        self.assertEqual(encounter.reward_multiplier, config.RISKY_HUNT_REWARD_MULTIPLIER)

    def test_conclude_marks_boss_and_clears_effects(self):
        session = GameSession.new_game("T", "Orc", rng=random.Random(4))
        encounter = session.create_hunt()
        encounter.enemy.hp = 0
        combat = session.begin_combat(encounter)
        combat.phase = Phase.VICTORY
        session.player.add_effect(StatusEffect(EffectKind.POISON, 2, 3))
        report = session.conclude_combat(combat)
        self.assertIsNotNone(report)
        self.assertFalse(session.player.effects)


class ShopTests(unittest.TestCase):
    def setUp(self):
        self.player = make_player("Orc")
        self.player.gold = 10_000
        self.shop = Shop(ShopMode.GENERAL)
        self.shop.rotate(8)

    def test_stock_composition(self):
        kinds = [o.item.kind for o in self.shop.offers]
        for kind, count in GENERAL_SHOP_COUNTS.items():
            if kind != "consumable":
                self.assertEqual(kinds.count(ItemKind(kind if kind != "curio" else "misc")), count, kind)

    def test_buy_gives_clone_and_reduces_stock(self):
        offer = self.shop.offers_of_kind(ItemKind.WEAPON)[0]
        item = self.shop.buy(self.player, offer)
        self.assertIsNot(item, offer.item)
        self.assertTrue(offer.sold_out)
        with self.assertRaises(ShopError):
            self.shop.buy(self.player, offer)

    def test_same_seed_does_not_restock(self):
        offer = self.shop.offers_of_kind(ItemKind.WEAPON)[0]
        self.shop.buy(self.player, offer)
        self.assertFalse(self.shop.rotate(8))
        self.assertTrue(self.shop.rotate(9))

    def test_not_enough_gold(self):
        self.player.gold = 0
        with self.assertRaises(ShopError):
            self.shop.buy(self.player, self.shop.offers[0])

    def test_sell_and_equipped_guard(self):
        with self.assertRaises(ShopError):
            Shop.sell(self.player, self.player.weapon)
        potion = self.player.inventory.consumables()[0].item
        gold = self.player.gold
        price = Shop.sell_price_for(potion, self.player)
        self.assertEqual(Shop.sell(self.player, potion), price)
        self.assertEqual(self.player.gold, gold + price)

    def test_charisma_changes_prices(self):
        offer = self.shop.offers_of_kind(ItemKind.WEAPON)[0]
        self.player.attributes.charisma = 10
        base = Shop.price_for(offer, self.player)
        self.assertEqual(base, offer.price)
        self.player.attributes.charisma = 20
        self.assertLess(Shop.price_for(offer, self.player), base)
        self.player.attributes.charisma = 5
        self.assertGreater(Shop.price_for(offer, self.player), base)
        potion = ITEMS.create("superior_health_potion")
        self.player.attributes.charisma = 15
        self.assertGreater(Shop.sell_price_for(potion, self.player), potion.value // 2)

    def test_repair(self):
        weapon = self.player.weapon
        weapon.durability = 0
        cost = Shop.repair_cost(weapon)
        self.assertGreater(cost, 0)
        self.shop.repair(self.player, weapon)
        self.assertEqual(weapon.durability, weapon.max_durability)
        with self.assertRaises(ShopError):
            self.shop.repair(self.player, weapon)

    def test_unlocks_appear_in_stock(self):
        shop = Shop(ShopMode.GENERAL)
        shop.rotate(3, {"titan_hammer"})
        self.assertIn("titan_hammer", [o.item.template_id for o in shop.offers])

    def test_magic_shop_sells_spells_and_potions(self):
        shop = Shop(ShopMode.MAGIC)
        shop.rotate(5)
        kinds = {o.item.kind for o in shop.offers}
        self.assertTrue({ItemKind.SPELL, ItemKind.CONSUMABLE, ItemKind.ACCESSORY} <= kinds)
        self.assertFalse(kinds & {ItemKind.MISC})


class CampfireTests(unittest.TestCase):
    def rest(self, *rolls):
        player = make_player()
        player.hp, player.mana = 1, 0
        world = WorldState()
        report = campfire.rest(player, world, ScriptedRandom(values=list(rolls), default=0.5))
        return player, world, report

    def test_rest_restores_and_advances_time(self):
        player, world, _ = self.rest(0.9)
        self.assertEqual((player.hp, player.mana), (player.max_hp, player.max_mana))
        self.assertEqual(world.bell, (config.START_BELL + config.REST_HOURS) % 24)

    def test_ambush(self):
        _, _, report = self.rest(0.1, 0.1)
        self.assertIsNotNone(report.ambush)

    def test_bad_and_good_dialogue(self):
        self.assertEqual(self.rest(0.1, 0.5)[2].dialogue_category, "bad")
        self.assertEqual(self.rest(0.5, 0.5)[2].dialogue_category, "good")

    def test_thieves_and_gifts(self):
        player, _, _ = self.rest(0.1, 0.8)
        self.assertLess(player.gold, config.STARTING_GOLD)
        player, _, _ = self.rest(0.5, 0.95)
        self.assertEqual(player.inventory.consumables()[0].quantity, 4)


if __name__ == "__main__":
    unittest.main()
