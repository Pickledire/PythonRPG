# Quest functions module

from DialogueEngine import show_dialogue as run_dialogue

def quest_tavern_keeper(self):
    """Quest from the tavern keeper"""
    run_dialogue(self, "tavern/intro")


def quest_blacksmith(self):
    """Quest from the blacksmith"""
    run_dialogue(self, "blacksmith/intro")


def quest_mages_academy(self):
    """Quest from the mages academy"""
    run_dialogue(self, "mages/intro")


def quest_dark_forest(self):
    """Quest from the dark forest"""
    run_dialogue(self, "forest/intro")


def quest_local_fighters(self):
    """Quest from the local fighters"""
    if self.quest_flags.get("arena_created"):
        run_dialogue(self, "fighters/arena")
    else:
        run_dialogue(self, "fighters/intro")


def quest_mt_aegis(self):
    """Quest from Mt. Aegis"""
    run_dialogue(self, "mt_aegis/intro")


def quest_ancient_city_valoria(self):
    """Quest from the ancient city of Valoria"""
    run_dialogue(self, "valoria/intro")


def quest_local_graveyard(self):
    """Quest from the local graveyard"""
    run_dialogue(self, "graveyard/intro")