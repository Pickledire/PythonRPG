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


def _load_dialogue(dialogue_id: str):
    """Load a dialogue node. Returns None (instead of crashing the game) if the file is missing or malformed."""
    path = _dialogue_path(dialogue_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[dialogue] Missing dialogue file: {path}")
        return None
    except json.JSONDecodeError as e:
        # Surface which file is malformed to aid debugging
        print(f"[dialogue] JSON error in {path}: {e}")
        return None


# Dialogue enemy ids -> EnemyFactory constructor names. Keys are normalized (lowercase, '_' -> ' ').
_ENEMY_IDS = {
    "goblin": "create_goblin",
    "orc": "create_orc",
    "orc warrior": "create_orc",
    "horrid monster": "create_horrid_monster",
    "yjurgen": "create_Yjurgen",
    "ziggy": "create_Ziggy",
    "jarvask": "create_Jarvask",
    "gorren": "create_Gorren",
    "morrg": "create_Morrg",
    "hagraven": "create_Hagraven",
    "archmage": "create_Archmage",
    "bandit": "create_bandit",
    "skeleton": "create_skeleton",
    "wraith": "create_wraith",
    "wolf": "create_wolf",
    "dire wolf": "create_dire_wolf",
    "spriggan": "create_spriggan",
    "troll": "create_troll",
    "cave troll": "create_troll",
    "giant": "create_giant",
    "ogre": "create_ogre",
    "minotaur": "create_minotaur",
    "dragon": "create_dragon",
    "young dragon": "create_dragon",
    "elder dragon": "create_elder_dragon",
    "valorian warden": "create_valorian_warden",
    "lich regent": "create_lich_regent",
    "clockwork colossus": "create_clockwork_colossus",
    "earth eater worm": "create_earth_eater_worm",
    "rat king": "create_rat_king",
}


def _create_enemy(enemy_id: str):
    from Enemy import EnemyFactory
    key = str(enemy_id or "").strip().lower().replace("_", " ")
    ctor_name = _ENEMY_IDS.get(key)
    if ctor_name is None:
        print(f"[dialogue] Unknown enemy id '{enemy_id}', defaulting to Goblin")
        ctor_name = "create_goblin"
    return getattr(EnemyFactory, ctor_name)()


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
        if "min_kills" in cond:
            try:
                needed = int(cond["min_kills"])
            except Exception:
                needed = 0
            current = getattr(getattr(engine, 'player', None), 'kills', 0)
            if current < needed:
                return False
        if "time_at" in cond:
            if getattr(engine, 'world_bells', 0) != int(cond["time_at"]):
                return False
        if "time_gte" in cond:
            if getattr(engine, 'world_bells', 0) < int(cond["time_gte"]):
                return False
        if "time_between" in cond:
            try:
                a, b = cond["time_between"][0], cond["time_between"][1]
                t = getattr(engine, 'world_bells', 0)
                if a <= b:
                    if not (a <= t <= b):
                        return False
                else:
                    # wraps midnight
                    if not (t >= a or t <= b):
                        return False
            except Exception:
                return False
    return True


def _choice_allowed(engine, choice: dict) -> bool:
    """Check optional conditions on a choice entry."""
    conds = choice.get("conditions")
    if not conds:
        return True
    # Reuse the same structure as node conditions
    return _check_conditions(engine, {"conditions": conds})


def _apply_effects(engine, effects: list):
    for eff in effects or []:
        if "set_flag" in eff:
            key, value = eff["set_flag"]
            engine.quest_flags[key] = value
        
        elif "set_health" in eff:
            # Clamp so dialogue can neither overheal nor leave a 0 HP "alive" character
            amount = max(1, min(engine.player.max_health, int(eff["set_health"])))
            engine.player.health = amount
            engine.print_centered(f"{engine.colors['success']}Your health is now {amount}{engine.colors['reset']}")
        elif "set_mana" in eff:
            amount = max(0, int(eff["set_mana"]))
            # Story effects may grant mana beyond the normal cap; raise the cap to match
            engine.player.max_mana = max(engine.player.max_mana, amount)
            engine.player.mana = amount
            engine.print_centered(f"{engine.colors['success']}Your mana is now {amount}{engine.colors['reset']}")
        elif "set_stamina" in eff:
            amount = eff["set_stamina"]
            engine.player.stamina = amount
            engine.print_centered(f"{engine.colors['success']}Your stamina is now {amount}{engine.colors['reset']}")
        elif "set_strength" in eff:
            try:
                amount = int(eff["set_strength"])
                engine.player.stats["strength"] = amount
                engine.print_centered(f"{engine.colors['success']}Your strength is now {amount}{engine.colors['reset']}")
            except Exception:
                pass
        elif "set_agility" in eff:
            try:
                amount = int(eff["set_agility"])
                engine.player.stats["agility"] = amount
                engine.print_centered(f"{engine.colors['success']}Your agility is now {amount}{engine.colors['reset']}")
            except Exception:
                pass
        elif "set_intelligence" in eff:
            try:
                amount = int(eff["set_intelligence"])
                engine.player.stats["intelligence"] = amount
                engine.print_centered(f"{engine.colors['success']}Your intelligence is now {amount}{engine.colors['reset']}")
            except Exception:
                pass
        elif "add_gold" in eff:
            amount = eff["add_gold"]
            engine.print_centered(engine.player.add_gold(amount))
        elif "advance_time" in eff:
            try:
                engine.world_bells = (engine.world_bells + int(eff["advance_time"])) % 24
            except Exception:
                pass
        elif "set_time" in eff:
            try:
                engine.world_bells = int(eff["set_time"]) % 24
            except Exception:
                pass
        elif "unlock_shop" in eff:
            item = eff["unlock_shop"]
            engine.quest_flags.setdefault("shop_unlocks", set())
            engine.quest_flags["shop_unlocks"].add(item)
            engine.print_centered(f"{engine.colors['gold']}[Shop] Unlocked: {item}{engine.colors['reset']}")
        elif "open_shop" in eff:
            mode = eff["open_shop"]
            try:
                if mode == "magic" and hasattr(engine, 'visit_magic_shop'):
                    engine.visit_magic_shop()
                elif hasattr(engine, 'visit_shop'):
                    engine.visit_shop()
            except Exception:
                pass
        elif "visual" in eff:
            try:
                engine.play_effect(eff["visual"], duration=eff.get("duration", 1.2))
            except Exception:
                pass
        elif "start_combat" in eff:
            from Enemy import Boss
            engine.current_enemy = _create_enemy(eff["start_combat"])
            engine.fight_reward_multiplier = 1.0
            engine.in_combat = True
            # Mirror normal combat intro with description
            if isinstance(engine.current_enemy, Boss) and hasattr(engine, 'display_boss_intro'):
                if getattr(engine.current_enemy, 'name', '') == 'Elder Dragon' and hasattr(engine, 'display_elder_dragon_intro'):
                    engine.display_elder_dragon_intro()
                elif getattr(engine.current_enemy, 'name', '') == 'Rat King' and hasattr(engine, 'display_rat_king_intro'):
                    engine.display_rat_king_intro()
                elif getattr(engine.current_enemy, 'name', '') == 'Earth Eater Worm' and hasattr(engine, 'display_earth_eater_worm_intro'):
                    engine.display_earth_eater_worm_intro()
                else:
                    engine.display_boss_intro()
            else:
                print()
                engine.print_border("", 60, engine.colors['combat'])
                engine.print_centered(f"{engine.colors['combat']}A wild {engine.colors['enemy']}{engine.current_enemy.name}{engine.colors['combat']} appears!{engine.colors['reset']}")
                engine.print_border("", 60, engine.colors['combat'])
                if hasattr(engine, 'print_centered_block'):
                    engine.print_centered_block(engine.current_enemy.get_info(), engine.colors['info'])
                else:
                    engine.print_centered(engine.current_enemy.get_info(), 120, engine.colors['info'])
                input(f"{engine.colors['menu']}Press Enter to start combat...{engine.colors['reset']}")
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
                    item = Consumable(name, "heal", 0, f"A mysterious item named {name}", 0)
            elif isinstance(payload, dict):
                name = payload.get("name", "Unknown Item")
                typ = payload.get("type", "consumable")
                # Graceful fallback for common mistakes: treat 'melee'/'ranged' as weapon type
                if typ in ("melee", "ranged"):
                    payload = dict(payload)
                    payload["weapon_type"] = typ
                    typ = "weapon"
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
        if node is None:
            engine.print_centered(f"{engine.colors['warning']}This path is not written yet...{engine.colors['reset']}")
            input(f"{engine.colors['menu']}Press Enter to continue...{engine.colors['reset']}")
            return
        if not _check_conditions(engine, node):
            engine.print_centered(f"{engine.colors['warning']}You cannot do this right now.{engine.colors['reset']}")
            return


        engine.clear_screen()

        # Advance simple world time by 1 bell per node
        try:
            engine.world_bells = (engine.world_bells + 1) % 24
        except Exception:
            pass

        speaker = node.get("speaker")
        if speaker:
            engine.print_border("─", 80, engine.colors['header'])
            engine.print_centered(f"{speaker}", 120, engine.colors['header'])
            engine.print_border("─", 80, engine.colors['header'])

        for line in node.get("lines", []):
            engine.print_centered(f"{engine.colors['info']}{line}{engine.colors['reset']}")

        # Node-level effects apply once on entering the node, whether or not it has choices
        _apply_effects(engine, node.get("effects"))

        choices = node.get("choices", [])
        if not choices:
            input(f"{engine.colors['menu']}Press Enter to continue...{engine.colors['reset']}")
            return

        filtered = []
        for ch in choices:
            if _choice_allowed(engine, ch):
                filtered.append(ch)
        if not filtered:
            engine.print_centered(f"{engine.colors['warning']}There is nothing you can do right now.{engine.colors['reset']}")
            input(f"{engine.colors['menu']}Press Enter to continue...{engine.colors['reset']}")
            return
        for idx, ch in enumerate(filtered, 1):
            engine.print_centered(f"{idx}. {engine.colors['menu']}{ch['text']}{engine.colors['reset']}")

        # Re-prompt in place on invalid input so the node (and its effects) is not replayed
        while True:
            sel = input(f"{engine.colors['menu']}Enter your choice: {engine.colors['reset']}").strip()
            try:
                idx = int(sel) - 1
                if 0 <= idx < len(filtered):
                    break
            except ValueError:
                pass
            engine.print_centered(f"{engine.colors['error']}Invalid choice.{engine.colors['reset']}")

        chosen = filtered[idx]
        _apply_effects(engine, chosen.get("effects"))
        next_id = chosen.get("next")
        if next_id:
            current = next_id
            continue
        return


