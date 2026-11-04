"""GameSession: the single façade the UI talks to.

It owns the mutable game state (player, world, shops) plus the RNG and the dialogue repository,
and exposes intention-revealing operations (hunt, rest, buy, equip, ...) that return events.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from rpg import config
from rpg.core import campfire
from rpg.core.attributes import Attribute
from rpg.core.combat import CombatSession, Phase, apply_consumable, consumable_blocker
from rpg.core.dialogue import DialogueRepository, DialogueRunner, check_conditions
from rpg.core.endings import Ending, EndingBook
from rpg.core.enemies import ENEMIES, Enemy, QTETrigger, UnknownEnemyError
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.items import Consumable, ConsumableEffect, Item
from rpg.core.minigames import Minigame, MinigameKind, MinigameSpec, Outcome, build_minigame
from rpg.core.progression import VictoryReport, apply_victory, grant_item, roll_victory
from rpg.core.quests import BoardEntry, QuestBook, load_board
from rpg.core.shop import Shop, ShopMode
from rpg.core.skills import SkillCheck, skill_check
from rpg.core.world import WorldState


# The quest board's destinations are data (story/board.yaml). ``Quest`` is the old name.
Quest = BoardEntry
QUESTS, BOARD_ERRORS = load_board(config.STORY_DIR / "board.yaml")
_QUESTBOOK: QuestBook | None = None
_ENDINGS: EndingBook | None = None


def default_questbook() -> QuestBook:
    global _QUESTBOOK
    if _QUESTBOOK is None:
        _QUESTBOOK = QuestBook.load(config.STORY_DIR / "quests")
    return _QUESTBOOK


def default_endings() -> EndingBook:
    global _ENDINGS
    if _ENDINGS is None:
        _ENDINGS = EndingBook.load(config.STORY_DIR / "endings.yaml")
    return _ENDINGS


@dataclass
class Encounter:
    enemy: Enemy
    reward_multiplier: float = 1.0
    is_milestone_boss: bool = False
    ambush: bool = False  # the enemy acts first (you were discovered)
    opener: float = 0.0  # share of the enemy's HP removed by a sneak attack

    @property
    def has_intro(self) -> bool:
        return bool(self.enemy.template.intro_lines)


class GameSession:
    def __init__(self, player: Player, world: WorldState | None = None, rng: random.Random | None = None,
                 dialogue_dir=None) -> None:
        self.player = player
        self.world = world or WorldState()
        self.rng = rng or random.Random()
        self.dialogues = DialogueRepository(dialogue_dir or config.DIALOGUE_DIR)
        self.quests = default_questbook()
        self.endings = default_endings()
        self.shops = {mode: Shop(mode) for mode in ShopMode}
        # Player settings (not saved with the game): see rpg/services/settings.py.
        self.difficulty = "normal"
        self.reaction_time = 1.0

    @property
    def difficulty_rules(self) -> dict:
        return config.DIFFICULTIES.get(self.difficulty, config.DIFFICULTIES["normal"])

    def _prepare(self, enemy: Enemy) -> Enemy:
        """Scale a freshly created enemy for the difficulty setting."""
        rules = self.difficulty_rules
        if rules["enemy_hp"] != 1.0 or rules["enemy_damage"] != 1.0:
            enemy.scale(rules["enemy_hp"], rules["enemy_damage"])
        return enemy

    @classmethod
    def new_game(cls, name: str, race: str, rng: random.Random | None = None, dialogue_dir=None) -> "GameSession":
        return cls(Player.create(name, race), rng=rng, dialogue_dir=dialogue_dir)

    # ------------------------------------------------------------ encounters
    def pending_boss(self) -> str | None:
        for level, boss_id in config.MILESTONE_BOSSES:
            if self.player.level >= level and boss_id not in self.world.bosses_defeated:
                return boss_id
        return None

    def create_hunt(self, risky: bool = False) -> Encounter:
        boss_id = self.pending_boss()
        if boss_id:
            boss = ENEMIES.create(boss_id, self.rng, self.player.level)
            return Encounter(self._prepare(boss), 1.0, is_milestone_boss=True)
        enemy = ENEMIES.random_for_level(self.player.level, self.rng)
        multiplier = 1.0
        if risky:
            scale = config.RISKY_HUNT_ENEMY_SCALE
            enemy.scale(scale, scale, scale)
            multiplier = config.RISKY_HUNT_REWARD_MULTIPLIER
        ENEMIES.roll_affix(enemy, self.rng)
        return Encounter(self._prepare(enemy), multiplier)

    def create_story_enemy(self, enemy_id: str) -> tuple[Enemy, list[LogEvent]]:
        try:
            return self._prepare(self._story_enemy(enemy_id)), []
        except UnknownEnemyError:
            note = LogEvent(f"(Unknown enemy '{enemy_id}' — a goblin appears instead.)", Tone.SYSTEM)
            return self._prepare(self._story_enemy("goblin")), [note]

    def _story_enemy(self, enemy_id: str) -> Enemy:
        """Story enemies keep their designed strength but grow with you if you arrive over-levelled."""
        template = ENEMIES.templates[ENEMIES.resolve(enemy_id)]
        return ENEMIES.create(enemy_id, self.rng, max(template.level, self.player.level))

    def ghost_horror_available(self) -> bool:
        return not self.world.ghost_horror_seen

    def summon_ghost_horror(self) -> Encounter:
        self.world.ghost_horror_seen = True
        return Encounter(self._prepare(ENEMIES.create("ghost_horror", self.rng, self.player.level)))

    def begin_combat(self, encounter: Encounter, allow_flee: bool = True) -> CombatSession:
        rewards = encounter.reward_multiplier * self.difficulty_rules["rewards"]
        combat = CombatSession(self.player, encounter.enemy, self.rng, rewards, allow_flee)
        if encounter.ambush:
            combat.ambush()
        if encounter.opener:
            combat.opening_strike(encounter.opener)
        return combat

    def conclude_combat(self, combat: CombatSession) -> VictoryReport | None:
        """Apply the outcome. Returns the victory report (XP/gold/loot already granted) on a win."""
        self.player.effects.clear()  # combat effects don't linger between fights
        if combat.phase != Phase.VICTORY:
            return None
        enemy = combat.enemy
        if enemy.is_boss:
            self.world.bosses_defeated.add(enemy.template_id)
        report = roll_victory(enemy, self.rng, combat.reward_multiplier, self.player.level)
        return apply_victory(self.player, report)

    def claim_trophy(self, item: Item) -> LogEvent:
        return grant_item(self.player, item)

    # ------------------------------------------------------------ minigames
    def minigame_check(self, spec: MinigameSpec) -> SkillCheck:
        """The skill check a minigame would use right now (for the briefing screen)."""
        return skill_check(self.player, spec.skill_used, spec.dc + self.difficulty_rules["trial_dc"])

    def start_minigame(self, spec: MinigameSpec) -> Minigame:
        """Build the game from the player's current skill check. Uses up the primed boost for that skill."""
        check = self.minigame_check(spec)
        self.player.consume_prime(check.skill.value)
        return build_minigame(spec, check, self.rng, picks=self.player.lockpicks(),
                              vitality=self.player.attributes.vitality, time_scale=self.reaction_time)

    def finish_minigame(self, game: Minigame) -> list[LogEvent]:
        """Spend what the game used up (broken lockpicks) and describe the outcome."""
        result = game.result
        if result is None:
            return []
        tone = {Outcome.SUCCESS: Tone.REWARD, Outcome.PARTIAL: Tone.WARNING, Outcome.FAILURE: Tone.DAMAGE}[result.outcome]
        events = [LogEvent(result.summary, tone)]
        for item in result.spent:
            if self.player.inventory.find(item.uid):
                self.player.inventory.remove(item.uid, 1)
        if result.spent:
            events.append(LogEvent(f"{len(result.spent)} lockpick(s) broken.", Tone.WARNING))
        return events

    @staticmethod
    def qte_spec(trigger: QTETrigger) -> MinigameSpec:
        return MinigameSpec(MinigameKind.QTE, trigger.dc, trigger.title, trigger.telegraph, {
            "prompts": trigger.prompts, "window": trigger.window, "keys": trigger.keys,
            "success_score": trigger.success_score, "partial_score": trigger.partial_score,
        })

    def skill_tonics(self, skill: str) -> list[Consumable]:
        """Tonics in the pack that prime ``skill``."""
        return [s.item for s in self.player.inventory.consumables()  # type: ignore[misc]
                if s.item.effect == ConsumableEffect.SKILL_BOOST and s.item.skill == skill]

    # ------------------------------------------------------------ character
    def allocate_stat(self, attribute: Attribute) -> int:
        return self.player.spend_stat_point(attribute)

    def equip(self, item: Item) -> str:
        return self.player.equip(item)

    def use_item(self, item: Consumable) -> list[LogEvent]:
        problem = consumable_blocker(self.player, item)
        if problem:
            raise ValueError(problem)
        self.player.inventory.remove(item.uid, 1)
        return apply_consumable(self.player, item)

    def drop_item(self, item: Item) -> LogEvent:
        if self.player.inventory.is_equipped(item):
            raise ValueError(f"Unequip {item.name} first.")
        self.player.inventory.remove(item.uid, 1)
        return LogEvent(f"You discard the {item.name}.", Tone.INFO)

    # ------------------------------------------------------------ camp, shops, quests
    def rest(self) -> campfire.CampfireReport:
        report = campfire.rest(self.player, self.world, self.rng)
        if report.ambush:
            self._prepare(report.ambush)
        return report

    def random_dialogue(self, category: str) -> str | None:
        return self.dialogues.random_id(category, self.rng)

    def shop(self, mode: ShopMode | str) -> Shop:
        mode = ShopMode(mode) if not isinstance(mode, ShopMode) else mode
        if mode not in self.shops:
            mode = ShopMode.GENERAL
        shop = self.shops[mode]
        seed = self.world.bell if mode == ShopMode.GENERAL else self.world.bell + self.player.level * 31
        shop.rotate(seed, self.world.shop_unlocks if mode == ShopMode.GENERAL else None, self.player.level)
        return shop

    def board(self) -> list[BoardEntry]:
        """The quest board's destinations that are open right now."""
        return [entry for entry in QUESTS if check_conditions(self, list(entry.conditions))]

    def quest_start(self, quest: BoardEntry) -> str:
        for conditions, start in quest.routes:
            if check_conditions(self, list(conditions)):
                return start
        return quest.start_node

    def journal(self) -> list[tuple[str, str, str, str]]:
        """(quest id, title, giver, current journal text) for every started quest, with its stage."""
        entries = []
        for quest_id, stage in self.world.quests.items():
            quest = self.quests.get(quest_id)
            title = quest.title if quest else quest_id
            entries.append((stage, title, quest.giver if quest else "", quest.stage_text(stage) if quest else ""))
        return entries

    def end_game(self, ending_id: str) -> Ending:
        return self.endings.resolve(self, ending_id)

    def dialogue(self, start_id: str) -> DialogueRunner:
        return DialogueRunner(self, self.dialogues, start_id)

    # ------------------------------------------------------------ persistence
    def snapshot(self) -> dict:
        """A deep copy of the save data as it is right now (for checkpoints)."""
        return json.loads(json.dumps(self.to_dict()))

    def to_dict(self) -> dict:
        return {"version": config.SAVE_VERSION, "player": self.player.to_dict(), "world": self.world.to_dict()}

    @classmethod
    def from_dict(cls, data: dict, rng: random.Random | None = None, dialogue_dir=None) -> "GameSession":
        return cls(Player.from_dict(data["player"]), WorldState.from_dict(data.get("world", {})), rng=rng,
                   dialogue_dir=dialogue_dir)
