"""End-to-end UI smoke test using Textual's headless pilot."""

import asyncio
import tempfile
import unittest

from rpg import config
from rpg.ui.app import RPGApp


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


if __name__ == "__main__":
    unittest.main()
