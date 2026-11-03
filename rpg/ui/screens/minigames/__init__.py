"""Screens for the minigames in ``rpg.core.minigames``: one per kind, plus the briefing."""

from __future__ import annotations

from rpg.core.minigames import Minigame, MinigameKind
from rpg.ui.screens.minigames.balance import BalanceScreen
from rpg.ui.screens.minigames.base import MinigameScreen
from rpg.ui.screens.minigames.briefing import MinigameBriefing
from rpg.ui.screens.minigames.lockpick import LockpickScreen
from rpg.ui.screens.minigames.memory import MemoryScreen
from rpg.ui.screens.minigames.qte import QTEScreen
from rpg.ui.screens.minigames.stealth import StealthScreen
from rpg.ui.screens.minigames.timing import TimingScreen

SCREENS: dict[MinigameKind, type[MinigameScreen]] = {
    MinigameKind.QTE: QTEScreen,
    MinigameKind.LOCKPICK: LockpickScreen,
    MinigameKind.TIMING: TimingScreen,
    MinigameKind.MEMORY: MemoryScreen,
    MinigameKind.BALANCE: BalanceScreen,
    MinigameKind.STEALTH: StealthScreen,
}


def screen_for(game: Minigame, heading: str = "", subtitle: str = "", auto_close: float | None = None) -> MinigameScreen:
    return SCREENS[game.kind](game, heading, subtitle, auto_close)


__all__ = ["MinigameBriefing", "MinigameScreen", "SCREENS", "screen_for"]
