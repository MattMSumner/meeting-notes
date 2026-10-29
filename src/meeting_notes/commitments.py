"""References and exact duplicates in extracted decisions and actions."""

from collections.abc import Sequence

from meeting_notes.summary import Commitments, ExtractedAction, ExtractedDecision
from meeting_notes.turns import Turn, verify_selection


def verify_commitments(commitments: Commitments, turns: Sequence[Turn]) -> None:
    """Check references and normalize exact repeats without merging distinct tasks."""
    commitments.decisions = _unique(commitments.decisions, turns)
    commitments.action_items = _unique(commitments.action_items, turns)


def _unique[T: ExtractedDecision | ExtractedAction](
    items: list[T], turns: Sequence[Turn]
) -> list[T]:
    result: list[T] = []
    seen: set[str] = set()
    for item in items:
        verify_selection(item.turn_ids, turns)
        selected = set(item.turn_ids)
        normalized = item.model_copy(
            update={"turn_ids": [turn.id for turn in turns if turn.id in selected]}
        )
        key = normalized.model_dump_json()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def commitment_texts(commitments: Commitments) -> list[str]:
    # IDs are references, not numbers someone said.
    return [
        *(decision.text for decision in commitments.decisions),
        *(f"{item.task} {item.due or ''}" for item in commitments.action_items),
    ]
