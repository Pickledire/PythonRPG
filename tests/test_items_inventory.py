import unittest

from rpg.core.attributes import Attribute
from rpg.core.catalog import ITEMS
from rpg.core.inventory import Inventory, InventoryFullError, Slot
from rpg.core.items import Armor, Consumable, Curio, Spell, Weapon, item_from_dict
from tests.helpers import make_player


class ItemTests(unittest.TestCase):
    def test_default_requirement_rules(self):
        def attrs(template_id):
            return [r.attribute for r in ITEMS.create(template_id).requirements]

        self.assertEqual(attrs("elven_bow"), [Attribute.DEXTERITY])  # ranged -> Dexterity
        self.assertEqual(attrs("halfling_dagger"), [Attribute.DEXTERITY])  # finesse -> Dexterity
        self.assertEqual(attrs("war_hammer"), [Attribute.STRENGTH])
        self.assertEqual(attrs("crystal_staff"), [Attribute.INTELLIGENCE])
        self.assertEqual(attrs("leather_armor"), [Attribute.AGILITY])
        self.assertEqual(attrs("chain_mail"), [Attribute.STRENGTH])
        self.assertEqual(attrs("heal"), [Attribute.WISDOM])  # support spells -> Wisdom
        self.assertEqual(attrs("ice_shard"), [Attribute.INTELLIGENCE])
        self.assertTrue(ITEMS.create("halfling_dagger").finesse)

    def test_multi_attribute_requirements(self):
        mithril = ITEMS.create("mithril_armor")
        self.assertEqual({(r.attribute, r.minimum) for r in mithril.requirements},
                         {(Attribute.STRENGTH, 15), (Attribute.DEXTERITY, 15)})
        player = make_player("Human")
        player.inventory.add(mithril)
        ok, reason = player.meets_requirement(mithril)
        self.assertFalse(ok)
        self.assertIn("Strength 15", reason)
        self.assertIn("Dexterity 15", reason)
        player.attributes.strength, player.attributes.dexterity = 15, 14
        ok, reason = player.meets_requirement(mithril)
        self.assertFalse(ok)
        self.assertNotIn("Strength", reason)
        player.attributes.dexterity = 15
        self.assertTrue(player.meets_requirement(mithril)[0])
        self.assertEqual(player.equip(mithril), "Equipped Mithril Armor.")

    def test_many_items_need_two_attributes(self):
        multi = [tid for tid in ITEMS.ids() if len(ITEMS.create(tid).requirements) > 1]
        self.assertGreaterEqual(len(multi), 25)

    def test_every_race_can_use_its_starting_kit(self):
        from rpg import config

        for race in config.RACES:
            player = make_player(race)
            for stack in player.inventory:
                ok, reason = player.meets_requirement(stack.item)
                self.assertTrue(ok, f"{race}: {stack.item.name} {reason}")
            self.assertIsNotNone(player.weapon)

    def test_weapon_durability_reduces_damage_and_breaks(self):
        sword = ITEMS.create("iron_sword")
        self.assertEqual(sword.effective_damage, sword.damage)
        sword.durability = sword.max_durability // 2
        self.assertEqual(sword.effective_damage, int(sword.damage * 0.85))  # worn: down to 70% at 0 durability
        sword.durability = 1
        self.assertTrue(sword.wear())
        self.assertTrue(sword.is_broken)
        self.assertEqual(sword.effective_damage, 0)
        sword.repair()
        self.assertEqual(sword.durability, sword.max_durability)

    def test_clone_has_new_uid(self):
        a = ITEMS.create("steel_sword")
        b = a.clone()
        self.assertNotEqual(a.uid, b.uid)
        self.assertEqual(a.to_dict() | {"uid": b.uid}, b.to_dict())

    def test_serialization_round_trip_all_kinds(self):
        for template_id in ("battle_axe", "plate_armor", "elixir", "fireball", "pestilent_swarm", "bone_claws"):
            item = ITEMS.create(template_id)
            restored = item_from_dict(item.to_dict())
            self.assertEqual(type(restored), type(item))
            self.assertEqual(restored.to_dict(), item.to_dict())

    def test_from_spec_handles_dialogue_payloads(self):
        self.assertIsInstance(ITEMS.from_spec("Health Potion"), Consumable)
        self.assertIsInstance(ITEMS.from_spec("spark"), Spell)
        self.assertIsInstance(ITEMS.from_spec("Mysterious Key"), Curio)
        sword = ITEMS.from_spec({"name": "Stone Sword", "type": "melee", "damage": 22})
        self.assertIsInstance(sword, Weapon)
        self.assertEqual(sword.damage, 22)
        self.assertIsInstance(ITEMS.from_spec({"name": "Bark Mail", "type": "armor", "defense": 9}), Armor)


class InventoryTests(unittest.TestCase):
    def test_consumables_stack_gear_does_not(self):
        inv = Inventory()
        inv.add(ITEMS.create("health_potion"), 2)
        inv.add(ITEMS.create("health_potion"))
        inv.add(ITEMS.create("plate_armor"))
        inv.add(ITEMS.create("plate_armor"))
        self.assertEqual(len(inv), 3)
        self.assertEqual(inv.consumables()[0].quantity, 3)

    def test_same_name_different_potency_does_not_merge(self):
        inv = Inventory()
        inv.add(ITEMS.create("superior_health_potion"))
        odd = ITEMS.create("superior_health_potion")
        odd.potency = 150
        inv.add(odd)
        self.assertEqual(len(inv), 2)

    def test_remove_unequips(self):
        player = make_player()
        sword = player.weapon
        player.inventory.remove(sword.uid)
        self.assertIsNone(player.weapon)

    def test_capacity(self):
        inv = Inventory(capacity=1)
        inv.add(ITEMS.create("axe"))
        with self.assertRaises(InventoryFullError):
            inv.add(ITEMS.create("axe"))

    def test_equip_validates_type(self):
        inv = Inventory()
        potion = ITEMS.create("health_potion")
        inv.add(potion)
        with self.assertRaises(TypeError):
            inv.equip(potion)
        spell = ITEMS.create("ward")
        inv.add(spell)
        self.assertEqual(inv.equip(spell), Slot.SPELL)

    def test_round_trip_keeps_equipment(self):
        player = make_player("Elf")
        restored = Inventory.from_dict(player.inventory.to_dict())
        self.assertEqual(restored.weapon.uid, player.weapon.uid)
        self.assertEqual(restored.spell.uid, player.spell.uid)

    def test_player_equip_enforces_requirement(self):
        player = make_player("Elf")  # STR 8
        greatsword = ITEMS.create("greatsword")
        player.inventory.add(greatsword)
        with self.assertRaises(ValueError):
            player.equip(greatsword)


if __name__ == "__main__":
    unittest.main()
