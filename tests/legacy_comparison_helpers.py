"""Historical comparison accounts for unchanged-response regressions."""

from meeting_notes.comparison import Account, Claim, Comparison, Meaning


def account(source_id: str, quote: str) -> Account:
    return Account(
        source_id=source_id,
        quote=quote,
        kind="fact",
        meaning=Meaning(
            subject="Synthetic subject",
            quantity=None,
            unit=None,
            period=None,
            scope=None,
            status="stated",
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
