"""References and exact duplicates in extracted decisions and actions."""

from collections.abc import Sequence

from pydantic import BaseModel

from meeting_notes.summary import (
    ActionItem,
    Commitments,
    ExtractedAction,
    SummaryError,
    TimingEvidence,
)
from meeting_notes.turns import Turn, verify_selection


def verify_commitments(commitments: Commitments, turns: Sequence[Turn]) -> None:
    """Check references and normalize exact repeats without merging distinct tasks."""

    def ordered(ids: Sequence[str]) -> list[str]:
        verify_selection(ids, turns)
        selected = set(ids)
        return [turn.id for turn in turns if turn.id in selected]

    decisions = [
        item.model_copy(update={"turn_ids": ordered(item.turn_ids)})
        for item in commitments.decisions
    ]
    source = {turn.id: turn.text for turn in turns}
    positions = {turn.id: index for index, turn in enumerate(turns)}

    def timing(item: TimingEvidence, field: str) -> TimingEvidence:
        verify_selection([item.turn_id], turns)
        quote, value = " ".join(item.quote.split()), " ".join(item.value.split())
        if quote not in " ".join(source[item.turn_id].split()):
            raise SummaryError(f"{field}.quote was not found verbatim in {item.turn_id}")
        if value not in quote:
            raise SummaryError(f"{field}.value was not found verbatim in its quote")
        return item.model_copy(update={"quote": quote, "value": value})

    actions: list[ExtractedAction] = []
    for index, item in enumerate(commitments.action_items):
        field = f"action_items.{index}"
        related = [
            timing(evidence, f"{field}.related_timing.{i}")
            for i, evidence in enumerate(item.related_timing)
        ]
        related.sort(
            key=lambda evidence: (positions[evidence.turn_id], evidence.quote, evidence.value)
        )
        actions.append(
            item.model_copy(
                update={
                    "commitment_turn_ids": ordered(item.commitment_turn_ids),
                    "request_turn_ids": ordered(item.request_turn_ids),
                    "context_turn_ids": ordered(item.context_turn_ids),
                    "related_timing": _unique(related),
                    "action_timing": timing(item.action_timing, f"{field}.action_timing")
                    if item.action_timing is not None
                    else None,
                }
            )
        )
    commitments.decisions = _unique(decisions)
    commitments.action_items = _unique(actions)


def _unique[T: BaseModel](items: list[T]) -> list[T]:
    result: list[T] = []
    seen: set[str] = set()
    for item in items:
        key = item.model_dump_json()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def action_turn_ids(item: ExtractedAction) -> set[str]:
    """All supporting sources, including the timing evidence."""
    return {
        *item.commitment_turn_ids,
        *item.request_turn_ids,
        *item.context_turn_ids,
        *(evidence.turn_id for evidence in item.related_timing),
        *([item.action_timing.turn_id] if item.action_timing is not None else []),
    }


def action_item(item: ExtractedAction) -> ActionItem:
    """Project only the action's own timing into the saved deadline."""
    return ActionItem(
        owner=item.owner,
        task=item.task,
        due=item.action_timing.value if item.action_timing is not None else None,
    )


def commitment_texts(commitments: Commitments) -> list[str]:
    # Internal evidence is not generated prose and cannot trigger number corrections.
    return [
        *(decision.text for decision in commitments.decisions),
        *(
            f"{saved.task} {saved.due or ''}"
            for saved in map(action_item, commitments.action_items)
        ),
    ]
