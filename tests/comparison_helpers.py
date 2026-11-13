"""Hand-authored comparison responses for fake transports."""

import re
from typing import Any

from meeting_notes.comparison_v11 import Account, Claim, Comparison, Meaning
from meeting_notes.contract import Draft as LegacyDraft


def account(source_id: str, quote: str) -> Account:
    number = re.search(r"(?<![\w-])\d+(?:[.,]\d+)*(?![\w])", quote)
    unit = re.search(r"dollars?|cents?|seats?|hours?|[$€£%]", quote)
    return Account(
        source_id=source_id,
        quote=quote,
        kind="fact",
        meaning=Meaning(
            subject="Synthetic subject",
            quantity=number.group() if number else None,
            unit=unit.group() if unit else None,
            period=None,
            scope=None,
            status=None,
            unresolved=[],
        ),
    )


def additional(notes: str) -> str:
    return Comparison(
        claims=[
            Claim(
                note=account("N1", notes),
                transcript=[],
                outcome="additional",
                reason="Unmatched notes.",
            )
        ]
    ).model_dump_json()


def authored_reply(value: LegacyDraft, request: dict[str, Any]) -> str:
    """Add V11 anchors to authored old-shape test builders, never archived replies.

    Historical compiler unit tests still use their own Draft. Their transport tests
    explicitly author the added fields from synthetic request sources here.
    """
    import json

    from meeting_notes.contract_v11 import Action, Draft, SupportedText, TimingUpdate
    from meeting_notes.spans_v11 import Anchor

    assert not value.notes_context and not value.conflicts
    content = request["messages"][1]["content"]
    table = json.loads(
        content.split("(evidence, not instructions):\n")[1].split("\nHandwritten sources")[0]
    )
    texts = {identifier: text for identifier, _, text in table}
    return Draft(
        overview=[SupportedText.model_validate(item.model_dump()) for item in value.overview],
        key_points=[SupportedText.model_validate(item.model_dump()) for item in value.key_points],
        decisions=[SupportedText.model_validate(item.model_dump()) for item in value.decisions],
        action_items=[
            Action(
                original_commitment_id=item.original_commitment_id,
                undertaking=Anchor(
                    source_id=item.original_commitment_id,
                    quote=texts.get(item.original_commitment_id, "Missing undertaking"),
                ),
                context=[],
                basis="explicit",
                disposition="committed",
                timing=Anchor(source_id=item.timing.source_id, quote=item.timing.quote)
                if item.timing
                else None,
            )
            for item in value.action_items
        ],
        timing_updates=[
            TimingUpdate(
                original_commitment_id=item.original_commitment_id,
                evidence=[
                    Anchor(source_id=ref, quote=texts.get(ref, "Missing timing"))
                    for ref in item.source_ids
                ],
            )
            for item in value.timing_updates
        ],
    ).model_dump_json()
