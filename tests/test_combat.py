import unittest

from rpg.core.catalog import ITEMS
from rpg.core.combat import Attack, CastSpell, CombatError, CombatSession, Flee, Hesitate, Phase, UseItem
from rpg.core.effects import EffectKind, EffectSpec, StatusEffect
from rpg.core.entities import DamageType
from tests.helpers import ScriptedRandom, make_enemy, make_player

HIT = 0.0  # random() < hit chance -> hit; also below any crit chance -> crit
NO_CRIT = 0.99


class CombatFlowTests(unittest.TestCase):
    def test_attack_hits_and_enemy_responds(self):
        player, enemy = make_player(), make_enemy("orc")
        combat = CombatSession(player, enemy, ScriptedRandom(default=0.5))
        combat.start()
        self.assertEqual(combat.phase, Phase.PLAYER_TURN)
        result = combat.act(Attack())
        self.assertTrue(result.accepted)
        self.assertLess(enemy.hp, enemy.max_hp)
        self.assertEqual(combat.phase, Phase.ENEMY_TURN)
        combat.enemy_turn()
        self.assertLess(player.hp, player.max_hp)
        self.assertEqual(combat.phase, Phase.PLAYER_TURN)
        self.assertEqual(player.weapon.durability, player.weapon.max_durability - 1)

    def test_acting_out_of_turn_raises(self):
        combat = CombatSession(make_player(), make_enemy(), ScriptedRandom())
        combat.start()
        with self.assertRaises(CombatError):
            combat.enemy_turn()

    def test_kill_ends_in_victory(self):
        enemy = make_enemy(hp=1)
        combat = CombatSession(make_player(), enemy, ScriptedRandom(default=0.5))
        combat.start()
        combat.act(Attack())
        self.assertEqual(combat.phase, Phase.VICTORY)
        self.assertTrue(combat.is_over)

    def test_broken_weapon_falls_back_to_fists(self):
        player = make_player()
        player.weapon.durability = 0
        enemy = make_enemy(max_hp=500)
        combat = CombatSession(player, enemy, ScriptedRandom(default=0.5))
        combat.start()
        events = combat.act(Attack()).events
        self.assertIn("bare fists", events[0].text)


class StatusEffectTests(unittest.TestCase):
    def test_poison_ticks_at_start_of_turn_and_expires(self):
        player, enemy = make_player(), make_enemy(max_hp=500)
        combat = CombatSession(player, enemy, ScriptedRandom(default=NO_CRIT))
        combat.start()
        enemy.add_effect(StatusEffect(EffectKind.POISON, 2, 10))
        combat.act(Hesitate())
        hp = enemy.hp
        combat.enemy_turn()
        self.assertEqual(enemy.hp, hp - 10)
        self.assertEqual(enemy.effects[EffectKind.POISON].turns, 1)
        combat.act(Hesitate())
        combat.enemy_turn()
        self.assertNotIn(EffectKind.POISON, enemy.effects)

    def test_damage_over_time_can_kill(self):
        player, enemy = make_player(), make_enemy()
        enemy.hp = 5
        enemy.add_effect(StatusEffect(EffectKind.BURN, 3, 10))
        combat = CombatSession(player, enemy, ScriptedRandom(default=NO_CRIT))
        combat.start()
        combat.act(Hesitate())
        combat.enemy_turn()
        self.assertFalse(enemy.alive)
        self.assertEqual(combat.phase, Phase.VICTORY)

    def test_player_dies_to_bleed_at_turn_start(self):
        player, enemy = make_player(), make_enemy(max_hp=500)
        combat = CombatSession(player, enemy, ScriptedRandom(default=NO_CRIT))
        combat.start()
        combat.act(Hesitate())
        player.hp = 3
        player.add_effect(StatusEffect(EffectKind.BLEED, 2, 8))
        enemy.add_effect(StatusEffect(EffectKind.FROZEN, 1))
        combat.enemy_turn()
        self.assertEqual(combat.phase, Phase.DEFEAT)

    def test_frozen_player_skips_turn(self):
        player, enemy = make_player(), make_enemy(max_hp=500)
        player.add_effect(StatusEffect(EffectKind.FROZEN, 1))
        combat = CombatSession(player, enemy, ScriptedRandom(default=NO_CRIT))
        combat.start()
        self.assertEqual(combat.phase, Phase.ENEMY_TURN)
        self.assertNotIn(EffectKind.FROZEN, player.effects)

    def test_frozen_enemy_skips_turn(self):
        player, enemy = make_player(), make_enemy(max_hp=500)
        combat = CombatSession(player, enemy, ScriptedRandom(default=NO_CRIT))
        combat.start()
        enemy.add_effect(StatusEffect(EffectKind.FROZEN, 1))
        combat.act(Hesitate())
        combat.enemy_turn()
        self.assertEqual(player.hp, player.max_hp)
        self.assertEqual(combat.phase, Phase.PLAYER_TURN)

    def test_shield_reduces_incoming_damage(self):
        player = make_player()
        unshielded = player.mitigate(100, DamageType.PHYSICAL)
        player.add_effect(StatusEffect(EffectKind.SHIELD, 2, 0.5))
        dealt = player.take_hit(100)
        self.assertEqual(dealt, max(1, int(unshielded * 0.5)))

    def test_reapplying_refreshes_to_stronger(self):
        player = make_player()
        player.add_effect(StatusEffect(EffectKind.POISON, 1, 5))
        player.add_effect(StatusEffect(EffectKind.POISON, 3, 4))
        effect = player.effects[EffectKind.POISON]
        self.assertEqual((effect.turns, effect.potency), (3, 5))

    def test_weapon_on_hit_applies_bleed(self):
        player = make_player("Orc")
        axe = ITEMS.create("titan_claw_dagger")
        axe.on_hit = EffectSpec(EffectKind.BLEED, 6, 3, 1.0)
        player.inventory.add(axe)
        player.attributes.agility = player.attributes.dexterity = 20
        player.equip(axe)
        enemy = make_enemy(max_hp=500)
        combat = CombatSession(player, enemy, ScriptedRandom(default=0.5))
        combat.start()
        combat.act(Attack())
        self.assertIn(EffectKind.BLEED, enemy.effects)

    def test_enemy_on_hit_poisons_player(self):
        player, enemy = make_player(), make_enemy("rat_king")
        combat = CombatSession(player, enemy, ScriptedRandom(values=[0.1, NO_CRIT, 0.1], default=0.1))  # hit, no crit, proc
        enemy.spellbook = []
        combat.start()
        combat.act(Hesitate())
        combat.enemy_turn()
        self.assertIn(EffectKind.POISON, player.effects)

    def test_bosses_can_resist_freeze(self):
        player, boss = make_player("Elf"), make_enemy("titan")
        freeze = ITEMS.create("freeze")
        player.inventory.add(freeze)
        player.attributes.intelligence = 20
        combat = CombatSession(player, boss, ScriptedRandom(default=0.1))
        combat.start()
        combat.act(CastSpell(freeze.uid))
        self.assertNotIn(EffectKind.FROZEN, boss.effects)


class PlayerActionTests(unittest.TestCase):
    def test_spell_without_mana_is_rejected_and_turn_kept(self):
        player = make_player("Elf")
        player.mana = 0
        combat = CombatSession(player, make_enemy(), ScriptedRandom())
        combat.start()
        result = combat.act(CastSpell(player.spell.uid))
        self.assertFalse(result.accepted)
        self.assertEqual(combat.phase, Phase.PLAYER_TURN)

    def test_damage_spell_spends_mana_and_hurts(self):
        player, enemy = make_player("Elf"), make_enemy(max_hp=500)
        combat = CombatSession(player, enemy, ScriptedRandom(default=0.5))
        combat.start()
        combat.act(CastSpell(player.spell.uid))
        self.assertEqual(player.mana, player.max_mana - player.spell.mana_cost)
        self.assertLess(enemy.hp, 500)

    def test_heal_and_ward_target_self(self):
        player = make_player("Elf")
        for template_id in ("heal", "ward"):
            player.inventory.add(ITEMS.create(template_id))
        heal = player.inventory.find_by_name("Heal").item
        ward = player.inventory.find_by_name("Ward").item
        player.hp = 10
        combat = CombatSession(player, make_enemy(max_hp=500), ScriptedRandom(default=NO_CRIT))
        combat.start()
        combat.act(CastSpell(heal.uid))
        self.assertGreater(player.hp, 10)
        combat.enemy_turn()
        combat.act(CastSpell(ward.uid))
        self.assertIn(EffectKind.SHIELD, player.effects)

    def test_potion_heals_and_is_consumed(self):
        player = make_player()
        player.hp = 20
        potion = player.inventory.consumables()[0].item
        combat = CombatSession(player, make_enemy(), ScriptedRandom())
        combat.start()
        combat.act(UseItem(potion.uid))
        self.assertEqual(player.hp, 70)
        self.assertEqual(player.inventory.consumables()[0].quantity, 2)

    def test_potion_at_full_health_is_refused(self):
        player = make_player()
        potion = player.inventory.consumables()[0].item
        combat = CombatSession(player, make_enemy(), ScriptedRandom())
        combat.start()
        self.assertFalse(combat.act(UseItem(potion.uid)).accepted)

    def test_antidote_cures(self):
        player = make_player()
        antidote = ITEMS.create("antidote")
        player.inventory.add(antidote)
        player.add_effect(StatusEffect(EffectKind.POISON, 3, 5))
        player.add_effect(StatusEffect(EffectKind.SHIELD, 3, 0.3))
        combat = CombatSession(player, make_enemy(), ScriptedRandom())
        combat.start()
        combat.act(UseItem(antidote.uid))
        self.assertNotIn(EffectKind.POISON, player.effects)
        self.assertIn(EffectKind.SHIELD, player.effects)

    def test_flee(self):
        combat = CombatSession(make_player(), make_enemy(), ScriptedRandom(values=[0.1]))
        combat.start()
        combat.act(Flee())
        self.assertEqual(combat.phase, Phase.FLED)
        combat = CombatSession(make_player(), make_enemy(), ScriptedRandom(values=[0.95]))
        combat.start()
        combat.act(Flee())
        self.assertEqual(combat.phase, Phase.ENEMY_TURN)

    def test_flee_disallowed(self):
        combat = CombatSession(make_player(), make_enemy(), ScriptedRandom(), allow_flee=False)
        combat.start()
        self.assertFalse(combat.act(Flee()).accepted)


if __name__ == "__main__":
    unittest.main()
