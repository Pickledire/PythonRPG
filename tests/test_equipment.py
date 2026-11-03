"""Jewelry, trinkets and passives; the new combat effects; enemy scaling; threat-based rewards; pricing."""

import random
import unittest

from rpg import config
from rpg.core.catalog import (
    ARMOR_POOL,
    COLLEGIUM_SPELLS,
    GENERAL_SPELLS,
    ITEMS,
    JEWELRY_POOL,
    WEAPON_POOL,
    fair_value,
)
from rpg.core.combat import Attack, CastSpell, CombatSession, Hesitate, Phase
from rpg.core.effects import EffectKind, StatusEffect
from rpg.core.enemies import ENEMIES
from rpg.core.entities import DamageType, Player
from rpg.core.inventory import Slot
from rpg.core.items import Accessory, Armor, Spell, Weapon
from rpg.core.progression import loot_value_target, roll_loot, xp_reward
from rpg.core.session import GameSession
from rpg.core.shop import Shop, ShopMode
from tests.helpers import ScriptedRandom, make_enemy, make_player


def combat_with(player, enemy=None, rng=None):
    enemy = enemy or make_enemy(max_hp=900)
    enemy.spellbook = []
    combat = CombatSession(player, enemy, rng or ScriptedRandom(default=0.5))
    combat.start()
    return combat, enemy


def learn(player, template_id):
    spell = player.inventory.add(ITEMS.create(template_id)).item
    player.attributes.intelligence = player.attributes.wisdom = 20
    return spell


class JewelryTests(unittest.TestCase):
    def test_slots_and_worn_bonuses_come_and_go(self):
        p = make_player()
        hp, strength = p.max_hp, p.attributes.strength
        amulet = p.inventory.add(ITEMS.create("amulet_of_vigor")).item
        ring = p.inventory.add(ITEMS.create("ring_of_fortitude")).item
        p.equip(amulet)
        p.equip(ring)
        self.assertIs(p.inventory.equipped[Slot.AMULET], amulet)
        self.assertIs(p.inventory.equipped[Slot.RING], ring)
        self.assertEqual(p.max_hp, hp + 25 + 2 * config.HP_PER_VITALITY)
        might = p.inventory.add(ITEMS.create("copper_ring_of_might")).item
        p.equip(might)  # replaces the ring in the single ring slot
        self.assertIs(p.inventory.equipped[Slot.RING], might)
        self.assertEqual(p.attributes.strength, strength + 1)
        self.assertEqual(p.max_hp, hp + 25)
        p.unequip(amulet)
        self.assertEqual(p.max_hp, hp)

    def test_save_round_trip_does_not_double_count(self):
        session = GameSession.new_game("T", "Orc", rng=random.Random(1))
        p = session.player
        signet = p.inventory.add(ITEMS.create("kings_signet")).item
        p.equip(signet)
        before = (p.attributes.to_dict(), p.max_hp, p.max_mana, p.hp)
        loaded = GameSession.from_dict(session.to_dict()).player
        self.assertEqual((loaded.attributes.to_dict(), loaded.max_hp, loaded.max_mana, loaded.hp), before)
        loaded.unequip(loaded.inventory.equipped[Slot.RING])
        self.assertEqual(loaded.attributes.strength, before[0]["strength"] - 1)

    def test_three_trinkets_and_plain_curios(self):
        p = make_player()
        trinkets = [p.inventory.add(ITEMS.create(t)).item for t in
                    ("thieves_tools", "owl_feather_charm", "memory_stone", "climbers_chalk")]
        for t in trinkets[:3]:
            p.equip(t)
        with self.assertRaises(ValueError):
            p.equip(trinkets[3])
        story = p.inventory.add(ITEMS.from_spec("Mysterious Key")).item
        with self.assertRaises(ValueError):
            p.equip(story)

    def test_requirements_apply_to_jewelry(self):
        p = make_player()
        amulet = p.inventory.add(ITEMS.create("archmage_amulet")).item
        p.attributes.intelligence = 10
        with self.assertRaises(ValueError):
            p.equip(amulet)


class PassiveTests(unittest.TestCase):
    def wear(self, player, template_id):
        item = player.inventory.add(ITEMS.create(template_id)).item
        for requirement in item.requirements:  # these tests are about the passive, not the gate
            player.attributes.set(requirement.attribute, max(player.attributes.get(requirement.attribute),
                                                             requirement.minimum))
        player.equip(item)

    def test_regeneration_and_mana_regen(self):
        p = make_player()
        p.attributes.vitality = 13
        self.wear(p, "troll_blood_amulet")
        self.wear(p, "ring_of_the_wellspring")
        p.hp, p.mana = 50, 0
        combat, _ = combat_with(p)
        combat.act(Hesitate())
        combat.enemy_turn()
        self.assertGreater(p.mana, 0)
        self.assertTrue(any("mends you" in e.text for e in combat.log))

    def test_lifesteal_thorns_and_immunity(self):
        p = make_player()
        self.wear(p, "vampire_fang_necklace")
        self.wear(p, "ring_of_thorns")
        p.hp = p.max_hp - 50
        combat, enemy = combat_with(p, rng=ScriptedRandom(default=0.3))
        hp = p.hp
        combat.act(Attack())
        self.assertGreater(p.hp, hp)
        enemy_hp = enemy.hp
        combat.enemy_turn()
        self.assertLess(enemy.hp, enemy_hp)  # thorns
        p2 = make_player()
        self.wear(p2, "talisman_of_purity")
        combat2, _ = combat_with(p2)
        events = combat2._apply(p2, ITEMS.create("venom_spray").primary_effect(), "test", roll=False)
        self.assertIn("immune", events[0].text)

    def test_opening_ward_and_cheaper_spells(self):
        p = make_player()
        self.wear(p, "amulet_of_warding")
        self.wear(p, "sorcerers_band")
        combat, _ = combat_with(p)
        self.assertIn(EffectKind.SHIELD, p.effects)
        spell = learn(p, "fireball")
        mana = p.mana
        combat.act(CastSpell(spell.uid))
        self.assertEqual(mana - p.mana, round(spell.mana_cost * 0.88))

    def test_physical_resistance(self):
        p = make_player()
        base = p.mitigate(100, DamageType.PHYSICAL)
        self.wear(p, "ring_of_ironskin")
        self.assertLess(p.mitigate(100, DamageType.PHYSICAL), base)


class EffectTests(unittest.TestCase):
    def test_haste_gives_a_second_action(self):
        p = make_player()
        p.add_effect(StatusEffect(EffectKind.HASTE, 1, 1))
        combat, enemy = combat_with(p)
        combat.act(Attack())
        self.assertEqual(combat.phase, Phase.PLAYER_TURN)
        combat.act(Attack())
        self.assertEqual(combat.phase, Phase.ENEMY_TURN)

    def test_weaken_and_expose(self):
        p, e = make_player(), make_enemy(max_hp=900)
        combat, _ = combat_with(p, e, rng=ScriptedRandom(default=0.5))
        plain = combat._hit(p, e, 100, DamageType.PHYSICAL)
        e.add_effect(StatusEffect(EffectKind.VULNERABLE, 2, 0.5))
        exposed = combat._hit(p, e, 100, DamageType.PHYSICAL)
        self.assertGreater(exposed, plain)
        p.add_effect(StatusEffect(EffectKind.WEAKEN, 2, 0.5))
        e.remove_effect(EffectKind.VULNERABLE)
        self.assertLess(combat._hit(p, e, 100, DamageType.PHYSICAL), plain)

    def test_silence_blocks_casting(self):
        p = make_player()
        spell = learn(p, "fire_bolt")
        p.add_effect(StatusEffect(EffectKind.SILENCE, 2, 0))
        combat, _ = combat_with(p)
        self.assertFalse(combat.act(CastSpell(spell.uid)).accepted)
        caster = make_enemy("hagraven")
        caster.add_effect(StatusEffect(EffectKind.SILENCE, 2, 0))
        combat2 = CombatSession(make_player(), caster, ScriptedRandom(default=0.01))
        combat2.start()
        combat2.act(Hesitate())
        self.assertFalse(any("casts" in e.text for e in combat2.enemy_turn()))

    def test_drain_cleanse_regen_and_sanctuary(self):
        p = make_player()
        drain, purify, renewal, sanctuary = (learn(p, t) for t in ("drain_life", "purify", "renewal", "sanctuary"))
        p.max_mana = p.mana = 500
        p.hp = 20
        combat, _ = combat_with(p)
        combat.act(CastSpell(drain.uid))
        self.assertGreater(p.hp, 20)
        combat.enemy_turn()
        p.add_effect(StatusEffect(EffectKind.POISON, 3, 5))
        p.add_effect(StatusEffect(EffectKind.WEAKEN, 3, 0.3))
        combat.act(CastSpell(purify.uid))
        self.assertFalse({EffectKind.POISON, EffectKind.WEAKEN} & set(p.effects))
        combat.enemy_turn()
        combat.act(CastSpell(renewal.uid))
        self.assertIn(EffectKind.REGEN, p.effects)
        combat.enemy_turn()
        combat.act(CastSpell(sanctuary.uid))
        self.assertIn(EffectKind.SHIELD, p.effects)

    def test_burn_stops_regeneration(self):
        troll = make_enemy("troll")
        troll.hp = 40
        troll.add_effect(StatusEffect(EffectKind.BURN, 3, 1))
        combat = CombatSession(make_player(), troll, ScriptedRandom(default=0.99))
        combat.start()
        combat.act(Hesitate())
        events = combat.enemy_turn()
        self.assertTrue(any("stop" in e.text for e in events))
        self.assertLess(troll.hp, 40)


class EnemyScalingTests(unittest.TestCase):
    def test_scaling_and_bosses_never_shrink(self):
        rng = random.Random(1)
        low, high = ENEMIES.create("orc", rng, 2), ENEMIES.create("orc", random.Random(1), 12)
        self.assertLess(low.max_hp, high.max_hp)
        self.assertEqual((low.level, high.level), (2, 12))
        titan_low = ENEMIES.create("titan", random.Random(2), 3)
        titan_base = ENEMIES.create("titan", random.Random(2))
        self.assertEqual((titan_low.max_hp, titan_low.level), (titan_base.max_hp, 10))

    def test_resistances_and_titan_elements(self):
        golem = make_enemy("stone_golem")
        self.assertLess(golem.mitigate(100, DamageType.PHYSICAL), golem.mitigate(100, DamageType.MAGIC))
        self.assertTrue(golem.immune(EffectKind.POISON))
        for seed in range(30):
            titan = ENEMIES.create("titan", random.Random(seed))
            if titan.description.endswith("Fire"):
                self.assertTrue(titan.immune(EffectKind.BURN))
                break

    def test_hunts_follow_player_level(self):
        rng = random.Random(4)
        levels = {ENEMIES.random_for_level(15, rng).level for _ in range(40)}
        self.assertTrue(levels <= {14, 15, 16})


class RewardTests(unittest.TestCase):
    def test_threat_drives_xp_and_farming_pays_less(self):
        goblin = ENEMIES.create("goblin", random.Random(1), 1)
        minotaur = ENEMIES.create("minotaur", random.Random(1), 14)
        self.assertGreater(xp_reward(minotaur, random.Random(1)), xp_reward(goblin, random.Random(1)) * 3)
        self.assertLess(xp_reward(goblin, random.Random(1), player_level=12), xp_reward(goblin, random.Random(1)))

    def test_loot_matches_the_enemy_tier(self):
        rng = random.Random(3)
        target = loot_value_target(20)
        values = []
        for _ in range(60):
            for item, _ in roll_loot(ENEMIES.create("wyvern", rng, 20), rng):
                if isinstance(item, (Weapon, Armor)):
                    values.append(item.value)
        self.assertTrue(values)
        self.assertGreater(min(values), target * 0.3)


class CatalogTests(unittest.TestCase):
    def test_content_counts(self):
        self.assertGreaterEqual(len(WEAPON_POOL), 40)
        self.assertGreaterEqual(len(ARMOR_POOL), 35)
        self.assertGreaterEqual(len(GENERAL_SPELLS) + len(COLLEGIUM_SPELLS), 45)
        jewelry = [t for t in ITEMS.ids() if isinstance(ITEMS.create(t), Accessory)]
        self.assertGreaterEqual(len(jewelry), 30)
        self.assertTrue(set(JEWELRY_POOL) <= set(jewelry))

    def test_prices_follow_power(self):
        for template_id in ITEMS.ids():
            self.assertGreater(ITEMS.create(template_id).value, 0, template_id)
        self.assertLess(ITEMS.create("bronze_sword").value, ITEMS.create("halberd").value)
        self.assertLess(ITEMS.create("halberd").value, ITEMS.create("ancestral_greatsword").value)
        self.assertLess(ITEMS.create("mend").value, ITEMS.create("divine_light").value)
        stronger = Weapon(template_id="x", name="X", damage=40, value=0)
        weaker = Weapon(template_id="y", name="Y", damage=20, value=0)
        self.assertGreater(fair_value(stronger), fair_value(weaker))

    def test_every_weapon_armor_and_spell_has_requirements(self):
        for template_id in ITEMS.ids():
            item = ITEMS.create(template_id)
            if isinstance(item, (Weapon, Armor, Spell)):
                self.assertTrue(item.requirements, template_id)

    def test_shops_stock_for_the_level(self):
        player = make_player()
        shop = Shop(ShopMode.GENERAL)
        shop.rotate(5, level=2)
        gear = [o.item for o in shop.offers if isinstance(o.item, (Weapon, Armor))]
        self.assertTrue(all(i.value <= Shop.stock_ceiling(2) * 1.6 for i in gear))
        late = Shop(ShopMode.GENERAL)
        late.rotate(5, level=22)
        self.assertGreater(max(o.item.value for o in late.offers if isinstance(o.item, Weapon)),
                           max(i.value for i in gear if isinstance(i, Weapon)))
        self.assertTrue(player)  # player unused beyond construction; shops don't depend on one


if __name__ == "__main__":
    unittest.main()
