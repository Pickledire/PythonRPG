import os
import json


def _dialogue_path(dialogue_id: str) -> str:
    """Resolve a dialogue id to a JSON path. Supports nested ids like 'tavern/intro'."""
    base = os.path.dirname(__file__)
    if dialogue_id.endswith(".json"):
        rel = dialogue_id
    else:
        rel = f"{dialogue_id}.json"
    return os.path.join(base, "dialogues", rel)


def _load_dialogue(dialogue_id: str) -> dict:
    path = _dialogue_path(dialogue_id)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_conditions(engine, node: dict) -> bool:
    conditions = node.get("conditions", [])
    for cond in conditions:
        if "flag_set" in cond:
            key = cond["flag_set"]
            if not engine.quest_flags.get(key):
                return False
        if "flag_not_set" in cond:
            key = cond["flag_not_set"]
            if engine.quest_flags.get(key):
                return False
    return True


def _apply_effects(engine, effects: list):
    for eff in effects or []:
        if "set_flag" in eff:
            key, value = eff["set_flag"]
            engine.quest_flags[key] = value
        elif "add_gold" in eff:
            amount = eff["add_gold"]
            engine.print_centered(engine.player.add_gold(amount))
        elif "unlock_shop" in eff:
            item = eff["unlock_shop"]
            engine.quest_flags.setdefault("shop_unlocks", set())
            engine.quest_flags["shop_unlocks"].add(item)
            engine.print_centered(f"{engine.colors['gold']}[Shop] Unlocked: {item}{engine.colors['reset']}")
        elif "start_combat" in eff:
            enemy_id = eff["start_combat"]
            from Enemy import EnemyFactory
            if enemy_id == "goblin":
                engine.current_enemy = EnemyFactory.create_goblin()
            elif enemy_id == "orc":
                engine.current_enemy = EnemyFactory.create_orc()
            elif enemy_id == "horrid_monster":
                engine.current_enemy = EnemyFactory.create_horrid_monster()
            else:
                engine.current_enemy = EnemyFactory.create_goblin()
            engine.in_combat = True
            engine.print_centered(f"{engine.colors['combat']}An enemy approaches!{engine.colors['reset']}")
            engine.combat_loop()
        elif "give_item" in eff:
            from Item import Consumable, Armor
            from Weapon import Weapon
            from Magic import Magic
            payload = eff["give_item"]
            item = None
            if isinstance(payload, str):
                name = payload
                if name.lower() == "health potion":
                    item = Consumable("Health Potion", "heal", 50, "Restores 50 HP", 25)
                elif name.lower() == "spark":
                    item = Magic("Spark", "A tiny burst of lightning", 12, 5, 50)
                else:
                    # Default to a basic trinket-like consumable
                    item = Consumable(name, "heal", 0, f"A mysterious item named {name}", 0)
            elif isinstance(payload, dict):
                name = payload.get("name", "Unknown Item")
                typ = payload.get("type", "consumable")
                if typ == "weapon":
                    dmg = int(payload.get("damage", 10))
                    item = Weapon(name, dmg, 100, payload.get("description", ""), int(payload.get("value", 0)), payload.get("weapon_type", "melee"))
                elif typ == "armor":
                    defense = int(payload.get("defense", 5))
                    item = Armor(name, defense, 100, payload.get("description", ""), int(payload.get("value", 0)))
                elif typ == "magic":
                    dmg = int(payload.get("damage", 15))
                    mana = int(payload.get("mana", 8))
                    item = Magic(name, payload.get("description", ""), dmg, mana, int(payload.get("value", 0)))
                else:
                    val = int(payload.get("value", 0))
                    item = Consumable(name, "heal", 0, payload.get("description", ""), val)
            if item is not None:
                engine.player.inventory.add_item(item)
                engine.print_centered(f"{engine.colors['success']}Received item: {item.name}{engine.colors['reset']}")
        elif "stat_change" in eff:
            # ["stat", delta]
            stat, delta = eff["stat_change"]
            if stat in engine.player.stats:
                engine.player.stats[stat] = engine.player.stats.get(stat, 0) + int(delta)
                engine.print_centered(f"{engine.colors['success']}Your {stat} changed by {int(delta)} (now {engine.player.stats[stat]}){engine.colors['reset']}")
            else:
                engine.print_centered(f"{engine.colors['warning']}Stat '{stat}' not found.{engine.colors['reset']}")
        else:
            # Unknown effect type
            pass


def show_dialogue(engine, dialogue_id: str):
    current = dialogue_id
    while True:
        node = _load_dialogue(current)
        if not _check_conditions(engine, node):
            engine.print_centered(f"{engine.colors['warning']}You cannot do this right now.{engine.colors['reset']}")
            return

        speaker = node.get("speaker")
        if speaker:
            engine.print_border("─", 80, engine.colors['header'])
            engine.print_centered(f"{speaker}", 120, engine.colors['header'])
            engine.print_border("─", 80, engine.colors['header'])

        for line in node.get("lines", []):
            engine.print_centered(f"{engine.colors['info']}{line}{engine.colors['reset']}")

        choices = node.get("choices", [])
        if not choices:
            _apply_effects(engine, node.get("effects"))
            input(f"{engine.colors['menu']}Press Enter to continue...{engine.colors['reset']}")
            return

        for idx, ch in enumerate(choices, 1):
            engine.print_centered(f"{idx}. {engine.colors['menu']}{ch['text']}{engine.colors['reset']}")

        sel = input(f"{engine.colors['menu']}Enter your choice: {engine.colors['reset']}").strip()
        try:
            idx = int(sel) - 1
            if idx < 0 or idx >= len(choices):
                raise ValueError()
        except ValueError:
            engine.print_centered(f"{engine.colors['error']}Invalid choice.{engine.colors['reset']}")
            continue

        chosen = choices[idx]
        _apply_effects(engine, chosen.get("effects"))
        next_id = chosen.get("next")
        if next_id:
            current = next_id
            continue
        return


