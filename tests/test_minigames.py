"""Skills, every minigame, boss quick-time events and the dialogue hooks."""

import random
import unittest

from rpg.core.catalog import ITEMS
from rpg.core.combat import CombatError, CombatSession, Hesitate, Phase, UseItem
from rpg.core.dialogue import MinigameRequest, apply_effects, check_conditions
from rpg.core.effects import EffectKind
from rpg.core.minigames import (
    BalanceBeam,
    Lockpicking,
    MemorySequence,
    MinigameSpec,
    Outcome,
    QuickTimeEvent,
    Stealth,
    TimingStrike,
)
from rpg.core.session import Encounter, GameSession
from rpg.core.skills import Skill, SkillCheck, skill_check, skill_rating
from tests.helpers import ScriptedRandom, make_enemy, make_player

DT = 1 / 30


def check(skill, rating=12, dc=12, traits=()):
    return SkillCheck(skill, dc, rating, [], frozenset(traits))


def run(game, seconds, step=DT):
    for _ in range(int(seconds / step)):
        game.tick(step)
        if game.finished:
            break


class SkillTests(unittest.TestCase):
    def test_race_gear_curio_and_prime_sources(self):
        halfling, orc = make_player("Halfling"), make_player("Orc")
        self.assertGreater(skill_rating(halfling, Skill.STEALTH), skill_rating(orc, Skill.STEALTH) + 5)
        before = skill_rating(halfling, Skill.STEALTH)
        halfling.inventory.equip(halfling.inventory.add(ITEMS.create("shadow_leathers")).item)
        charm = halfling.inventory.add(ITEMS.create("owl_feather_charm"), 2).item
        self.assertEqual(skill_rating(halfling, Skill.STEALTH), before + 3)  # trinkets only count when equipped
        halfling.equip(charm)
        halfling.prime_skill("stealth", 3)
        result = skill_check(halfling, Skill.STEALTH, 12)
        self.assertEqual(result.rating, before + 3 + 1 + 3)
        self.assertEqual({s.label for s in result.sources},
                         {"Halfling", "Shadow Leathers", "Owl Feather Charm", "Primed"})
        self.assertTrue(result.has("small_frame") and result.has("keen_senses"))

    def test_heavy_armor_is_loud(self):
        player = make_player("Orc")
        quiet = skill_rating(player, Skill.STEALTH)
        player.inventory.equip(player.inventory.add(ITEMS.create("plate_armor")).item)
        self.assertEqual(skill_rating(player, Skill.STEALTH), quiet - 4)

    def test_ease_follows_edge(self):
        self.assertGreater(check(Skill.FOCUS, 16).ease(), 1.0)
        self.assertLess(check(Skill.FOCUS, 8).ease(), 1.0)
        self.assertEqual(check(Skill.FOCUS, 40).edge, 10)
        self.assertEqual(check(Skill.FOCUS, 12).odds_label, "Even")


class QTETests(unittest.TestCase):
    def test_all_hits_succeed(self):
        game = QuickTimeEvent(check(Skill.REFLEXES), random.Random(1), prompts=3)
        run(game, 1.05)
        while not game.finished:
            if game.current_key:
                game.press(game.current_key)
            game.tick(DT)
        self.assertEqual(game.result.outcome, Outcome.SUCCESS)

    def test_timeouts_and_wrong_keys_fail(self):
        game = QuickTimeEvent(check(Skill.REFLEXES), random.Random(1), prompts=2)
        run(game, 1.05)
        wrong = next(k for k in "wasdqe" if k != game.current_key)
        game.press(wrong)
        run(game, 10)
        self.assertEqual(game.result.outcome, Outcome.FAILURE)
        self.assertEqual(game.results, [False, False])

    def test_reflexes_and_traits_widen_window(self):
        slow = QuickTimeEvent(check(Skill.REFLEXES, 8), random.Random(1), window=1.5)
        quick = QuickTimeEvent(check(Skill.REFLEXES, 16, traits=("keen_senses", "quickened")), random.Random(1),
                               window=1.5)
        self.assertGreater(quick.window, slow.window * 1.5)


class Pick:
    def __init__(self, potency=1, uid="p"):
        self.potency, self.uid, self.name = potency, uid, "Lockpick"


class LockpickTests(unittest.TestCase):
    def open_pin(self, game):
        game.position = game.sweet[game.pin]
        game.press("space")

    def test_sweet_spots_open_the_lock(self):
        game = Lockpicking(check(Skill.LOCKPICKING), random.Random(2), pins=3, picks=[Pick()])
        for _ in range(3):
            self.open_pin(game)
        self.assertEqual(game.result.outcome, Outcome.SUCCESS)
        self.assertEqual(game.result.spent, [])

    def test_strain_snaps_picks_and_running_out_fails(self):
        game = Lockpicking(check(Skill.LOCKPICKING), random.Random(2), pins=2, picks=[Pick(1, "a"), Pick(1, "b")])
        game.position = (game.sweet[0] + 50) % 100
        for _ in range(40):
            if game.finished:
                break
            game.press("space")
        self.assertEqual(game.result.outcome, Outcome.FAILURE)
        self.assertEqual([p.uid for p in game.result.spent], ["a", "b"])

    def test_better_picks_skill_and_tinker_reduce_strain(self):
        base = Lockpicking(check(Skill.LOCKPICKING), random.Random(2), picks=[Pick(1)])
        good = Lockpicking(check(Skill.LOCKPICKING), random.Random(2), picks=[Pick(2)])
        skilled = Lockpicking(check(Skill.LOCKPICKING, 18), random.Random(2), picks=[Pick(1)])
        tinker = Lockpicking(check(Skill.LOCKPICKING, traits=("tinker",)), random.Random(2), picks=[Pick(1)])
        for other in (good, skilled, tinker):
            self.assertLess(other.strain_per_miss(0.0), base.strain_per_miss(0.0))
        self.assertGreater(skilled.half_width, base.half_width)

    def test_no_picks_fails_immediately(self):
        self.assertEqual(Lockpicking(check(Skill.LOCKPICKING), picks=[]).result.outcome, Outcome.FAILURE)

    def test_session_spends_broken_picks(self):
        session = GameSession.new_game("T", "Human", rng=random.Random(3))
        session.player.inventory.add(ITEMS.create("lockpick"), 2)
        session.player.inventory.add(ITEMS.create("masterwork_lockpick"))
        game = session.start_minigame(MinigameSpec.from_dict({"type": "lockpick", "dc": 11}))
        self.assertEqual(game.current_pick.name, "Masterwork Lockpick")  # best pick first
        game.position = (game.sweet[0] + 50) % 100
        while game.picks_left == 3:
            game.press("space")
        game.abandon()
        session.finish_minigame(game)
        self.assertEqual([p.name for p in session.player.lockpicks()], ["Lockpick", "Lockpick"])


class TimingTests(unittest.TestCase):
    def test_perfect_strikes(self):
        game = TimingStrike(check(Skill.PRECISION), random.Random(4), strikes=3)
        while not game.finished:
            game.tick(DT / 4)
            if not game.waiting and abs(game.needle - game.center) <= game.perfect / 2:
                game.press("space")
        self.assertEqual(game.grades, ["perfect"] * 3)
        self.assertEqual(game.result.outcome, Outcome.SUCCESS)

    def test_idle_strikes_miss(self):
        game = TimingStrike(check(Skill.PRECISION), random.Random(4), strikes=2)
        run(game, 20)
        self.assertEqual(game.result.outcome, Outcome.FAILURE)

    def test_precision_and_steady_hands(self):
        base = TimingStrike(check(Skill.PRECISION), random.Random(4))
        steady = TimingStrike(check(Skill.PRECISION, 16, traits=("steady_hands",)), random.Random(4))
        self.assertGreater(steady.zone, base.zone)
        self.assertLess(steady.speed, base.speed)


class MemoryTests(unittest.TestCase):
    def play(self, game, mistakes_on_round=None):
        while not game.finished:
            game.tick(DT)
            if game.state == "input":
                if mistakes_on_round is not None and game.round == mistakes_on_round:
                    mistakes_on_round = None
                    game.click((game.sequence[len(game.entered)] + 1) % 9)
                else:
                    game.click(game.sequence[len(game.entered)])

    def test_perfect_recall_succeeds_and_lengths_grow(self):
        game = MemorySequence(check(Skill.FOCUS), random.Random(5), rounds=3, start_length=3)
        lengths = []
        while not game.finished:
            game.tick(DT)
            if game.state == "input":
                if not game.entered:
                    lengths.append(len(game.sequence))
                game.click(game.sequence[len(game.entered)])
        self.assertEqual(lengths, [3, 4, 5])
        self.assertEqual(game.result.outcome, Outcome.SUCCESS)

    def test_a_mistake_spends_a_glance(self):
        game = MemorySequence(check(Skill.FOCUS, 16), random.Random(5), rounds=2)
        self.assertEqual(game.glances, 2)  # focus edge earns a second glance
        self.play(game, mistakes_on_round=0)
        self.assertEqual(game.result.outcome, Outcome.PARTIAL)

    def test_out_of_glances_fails_and_keys_do_nothing(self):
        game = MemorySequence(check(Skill.FOCUS), random.Random(5))
        self.assertEqual(game.glances, 1)
        run(game, 10)
        self.assertEqual(game.state, "input")
        game.press("1")
        game.press("enter")
        self.assertEqual(game.entered, [])
        game.click((game.sequence[0] + 1) % 9)
        self.assertEqual(game.result.outcome, Outcome.FAILURE)

    def test_eidetic_lingers(self):
        self.assertGreater(MemorySequence(check(Skill.FOCUS, traits=("eidetic",))).show_time,
                           MemorySequence(check(Skill.FOCUS)).show_time)


class BalanceTests(unittest.TestCase):
    def test_doing_nothing_falls(self):
        game = BalanceBeam(check(Skill.BALANCE), random.Random(6), duration=60)
        run(game, 60)
        self.assertEqual(game.result.outcome, Outcome.FAILURE)

    def test_correcting_crosses(self):
        game = BalanceBeam(check(Skill.BALANCE, 15), random.Random(6), duration=10)
        cooldown = 0.0
        while not game.finished:
            game.tick(DT)
            cooldown -= DT
            predicted = game.lean + game.velocity * 0.4
            if cooldown <= 0 and abs(predicted) > 0.15:
                game.press("left" if predicted > 0 else "right")
                cooldown = 0.25
        self.assertNotEqual(game.result.outcome, Outcome.FAILURE)

    def test_skill_and_stoneborn_soften_gusts(self):
        base = BalanceBeam(check(Skill.BALANCE))
        dwarf = BalanceBeam(check(Skill.BALANCE, 15, traits=("stoneborn",)))
        self.assertLess(dwarf.gust_strength, base.gust_strength * 0.7)


class StealthTests(unittest.TestCase):
    def test_holding_breath_runs_out_and_gasps(self):
        game = Stealth(check(Skill.STEALTH), random.Random(7), duration=60)
        game.mishap_timer = 999
        game.press("space")
        self.assertTrue(game.holding)
        run(game, 9)
        self.assertFalse(game.holding)
        self.assertGreater(game.peak, 5)

    def test_breathless_and_vitality_lungs(self):
        base = Stealth(check(Skill.STEALTH), random.Random(7), vitality=10)
        tough = Stealth(check(Skill.STEALTH), random.Random(7), vitality=16)
        revenant = Stealth(check(Skill.STEALTH, traits=("breathless",)), random.Random(7))
        self.assertLess(tough.drain, base.drain)
        self.assertLess(revenant.drain, base.drain * 0.5)

    def test_missed_mishap_is_loud_and_answered_one_is_silent(self):
        game = Stealth(check(Skill.STEALTH), random.Random(7), duration=60)
        game.mishap_timer = 0
        game.tick(DT)
        self.assertIsNotNone(game.mishap)
        game.press(game.mishap.key)
        self.assertIsNone(game.mishap)
        quiet = game.noise
        game.mishap_timer = 0
        game.tick(DT)
        run(game, game.mishap.window + 0.1)
        self.assertGreater(game.noise, quiet + 3)

    def test_discovery_and_escape(self):
        loud = Stealth(check(Skill.STEALTH, 2), random.Random(7), duration=60, presence=3)
        run(loud, 60)  # breathing loudly the whole time with a terrible rating
        self.assertEqual(loud.result.outcome, Outcome.FAILURE)
        calm = Stealth(check(Skill.STEALTH, 22, traits=("small_frame",)), random.Random(7), duration=8)
        calm.mishap_timer = 999
        run(calm, 9)
        self.assertEqual(calm.result.outcome, Outcome.SUCCESS)

    def test_small_frame_is_quieter(self):
        self.assertLess(Stealth(check(Skill.STEALTH, traits=("small_frame",))).loudness,
                        Stealth(check(Skill.STEALTH)).loudness)


class BossQTETests(unittest.TestCase):
    def setUp(self):
        self.player = make_player()
        self.boss = make_enemy("stone_sentinel")
        self.boss.spellbook = []
        self.combat = CombatSession(self.player, self.boss, ScriptedRandom(default=0.99))
        self.combat.start()

    def enemy_turn_at(self, ratio):
        self.boss.hp = int(self.boss.max_hp * ratio)
        self.combat.act(Hesitate())
        return self.combat.enemy_turn()

    def test_trigger_fires_once_and_blocks_the_turn(self):
        events = self.enemy_turn_at(0.69)
        self.assertIsNotNone(self.combat.pending_qte)
        self.assertTrue(any("lifts its fist" in e.text for e in events))
        with self.assertRaises(CombatError):
            self.combat.enemy_turn()
        self.combat.resolve_qte(1.0)
        self.assertEqual(self.combat.phase, Phase.PLAYER_TURN)
        self.assertEqual(self.player.hp, self.player.max_hp)
        self.assertIn(EffectKind.FROZEN, self.boss.effects)  # staggered
        self.combat.act(Hesitate())
        self.combat.enemy_turn()  # the boss loses this turn
        self.assertIsNone(self.combat.pending_qte)

    def test_failure_and_partial_damage(self):
        self.enemy_turn_at(0.69)
        self.combat.resolve_qte(0.0)
        full = self.player.max_hp - self.player.hp
        self.assertGreater(full, 0)
        self.player.hp = self.player.max_hp
        self.enemy_turn_at(0.34)
        self.combat.resolve_qte(0.5)
        self.assertAlmostEqual(self.player.max_hp - self.player.hp, full / 2, delta=1)

    def test_counter_damage(self):
        self.enemy_turn_at(0.34)  # below both thresholds: the first fires now, CORE BREACH next turn
        self.assertEqual(self.combat.pending_qte.title, "STONE FIST")
        self.combat.resolve_qte(0.0)
        self.boss.remove_effect(EffectKind.FROZEN)
        self.combat.act(Hesitate())
        self.combat.enemy_turn()
        self.assertEqual(self.combat.pending_qte.title, "CORE BREACH")
        hp = self.boss.hp
        self.combat.resolve_qte(1.0)
        self.assertLess(self.boss.hp, hp)

    def test_session_builds_qte_from_trigger(self):
        session = GameSession.new_game("T", "Elf", rng=random.Random(1))
        trigger = self.boss.template.qte_triggers[0]
        game = session.start_minigame(session.qte_spec(trigger))
        self.assertIsInstance(game, QuickTimeEvent)
        self.assertEqual(len(game.sequence), trigger.prompts)
        self.assertTrue(game.check.has("keen_senses"))

    def test_real_bosses_have_qtes(self):
        for boss in ("titan", "elder_dragon", "earth_eater_worm", "rat_king"):
            self.assertGreaterEqual(len(make_enemy(boss).template.qte_triggers), 2, boss)


class AmbushTests(unittest.TestCase):
    def test_ambush_enemy_strikes_first(self):
        session = GameSession.new_game("T", "Human", rng=random.Random(2))
        combat = session.begin_combat(Encounter(make_enemy(), ambush=True))
        events = combat.start()
        self.assertEqual(combat.phase, Phase.ENEMY_TURN)
        self.assertIn("off guard", events[-1].text)

    def test_opener_hurts_enemy(self):
        session = GameSession.new_game("T", "Human", rng=random.Random(2))
        enemy = make_enemy(max_hp=200)
        combat = session.begin_combat(Encounter(enemy, opener=0.25))
        events = combat.start()
        self.assertEqual(enemy.hp, 150)
        self.assertIn("strike from hiding", events[0].text)


class DialogueMinigameTests(unittest.TestCase):
    def setUp(self):
        self.session = GameSession.new_game("T", "Halfling", rng=random.Random(1))

    def test_effect_becomes_request_and_routes_outcomes(self):
        result = apply_effects(self.session, [{"minigame": {
            "type": "hide", "dc": 13, "duration": 15, "success": "a", "failure": "b", "retreat": "c", "flag": "f"}}])
        request = result.requests[0]
        self.assertIsInstance(request, MinigameRequest)
        self.assertEqual(request.spec.params, {"duration": 15})
        self.assertEqual(request.next_node(Outcome.PARTIAL), "a")  # partial falls back to success
        self.assertEqual(request.next_node(Outcome.FAILURE), "b")
        self.assertEqual(request.next_node(None), "c")
        runner = self.session.dialogue("test_vault/hall")
        runner.start()
        runner.resolve_minigame(request, Outcome.SUCCESS)
        self.assertTrue(runner.redirected)
        self.assertEqual(self.session.world.flags["f"], "success")

    def test_hide_in_the_vault_routes_by_outcome(self):
        runner = self.session.dialogue("test_vault/hall")
        runner.start()
        result = runner.choose(0)
        request = result.requests[0]
        runner.resolve_minigame(request, Outcome.FAILURE)
        step = runner.proceed()
        self.assertEqual(runner.node.node_id, "test_vault/hall_discovered")
        self.assertTrue(step.requests[0].ambush)

    def test_conditions_and_damage(self):
        p = self.session.player
        self.assertTrue(check_conditions(self.session, [{"min_skill": ["stealth", 15]}]))
        self.assertFalse(check_conditions(self.session, [{"has_lockpick": True}]))
        p.inventory.add(ITEMS.create("lockpick"))
        self.assertTrue(check_conditions(self.session, [{"has_lockpick": True}]))
        self.session.world.flags["x"] = "partial"
        self.assertTrue(check_conditions(self.session, [{"flag_is": ["x", "partial"]}]))
        p.hp = 10
        apply_effects(self.session, [{"damage": 50}])
        self.assertEqual(p.hp, 1)  # dialogue damage never kills

    def test_bad_specs_are_linted(self):
        self.assertTrue(MinigameSpec.problems({"type": "juggling"}))
        self.assertTrue(MinigameSpec.problems({"type": "stealth", "speed": 3}))
        self.assertFalse(MinigameSpec.problems({"type": "timing", "dc": 10, "strikes": 4, "success": "x"}))


class ToolAndTonicTests(unittest.TestCase):
    def test_tonics_prime_once_and_are_consumed_by_the_trial(self):
        session = GameSession.new_game("T", "Human", rng=random.Random(1))
        salve = session.player.inventory.add(ITEMS.create("muffling_salve"), 2).item
        session.use_item(salve)
        self.assertEqual(session.player.skill_primes, {"stealth": 3})
        with self.assertRaises(ValueError):
            session.use_item(salve)  # primes don't stack
        spec = MinigameSpec.from_dict({"type": "stealth"})
        primed = session.minigame_check(spec).rating
        session.start_minigame(spec)
        self.assertEqual(session.player.skill_primes, {})
        self.assertEqual(session.minigame_check(spec).rating, primed - 3)

    def test_lockpicks_not_usable_and_hidden_in_combat(self):
        session = GameSession.new_game("T", "Human", rng=random.Random(1))
        pick = session.player.inventory.add(ITEMS.create("lockpick")).item
        with self.assertRaises(ValueError):
            session.use_item(pick)
        combat = CombatSession(session.player, make_enemy())
        combat.start()
        self.assertNotIn(pick, [item for item, _ in combat.usable_items()])
        self.assertFalse(combat.act(UseItem(pick.uid)).accepted)

    def test_primes_and_modifiers_survive_save(self):
        session = GameSession.new_game("T", "Gnome", rng=random.Random(1))
        session.player.prime_skill("focus", 3)
        tools = session.player.inventory.add(ITEMS.create("thieves_tools")).item
        session.player.equip(tools)
        data = session.to_dict()
        for stack in data["player"]["inventory"]["stacks"]:
            stack["item"].pop("skill_bonuses", None)  # older saves had none; the catalog refills them
        loaded = GameSession.from_dict(data)
        self.assertEqual(loaded.player.skill_primes, {"focus": 3})
        self.assertEqual(loaded.player.inventory.find(tools.uid).item.skill_bonuses, {"lockpicking": 2})


if __name__ == "__main__":
    unittest.main()
