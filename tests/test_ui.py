"""End-to-end UI smoke test using Textual's headless pilot."""

import asyncio
import tempfile
import unittest

from rpg import config
from rpg.ui.app import RPGApp
from rpg.ui.screens.dialogue import DialogueScreen


def screen_name(app) -> str:
    return type(app.screen).__name__


async def wait_for(pilot, condition, timeout: float = 10.0) -> None:
    waited = 0.0
    while not condition():
        await pilot.pause(0.05)
        waited += 0.05
        if waited > timeout:
            raise AssertionError(f"Timed out on {screen_name(pilot.app)}")


class UISmokeTest(unittest.TestCase):
    def setUp(self):
        self._timer = config.TURN_TIMER_SECONDS
        config.TURN_TIMER_SECONDS = 0

    def tearDown(self):
        config.TURN_TIMER_SECONDS = self._timer

    def test_new_game_hunt_and_save(self):
        asyncio.run(self._play())

    async def _play(self):
        app = RPGApp(save_dir=tempfile.mkdtemp(), seed=4)
        async with app.run_test(size=(140, 45)) as pilot:
            await wait_for(pilot, lambda: screen_name(app) == "TitleScreen")
            await pilot.click("#new")
            await wait_for(pilot, lambda: screen_name(app) == "CreateCharacterScreen")
            await pilot.click("#name")
            await pilot.press(*"Hero")
            await pilot.click("#begin")
            await wait_for(pilot, lambda: screen_name(app) == "HubScreen")
            self.assertEqual(app.session.player.name, "Hero")

            await pilot.press("h")
            await wait_for(pilot, lambda: screen_name(app) == "ChoiceModal")
            await pilot.press("enter")
            await wait_for(pilot, lambda: screen_name(app) == "EncounterScreen")
            await pilot.press("enter")
            await wait_for(pilot, lambda: screen_name(app) == "CombatScreen")
            for _ in range(200):
                name = screen_name(app)
                if name == "CombatScreen":
                    screen = app.screen
                    if screen.combat.is_over and screen.query_one("#combat-done").display:
                        await pilot.click("#done")
                    elif not screen._busy:
                        await pilot.press("1")
                elif name == "VictoryModal":
                    await pilot.press("enter")
                elif name == "LevelUpModal":
                    await pilot.press("1")
                elif name in ("HubScreen", "GameOverScreen"):
                    break
                await pilot.pause(0.1)
            self.assertIn(screen_name(app), ("HubScreen", "GameOverScreen"))

            if screen_name(app) == "HubScreen":
                await pilot.press("ctrl+s")
                await wait_for(pilot, lambda: screen_name(app) == "SaveLoadScreen")
                await pilot.press("enter")
                await wait_for(pilot, lambda: screen_name(app) == "HubScreen")
                self.assertEqual(app.saves.slot_info(1).name, "Hero")


class MinigameUITest(unittest.TestCase):
    """Practice hall trials through the real screens, plus a boss QTE in combat."""

    def setUp(self):
        self._timer = config.TURN_TIMER_SECONDS
        config.TURN_TIMER_SECONDS = 0

    def tearDown(self):
        config.TURN_TIMER_SECONDS = self._timer

    def test_practice_hall_and_boss_qte(self):
        asyncio.run(self._play())

    async def _choose(self, pilot, app, text):
        await wait_for(pilot, lambda: screen_name(app) == "DialogueScreen" and not app.screen._busy)
        choices = app.screen.runner.choices()
        await pilot.press(str(next(i for i, c in enumerate(choices) if text in c.text.lower()) + 1))

    async def _begin(self, pilot, app):
        await wait_for(pilot, lambda: screen_name(app) == "MinigameBriefing")
        await pilot.click("#begin")
        await wait_for(pilot, lambda: hasattr(app.screen, "game"))
        return app.screen.game

    async def _finish(self, pilot, app, game, keyboard=False):
        await wait_for(pilot, lambda: game.finished and app.screen.query_one("#mg-done").display)
        if keyboard:  # stray keys after a trial ends must not crash, and Enter continues
            await pilot.press("left", "a", "enter")
        else:
            await pilot.click("#mg-continue")
        await wait_for(pilot, lambda: screen_name(app) == "DialogueScreen")
        return game.result

    async def _play(self):
        from rpg.core.catalog import ITEMS
        from rpg.core.combat import Phase
        from rpg.core.enemies import ENEMIES
        from rpg.core.minigames import Outcome
        from rpg.core.session import Encounter, GameSession

        app = RPGApp(save_dir=tempfile.mkdtemp(), seed=5)
        async with app.run_test(size=(130, 46)) as pilot:
            await wait_for(pilot, lambda: screen_name(app) == "TitleScreen")
            session = GameSession.new_game("Pip", "Gnome", rng=app.make_rng())
            session.player.inventory.add(ITEMS.create("lockpick"), 2)
            app.start_session(session)
            await wait_for(pilot, lambda: screen_name(app) == "HubScreen")
            app.push_screen(DialogueScreen(session.dialogue("test_vault/practice"), "Practice"))

            await self._choose(pilot, app, "sandbag")
            game = await self._begin(pilot, app)
            while not game.finished:
                if game.current_key:
                    await pilot.press(game.current_key)
                await pilot.pause(0.05)
            self.assertEqual((await self._finish(pilot, app, game, keyboard=True)).outcome, Outcome.SUCCESS)

            await self._choose(pilot, app, "padlock")
            game = await self._begin(pilot, app)
            await pilot.press("space")  # a probe in the wrong place strains the pick
            while not game.finished:
                game.position = game.sweet[game.pin]
                await pilot.press("space")
            self.assertTrue((await self._finish(pilot, app, game, keyboard=True)).succeeded)

            await self._choose(pilot, app, "runes")
            game = await self._begin(pilot, app)
            while not game.finished:
                if game.state == "input":
                    await pilot.press("enter", "1")  # the keyboard does nothing here
                    await pilot.click(f"#rune-{game.sequence[len(game.entered)]}")
                await pilot.pause(0.05)
            self.assertEqual((await self._finish(pilot, app, game)).outcome, Outcome.SUCCESS)

            # A boss at 60% health telegraphs its first move on its first turn.
            sentinel = ENEMIES.create("stone_sentinel", app.make_rng())
            sentinel.hp = int(sentinel.max_hp * 0.6)
            sentinel.spellbook = []
            session.player.max_hp = session.player.hp = 5000
            phase = []

            async def fight():
                phase.append(await app.run_encounter(Encounter(sentinel, ambush=True)))

            app.run_flow(fight())
            await wait_for(pilot, lambda: screen_name(app) == "EncounterScreen")
            await pilot.press("space", "enter")
            await wait_for(pilot, lambda: screen_name(app) == "QTEScreen")
            qte = app.screen.game
            while not qte.finished:
                await pilot.press("z")  # miss every prompt
                await pilot.pause(0.05)
            await wait_for(pilot, lambda: screen_name(app) == "CombatScreen")
            self.assertTrue(any("You take" in e.text for e in app.screen.combat.log))
            self.assertLess(session.player.hp, 5000)
            sentinel.hp = int(sentinel.max_hp * 0.3)  # straight to the second telegraph
            for _ in range(400):
                name = screen_name(app)
                if phase:
                    break
                if name == "QTEScreen" and app.screen.game.current_key:
                    await pilot.press(app.screen.game.current_key)
                elif name == "CombatScreen":
                    screen = app.screen
                    if screen.combat.is_over and screen.query_one("#combat-done").display:
                        await pilot.click("#done")
                    elif not screen._busy:
                        await pilot.press("1")
                elif name in ("VictoryModal", "LevelUpModal", "ChoiceModal"):  # rewards, trophy pick
                    await pilot.press("enter")
                await pilot.pause(0.05)
            self.assertEqual(phase, [Phase.VICTORY])
            self.assertTrue(any(session.player.inventory.find_by_name(n) for n in
                                ("Sentinel Plate", "Sentinel Core", "Hourglass Pendant")))


if __name__ == "__main__":
    unittest.main()
