"""The story bot: plays a questline over and over with random choices to prove it can be finished.

It starts a capable character in the quest's region, opens the quest board entry, and wanders: picks a random
available choice (preferring scenes it hasn't seen), wins or flees fights, passes or fails trials at random, and
between conversations lets some hours go by, the way a player would go hunting or resting. It stops when the
quest is done or it runs out of steps, and reports which scenes it reached.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from rpg.core.attributes import Attribute
from rpg.core.catalog import ITEMS
from rpg.core.dialogue import EndGameRequest, MinigameRequest, StartCombatRequest
from rpg.core.minigames import Outcome
from rpg.core.quests import DONE, BoardEntry
from rpg.core.session import QUESTS, GameSession


@dataclass
class BotRun:
    entry: str
    quest: str
    finished: bool
    steps: int
    visited: set[str] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)


def capable_hero(seed: int, race: str = "Human", stats: int = 20, gold: int = 5000) -> GameSession:
    session = GameSession.new_game("Bot", race, rng=random.Random(seed))
    for attribute in Attribute:
        session.player.set_attribute(attribute, stats)
    session.player.gold = gold
    session.player.inventory.add(ITEMS.create("lockpick"), 5)
    session.player.inventory.add(ITEMS.create("health_potion"), 3)
    return session


def play(entry: BoardEntry, quest: str, seed: int, race: str = "Human", max_steps: int = 500,
         stats: int = 20, win_chance: float = 0.9, pass_chance: float = 0.7) -> BotRun:
    rng = random.Random(seed)
    session = capable_hero(seed, race, stats)
    if entry.where:
        session.world.region = entry.where[0]
    seen: set[str] = set()
    problems: list[str] = []
    steps = 0
    while steps < max_steps and session.world.quests.get(quest) != DONE:
        runner = session.dialogue(session.quest_start(entry))
        result = runner.start()
        while not runner.finished and steps < max_steps:
            steps += 1
            if runner.node is not None:
                seen.add(runner.node.node_id)
            ended = False
            for request in result.requests:
                if isinstance(request, MinigameRequest):
                    runner.resolve_minigame(request, _trial(rng, pass_chance))
                elif isinstance(request, StartCombatRequest):
                    if rng.random() > win_chance and request.fled:
                        runner.resolve_flight(request)
                elif isinstance(request, EndGameRequest):
                    ended = True
            if ended:
                problems.append(f"the run ended at {runner.node.node_id}")
                return BotRun(entry.key, quest, False, steps, seen, problems)
            if runner.redirected:
                result = runner.proceed()
                continue
            options = runner.choices()
            if not options:
                result = runner.proceed()
                continue
            fresh = [i for i, c in enumerate(options) if c.next_id and c.next_id not in seen]
            index = rng.choice(fresh) if fresh and rng.random() < 0.8 else rng.randrange(len(options))
            choice_result = runner.choose(index)
            pending = [r for r in choice_result.requests]
            result = runner.proceed() if not any(isinstance(r, MinigameRequest) for r in pending) else None
            if result is None:  # a trial on the choice itself: settle it, then go where it says
                for request in pending:
                    if isinstance(request, MinigameRequest):
                        runner.resolve_minigame(request, _trial(rng, pass_chance))
                result = runner.proceed()
        if runner.blocked_reason and "not written" in runner.blocked_reason:
            problems.append(f"missing scene after {runner.node.node_id if runner.node else entry.start_node}")
        session.player.hp = session.player.max_hp
        session.world.advance(rng.randint(1, 10))  # off hunting, resting, travelling
        steps += 1
    return BotRun(entry.key, quest, session.world.quests.get(quest) == DONE, steps, seen, problems)


def _trial(rng: random.Random, pass_chance: float) -> Outcome:
    """A trial result: mostly passes, some partial passes, some failures."""
    roll = rng.random()
    if roll < pass_chance * 0.8:
        return Outcome.SUCCESS
    if roll < pass_chance:
        return Outcome.PARTIAL
    return Outcome.FAILURE


def board_entry(key: str) -> BoardEntry:
    return next(e for e in QUESTS if e.key == key)
