"""The region creatures (how many, how strong, how named) and the Bestiary."""

import asyncio
import math
import random
import statistics
import tempfile
import unittest

from rpg.core import bestiary
from rpg.core.combat import Phase
from rpg.core.creatures import STD_DAMAGE, STD_HP, _curve
from rpg.core.enemies import AFFIXES, ENEMIES
from rpg.core.formulas import armor_mitigation
from rpg.core.session import Encounter, GameSession, default_lore, default_regions
from rpg.core.world import WorldState

ORIGINAL = {"goblin", "skeleton", "wolf", "bandit", "orc", "spriggan", "troll", "dire_wolf", "hagraven", "cave_bear",
            "harpy", "giant", "wraith", "barrow_wight", "ogre", "werewolf", "minotaur", "basilisk", "stone_golem",
            "dragon", "wyvern", "fire_elemental", "frost_troll", "wraith_lord", "horrid_monster", "ghost_horror",
            "cellar_rat"}


def danger(template_id: str, level: int) -> float:
    """Health (after physical armour and resistance) times damage, square-rooted: one number for how dangerous."""
    rng = random.Random(3)
    values = []
    for _ in range(20):
        e = ENEMIES.create(template_id, rng, level)
        effective_hp = e.max_hp / max(0.05, armor_mitigation(e.defense) * (1 - e.resistances.get("physical", 0)))
        values.append(math.sqrt(effective_hp * e.base_damage))
    return statistics.mean(values)


class CreatureTests(unittest.TestCase):
    def test_every_region_has_at_least_ten_new_creatures(self):
        for region in default_regions().regions.values():
            new = [e for e, _ in region.hunt if e not in ORIGINAL]
            self.assertGreaterEqual(len(new), 10, region.region_id)

    def test_names_never_clash_with_elite_modifiers(self):
        words = {a.name for a in AFFIXES}
        for template in ENEMIES.templates.values():
            self.assertNotIn(template.name.split()[0], words, template.template_id)

    def test_new_creatures_are_about_as_dangerous_as_the_originals(self):
        def ratio(t):
            return danger(t.template_id, t.level) / math.sqrt(_curve(STD_HP, t.level) * _curve(STD_DAMAGE, t.level))

        originals = [ratio(t) for k, t in ENEMIES.templates.items() if k in ORIGINAL - {"ghost_horror", "cellar_rat"}]
        hunted = {e for r in default_regions().regions.values() for e, _ in r.hunt}
        for template_id in hunted - ORIGINAL:
            r = ratio(ENEMIES.templates[template_id])
            self.assertGreater(r, min(originals) * 0.9, template_id)
            self.assertLess(r, max(originals) * 1.1, template_id)

    def test_every_hunted_creature_has_lore(self):
        lore, errors = default_lore()
        self.assertEqual(errors, [])
        hunted = {e for r in default_regions().regions.values() for e, _ in r.hunt}
        self.assertEqual(sorted(hunted - set(lore)), [])


class BestiaryTests(unittest.TestCase):
    def test_meeting_and_defeating_are_remembered(self):
        session = GameSession.new_game("Wren", "Human", rng=random.Random(2))
        enemy = ENEMIES.create("hollow_scarecrow", random.Random(1), 1)
        combat = session.begin_combat(Encounter(enemy))
        self.assertEqual(session.world.bestiary, {"hollow_scarecrow": {"seen": 1, "defeated": 0}})
        combat.phase = Phase.VICTORY
        session.conclude_combat(combat)
        self.assertEqual(session.world.bestiary["hollow_scarecrow"], {"seen": 1, "defeated": 1})
        again = WorldState.from_dict(session.world.to_dict())
        self.assertEqual(again.bestiary, session.world.bestiary)

        groups = session.bestiary()
        entry = groups["hearthlands"][0]
        self.assertEqual((entry.template_id, entry.habitats), ("hollow_scarecrow", ["hearthlands"]))
        self.assertIn("Straw", entry.lore + entry.template.description)

    def test_traits_in_plain_words(self):
        lines = bestiary.traits(ENEMIES.templates["wisp"])
        self.assertIn("Shrugs off 35% of damage from weapons.", lines)
        self.assertIn("Weak to spells: takes 25% more damage from them.", lines)
        self.assertIn("Casts Witchlight: blinds you (you miss more often).", lines)
        self.assertIn("Its attacks have a 20% chance to blind you (you miss more often).",
                      bestiary.traits(ENEMIES.templates["crow_swarm"]))

    def test_bestiary_screen(self):
        asyncio.run(self._play())

    async def _play(self):
        from rpg.ui.app import RPGApp
        from tests.test_ui import screen_name, wait_for

        app = RPGApp(save_dir=tempfile.mkdtemp(), seed=2)
        async with app.run_test(size=(120, 40)) as pilot:
            await wait_for(pilot, lambda: screen_name(app) == "TitleScreen")
            session = GameSession.new_game("Wren", "Dwarf", rng=app.make_rng())
            for template_id in ("wolf", "hollow_scarecrow"):
                bestiary.record(session.world, template_id)
            bestiary.record(session.world, "wolf", defeated=True)
            app.start_session(session)
            await wait_for(pilot, lambda: screen_name(app) == "HubScreen")
            await pilot.press("b")
            await wait_for(pilot, lambda: screen_name(app) == "BestiaryScreen")
            text = lambda: str(app.screen.query_one("#bestiary-text").render())  # noqa: E731
            await wait_for(pilot, lambda: "Wolf" in text())
            self.assertIn("winter has made the packs bolder", text())  # lore: a wolf was defeated
            await pilot.press("down")
            await wait_for(pilot, lambda: "Hollow Scarecrow" in text())
            self.assertIn("Defeat one to learn more.", text())
            self.assertIn("Weak to spells", text())


if __name__ == "__main__":
    unittest.main()
