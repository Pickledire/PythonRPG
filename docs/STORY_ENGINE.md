# Writing story content

How to write scenes, quests and endings. The working example is Emberwick's inn:
[dialogues/emberwick/](../dialogues/emberwick/), [story/quests/emberwick.yaml](../story/quests/emberwick.yaml)
and [story/endings.yaml](../story/endings.yaml). The complete list of conditions and effects is at the top of
[rpg/core/dialogue.py](../rpg/core/dialogue.py).

## Where things live

| What | Where |
|---|---|
| Scenes (what people say, the choices) | `dialogues/<place>/<file>.yaml`, many scenes per file |
| Quests (the journal) | `story/quests/*.yaml` |
| The quest board (places to go from the hub) | `story/board.yaml` |
| Endings | `story/endings.yaml` |

After any change, run `python tools/story_check.py`. It catches broken links, unknown quests and stages,
condition typos, flags that are checked but never set, and scenes nothing leads to.

## Scenes

```yaml
# Comments are fine anywhere.
_defaults:
  speaker: Brannoc          # every scene in this file, unless it says otherwise

counter:                    # this scene's id is emberwick/inn/counter
  lines:
    - '"Well?"'
    - text: He gives your beard an approving look.
      if: {race: Dwarf}     # a line that only shows sometimes
  choices:
    - text: Go down to the cellar.
      next: emberwick/cellar/stairs   # a full id (with a slash) reaches another file
    - text: Ask about the town.
      next: town                      # no slash: a scene in this same file
    - text: Buy the cottage. (500 gold)
      if: {min_gold: 500}
      locked: true          # shown greyed out as "[Requires 500 gold]" instead of hidden
      effects:
        - add_gold: -500
    - text: Leave.          # no next: the conversation ends
```

- **`next` on a scene** with no choices shows a Continue button that goes there.
- **Text** can use `{name}`, `{race}`, `{level}`, `{gold}` and `{var.rep.brannoc}`.
- **Quoting.** A line that starts with a quote mark needs wrapping: `'"Well?"'`, or use `>-` and put the text
  on the next lines. Inside single quotes, write an apostrophe twice: `'"Don''t."'`.
- **Locked choices** explain themselves for money, attributes, skills, levels, items and race. Give your own
  reason with `locked: The Wardens no longer trust you`. Choices without `locked` simply stay hidden.
- **Spacing.** YAML scenes put a blank line between lines. Add `paragraphs: false` to a scene to pack them.

## Remembering things: the Ledger

| Kind | Set it | Check it |
|---|---|---|
| Flags (facts) | `set_flag: [oswin, paid_for]`, `remove_flag: oswin` | `flag_set`, `flag_not_set`, `flag_is: [oswin, paid_for]` |
| Numbers | `add_var: [rep.brannoc, 1]`, `set_var: [rep.brannoc, 0]` | `var: "rep.brannoc >= 3"` |
| Visits | automatic | `visited`, `not_visited`, `first_visit: true` |
| Quests | `start_quest`, `quest_stage: [id, stage]`, `complete_quest`, `fail_quest` | `quest_active`, `quest_at: [id, stage]`, `quest_done`, `quest_not_started`, `quest_failed` |

Conditions combine: one mapping with several keys means all of them, and `any: [...]`, `all: [...]` and
`not: {...}` do the rest. `race: Dwarf`, `race: [Elf, Gnome]` and `not_race` check the player's race.

## Rewards pay once

Gold, XP, items, stat gains and reputation (`add_var`) from a scene or a choice pay **the first time only**,
so nobody can farm a conversation. Costs, flags, fights, healing, shops and time apply every time.

- `repeat: true` on a scene or choice pays its rewards every time (a shop counter, a bed).
- `once: true` makes *every* effect on it happen only once.
- Any effect can have its own `if:`, for example a bigger payment if you haggled:
  `{add_gold: 50, if: {flag_set: brannoc_haggled}}`.

## Fights and trials

```yaml
effects:
  - start_combat: cellar_rat
    ambush: true            # it strikes first
    opener: 0.3             # or you strike first, taking 30% of its health
    fled: ran_away          # where the story goes if the player runs
```

The scene's choices appear after the fight. Trials (`minigame:`) pick the next scene by outcome
(`success`, `partial`, `failure`, `retreat`); see the existing scenes for examples.

## Quests

```yaml
inn_rats:
  title: Rats in the Cellar
  giver: Brannoc
  stages:                   # in order; the journal shows the current stage's text
    started: Brannoc wants the rats out of his cellar.
    cleared: The cellar is clear. Tell Brannoc.
    done: You cleared Brannoc's cellar.     # "done" (and "failed") finish the quest
```

`start_quest` begins at the first stage and does nothing if the quest has already started. Finished quests
stay finished.

## Endings

A scene ends the run with `end_game: <id>`. The player presses Continue, the screen cuts to black, then THE
END, the ending's title and its epilogue one line at a time. Epilogue lines take `if:` like scene lines, so
the run shows in how it ends.

Before the ending plays, the game autosaves the state **from when that conversation began**, so the player
can reload and carry on. Every ending a player finds is recorded in their profile (`saves/profile.json`).
