"""Regions, travel on foot and by carriage, region hunts, the calendar, and the board filtered by place."""

import asyncio
import random
import tempfile
import unittest

from rpg import config
from rpg.core.dialogue import check_conditions
from rpg.core.session import GameSession, default_regions
from rpg.core.travel import TravelError, TravelMode
from rpg.core.world import WorldState
from tests.helpers import ScriptedRandom


def new_session(seed=1, race="Human") -> GameSession:
    return GameSession.new_game("Wren", race, rng=random.Random(seed))


class MapTests(unittest.TestCase):
    def test_the_map_is_sound(self):
        regions = default_regions()
        self.assertEqual(regions.errors, [])
        self.assertEqual(len(regions.regions), 12)
        roads = regions.roads("hearthlands")
        self.assertEqual(len(roads), 12)  # every region can be reached
        self.assertEqual(roads["brennhold"], 1)
        self.assertEqual(roads["titanfell"], 4)

    def test_fares(self):
        regions = default_regions()
        fares = {r: regions.fare("hearthlands", r) for r in ("brennhold", "barrowfields", "glassmere", "valoria",
                                                              "emberpeaks", "titanfell")}
        self.assertEqual(fares, {"brennhold": 30, "barrowfields": 35, "glassmere": 40, "valoria": 55,
                                 "emberpeaks": 70, "titanfell": 90})
        # Every fare in the game sits between "nothing" and "a fortune" (riding home to safety is cheapest).
        everywhere = [regions.fare(a, b) for a in regions.regions for b in regions.regions if a != b]
        self.assertEqual(regions.fare("brennhold", "hearthlands"), 25)
        self.assertGreaterEqual(min(everywhere), 25)
        self.assertLess(max(everywhere), 100)


class TravelTests(unittest.TestCase):
    def test_walking_reaches_only_the_regions_next_door(self):
        session = new_session()
        walkable = sorted(o.region.region_id for o in session.travel_options() if o.walkable)
        self.assertEqual(walkable, ["ashwood", "barrowfields", "brennhold"])
        with self.assertRaises(TravelError):
            session.travel("glassmere", TravelMode.WALK)
        session.rng = ScriptedRandom([0.99])  # a quiet road
        day, bell = session.world.day, session.world.bell
        report = session.travel("brennhold", TravelMode.WALK)
        self.assertEqual(session.world.region, "brennhold")
        self.assertEqual(session.place, "Brennhold")
        self.assertTrue(report.first_visit)
        self.assertIn("brennhold", session.world.regions_visited)
        self.assertEqual((session.world.day * 24 + session.world.bell) - (day * 24 + bell),
                         config.WALK_HOURS_PER_ROAD)
        self.assertEqual([e.text for e in report.arrival][0], "You arrive at Brennhold.")

    def test_the_carriage_goes_anywhere_for_a_fare(self):
        session = new_session()
        session.player.gold = 50
        with self.assertRaises(TravelError):
            session.travel("titanfell", TravelMode.CARRIAGE)  # 90 gold
        self.assertEqual(session.world.region, "hearthlands")
        session.rng = ScriptedRandom([0.5])  # no highwaymen
        report = session.travel("glassmere", TravelMode.CARRIAGE)
        self.assertEqual((session.world.region, session.player.gold, report.ambush), ("glassmere", 10, None))

    def test_the_road_is_riskier_than_the_carriage(self):
        def ambush_rate(mode):
            hits = 0
            for seed in range(2000):
                session = new_session(seed)
                session.player.gold = 1000
                hits += session.travel("brennhold", mode).ambush is not None
            return hits / 2000

        walk, ride = ambush_rate(TravelMode.WALK), ambush_rate(TravelMode.CARRIAGE)
        self.assertAlmostEqual(walk, config.WALK_TROUBLE_CHANCE * 0.55, delta=0.03)
        self.assertAlmostEqual(ride, config.CARRIAGE_AMBUSH_CHANCE, delta=0.015)

    def test_hunting_meets_the_regions_creatures_at_its_level(self):
        session = new_session()
        session.world.region = "frostreach"
        pool = dict(session.region.hunt)
        for _ in range(40):
            encounter = session.create_hunt()
            self.assertIn(encounter.enemy.template_id, pool)
            self.assertGreaterEqual(encounter.enemy.level, 25)  # a level 1 hero meets level 25 trolls up here

    def test_the_board_only_lists_what_is_here(self):
        session = new_session()
        here = [e.key for e in session.board()]
        self.assertIn("emberwick_inn", here)
        self.assertIn("test_vault", here)  # dev entries are everywhere
        session.world.region = "brennhold"
        self.assertNotIn("emberwick_inn", [e.key for e in session.board()])
        self.assertIn("test_vault", [e.key for e in session.board()])


class CalendarTests(unittest.TestCase):
    def test_days_and_weekdays(self):
        world = WorldState(bell=20)
        self.assertEqual((world.day, world.weekday), (1, "Kindlemorn"))
        world.advance(6)  # past midnight
        self.assertEqual((world.day, world.bell, world.weekday), (2, 2, "Rimeday"))
        world.advance(24 * 6)
        self.assertEqual((world.day, world.weekday), (8, "Kindlemorn"))  # a week has seven days
        world.set_time(7)  # later today
        self.assertEqual((world.day, world.bell), (8, 7))
        world.set_time(7)  # that hour has passed: tomorrow
        self.assertEqual((world.day, world.bell), (9, 7))
        self.assertEqual(world.time_label, "Rimeday, Dawn")
        self.assertEqual(world.date_label, "Day 9: Rimeday, Dawn")

    def test_saves_keep_the_day_and_place_and_old_saves_start_at_emberwick(self):
        world = WorldState(day=12, region="ashwood", regions_visited={"hearthlands", "ashwood"})
        again = WorldState.from_dict(world.to_dict())
        self.assertEqual((again.day, again.region, again.regions_visited), (12, "ashwood", {"hearthlands", "ashwood"}))
        old = WorldState.from_dict({"bell": 5})
        self.assertEqual((old.day, old.region, old.regions_visited), (1, "hearthlands", {"hearthlands"}))

    def test_place_and_day_conditions(self):
        session = new_session()
        self.assertTrue(check_conditions(session, [{"in_region": "hearthlands"}, {"weekday": "Kindlemorn"}]))
        self.assertTrue(check_conditions(session, [{"in_region": ["ashwood", "hearthlands"]}]))
        self.assertFalse(check_conditions(session, [{"weekday": ["Hearthsday"]}]))
        self.assertFalse(check_conditions(session, [{"min_day": 2}]))


class TravelUITest(unittest.TestCase):
    def test_taking_the_carriage_from_the_hub(self):
        asyncio.run(self._play())

    async def _play(self):
        from rpg.ui.app import RPGApp
        from tests.test_ui import screen_name, wait_for

        chance, config.CARRIAGE_AMBUSH_CHANCE = config.CARRIAGE_AMBUSH_CHANCE, 0.0
        try:
            app = RPGApp(save_dir=tempfile.mkdtemp(), seed=2)
            async with app.run_test(size=(120, 40)) as pilot:
                await wait_for(pilot, lambda: screen_name(app) == "TitleScreen")
                session = GameSession.new_game("Wren", "Elf", rng=app.make_rng())
                session.player.gold = 200
                app.start_session(session)
                title = lambda: str(app.screen.query_one("#hub-title").render())  # noqa: E731
                await wait_for(pilot, lambda: screen_name(app) == "HubScreen" and title())
                self.assertTrue(title().startswith("Emberwick · Kindlemorn"))

                await pilot.press("t")
                await wait_for(pilot, lambda: screen_name(app) == "TravelScreen")
                await pilot.press("enter")  # the nearest region first: Brennhold
                await wait_for(pilot, lambda: screen_name(app) == "ChoiceModal")
                await pilot.press("down", "enter")  # the carriage
                await wait_for(pilot, lambda: screen_name(app) == "HubScreen" and session.world.region == "brennhold")
                await pilot.pause(0.2)
                self.assertEqual(session.player.gold, 170)
                await wait_for(pilot, lambda: title().startswith("Brennhold"))
                await pilot.press("q")
                await wait_for(pilot, lambda: screen_name(app) == "QuestBoardScreen")
                self.assertNotIn("emberwick_inn", [o.id for o in app.screen.query_one("#quest-list")._options])
        finally:
            config.CARRIAGE_AMBUSH_CHANCE = chance


if __name__ == "__main__":
    unittest.main()
