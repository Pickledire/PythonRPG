"""GameSession: the single façade the UI talks to.

It owns the mutable game state (player, world, shops) plus the RNG and the dialogue repository,
and exposes intention-revealing operations (hunt, rest, buy, equip, ...) that return events.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rpg import config
from rpg.core import campfire
from rpg.core.attributes import Attribute
from rpg.core.combat import CombatSession, Phase, apply_consumable, consumable_blocker
from rpg.core.dialogue import DialogueRepository, DialogueRunner
from rpg.core.enemies import ENEMIES, Enemy, UnknownEnemyError
from rpg.core.entities import Player
from rpg.core.events import LogEvent, Tone
from rpg.core.items import Consumable, Item
from rpg.core.progression import VictoryReport, apply_victory, grant_item, roll_victory
from rpg.core.shop import Shop, ShopMode
from rpg.core.world import WorldState


@dataclass(frozen=True)
class Quest:
    key: str
    title: str
    blurb: str
    start_node: str
    alt_node: str | None = None  # used instead of start_node when alt_flag is set
    alt_flag: str | None = None


QUESTS: list[Quest] = [
    Quest("tavern", "The Tavern", "Ask the tavern keeper if they've heard about something interesting.", "tavern/intro"),
    Quest("blacksmith", "The Blacksmith", "Ask the blacksmith about a strange artifact.", "blacksmith/intro"),
    Quest("mages", "Mages Academy", "Seek out a powerful wizard at the academy.", "mages/intro"),
    Quest("forest", "The Dark Forest", "Head into the dark forest blindly.", "forest/intro"),
    Quest("fighters", "Local Fighters", "Start a fighting competition with the local fighters.", "fighters/intro",
          alt_node="fighters/arena", alt_flag="arena_created"),
    Quest("mt_aegis", "Mt. Aegis", "Climb Mt. Aegis in search of something strange.", "mt_aegis/intro"),
    Quest("valoria", "Ruins of Valoria", "Explore the ruins of the ancient city.", "valoria/intro"),
    Quest("graveyard", "The Graveyard", "Visit the local graveyard in search of a lost soul.", "graveyard/intro"),
]


@dataclass
class Encounter:
    enemy: Enemy
    reward_multiplier: float = 1.0
    is_milestone_boss: bool = False

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
        self.shops = {mode: Shop(mode) for mode in ShopMode}

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
            return Encounter(ENEMIES.create(boss_id, self.rng), 1.0, is_milestone_boss=True)
        enemy = ENEMIES.random_for_level(self.player.level, self.rng)
        multiplier = 1.0
        if risky:
            scale = config.RISKY_HUNT_ENEMY_SCALE
            enemy.scale(scale, scale, scale)
            multiplier = config.RISKY_HUNT_REWARD_MULTIPLIER
        ENEMIES.roll_affix(enemy, self.rng)
        return Encounter(enemy, multiplier)

    def create_story_enemy(self, enemy_id: str) -> tuple[Enemy, list[LogEvent]]:
        try:
            return ENEMIES.create(enemy_id, self.rng), []
        except UnknownEnemyError:
            note = LogEvent(f"(Unknown enemy '{enemy_id}' — a goblin appears instead.)", Tone.SYSTEM)
            return ENEMIES.create("goblin", self.rng), [note]

    def ghost_horror_available(self) -> bool:
        return not self.world.ghost_horror_seen

    def summon_ghost_horror(self) -> Encounter:
        self.world.ghost_horror_seen = True
        return Encounter(ENEMIES.create("ghost_horror", self.rng))

    def begin_combat(self, encounter: Encounter, allow_flee: bool = True) -> CombatSession:
        return CombatSession(self.player, encounter.enemy, self.rng, encounter.reward_multiplier, allow_flee)

    def conclude_combat(self, combat: CombatSession) -> VictoryReport | None:
        """Apply the outcome. Returns the victory report (XP/gold/loot already granted) on a win."""
        self.player.effects.clear()  # combat effects don't linger between fights
        if combat.phase != Phase.VICTORY:
            return None
        enemy = combat.enemy
        if enemy.is_boss:
            self.world.bosses_defeated.add(enemy.template_id)
        report = roll_victory(enemy, self.rng, combat.reward_multiplier)
        return apply_victory(self.player, report)

    def claim_trophy(self, item: Item) -> LogEvent:
        return grant_item(self.player, item)

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
        return campfire.rest(self.player, self.world, self.rng)

    def random_dialogue(self, category: str) -> str | None:
        return self.dialogues.random_id(category, self.rng)

    def shop(self, mode: ShopMode | str) -> Shop:
        mode = ShopMode(mode) if not isinstance(mode, ShopMode) else mode
        if mode not in self.shops:
            mode = ShopMode.GENERAL
        shop = self.shops[mode]
        seed = self.world.bell if mode == ShopMode.GENERAL else self.world.bell + self.player.level * 31
        shop.rotate(seed, self.world.shop_unlocks if mode == ShopMode.GENERAL else None)
        return shop

    def quest_start(self, quest: Quest) -> str:
        if quest.alt_flag and self.world.flags.get(quest.alt_flag) and quest.alt_node:
            return quest.alt_node
        return quest.start_node

    def dialogue(self, start_id: str) -> DialogueRunner:
        return DialogueRunner(self, self.dialogues, start_id)

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {"version": config.SAVE_VERSION, "player": self.player.to_dict(), "world": self.world.to_dict()}

    @classmethod
    def from_dict(cls, data: dict, rng: random.Random | None = None, dialogue_dir=None) -> "GameSession":
        return cls(Player.from_dict(data["player"]), WorldState.from_dict(data.get("world", {})), rng=rng,
                   dialogue_dir=dialogue_dir)
