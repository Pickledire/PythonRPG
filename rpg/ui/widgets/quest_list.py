"""The quest list shown in the hub's journal box: quests in progress, then a short line of finished ones."""

from __future__ import annotations

from rich.text import Text

from rpg.core.quests import DONE, FAILED
from rpg.ui.palette import MUTED_STYLE


def quest_text(entries: list[tuple[str, str, str, str]]) -> Text:
    """Render ``GameSession.journal()`` entries (stage, title, giver, journal text)."""
    active = [e for e in entries if e[0] not in (DONE, FAILED)]
    done = [title for stage, title, _, _ in entries if stage == DONE]
    failed = [title for stage, title, _, _ in entries if stage == FAILED]
    text = Text()
    if not active:
        text.append("No quests in progress. People in town may have work for you.", style=MUTED_STYLE)
    for i, (_, title, giver, note) in enumerate(reversed(active)):  # newest first
        if i:
            text.append("\n")
        text.append(title, style="bold #E0A458")
        if giver:
            text.append(f"  ({giver})", style=MUTED_STYLE)
        text.append(f"\n{note}", style="#C9BFAE")
    if done:
        text.append(f"\n\nFinished: {', '.join(done)}", style=MUTED_STYLE)
    if failed:
        text.append(f"\nFailed: {', '.join(failed)}", style=MUTED_STYLE)
    return text
