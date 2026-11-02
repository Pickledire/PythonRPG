import unittest

from rpg.core.attributes import Attribute
from rpg.core.catalog import ITEMS
from rpg.core.inventory import Inventory, InventoryFullError, Slot
from rpg.core.items import Armor, Consumable, Curio, Spell, Weapon, item_from_dict
from tests.helpers import make_player


class ItemTests(unittest.TestCase):
    def test_default_requirements_follow_original_rules(self):
        self.assertEqual(ITEMS.create("elven_bow").requirement.attribute, Attribute.AGILITY)
        self.assertEqual(ITEMS.create("battle_axe").requirement.minimum, 15)
        self.assertEqual(ITEMS.create("titan_claw_dagger").requirement.attribute, Attribute.AGILITY)
        self.assertEqual(ITEMS.create("leather_armor").requirement.attribute, Attribute.AGILITY)
        self.assertEqual(ITEMS.create("enchanted_robes").requirement.attribute, Attribute.INTELLIGENCE)
        self.assertEqual(ITEMS.create("lightning_bolt").requirement.minimum, 14)

    def test_every_race_can_use_its_starting_kit(self):
        for race in ("Human", "Elf", "Orc", "Dwarf"):
            player = make_player(race)
            for stack in player.inventory:
                ok, reason = player.meets_requirement(stack.item)
                self.assertTrue(ok, f"{race}: {stack.item.name} {reason}")
            self.assertIsNotNone(player.weapon)

    def test_weapon_durability_reduces_damage_and_breaks(self):
        sword = ITEMS.create("iron_sword")
        self.assertEqual(sword.effective_damage, 15)
        sword.durability = 50
        self.assertEqual(sword.effective_damage, 7)
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
        for template_id in ("battle_axe", "plate_armor", "elixir", "fireball", "pestilent_swarm"):
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
