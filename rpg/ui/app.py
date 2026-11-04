"""The Textual application: screen navigation and the multi-screen game flows."""

from __future__ import annotations

import random
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from textual.app import App
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen

from rpg import config
from rpg.core.combat import Phase
from rpg.core.events import LogEvent, Tone
from rpg.core.minigames import MinigameResult, MinigameSpec
from rpg.core.session import Encounter, GameSession
from rpg.services.persistence import SaveManager
from rpg.services.profile import ProfileStore
from rpg.services.settings import Settings, SettingsStore
from rpg.ui.palette import THEMES


class RPGApp(App):
    """Owns the current ``GameSession`` and orchestrates flows that span several screens.

    State changes are announced by bumping the reactive ``revision`` (see ``touch``); widgets such as
    ``PlayerPanel`` watch it and redraw themselves.
    """

    CSS_PATH = "styles.tcss"
    TITLE = "Epic RPG Adventure"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", priority=True)]

    revision: reactive[int] = reactive(0)

    def __init__(self, save_dir: Path | None = None, seed: int | None = None) -> None:
        super().__init__()
        self.saves = SaveManager(save_dir)
        self.settings_store = SettingsStore(save_dir)
        self.profile_store = ProfileStore(save_dir)
        self.settings: Settings = self.settings_store.load()
        self.session: GameSession | None = None
        self._seed = seed
        self._hunting = False  # guards against starting two encounters at once

    def make_rng(self) -> random.Random:
        return random.Random(self._seed)

    def on_mount(self) -> None:
        from rpg.ui.screens.title import TitleScreen

        for theme in THEMES:
            self.register_theme(theme)
        self.theme = self.settings.theme if self.settings.theme in self.available_themes else "ember"
        self.watch(self, "theme", self._theme_changed, init=False)
        self.push_screen(TitleScreen())

    # ------------------------------------------------------------ settings
    def _theme_changed(self, theme: str) -> None:
        """Remember themes picked anywhere, including the Ctrl+P command palette."""
        if self.settings.theme != theme:
            self.settings.theme = theme
            self.save_settings()

    def change_setting(self, key: str, value: object) -> None:
        self.settings.set(key, value)
        if key == "theme" and value in self.available_themes:
            self.theme = value
        self.apply_settings()
        self.save_settings()

    def apply_settings(self) -> None:
        """Push settings the rules need into the current session."""
        if self.session is not None:
            self.session.difficulty = self.settings.difficulty
            self.session.reaction_time = float(self.settings.reaction_time)
        self.touch()

    def save_settings(self) -> None:
        try:
            self.settings_store.save(self.settings)
        except OSError as exc:
            self.notify(f"Couldn't save settings: {exc}", severity="error")

    # ------------------------------------------------------------ state & navigation
    def touch(self) -> None:
        """Announce that game state changed so watchers refresh."""
        if self.session:
            self.sub_title = f"{self.session.player.name} · {self.session.place} · {self.session.world.time_label}"
        else:
            self.sub_title = ""
        self.revision += 1

    def run_flow(self, flow: Coroutine[Any, Any, Any]):
        """Run a multi-screen flow as an app-level worker, so it survives the screens it pops."""
        return self.run_worker(flow, group="flows")

    async def reset_to(self, screen: Screen) -> None:
        """Clear the screen stack and show ``screen``."""
        while len(self.screen_stack) > 1:
            await self.pop_screen()
        await self.push_screen(screen)

    def start_session(self, session: GameSession, welcome: bool = False) -> None:
        from rpg.ui.screens.hub import HubScreen

        self.session = session
        self.apply_settings()

        async def go() -> None:
            hub = HubScreen()
            await self.reset_to(hub)
            if welcome:
                p = session.player
                hub.journal(LogEvent(f"Welcome, {p.name} the {p.race}! Your legend begins today.", Tone.REWARD))

        self.run_flow(go())

    async def quit_to_title_flow(self) -> None:
        from rpg.ui.screens.modals import ConfirmModal
        from rpg.ui.screens.title import TitleScreen

        if await self.push_screen_wait(ConfirmModal("Return to the title screen? Unsaved progress will be lost.",
                                                    "Return", "Stay")):
            self.session = None
            self.touch()
            await self.reset_to(TitleScreen())

    # ------------------------------------------------------------ flows (must run inside a worker)
    async def resolve_level_ups(self) -> None:
        from rpg.ui.screens.modals import LevelUpModal

        session = self.session
        while session is not None and session.player.stat_points > 0:
            attribute = await self.push_screen_wait(LevelUpModal(session.player))
            if attribute is None:
                break
            value = session.allocate_stat(attribute)
            self.notify(f"{attribute.label} increased to {value}.")
            self.touch()

    async def run_encounter(self, encounter: Encounter, allow_flee: bool = True) -> Phase:
        """Intro → combat → rewards → level-ups (or game over). Returns how the fight ended."""
        from rpg.ui.screens.combat import CombatScreen
        from rpg.ui.screens.encounter import EncounterScreen
        from rpg.ui.screens.modals import VictoryModal, trophy_modal

        session = self.session
        assert session is not None
        await self.push_screen_wait(EncounterScreen(encounter))
        combat = session.begin_combat(encounter, allow_flee=allow_flee)
        phase = await self.push_screen_wait(CombatScreen(combat))
        report = session.conclude_combat(combat)
        self.touch()
        if phase == Phase.VICTORY and report:
            await self.push_screen_wait(VictoryModal(report))
            if report.trophy_choices:
                item = await self.push_screen_wait(trophy_modal(report.trophy_choices, session.player))
                if item is not None:
                    self.notify(session.claim_trophy(item).text)
            await self.resolve_level_ups()
        elif phase == Phase.DEFEAT:
            await self.handle_defeat(combat.enemy.name)
        self.touch()
        return phase

    async def minigame_flow(self, spec: MinigameSpec, allow_retreat: bool = True,
                            briefing: bool = True) -> tuple[MinigameResult | None, list[LogEvent]]:
        """Briefing → trial → bookkeeping. Returns (result, events); result is None if the player backed out."""
        from rpg.ui.screens.minigames import MinigameBriefing, screen_for

        session = self.session
        assert session is not None
        if briefing and not await self.push_screen_wait(MinigameBriefing(spec, allow_retreat)):
            return None, []
        game = session.start_minigame(spec)
        result = await self.push_screen_wait(screen_for(game, spec.display_title, spec.intro))
        events = session.finish_minigame(game)
        self.touch()
        return result, events

    async def handle_defeat(self, killer: str) -> None:
        from rpg.ui.screens.game_over import GameOverScreen

        session = self.session
        assert session is not None
        p = session.player
        self.session = None
        self.touch()
        await self.reset_to(GameOverScreen(p.name, p.level, p.kills, killer))

    async def ending_flow(self, ending_id: str, checkpoint: dict | None = None) -> None:
        """A scene ended the game: autosave the checkpoint, record the ending, roll the credits."""
        from rpg.ui.screens.ending import EndingScreen

        session = self.session
        if session is None:
            return
        ending = session.end_game(ending_id)
        autosaved = False
        if checkpoint is not None:
            try:
                self.saves.save_payload(checkpoint, config.AUTOSAVE_SLOT)
                autosaved = True
            except OSError as exc:
                self.notify(f"Couldn't write the autosave: {exc}", severity="error")
        profile = self.profile_store.load()
        first_time = profile.record_ending(ending.ending_id, ending.title, session.player.name)
        try:
            self.profile_store.save(profile)
        except OSError as exc:
            self.notify(f"Couldn't save your profile: {exc}", severity="error")
        hero = session.player.name
        self.session = None
        self.touch()
        await self.reset_to(EndingScreen(ending, hero, first_time, len(profile.endings), autosaved))

    async def travel_flow(self, destination: str, mode) -> None:
        """Walk or ride to another region: the road (maybe a fight), then the arrival."""
        from rpg.core.travel import TravelError
        from rpg.ui.screens.hub import HubScreen

        session = self.session
        if session is None or self._hunting:
            return
        hub = next((s for s in self.screen_stack if isinstance(s, HubScreen)), None)
        self._hunting = True
        try:
            try:
                report = session.travel(destination, mode)
            except TravelError as exc:
                self.notify(str(exc), severity="warning")
                return
            if hub:
                hub.journal(report.events)
            self.touch()
            if report.ambush:
                phase = await self.run_encounter(Encounter(report.ambush, ambush=True))
                if phase == Phase.DEFEAT:
                    return
            if hub:
                hub.journal(report.arrival)
            await self.resolve_level_ups()
            self.touch()
        finally:
            self._hunting = False

    async def hunt_flow(self) -> None:
        from rpg.ui.screens.modals import Choice, ChoiceModal

        session = self.session
        if session is None or self._hunting:
            return
        self._hunting = True
        try:
            risky = False
            if session.pending_boss() is None:
                choice = await self.push_screen_wait(ChoiceModal("Choose your hunt", [
                    Choice("Standard hunt — normal enemies, normal rewards", False),
                    Choice("Risky hunt — enemies +20% stronger, rewards +50%", True),
                ]))
                if choice is None:
                    return
                risky = choice
            await self.run_encounter(session.create_hunt(risky))
        finally:
            self._hunting = False

    async def ghost_horror_flow(self) -> None:
        session = self.session
        if session is None or self._hunting or not session.ghost_horror_available():
            return
        self._hunting = True
        try:
            await self.run_encounter(session.summon_ghost_horror())
        finally:
            self._hunting = False
