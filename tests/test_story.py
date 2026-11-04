"""The story engine: YAML scenes, the Ledger, rewards-once, locked choices, quests, endings, the story
checker, and a scripted run through Brannoc's jobs to the house in Emberwick."""

import asyncio
import random
import tempfile
import textwrap
import unittest
from pathlib import Path

from rpg import config
from rpg.core.dialogue import (
    DialogueRepository,
    EndGameRequest,
    MinigameRequest,
    StartCombatRequest,
    apply_effects,
    check_conditions,
    render_text,
)
from rpg.core.endings import EndingBook
from rpg.core.minigames import Outcome
from rpg.core.quests import BoardEntry, QuestBook
from rpg.core.session import BOARD_ERRORS, QUESTS, GameSession, default_endings, default_questbook
from rpg.core.storycheck import check_story
from rpg.services.persistence import SaveManager
from rpg.services.profile import ProfileStore


def write(base: Path, rel: str, text: str) -> None:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


QUESTS_YAML = """
    job:
      title: A Job
      giver: Someone
      stages:
        started: Do the job.
        halfway: Half done.
        done: Done.
"""


class StoryFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write(self.tmp, "story/quests/q.yaml", QUESTS_YAML)
        self.session = GameSession.new_game("Tess", "Dwarf", rng=random.Random(1), dialogue_dir=self.tmp / "d")
        self.session.quests = QuestBook.load(self.tmp / "story/quests")
        self.world, self.player = self.session.world, self.session.player

    def scenes(self, rel: str, text: str) -> DialogueRepository:
        write(self.tmp / "d", rel, text)
        self.session.dialogues = DialogueRepository(self.tmp / "d")
        return self.session.dialogues


class YamlSceneTests(StoryFixture):
    def test_many_scenes_per_file_with_defaults_and_local_links(self):
        repo = self.scenes("town/inn.yaml", """
            # comments are fine
            _defaults:
              speaker: Brannoc
            start:
              lines: ["Hello."]
              choices:
                - {text: Go down, next: cellar}
                - {text: Elsewhere, next: other/place}
            cellar:
              speaker: The Cellar
              lines: ["Dark."]
        """)
        start = repo.load("town/inn/start")
        self.assertEqual(start.speaker, "Brannoc")
        self.assertEqual([c.next_id for c in start.choices], ["town/inn/cellar", "other/place"])
        self.assertEqual(repo.load("town/inn/cellar").speaker, "The Cellar")
        self.assertTrue(repo.exists("town/inn/cellar"))
        self.assertIn("town/inn/start", repo.all_ids())
        self.assertIn("choice 'Elsewhere' points to missing 'other/place'", "\n".join(repo.validate()))

    def test_broken_yaml_is_reported_not_fatal(self):
        repo = self.scenes("bad.yaml", "start: [unclosed\n")
        self.assertFalse(repo.exists("bad/start"))
        self.assertTrue(any("bad.yaml" in p for p in repo.validate()))

    def test_json_scenes_still_load_beside_yaml(self):
        write(self.tmp / "d", "old/scene.json", '{"lines": ["Old."], "choices": [{"text": "On", "next": "new/a"}]}')
        repo = self.scenes("new.yaml", "a:\n  lines: [New.]\n")
        self.assertEqual(repo.load("old/scene").lines[0].text, "Old.")
        self.assertEqual(repo.validate(), [])

    def test_next_on_a_scene_without_choices_continues(self):
        self.scenes("s.yaml", "a:\n  lines: [A]\n  next: b\nb:\n  lines: [B]\n")
        runner = self.session.dialogue("s/a")
        runner.start()
        self.assertTrue(runner.is_terminal)
        runner.proceed()
        self.assertEqual(runner.node.node_id, "s/b")
        runner.proceed()
        self.assertTrue(runner.finished)


class LedgerTests(StoryFixture):
    def test_numbers_conditions_and_text(self):
        apply_effects(self.session, [{"add_var": ["rep.brannoc", 2]}, {"add_var": ["rep.brannoc", 1]}])
        self.assertEqual(self.world.var("rep.brannoc"), 3)
        self.assertEqual(self.world.var("never.set"), 0)
        self.assertTrue(check_conditions(self.session, [{"var": "rep.brannoc >= 3"}]))
        self.assertFalse(check_conditions(self.session, [{"var": "rep.brannoc > 3"}]))
        self.assertTrue(check_conditions(self.session, [{"var": ["rep.brannoc", "==", 3]}]))
        self.assertFalse(check_conditions(self.session, [{"var": "this is not an expression"}]))
        self.assertEqual(render_text(self.session, "{name} the {race}, rep {var.rep.brannoc}, {unknown}"),
                         "Tess the Dwarf, rep 3, {unknown}")

    def test_race_and_combinators(self):
        self.world.flags["a"] = True
        self.assertTrue(check_conditions(self.session, [{"race": "Dwarf"}]))
        self.assertTrue(check_conditions(self.session, [{"race": ["Elf", "Dwarf"]}]))
        self.assertFalse(check_conditions(self.session, [{"not_race": "Dwarf"}]))
        self.assertTrue(check_conditions(self.session, [{"any": [{"flag_set": "zzz"}, {"flag_set": "a"}]}]))
        self.assertFalse(check_conditions(self.session, [{"not": {"flag_set": "a"}}]))
        self.assertTrue(check_conditions(self.session, [{"all": [{"flag_set": "a"}, {"race": "Dwarf"}]}]))

    def test_visits_and_first_visit_lines(self):
        self.scenes("s.yaml", """
            a:
              lines:
                - {text: First time., if: {first_visit: true}}
                - {text: Back again., if: {first_visit: false}}
                - {text: Dwarves only., if: {race: Dwarf}}
                - {text: Elves only., if: {race: Elf}}
        """)
        runner = self.session.dialogue("s/a")
        runner.start()
        self.assertEqual(runner.lines(), ["First time.", "Dwarves only."])
        again = self.session.dialogue("s/a")
        again.start()
        self.assertEqual(again.lines(), ["Back again.", "Dwarves only."])
        self.assertEqual(self.world.visits["s/a"], 2)
        self.assertTrue(check_conditions(self.session, [{"visited": "s/a"}]))
        self.assertFalse(check_conditions(self.session, [{"not_visited": "s/a"}]))

    def test_ledger_survives_save_and_load(self):
        apply_effects(self.session, [{"add_var": ["rep.x", 4]}, {"start_quest": "job"}])
        self.world.visits["s/a"] = 2
        self.world.claimed.add("s/a")
        restored = GameSession.from_dict(self.session.to_dict())
        self.assertEqual(restored.world.vars, {"rep.x": 4})
        self.assertEqual(restored.world.visits, {"s/a": 2})
        self.assertEqual(restored.world.claimed, {"s/a"})
        self.assertEqual(restored.world.quests, {"job": "started"})
        old_save = GameSession.from_dict({"player": self.player.to_dict(), "world": {"bell": 3}})
        self.assertEqual(old_save.world.vars, {})  # saves from before the Ledger still load


class RewardsOnceTests(StoryFixture):
    def run_scene(self, start="s/a", choose=None):
        runner = self.session.dialogue(start)
        runner.start()
        if choose is not None:
            runner.choose(choose)
        return runner

    def test_scene_rewards_pay_once_but_costs_and_flags_repeat(self):
        self.scenes("s.yaml", """
            a:
              effects:
                - add_gold: 25
                - give_xp: 10
                - add_gold: -5
                - set_flag: [seen, true]
        """)
        start_gold = self.player.gold
        self.run_scene()
        self.assertEqual(self.player.gold, start_gold + 20)
        self.world.flags.pop("seen")
        self.run_scene()
        self.assertEqual(self.player.gold, start_gold + 15)  # only the cost applies again
        self.assertTrue(self.world.flags["seen"])

    def test_choice_rewards_pay_once_unless_repeat(self):
        self.scenes("s.yaml", """
            a:
              choices:
                - {text: Loot, effects: [{add_gold: 10}]}
                - {text: Shop, repeat: true, effects: [{add_gold: -3}, {give_xp: 5}]}
                - {text: Once, once: true, effects: [{add_gold: -1}]}
        """)
        gold, xp = self.player.gold, self.player.xp
        for _ in range(3):
            self.run_scene(choose=0)
            self.run_scene(choose=1)
            self.run_scene(choose=2)
        self.assertEqual(self.player.gold, gold + 10 - 9 - 1)
        self.assertEqual(self.player.xp, xp + 15)

    def test_effects_can_have_their_own_condition(self):
        self.scenes("s.yaml", """
            a:
              effects:
                - {add_gold: 40, if: {flag_not_set: haggled}}
                - {add_gold: 50, if: {flag_set: haggled}}
        """)
        self.world.flags["haggled"] = True
        gold = self.player.gold
        self.run_scene()
        self.assertEqual(self.player.gold, gold + 50)


class ChoiceMenuTests(StoryFixture):
    def test_locked_choices_show_greyed_with_reasons(self):
        self.scenes("s.yaml", """
            a:
              choices:
                - {text: Open, next: a}
                - {text: Buy it (500 gold), if: {min_gold: 500}, locked: true}
                - {text: Persuade, if: {min_stat: [charisma, 30]}, locked: true}
                - {text: Secret, if: {flag_set: nope}}
                - {text: Custom, if: {flag_set: nope}, locked: The Wardens no longer trust you}
                - {text: "[Elf] Speak Elvish", if: {race: Elf}, locked: true}
        """)
        self.player.gold = 10
        runner = self.session.dialogue("s/a")
        runner.start()
        menu = runner.menu()
        self.assertEqual([(e.text, e.index, e.reason) for e in menu], [
            ("Open", 0, ""),
            ("Buy it (500 gold)", None, "Requires 500 gold"),
            ("Persuade", None, "Requires Charisma 30"),
            ("Custom", None, "The Wardens no longer trust you"),
            ("[Elf] Speak Elvish", None, "Elf only"),
        ])
        self.assertEqual(len(runner.choices()), 1)  # locked choices can't be chosen

    def test_fleeing_a_fight_can_lead_somewhere(self):
        self.scenes("s.yaml", """
            a:
              effects: [{start_combat: wolf, fled: ran}]
              choices: [{text: After, next: won}]
            won: {lines: [Won.]}
            ran: {lines: [Ran.]}
        """)
        runner = self.session.dialogue("s/a")
        request = runner.start().requests[0]
        self.assertEqual(request, StartCombatRequest("wolf", fled="s/ran"))
        runner.resolve_flight(request)
        self.assertTrue(runner.redirected)
        runner.proceed()
        self.assertEqual(runner.node.node_id, "s/ran")


class QuestAndEndingTests(StoryFixture):
    def test_quest_effects_conditions_and_journal(self):
        events = apply_effects(self.session, [{"start_quest": "job"}]).events
        self.assertEqual(events[0].text, "New quest: A Job")
        self.assertTrue(check_conditions(self.session, [{"quest_active": "job"}, {"quest_at": ["job", "started"]}]))
        apply_effects(self.session, [{"start_quest": "job"}])  # starting again does nothing
        self.assertEqual(self.world.quests["job"], "started")
        apply_effects(self.session, [{"quest_stage": ["job", "halfway"]}])
        self.assertEqual(self.session.journal(), [("halfway", "A Job", "Someone", "Half done.")])
        apply_effects(self.session, [{"complete_quest": "job"}])
        self.assertTrue(check_conditions(self.session, [{"quest_done": "job"}]))
        self.assertFalse(check_conditions(self.session, [{"quest_active": "job"}]))
        apply_effects(self.session, [{"quest_stage": ["job", "started"]}])  # finished quests stay finished
        self.assertEqual(self.world.quests["job"], "done")
        self.assertTrue(check_conditions(self.session, [{"quest_not_started": "other"}]))

    def test_end_game_request_and_epilogue(self):
        write(self.tmp, "story/endings.yaml", """
            quiet:
              title: The Quiet
              epilogue:
                - Always.
                - {text: Dwarf line., if: {race: Dwarf}}
                - {text: Friend line., if: {var: "rep.x >= 2"}}
        """)
        self.session.endings = EndingBook.load(self.tmp / "story/endings.yaml")
        result = apply_effects(self.session, [{"end_game": "quiet"}])
        self.assertEqual(result.requests, [EndGameRequest("quiet")])
        ending = self.session.end_game("quiet")
        self.assertEqual((ending.title, ending.epilogue), ("The Quiet", ["Always.", "Dwarf line."]))

    def test_board_entries_routes_and_visibility(self):
        entry = BoardEntry("x", "X", "", "x/start", ({"flag_set": "unlocked"},),
                           ((({"flag_set": "back"},), "x/again"),))
        self.assertEqual(self.session.quest_start(entry), "x/start")
        self.world.flags["back"] = True
        self.assertEqual(self.session.quest_start(entry), "x/again")
        board = [q.key for q in self.session.board()]
        self.assertIn("emberwick_inn", board)


class StoryCheckTests(StoryFixture):
    def test_catches_typos_bad_quest_stages_and_dead_scenes(self):
        repo = self.scenes("s.yaml", """
            a:
              lines: [{text: Hi, if: {flag_set: met_brannok}}]
              effects:
                - set_flag: [met_brannoc, true]
                - quest_stage: [job, nonsense]
                - start_quest: no_such_quest
                - end_game: no_such_ending
              choices:
                - {text: Bad race, if: {race: Ogre}}
                - {text: Bad cond, if: {flag_sett: x}}
            lonely: {lines: [Nobody comes here.]}
        """)
        board = [BoardEntry("s", "S", "", "s/a")]
        errors, warnings = check_story(repo, self.session.quests, EndingBook(), board)
        text = "\n".join(errors + warnings)
        for expected in ("quest 'job' has no stage 'nonsense'", "unknown quest 'no_such_quest'",
                         "unknown ending 'no_such_ending'", "unknown race 'Ogre'", "unknown condition 'flag_sett'",
                         "flag 'met_brannok' is checked but nothing sets it", "scene 'lonely' can't be reached"):
            self.assertIn(expected, text)

    def test_shipped_story_is_clean(self):
        repo = DialogueRepository(config.DIALOGUE_DIR)
        errors, warnings = check_story(repo, default_questbook(), default_endings(), QUESTS, BOARD_ERRORS)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class EmberwickPlaythroughTests(unittest.TestCase):
    """A scripted player walks the real content: three jobs, the cottage offer, the house, the ending."""

    def play(self, session, start, *picks):
        """Enter ``start`` and pick choices by their text (a substring). Fights are won, games succeed."""
        def handle(requests):
            """What the dialogue screen does with requests: here minigames succeed; endings stop the run."""
            for request in requests:
                if isinstance(request, MinigameRequest):
                    runner.resolve_minigame(request, Outcome.SUCCESS)
                if isinstance(request, EndGameRequest):
                    return request
            return None

        runner = session.dialogue(start)
        requests = runner.start().requests
        picks = list(picks)
        while True:
            ending = handle(requests)
            if ending:
                return runner, ending
            if runner.redirected:  # a minigame on this scene chose where to go
                requests = runner.proceed().requests
                continue
            if not picks:
                return runner, None
            pick = picks.pop(0)
            texts = [c.text for c in runner.choices()]
            if pick == "<continue>":
                self.assertEqual(texts, [], f"expected no choices at {runner.node.node_id}")
                requests = runner.proceed().requests
                continue
            index = next((i for i, t in enumerate(texts) if pick in t), None)
            self.assertIsNotNone(index, f"no choice like {pick!r} at {runner.node.node_id}: {texts}")
            ending = handle(runner.choose(index).requests)
            if ending:
                return runner, ending
            requests = runner.proceed().requests

    def test_the_whole_slice(self):
        session = GameSession.new_game("Hearth", "Human", rng=random.Random(3))
        player = session.player
        player.gold = 0
        runner, _ = self.play(session, "emberwick/inn/start", "<continue>", "any work", "I'll do it", "Kick")
        self.assertEqual(session.world.quests["inn_rats"], "started")
        self.assertEqual(runner.node.node_id, "emberwick/cellar/fight")
        # (the fight is the UI's job) ... then:
        self.play(session, "emberwick/cellar/aftermath", "tell Brannoc", "<continue>")
        self.assertEqual(session.world.quests["inn_rats"], "done")
        self.assertTrue(session.world.flags["saw_crowned_rat"])
        self.assertEqual(player.gold, 40)

        # The rewards don't pay twice even if the scene is somehow reached again.
        self.play(session, "emberwick/inn/rats_paid")
        self.assertEqual(player.gold, 40)

        self.play(session, "emberwick/inn/counter", "any more work", "I'll go", "axe")
        self.assertEqual(session.world.quests["inn_firewood"], "started")
        self.assertTrue(session.world.flags["firewood_extra"])  # a clean chop
        self.play(session, "emberwick/firewood/stared_down", "Haul", "Bring it in", "<continue>")
        self.assertEqual(session.world.quests["inn_firewood"], "done")
        self.assertEqual(player.gold, 80)

        player.gold += 30
        self.play(session, "emberwick/inn/counter", "any more work", "talk to him", "Pay his slate", "Go back",
                  "<continue>")
        self.assertEqual(session.world.flags["oswin"], "paid_for")
        self.assertEqual(session.world.quests["inn_drunk"], "done")
        self.assertEqual(session.world.quests["the_cottage"], "offered")
        self.assertEqual(session.world.var("rep.brannoc"), 4)
        self.assertEqual(player.gold, 110)  # paid 30 for Oswin; Brannoc gave it back

        runner, _ = self.play(session, "emberwick/inn/counter", "cottage")
        locked = [e for e in runner.menu() if not e.available]
        self.assertEqual([(e.text, e.reason) for e in locked], [("Buy the cottage. (500 gold)", "Requires 500 gold")])
        self.assertIn('"I\'d throw in a chair," he adds. "Good chair."', runner.lines())

        player.gold = 520
        runner, ending = self.play(session, "emberwick/cottage/ask", "Buy the cottage", "<continue>")
        self.assertEqual(ending, EndGameRequest("a_house_in_emberwick"))
        self.assertEqual(runner.lines()[-1], "You sit down.")
        self.assertEqual(player.gold, 20)
        epilogue = session.end_game(ending.ending_id).epilogue
        self.assertIn("Brannoc came by most evenings. He brought the chair. It was a good chair.", epilogue)
        self.assertIn("Oswin brought you a sack of salt every spring, though spring never really came.", epilogue)
        self.assertIn("You never went back to the Hearthlands. There was nothing there to go back to.", epilogue)
        self.assertEqual(epilogue[-1], "You didn't really notice.")


class AutosaveAndProfileTests(unittest.TestCase):
    def test_autosave_slot_and_profile(self):
        directory = Path(tempfile.mkdtemp())
        saves = SaveManager(directory)
        session = GameSession.new_game("Tess", "Elf", rng=random.Random(1))
        self.assertEqual([i.slot for i in saves.list_slots(include_autosave=True)], [1, 2, 3])
        self.assertFalse(saves.any_saves())
        snapshot = session.snapshot()
        session.player.gold = 0  # changes after the checkpoint don't leak into it
        saves.save_payload(snapshot, config.AUTOSAVE_SLOT)
        self.assertTrue(saves.any_saves())
        infos = saves.list_slots(include_autosave=True)
        self.assertEqual(infos[0].slot, config.AUTOSAVE_SLOT)
        self.assertTrue(infos[0].label.startswith("Autosave — Tess"))
        self.assertEqual([i.slot for i in saves.list_slots()], [1, 2, 3])
        self.assertEqual(saves.load(config.AUTOSAVE_SLOT).player.gold, snapshot["player"]["gold"])

        store = ProfileStore(directory)
        profile = store.load()
        self.assertTrue(profile.record_ending("house", "A House", "Tess"))
        self.assertFalse(profile.record_ending("house", "A House", "Tess"))
        store.save(profile)
        again = store.load()
        self.assertEqual((again.endings["house"].count, again.endings["house"].first_hero), (2, "Tess"))


class HouseEndingUITest(unittest.TestCase):
    def test_buying_the_house_ends_the_game(self):
        asyncio.run(self._play())

    async def _play(self):
        from rpg.ui.app import RPGApp
        from rpg.ui.screens import ending as ending_screen
        from rpg.ui.screens.dialogue import DialogueScreen
        from tests.test_ui import screen_name, wait_for

        save_dir = tempfile.mkdtemp()
        app = RPGApp(save_dir=save_dir, seed=2)
        async with app.run_test(size=(120, 40)) as pilot:
            await wait_for(pilot, lambda: screen_name(app) == "TitleScreen")
            session = GameSession.new_game("Hearth", "Orc", rng=app.make_rng())
            session.world.quests.update(inn_rats="done", inn_firewood="done", inn_drunk="done", the_cottage="offered")
            session.player.gold = 600
            app.start_session(session)
            await wait_for(pilot, lambda: screen_name(app) == "HubScreen")

            quests = str(app.screen.query_one("#hub-quests").render())  # the hub's journal box lists quests
            self.assertIn("A House in Emberwick", quests)
            self.assertIn("Finished: Rats in the Cellar, Firewood, The Carter's Slate", quests)

            app.push_screen(DialogueScreen(session.dialogue("emberwick/cottage/ask"), "The Banked Fire"))
            await wait_for(pilot, lambda: screen_name(app) == "DialogueScreen" and app.screen.query("#choice-0"))
            await pilot.press("1")  # buy the cottage
            for _ in range(2):  # the key, then the house: Continue each time
                await wait_for(pilot, lambda: app.screen.query("#choice-continue, #choice-end")
                               and not app.screen._busy)
                await pilot.press("enter")
            await wait_for(pilot, lambda: screen_name(app) == "EndingScreen")
            self.assertIsNone(app.session)
            await pilot.press("space")  # skip the slow reveal
            await wait_for(pilot, lambda: app.screen.query_one("#ending-menu").display)
            self.assertIn("A House in Emberwick", str(app.screen.query_one("#ending-title").render()))
            self.assertTrue(ending_screen.EndingScreen)  # imported fine

            saves = SaveManager(Path(save_dir))
            self.assertEqual(saves.load(config.AUTOSAVE_SLOT).player.gold, 600)  # from before the purchase
            self.assertIn("a_house_in_emberwick", ProfileStore(Path(save_dir)).load().endings)

            await pilot.click("#ending-load")
            await wait_for(pilot, lambda: screen_name(app) == "HubScreen")
            self.assertEqual(app.session.player.gold, 600)
            self.assertEqual(app.session.world.quests["the_cottage"], "offered")


if __name__ == "__main__":
    unittest.main()
